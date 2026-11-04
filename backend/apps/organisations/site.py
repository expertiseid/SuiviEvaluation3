"""
Site vitrine : actualités et partenaires (base centrale).

- Console Expertise-ID (EstOperateur) : ajouter, modifier, publier ou masquer, supprimer ; image ou logo
  (PNG, JPEG ou WEBP, 3 Mo au plus) ; traductions facultatives par langue.
- Public, sans compte (le site les lit) : actualités publiées et partenaires visibles, dans la langue
  demandée (?langue=en…, le français si la traduction manque), et leurs images.
"""
import mimetypes

from django.core import signing

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.vocabulaire import v

from .console import EstOperateur
from .models import LANGUES_SITE, Actualite, PartenaireSite

TAILLE_MAX_IMAGE = 3 * 1024 * 1024
SEL_APERCU = "site.apercu"
FORMATS_IMAGE = {"PNG", "JPEG", "WEBP"}
CHAMPS_TRADUITS = {Actualite: ("titre", "resume", "contenu"), PartenaireSite: ("description",)}


def verifier_image(fichier):
    if fichier in (None, ""):
        return fichier
    from PIL import Image

    if fichier.size > TAILLE_MAX_IMAGE:
        raise serializers.ValidationError(v("Image trop lourde : 3 Mo au plus."))
    try:
        image = Image.open(fichier)
        image.verify()
        format_ = image.format
    except Exception:
        raise serializers.ValidationError(v("Ce fichier n'est pas une image valide."))
    finally:
        fichier.seek(0)
    if format_ not in FORMATS_IMAGE:
        raise serializers.ValidationError(v("Format d'image accepté : PNG, JPEG ou WEBP."))
    return fichier


class TraductionsMixin(serializers.ModelSerializer):
    """Traductions envoyées en JSON (texte, en multipart) : seules les langues et champs prévus sont gardés."""

    def to_internal_value(self, data):
        import json

        if hasattr(data, "getlist"):
            data = {cle: data.get(cle) for cle in data.keys()}
        if isinstance(data.get("traductions"), str):
            try:
                data["traductions"] = json.loads(data["traductions"] or "{}")
            except ValueError:
                raise serializers.ValidationError({"traductions": v("Traductions illisibles.")})
        return super().to_internal_value(data)

    def validate_traductions(self, valeur):
        champs = CHAMPS_TRADUITS[self.Meta.model]
        if not isinstance(valeur, dict):
            return {}
        return {langue: {c: str(t.get(c, ""))[:5000] for c in champs if str(t.get(c, "")).strip()}
                for langue, t in valeur.items() if langue in LANGUES_SITE and isinstance(t, dict)}


def adresse_apercu(request, type_, objet, champ):
    """Console : adresse signée (1 heure) de l'image, même pour un brouillon ou un partenaire masqué."""
    if not getattr(objet, champ):
        return None
    cle = signing.dumps({"t": type_, "id": objet.pk}, salt=SEL_APERCU)
    return request.build_absolute_uri(f"/api/v1/public/site/images/{type_}/{objet.pk}/?cle={cle}&v={int(objet.modifie_le.timestamp())}")


class ActualiteSerializer(TraductionsMixin):
    supprimer_image = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Actualite
        fields = ("id", "titre", "resume", "contenu", "image", "lien", "date_publication", "publiee", "traductions",
                  "supprimer_image", "modifie_le")

    def validate_image(self, valeur):
        return verifier_image(valeur)

    def to_representation(self, instance):
        donnees = super().to_representation(instance)
        donnees["image"] = adresse_apercu(self.context["request"], "actualite", instance, "image")
        return donnees

    def update(self, instance, validated_data):
        if validated_data.pop("supprimer_image", False) and instance.image:
            instance.image.delete(save=False)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        validated_data.pop("supprimer_image", None)
        return super().create(validated_data)


