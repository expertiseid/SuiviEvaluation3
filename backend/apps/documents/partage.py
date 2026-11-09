"""
Partage d'un document par lien (LienDocument) avec une personne qui n'a pas de compte.

- Création, liste et révocation : depuis le document (DocumentViewSet), par qui peut modifier les
  documents et voit celui-ci. Chaque création et révocation est inscrite au journal d'audit.
- Page publique (/document/<jeton>?org=…) : la description du lien (nom du document, droit, expiration,
  mot de passe demandé ?), puis l'ouverture : mot de passe vérifié, ouverture comptée, et adresse signée
  du fichier valable 5 minutes (aperçu dans le navigateur, ou téléchargement si le droit le permet).
- « Consulter seulement » n'est possible que pour les fichiers qui s'affichent dans un navigateur (PDF,
  images, vidéos, texte) : les autres ne peuvent que se télécharger.
"""
import mimetypes
import os
from datetime import timedelta
from urllib.parse import quote

from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.db.models import F
from django.http import FileResponse, Http404
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
from .models import LienDocument

SEL = "documents.partage"
DUREE_ADRESSE_S = 300
DUREE_MAX = timedelta(days=365)


def type_mime(version) -> str:
    return mimetypes.guess_type(version.fichier.name)[0] or "application/octet-stream"


def version_du_lien(lien):
    return lien.version or lien.document.derniere_version


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
            **validated_data, document=self.context["document"], cree_par=self.context["request"].user,
            mot_de_passe=make_password(mot_de_passe) if mot_de_passe else "",
        )


def liens_du_document(viewset, request, document):
    """GET : les liens du document ; POST : en crée un (droit d'écriture requis)."""
    from apps.core.audit import A, auditer
    from apps.core.permissions import peut_modifier

    if request.method == "GET":
        return Response(LienDocumentSerializer(document.liens.select_related("cree_par", "version"), many=True).data)
    if not peut_modifier(request.user):
        raise PermissionDenied(v("Vous n'avez pas le droit de partager des documents."))
    serializer = LienDocumentSerializer(data=request.data, context={"document": document, "request": request})
    serializer.is_valid(raise_exception=True)
    lien = serializer.save()
    auditer(request.user, A.PARTAGE, document.nom, module="documents", operation="création", droit=lien.droit,
            expire_le=lien.expire_le.isoformat(), pour=lien.libelle)
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
    lien = LienDocument.objects.select_related("document", "version").filter(jeton=jeton).first()
    if lien is None or lien.document.supprime_le is not None:
        raise Http404
    return lien


def _description(lien):
    from apps.core.models import IdentiteOrganisation

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


def fichier_partage(request, jeton):
    """Le fichier d'un lien ouvert : adresse signée de 5 minutes, revérifiée (lien toujours valable)."""
    lien = _lien_public(jeton)
    try:
        contenu = signing.loads(request.GET.get("cle", ""), salt=sel(SEL), max_age=DUREE_ADRESSE_S)
    except signing.BadSignature:
        raise Http404
    if contenu.get("l") != lien.pk or lien.actif is False or lien.expire_le <= timezone.now():
        raise Http404
    version = lien.document.versions.filter(pk=contenu.get("v")).first()
    mode = contenu.get("m")
    if version is None or not version.fichier.storage.exists(version.fichier.name):
        raise Http404
    if mode == "telechargement" and lien.droit != LienDocument.Droit.TELECHARGER:
        raise Http404
    mime = type_mime(version)
    if mode == "apercu" and mime not in APERCU:
        raise Http404
    extension = os.path.splitext(version.fichier.name)[1]
    nom = lien.document.nom if lien.document.nom.lower().endswith(extension.lower()) else f"{lien.document.nom}{extension}"
    reponse = FileResponse(version.fichier.open("rb"), content_type=mime)
    reponse["Content-Disposition"] = f"{'attachment' if mode == 'telechargement' else 'inline'}; filename*=UTF-8''{quote(nom)}"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Cache-Control"] = "private, no-store"
    # La page publique l'affiche dans un cadre : autorisé pour l'aperçu seulement.
    if mode == "apercu":
        reponse.xframe_options_exempt = True
    return reponse
