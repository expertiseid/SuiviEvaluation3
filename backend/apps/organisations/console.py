"""
Console Expertise-ID (adresse principale, opérateurs de la plateforme seulement) : demandes
d'inscription, activation de l'espace, organisations actives et suspendues.
"""
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.core.audit import A, auditer

from . import activation, contexte, gestion
from .models import Organisation


class EstOperateur(BasePermission):
    """Opérateur Expertise-ID : compte « superutilisateur » de la base centrale, sur l'adresse principale."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser
                    and contexte.courante() is None)


class OrganisationSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    comptes = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ("id", "nom", "sous_domaine", "base", "statut", "statut_libelle", "offre", "mode_demo",
                  "courriel_contact", "cree_le", "active_le", "comptes")

    def get_comptes(self, obj):
        """Nombre de comptes qui peuvent se connecter (adresse courriel réelle, indexée)."""
        return obj.comptes.count()


@api_view(["GET"])
@permission_classes([EstOperateur])
def organisations(request):
    return Response(OrganisationSerializer(Organisation.objects.using("central").order_by("nom"), many=True).data)


@api_view(["POST"])
@permission_classes([EstOperateur])
def changer_statut(request, pk):
    """{statut: ACTIVE | SUSPENDUE} : suspendre ou réactiver un espace (effet immédiat)."""
    org = Organisation.objects.using("central").filter(pk=pk).first()
    statut = request.data.get("statut")
    if org is None or statut not in (Organisation.Statut.ACTIVE, Organisation.Statut.SUSPENDUE):
        raise ValidationError({"statut": "Choisissez « active » ou « suspendue »."})
    org.statut = statut
    org.save(using="central", update_fields=["statut"])
    auditer(request.user, A.CONFIGURATION, f"Espace {org.sous_domaine}", module="console", operation=statut.lower())
    return Response(OrganisationSerializer(org).data)


@api_view(["GET"])
@permission_classes([EstOperateur])
def demandes(request):
    from apps.accounts.models import DemandeInscription
    from apps.accounts.serializers import DemandeInscriptionSerializer

    return Response(DemandeInscriptionSerializer(DemandeInscription.objects.using("central").all(), many=True).data)


@api_view(["POST"])
@permission_classes([EstOperateur])
def activer(request, pk):
    """{sous_domaine?, zones?} : crée l'espace de la demande (en arrière-plan) ; la console suit son état."""
    from apps.accounts.models import DemandeInscription
    from apps.accounts.serializers import DemandeInscriptionSerializer

    demande = DemandeInscription.objects.using("central").filter(pk=pk).first()
    if demande is None:
        raise ValidationError({"detail": "Demande introuvable."})
    if demande.statut in (DemandeInscription.Statut.ACTIVEE, DemandeInscription.Statut.EN_ACTIVATION):
        raise ValidationError({"detail": "Cet espace est déjà créé ou en cours de création."})
    sous_domaine = (request.data.get("sous_domaine") or demande.sous_domaine or "").strip().lower()
    try:
        demande.sous_domaine = gestion.verifier_sous_domaine(sous_domaine)
    except gestion.ErreurOrganisation as erreur:
        raise ValidationError({"sous_domaine": str(erreur)})
    demande.save(using="central", update_fields=["sous_domaine"])
    auditer(request.user, A.CONFIGURATION, f"Espace {demande.sous_domaine}", module="console", operation="activation")
    activation.lancer(demande, zones=request.data.get("zones", True) is not False)
    return Response(DemandeInscriptionSerializer(demande).data, status=202)