class PartenaireSiteSerializer(TraductionsMixin):
    supprimer_logo = serializers.BooleanField(write_only=True, required=False)
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)

    class Meta:
        model = PartenaireSite
        fields = ("id", "nom", "categorie", "categorie_libelle", "description", "logo", "site_web", "ordre", "visible",
                  "traductions", "supprimer_logo", "modifie_le")

    def validate_logo(self, valeur):
        return verifier_image(valeur)

    def to_representation(self, instance):
        donnees = super().to_representation(instance)
        donnees["logo"] = adresse_apercu(self.context["request"], "partenaire", instance, "logo")
        return donnees

    def update(self, instance, validated_data):
        if validated_data.pop("supprimer_logo", False) and instance.logo:
            instance.logo.delete(save=False)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        validated_data.pop("supprimer_logo", None)
        return super().create(validated_data)


class ConsoleSiteMixin:
    permission_classes = (EstOperateur,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    pagination_class = None

    def perform_destroy(self, instance):
        for champ in ("image", "logo"):
            fichier = getattr(instance, champ, None)
            if fichier:
                fichier.delete(save=False)
        instance.delete()


class ActualiteConsoleViewSet(ConsoleSiteMixin, viewsets.ModelViewSet):
    serializer_class = ActualiteSerializer
    queryset = Actualite.objects.all()


class PartenaireConsoleViewSet(ConsoleSiteMixin, viewsets.ModelViewSet):
    serializer_class = PartenaireSiteSerializer
    queryset = PartenaireSite.objects.all()


# --- Lecture publique (site vitrine) ---------------------------------------------------------------


def _traduit(objet, champ, langue):
    return ((objet.traductions or {}).get(langue) or {}).get(champ) or getattr(objet, champ)


def _image(request, type_, objet, champ):
    fichier = getattr(objet, champ)
    if not fichier:
        return None
    return request.build_absolute_uri(f"/api/v1/public/site/images/{type_}/{objet.pk}/?v={int(objet.modifie_le.timestamp())}")


def _actualite(request, a, langue, complet=False):
    donnees = {"id": a.id, "titre": _traduit(a, "titre", langue), "resume": _traduit(a, "resume", langue),
               "date": a.date_publication, "image": _image(request, "actualite", a, "image"), "lien": a.lien}
    if complet:
        donnees["contenu"] = _traduit(a, "contenu", langue)
    return donnees


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def actualites_publiques(request, pk=None):
    langue = request.query_params.get("langue", "fr")
    publiees = Actualite.objects.filter(publiee=True)
    if pk is not None:
        return Response(_actualite(request, get_object_or_404(publiees, pk=pk), langue, complet=True))
    return Response([_actualite(request, a, langue) for a in publiees[:100]])


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def partenaires_publics(request):
    langue = request.query_params.get("langue", "fr")
    return Response([{
        "id": p.id, "nom": p.nom, "categorie": p.categorie, "description": _traduit(p, "description", langue),
        "logo": _image(request, "partenaire", p, "logo"), "site_web": p.site_web,
    } for p in PartenaireSite.objects.filter(visible=True)])


def image_publique(request, type_, pk):
    """
    Image d'une actualité publiée ou logo d'un partenaire visible ; avec ?cle= (adresse signée remise à
    la console), aussi celle d'un brouillon ou d'un partenaire masqué.
    """
    try:
        apercu = signing.loads(request.GET.get("cle", ""), salt=SEL_APERCU, max_age=3600) == {"t": type_, "id": pk}
    except signing.BadSignature:
        apercu = False
    if type_ == "actualite":
        objet, champ = Actualite.objects.filter(pk=pk, **({} if apercu else {"publiee": True})).first(), "image"
    elif type_ == "partenaire":
        objet, champ = PartenaireSite.objects.filter(pk=pk, **({} if apercu else {"visible": True})).first(), "logo"
    else:
        raise Http404
    fichier = getattr(objet, champ, None) if objet else None
    if not fichier or not fichier.storage.exists(fichier.name):
        raise Http404
    reponse = FileResponse(fichier.open("rb"), content_type=mimetypes.guess_type(fichier.name)[0] or "image/png")
    reponse["Cache-Control"] = "private, max-age=3600" if apercu else "public, max-age=86400"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse
