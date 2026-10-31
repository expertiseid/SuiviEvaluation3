"""
API du paramétrage du mécanisme de plaintes (lot 1). Lecture pour tout utilisateur connecté (aucun
contenu de plainte ici) ; écriture selon les droits du module « Plaintes et retours »
(apps.core.modules : /api/v1/plaintes/).
"""
from django.db.models import ProtectedError
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.langues import dans_la_langue_demandee, en_langue, langue_demandee, traduire
from apps.core.permissions import HasGlobalVisibilityOrAssigned

from .controles import controler_activation
from .models import Categorie, Circuit, EtapeCircuit, Mecanisme, Priorite, TypeRetour
from .modeles_mecanisme import MODELES, appliquer_modele, liste_modeles
from .serializers import (
    CategorieSerializer,
    CircuitSerializer,
    EtapeCircuitSerializer,
    MecanismeSerializer,
    PrioriteSerializer,
    TypeRetourSerializer,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@api_view(["GET", "PATCH"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def mecanisme(request):
    """Le mécanisme de l'organisation ; « controles » : ce qui manque pour l'activer."""
    objet = Mecanisme.courant()
    if request.method == "PATCH":
        serializer = MecanismeSerializer(objet, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        objet.refresh_from_db()
    return Response(MecanismeSerializer(objet).data)


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def activer(request):
    """Ouvre le mécanisme ; refusé, avec la liste de ce qui manque, si un contrôle échoue."""
    objet = Mecanisme.courant()
    erreurs = controler_activation(objet)
    if erreurs:
        return Response({"detail": "Le mécanisme ne peut pas encore être activé.", "controles": erreurs},
                        status=status.HTTP_400_BAD_REQUEST)
    objet.actif = True
    objet.save(update_fields=["actif", "updated_at"])
    return Response(MecanismeSerializer(objet).data)


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def desactiver(request):
    objet = Mecanisme.courant()
    objet.actif = False
    objet.save(update_fields=["actif", "updated_at"])
    return Response(MecanismeSerializer(objet).data)


@api_view(["GET", "POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def modeles(request):
    """GET : modèles prêts à l'emploi ; POST {modele} : le copie dans la configuration (ajouts seulement)."""
    if request.method == "GET":
        with en_langue(langue_demandee(request)):
            return Response([{**m, "libelle": traduire(m["libelle"]), "description": traduire(m["description"])}
                             for m in liste_modeles()])
    code = request.data.get("modele")
    if code not in MODELES:
        raise ValidationError({"modele": "Choisissez un modèle de la liste."})
    ajouts = appliquer_modele(code)
    return Response({"ajouts": ajouts, "mecanisme": MecanismeSerializer(Mecanisme.courant()).data})


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def canevas(request):
    """Canevas Excel du paramétrage, prérempli avec la configuration actuelle."""
    from .excel import exporter_parametrage

    response = HttpResponse(exporter_parametrage(), content_type=XLSX)
    response["Content-Disposition"] = "attachment; filename=parametrage_plaintes.xlsx"
    return response


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@parser_classes([MultiPartParser, FormParser])
def importer_canevas(request):
    from .excel import importer_parametrage

    fichier = request.data.get("fichier")
    if not fichier:
        raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
    try:
        return Response(importer_parametrage(fichier))
    except (KeyError, OSError, ValueError) as exc:
        raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})


class _Base(viewsets.ModelViewSet):
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    pagination_class = None

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError({"detail": "Cet élément est encore utilisé : retirez d'abord ce qui en dépend."})


class TypeRetourViewSet(_Base):
    queryset = TypeRetour.objects.all()
    serializer_class = TypeRetourSerializer


class PrioriteViewSet(_Base):
    queryset = Priorite.objects.all()
    serializer_class = PrioriteSerializer

    def perform_destroy(self, instance):
        if instance.urgente and not Priorite.objects.filter(urgente=True, actif=True).exclude(pk=instance.pk).exists():
            raise ValidationError({"detail": "Gardez au moins une priorité urgente active."})
        super().perform_destroy(instance)


class CircuitViewSet(_Base):
    queryset = Circuit.objects.prefetch_related("etapes__role", "etapes__responsable")
    serializer_class = CircuitSerializer


class EtapeCircuitViewSet(_Base):
    queryset = EtapeCircuit.objects.select_related("role", "responsable")
    serializer_class = EtapeCircuitSerializer
    filterset_fields = ("circuit",)


class CategorieViewSet(_Base):
    queryset = Categorie.objects.select_related("parent", "circuit")
    serializer_class = CategorieSerializer

    def perform_destroy(self, instance):
        if instance.verrouillee:
            raise ValidationError({"detail": "Cette catégorie protège les personnes : elle ne peut pas être supprimée."})
        if instance.sous_categories.exists():
            raise ValidationError({"detail": "Supprimez ou déplacez d'abord ses sous-catégories."})
        super().perform_destroy(instance)
