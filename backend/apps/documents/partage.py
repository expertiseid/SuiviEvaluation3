"""
Partage d'un document par lien (LienDocument) avec une personne qui n'a pas de compte.

- Création, liste et révocation : depuis le document (DocumentViewSet), par qui peut modifier les
  documents et voit celui-ci. Chaque création et révocation est inscrite au journal d'audit.
- Page publique (/document/<jeton>?org=…) : la description du lien (nom du document, droit, expiration,
  mot de passe demandé ?), puis l'ouverture : mot de passe vérifié, ouverture comptée, et adresse signée
  du fichier valable 5 minutes (aperçu dans le navigateur, ou téléchargement si le droit le permet).
- « Consulter seulement » n'est possible que pour les fichiers qui s'affichent dans un navigateur (PDF,
  images, vidéos, texte) : les autres ne peuvent que se télécharger.
- Lien vers un dossier (DossierViewSet) : la page liste les fichiers du dossier et de ses sous-dossiers
  (dernières versions, documents visibles par le créateur du lien), à télécharger un par un ou en zip ;
  ses adresses valent 30 minutes, le temps de parcourir la liste.
"""
import mimetypes
import os
from datetime import timedelta
from urllib.parse import quote

from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.generics import get_object_or_404  # répond 404 (pas 500) si l'identifiant n'est pas un nombre
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.core.vocabulaire import v
from apps.organisations.contexte import parametre_org, sel

from .liens import APERCU
from .models import DocumentVersion, LienDocument

SEL = "documents.partage"
DUREE_ADRESSE_S = 300
DUREE_ADRESSE_DOSSIER_S = 1800
DUREE_MAX = timedelta(days=365)


def type_mime(version) -> str:
    return mimetypes.guess_type(version.fichier.name)[0] or "application/octet-stream"


def version_du_lien(lien):
    return lien.version or lien.document.derniere_version


def documents_du_dossier(lien):
    """Documents du dossier du lien et de ses sous-dossiers, avec leur chemin (« Sous-dossier/ »)."""
    from .corbeille import _visibles
    from .models import Document, Dossier

    visibles = _visibles(lien.cree_par, Document)
    resultat = []

    def parcourir(dossier, chemin):
        for document in visibles.filter(dossier=dossier).order_by("nom"):
            resultat.append((chemin, document))
        for sous in Dossier.objects.filter(parent=dossier).order_by("nom"):
            parcourir(sous, f"{chemin}{sous.nom}/")

    parcourir(lien.dossier, "")
    return resultat


def nom_de_fichier(document, version) -> str:
    extension = os.path.splitext(version.fichier.name)[1]
    return document.nom if document.nom.lower().endswith(extension.lower()) else f"{document.nom}{extension}"


class LienDocumentSerializer(serializers.ModelSerializer):
    mot_de_passe = serializers.CharField(write_only=True, required=False, allow_blank=True)
    a_mot_de_passe = serializers.SerializerMethodField()
    etat = serializers.CharField(read_only=True)
    droit_libelle = serializers.CharField(source="get_droit_display", read_only=True)
    cree_par_nom = serializers.SerializerMethodField()
    version_numero = serializers.IntegerField(source="version.version", read_only=True, default=None)

    class Meta:
        model = LienDocument
        fields = ("id", "jeton", "droit", "droit_libelle", "libelle", "expire_le", "mot_de_passe", "a_mot_de_passe",
                  "ouvertures_max", "nombre_ouvertures", "derniere_ouverture", "etat", "version", "version_numero",
                  "cree_par_nom", "created_at", "revoque_le")
        read_only_fields = ("jeton", "nombre_ouvertures", "derniere_ouverture", "created_at", "revoque_le")

    def get_a_mot_de_passe(self, obj):
        return bool(obj.mot_de_passe)

    def get_cree_par_nom(self, obj):
        return obj.cree_par.get_full_name() or obj.cree_par.username

    def validate_expire_le(self, valeur):
        maintenant = timezone.now()
        if valeur <= maintenant:
            raise ValidationError(v("La date d'expiration doit être dans le futur."))
        if valeur > maintenant + DUREE_MAX:
            raise ValidationError(v("Un lien ne peut pas durer plus d'un an."))
        return valeur

    def validate_ouvertures_max(self, valeur):
        if valeur is not None and valeur < 1:
            raise ValidationError(v("Au moins une ouverture."))
        return valeur

    def validate(self, attrs):
        if self.context.get("dossier") is not None:
            # Dossier : ses fichiers se téléchargent pour être lus (pas d'aperçu d'un dossier entier).
            attrs["droit"], attrs["version"] = LienDocument.Droit.TELECHARGER, None
            return attrs
        document = self.context["document"]
        version = attrs.get("version")
        if version is not None and version.document_id != document.id:
            raise ValidationError({"version": v("Cette version n'appartient pas au document.")})
        cible = version or document.derniere_version
        if cible is None:
            raise ValidationError({"detail": v("Ce document n'a pas encore de fichier.")})
        if attrs.get("droit", LienDocument.Droit.CONSULTER) == LienDocument.Droit.CONSULTER and type_mime(cible) not in APERCU:
            raise ValidationError({"droit": v(
                "Ce type de fichier ne s'affiche pas dans un navigateur : choisissez « Consulter et télécharger ».")})
        return attrs

    def create(self, validated_data):
        mot_de_passe = validated_data.pop("mot_de_passe", "") or ""
        return LienDocument.objects.create(
            **validated_data, document=self.context.get("document"), dossier=self.context.get("dossier"),
            cree_par=self.context["request"].user,
            mot_de_passe=make_password(mot_de_passe) if mot_de_passe else "",
        )


