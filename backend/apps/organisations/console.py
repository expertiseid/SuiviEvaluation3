"""
Console Expertise-ID (adresse principale, opérateurs de la plateforme seulement) : demandes
d'inscription, activation de l'espace, organisations actives et suspendues.
"""
from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.constants import ROLE_ADMIN
from apps.core.audit import A, auditer

from . import activation, contexte, gestion, paiement, quota
from .models import Organisation


class EstOperateur(BasePermission):
    """Opérateur Expertise-ID : compte « superutilisateur » de la base centrale, sur l'adresse principale."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser
                    and contexte.courante() is None)


class OrganisationSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    comptes = serializers.SerializerMethodField()
    stockage = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ("id", "nom", "sous_domaine", "base", "statut", "statut_libelle", "offre", "mode_demo",
                  "courriel_contact", "cree_le", "active_le", "comptes", "stockage_go", "stockage")

    def get_stockage(self, obj):
        """Espace occupé et limite (quota.py) ; stockage_go vide : l'espace de l'offre."""
        return quota.etat(obj)

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


@api_view(["POST"])
@permission_classes([EstOperateur])
def changer_stockage(request, pk):
    """{stockage_go: nombre | null} : agrandir (ou réduire) l'espace d'une organisation ; null : celui de l'offre."""
    org = Organisation.objects.using("central").filter(pk=pk).first()
    valeur = request.data.get("stockage_go")
    if org is None:
        raise ValidationError({"stockage_go": "Organisation inconnue."})
    if valeur in (None, ""):
        org.stockage_go = None
    else:
        try:
            org.stockage_go = int(valeur)
        except (TypeError, ValueError):
            org.stockage_go = 0
        if not 1 <= org.stockage_go <= 100000:
            raise ValidationError({"stockage_go": "Indiquez un nombre de Go entre 1 et 100 000."})
    org.stockage_alerte = 0  # espace changé : alertes à nouveau possibles
    org.save(using="central", update_fields=["stockage_go", "stockage_alerte"])
    auditer(request.user, A.CONFIGURATION, f"Espace {org.sous_domaine} : stockage {quota.limite_go(org) or '∞'} Go",
            module="console", operation="stockage")
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


def _organisation_du_compte():
    org = contexte.courante()
    return Organisation.objects.using("central").get(pk=org.pk) if org else None


@api_view(["GET"])
def stockage(request):
    """
    Page Stockage : espace de l'organisation du compte connecté (alloué, occupé), tarifs du stockage
    supplémentaire et achats déjà payés. Hors organisation : sans limite.
    """
    org = _organisation_du_compte()
    if org is None:
        return Response({"utilise": None, "limite": None, "limite_go": None})
    return Response({
        **quota.etat(org), "offre": org.offre, "offre_go": quota.OFFRE_GO.get(org.offre),
        "peut_acheter": request.user.role == ROLE_ADMIN,
        "tarifs": {"paiement": paiement.actif(), "devise": settings.ABONNEMENT_DEVISE, "tranche": settings.ABONNEMENT_PRIX_TRANCHE,
                   "tranche_usd": settings.ABONNEMENT_PRIX_TRANCHE_USD, "durees": list(paiement.DUREES),
                   "tranches_max": paiement.TRANCHES_MAX},
        "achats": paiement.achats_stockage(org),
    })


@api_view(["POST"])
def acheter_stockage(request):
    """
    {tranches, mois, moyen} : stockage supplémentaire (administrateur de l'organisation). Mobile money : lien
    vers la page de paiement de CinetPay (espace agrandi dès le paiement) ; carte : demande à Expertise-ID.
    """
    org = _organisation_du_compte()
    if org is None or request.user.role != ROLE_ADMIN:
        raise PermissionDenied("Réservé à l'administrateur de l'organisation.")
    tranches, mois = request.data.get("tranches"), request.data.get("mois")
    if request.data.get("moyen") == "carte":
        paiement.stockage_par_carte(org, request.user, tranches, mois)
        return Response({"carte": True})
    achat = paiement.creer_stockage(org, request.user, tranches, mois, langue=request.data.get("langue") or "fr")
    return Response({"paiement": achat.reference, "lien": achat.lien, "montant": achat.montant, "devise": achat.devise})


@api_view(["GET"])
def paiement_stockage(request, reference):
    org = _organisation_du_compte()
    if org is None:
        raise PermissionDenied()
    return Response(paiement.etat_stockage(org, reference))
