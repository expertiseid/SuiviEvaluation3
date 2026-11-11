"""
Console Expertise-ID (adresse principale, opérateurs de la plateforme seulement) : demandes
d'inscription, activation de l'espace, organisations actives et suspendues.
"""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.constants import ROLE_ADMIN
from apps.core.audit import A, auditer

from . import abonnement, activation, contexte, gestion, paiement, quota, supervision
from .models import Organisation


class EstOperateur(BasePermission):
    """Opérateur Expertise-ID : compte « superutilisateur » de la base centrale, sur l'adresse principale."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser
                    and contexte.courante() is None)


class OrganisationSerializer(serializers.ModelSerializer):
    stockage_go = serializers.FloatField(read_only=True, allow_null=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    comptes = serializers.SerializerMethodField()
    stockage = serializers.SerializerMethodField()
    abonnement = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ("id", "nom", "sous_domaine", "base", "statut", "statut_libelle", "offre", "mode_demo",
                  "courriel_contact", "cree_le", "active_le", "comptes", "stockage_go", "stockage",
                  "abonnement_fin", "abonnement")

    def get_stockage(self, obj):
        """Espace occupé et limite (quota.py) ; stockage_go vide : l'espace de l'offre."""
        return quota.etat(obj)

    def get_abonnement(self, obj):
        return abonnement.etat(obj)["statut"]

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
            org.stockage_go = Decimal(str(valeur)).quantize(Decimal("0.001"))
        except (InvalidOperation, TypeError, ValueError):
            org.stockage_go = Decimal(0)
        if not Decimal("0.001") <= org.stockage_go <= 100000:  # 0,01 Go = 10 Mo (essai)
            raise ValidationError({"stockage_go": "Indiquez un nombre de Go entre 0,001 et 100 000."})
    org.stockage_alerte = 0  # espace changé : alertes à nouveau possibles
    org.save(using="central", update_fields=["stockage_go", "stockage_alerte"])
    auditer(request.user, A.CONFIGURATION, f"Espace {org.sous_domaine} : stockage {quota.lisible(quota.limite_go(org)) if quota.limite_go(org) else '∞'}",
            module="console", operation="stockage")
    return Response(OrganisationSerializer(org).data)


@api_view(["POST"])
@permission_classes([EstOperateur])
def changer_abonnement(request, pk):
    """{fin: AAAA-MM-JJ | null} : échéance fixée à la main (paiement par carte, geste commercial) ; null : sans échéance."""
    from datetime import date

    org = Organisation.objects.using("central").filter(pk=pk).first()
    if org is None:
        raise ValidationError({"fin": "Organisation inconnue."})
    valeur = request.data.get("fin")
    try:
        org.abonnement_fin = date.fromisoformat(str(valeur)) if valeur else None
    except ValueError:
        raise ValidationError({"fin": "Date invalide."})
    org.abonnement_alerte = 0
    if org.abonnement_fin and not org.abonnement_prix_mois and org.offre in paiement.OFFRES_PAYANTES:
        org.abonnement_prix_mois = paiement.prix_mois(org.offre)
    org.save(using="central", update_fields=["abonnement_fin", "abonnement_alerte", "abonnement_prix_mois"])
    auditer(request.user, A.CONFIGURATION, f"Espace {org.sous_domaine} : échéance {org.abonnement_fin or 'aucune'}",
            module="console", operation="abonnement")
    return Response(OrganisationSerializer(org).data)


@api_view(["GET"])
@permission_classes([EstOperateur])
def vue_ensemble(request):
    """Organisations, demandes à traiter, paiements, disque commun et état des serveurs (supervision.py)."""
    return Response(supervision.vue_ensemble())


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


# --- Abonnement (page de l'organisation) ------------------------------------------------------------

def _offres():
    from apps.accounts.models import DemandeInscription

    libelles = dict(DemandeInscription.Offre.choices)
    return [{"offre": o, "libelle": libelles.get(o, o), "prix_mois": paiement.prix_mois(o), "prix_mois_usd": paiement.prix_mois(o, usd=True),
             "go": quota.OFFRE_GO.get(o)} for o in abonnement.OFFRES_CHANGEMENT]


@api_view(["GET"])
def abonnement_organisation(request):
    """Page Abonnement : échéance, offre, offres possibles, paiements ; payer : administrateurs seulement."""
    from apps.accounts.models import DemandeInscription

    org = _organisation_du_compte()
    if org is None:
        return Response({"statut": "SANS_ECHEANCE"})
    jours, valeur = abonnement.reste(org)
    return Response({
        **abonnement.etat(org), "offre_libelle": dict(DemandeInscription.Offre.choices).get(org.offre, org.offre or "—"),
        "prix_mois": org.abonnement_prix_mois, "reste": valeur, "grace": abonnement.grace(org),
        "peut_payer": request.user.role == ROLE_ADMIN, "paiement": paiement.actif(), "devise": settings.ABONNEMENT_DEVISE,
        "renouvelable": org.offre in paiement.OFFRES_PAYANTES, "offres": _offres(), "durees": list(paiement.DUREES),
        "paiements": paiement.paiements_abonnement(org) if request.user.role == ROLE_ADMIN else [],
    })


@api_view(["GET"])
def abonnement_devis(request):
    org = _organisation_du_compte()
    if org is None:
        raise ValidationError({"detail": "Aucune organisation."})
    return Response(abonnement.devis(org, request.query_params.get("offre") or org.offre, request.query_params.get("mois") or 12))


@api_view(["POST"])
def abonnement_payer(request):
    """{offre, mois, moyen: mobile | carte, langue} : renouveler ou changer d'offre (administrateurs)."""
    org = _organisation_du_compte()
    if org is None or request.user.role != ROLE_ADMIN:
        raise PermissionDenied("Réservé à l'administrateur de l'organisation.")
    offre, mois = request.data.get("offre") or org.offre, request.data.get("mois")
    if request.data.get("moyen") == "carte":
        paiement.renouvellement_par_carte(org, request.user, offre, mois)
        return Response({"carte": True})
    p = paiement.creer_renouvellement(org, request.user, offre, mois, langue=request.data.get("langue") or "fr")
    return Response({"paiement": p.reference, "lien": p.lien, "montant": p.montant, "devise": p.devise})


@api_view(["GET"])
def abonnement_paiement(request, reference):
    org = _organisation_du_compte()
    if org is None:
        raise ValidationError({"detail": "Aucune organisation."})
    return Response(paiement.etat_renouvellement(org, reference))