def liens_du_document(viewset, request, document, dossier=False):
    """GET : les liens du document (ou du dossier) ; POST : en crée un (droit d'écriture requis)."""
    from apps.core.audit import A, auditer
    from apps.core.permissions import peut_modifier

    if request.method == "GET":
        return Response(LienDocumentSerializer(document.liens.select_related("cree_par", "version"), many=True).data)
    if not peut_modifier(request.user):
        raise PermissionDenied(v("Vous n'avez pas le droit de partager des documents."))
    contexte = {"dossier" if dossier else "document": document, "request": request}
    serializer = LienDocumentSerializer(data=request.data, context=contexte)
    serializer.is_valid(raise_exception=True)
    lien = serializer.save()
    auditer(request.user, A.PARTAGE, document.nom, module="documents", operation="création", droit=lien.droit,
            expire_le=lien.expire_le.isoformat(), pour=lien.libelle, **({"dossier": True} if dossier else {}))
    return Response(LienDocumentSerializer(lien).data, status=201)


def revoquer(request, document, lien_id):
    from apps.core.audit import A, auditer
    from apps.core.permissions import peut_modifier

    if not peut_modifier(request.user):
        raise PermissionDenied(v("Vous n'avez pas le droit de partager des documents."))
    lien = get_object_or_404(document.liens, pk=lien_id)
    if lien.actif:
        lien.actif, lien.revoque_le = False, timezone.now()
        lien.save(update_fields=["actif", "revoque_le", "updated_at"])
        auditer(request.user, A.PARTAGE, document.nom, module="documents", operation="révocation", pour=lien.libelle)
    return Response(LienDocumentSerializer(lien).data)


# --- Page publique ---------------------------------------------------------------------------------


class LimitePartageDocument(AnonRateThrottle):
    rate = "60/hour"


def _lien_public(jeton):
    lien = LienDocument.objects.select_related("document", "dossier", "version", "cree_par").filter(jeton=jeton).first()
    if lien is None or (lien.document or lien.dossier).supprime_le is not None:
        raise Http404
    return lien


def _description(lien):
    from apps.core.models import IdentiteOrganisation

    if lien.dossier_id:
        return {
            "etat": lien.etat, "droit": lien.droit, "dossier": lien.dossier.nom, "document": None,
            "expire_le": lien.expire_le, "mot_de_passe": bool(lien.mot_de_passe),
            "organisation": IdentiteOrganisation.courante().nom, "apercu": False, "version": None, "type": "",
        }
    version = version_du_lien(lien)
    return {
        "etat": lien.etat, "droit": lien.droit, "document": lien.document.nom, "expire_le": lien.expire_le,
        "mot_de_passe": bool(lien.mot_de_passe), "organisation": IdentiteOrganisation.courante().nom,
        "type": type_mime(version) if version else "", "apercu": bool(version and type_mime(version) in APERCU),
        "version": version.version if version else None,
    }


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LimitePartageDocument])
def document_partage(request, jeton):
    """
    GET : description du lien. POST {mot_de_passe} : ouvre le document (compte une ouverture) et
    renvoie les adresses du fichier, valables 5 minutes.
    """
    lien = _lien_public(jeton)
    if request.method == "GET":
        return Response(_description(lien))
    if lien.etat != "ACTIF":
        return Response({**_description(lien), "detail": v("Ce lien n'est plus valable.")}, status=410)
    if lien.mot_de_passe and not check_password(request.data.get("mot_de_passe") or "", lien.mot_de_passe):
        return Response({"detail": v("Mot de passe incorrect."), "code": "mot_de_passe"}, status=403)
    if lien.dossier_id:
        return _ouvrir_dossier(request, jeton, lien)
    version = version_du_lien(lien)
    if version is None:
        raise Http404
    LienDocument.objects.filter(pk=lien.pk).update(nombre_ouvertures=F("nombre_ouvertures") + 1, derniere_ouverture=timezone.now())

    def adresse(mode):
        cle = signing.dumps({"l": lien.pk, "v": version.pk, "m": mode}, salt=sel(SEL))
        org = parametre_org()
        return request.build_absolute_uri(f"/api/v1/public/document-partage/{jeton}/fichier/?cle={quote(cle)}"
                                          + (f"&{org}" if org else ""))

    return Response({
        **_description(lien),
        "apercu_url": adresse("apercu") if type_mime(version) in APERCU else None,
        "telechargement_url": adresse("telechargement") if lien.droit == LienDocument.Droit.TELECHARGER else None,
        "duree_minutes": DUREE_ADRESSE_S // 60,
    })


def _adresse_fichier(request, jeton, contenu):
    cle = signing.dumps(contenu, salt=sel(SEL))
    org = parametre_org()
    return request.build_absolute_uri(f"/api/v1/public/document-partage/{jeton}/fichier/?cle={quote(cle)}"
                                      + (f"&{org}" if org else ""))


def _taille(version):
    try:
        return version.fichier.size
    except OSError:  # fichier absent du stockage
        return None


def _ouvrir_dossier(request, jeton, lien):
    """Lien vers un dossier : ouverture comptée, liste des fichiers avec leur adresse de téléchargement."""
    LienDocument.objects.filter(pk=lien.pk).update(nombre_ouvertures=F("nombre_ouvertures") + 1, derniere_ouverture=timezone.now())
    fichiers = []
    for chemin, document in documents_du_dossier(lien):
        version = document.derniere_version
        if version is None or not version.fichier:
            continue
        fichiers.append({
            "chemin": chemin, "nom": nom_de_fichier(document, version), "taille": _taille(version),
            "telechargement_url": _adresse_fichier(request, jeton, {"l": lien.pk, "v": version.pk, "m": "telechargement"}),
        })
    return Response({
        **_description(lien), "fichiers": fichiers,
        "zip_url": _adresse_fichier(request, jeton, {"l": lien.pk, "m": "zip"}) if fichiers else None,
        "duree_minutes": DUREE_ADRESSE_DOSSIER_S // 60,
    })


def fichier_partage(request, jeton):
    """
    Le fichier d'un lien ouvert : adresse signée de 5 minutes (30 pour un dossier), revérifiée (lien toujours
    valable ; pour un dossier, document toujours dedans).
    """
    lien = _lien_public(jeton)
    try:
        contenu = signing.loads(request.GET.get("cle", ""), salt=sel(SEL),
                                max_age=DUREE_ADRESSE_DOSSIER_S if lien.dossier_id else DUREE_ADRESSE_S)
    except signing.BadSignature:
        raise Http404
    if contenu.get("l") != lien.pk or lien.actif is False or lien.expire_le <= timezone.now():
        raise Http404
    if lien.dossier_id:
        return _fichier_du_dossier(lien, contenu)
    version = lien.document.versions.filter(pk=contenu.get("v")).first()
    mode = contenu.get("m")
    if version is None or not version.fichier.storage.exists(version.fichier.name):
        raise Http404
    if mode == "telechargement" and lien.droit != LienDocument.Droit.TELECHARGER:
        raise Http404
    mime = type_mime(version)
    if mode == "apercu" and mime not in APERCU:
        raise Http404
    nom = nom_de_fichier(lien.document, version)
    reponse = FileResponse(version.fichier.open("rb"), content_type=mime)
    reponse["Content-Disposition"] = f"{'attachment' if mode == 'telechargement' else 'inline'}; filename*=UTF-8''{quote(nom)}"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Cache-Control"] = "private, no-store"
    # La page publique l'affiche dans un cadre : autorisé pour l'aperçu seulement.
    if mode == "apercu":
        reponse.xframe_options_exempt = True
    return reponse


def _fichier_du_dossier(lien, contenu):
    """Un fichier du dossier partagé, ou tout le dossier en zip (dernières versions)."""
    from .corbeille import archive

    if contenu.get("m") == "zip":
        try:
            fichier = archive([lien.dossier], [])
        except ValueError:
            return HttpResponse(v("Dossier trop volumineux (plus de 500 Mo) : téléchargez les fichiers un par un."), status=413,
                                content_type="text/plain; charset=utf-8")
        reponse = FileResponse(fichier, as_attachment=True, filename=f"{lien.dossier.nom}.zip", content_type="application/zip")
    else:
        documents = {document.pk: document for _chemin, document in documents_du_dossier(lien)}
        version = DocumentVersion.objects.filter(pk=contenu.get("v"), document_id__in=documents).first()
        if version is None or contenu.get("m") != "telechargement" or not version.fichier.storage.exists(version.fichier.name):
            raise Http404
        nom = nom_de_fichier(documents[version.document_id], version)
        reponse = FileResponse(version.fichier.open("rb"), content_type=type_mime(version))
        reponse["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(nom)}"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Cache-Control"] = "private, no-store"
    return reponse
