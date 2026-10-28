"""
Circuit d'approbation, activable projet par projet.

- Projet.approbation_realisations : une saisie de réalisation (point de suivi, valeur
  d'indicateur, taux manuel) faite par quelqu'un qui n'a pas le droit d'approuver reste « en
  attente » et ne compte nulle part (le gestionnaire par défaut de ces modèles ne renvoie que
  les saisies approuvées, voir apps.core.models.SaisieApprouvable) ; la modifier la remet en
  attente ; il ne peut pas supprimer une saisie déjà approuvée.
- Projet.approbation_planification : ajouter, modifier ou supprimer un élément de la
  planification ou une sous-activité crée une DemandeModification, appliquée une fois
  approuvée (voir les vues ActiviteViewSet / SousActiviteViewSet).

Droit d'approuver : Administrateur, ou rôle avec « peut approuver » (core.permissions).
Sans requête (commandes, migrations), rien n'est mis en attente.
"""
from django.db import transaction
from django.db.models.signals import pre_delete, pre_save
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.core.models import EtatApprobation
from apps.core.permissions import peut_approuver

from .models import Activite, DemandeModification, Projet, SousActivite
from .verrou import _desactive, _projet_id, utilisateur_courant


def _projet(instance):
    projet_id = _projet_id(instance)
    return Projet.objects.filter(id=projet_id).first() if projet_id else None


def _avant_enregistrement_saisie(sender, instance, **kwargs):
    if _desactive.get():
        return
    utilisateur = utilisateur_courant()
    projet = _projet(instance)
    if utilisateur is None or projet is None or not projet.approbation_realisations:
        return
    if peut_approuver(utilisateur):
        if instance.pk is None:  # saisie d'un approbateur : approuvée d'emblée
            instance.etat_approbation = EtatApprobation.APPROUVEE
            instance.approbation_par, instance.approbation_le = utilisateur, timezone.now()
        return
    # Saisie ou modification par quelqu'un qui ne peut pas approuver : à (re)valider.
    instance.etat_approbation = EtatApprobation.EN_ATTENTE
    instance.approbation_par, instance.approbation_le, instance.motif_rejet = None, None, ""


def _avant_suppression_saisie(sender, instance, **kwargs):
    if _desactive.get() or instance.etat_approbation != EtatApprobation.APPROUVEE:
        return
    utilisateur = utilisateur_courant()
    projet = _projet(instance)
    if utilisateur is not None and projet is not None and projet.approbation_realisations and not peut_approuver(utilisateur):
        raise PermissionDenied("Cette saisie a été approuvée : seul un approbateur peut la supprimer.")


def connecter():
    from apps.indicators.models import ValeurIndicateur
    from apps.suivi.models import PointSuivi

    from .models import TauxManuel

    for modele in (PointSuivi, ValeurIndicateur, TauxManuel):
        pre_save.connect(_avant_enregistrement_saisie, sender=modele, dispatch_uid=f"approbation_{modele.__name__}")
        pre_delete.connect(_avant_suppression_saisie, sender=modele, dispatch_uid=f"approbation_del_{modele.__name__}")


# ---------------------------------------------------------------------------------- saisies

def _resynchroniser(saisie):
    """Les totaux de l'activité / sous-activité ne comptent que les saisies approuvées."""
    from apps.suivi.services import synchroniser_activite_depuis_suivi, synchroniser_sous_activite_depuis_suivi

    if type(saisie).__name__ != "PointSuivi":
        return
    if saisie.activite_id:
        synchroniser_activite_depuis_suivi(saisie.activite)
    else:
        synchroniser_sous_activite_depuis_suivi(saisie.sous_activite)


def traiter_saisie(saisie, utilisateur, approuver: bool, motif=""):
    if not peut_approuver(utilisateur):
        raise PermissionDenied("Vous n'avez pas le droit d'approuver.")
    with transaction.atomic():
        saisie.etat_approbation = EtatApprobation.APPROUVEE if approuver else EtatApprobation.REJETEE
        saisie.approbation_par, saisie.approbation_le = utilisateur, timezone.now()
        saisie.motif_rejet = "" if approuver else motif
        saisie.save()
        _resynchroniser(saisie)
    return saisie


# --------------------------------------------------------------------- demandes de planification

def exige_demande(projet, utilisateur) -> bool:
    return bool(projet and projet.approbation_planification and not peut_approuver(utilisateur))


# Noms des champs tels qu'affichés dans l'écran Approbations.
LIBELLES_CHAMPS = {
    "libelle": "Libellé", "description": "Description", "commentaire": "Commentaire", "code_activite": "Code",
    "quantite_prevue": "Quantité prévue", "unite_quantite": "Unité", "valeur_reference": "Valeur de référence",
    "budget_alloue": "Budget alloué", "date_debut": "Date de début", "date_fin": "Date de fin",
    "date_rappel": "Date de rappel", "methode_calcul": "Méthode de calcul", "methode_agregation": "Agrégation",
    "poids": "Poids", "avancement": "Avancement", "statut": "Statut", "responsables": "Responsables",
    "responsable": "Responsable", "equipe_responsable": "Équipe responsable", "axe_strategique": "Élément stratégique",
    "activite_parent": "Élément parent", "activite": "Élément", "projet": "Projet",
    "structures": "Services chargés", "axes_strategiques_secondaires": "Contribue aussi à",
}


def _valeur_affichable(valeur):
    from decimal import Decimal

    if isinstance(valeur, Decimal):
        return f"{valeur.normalize():f}"
    return valeur if valeur is None or isinstance(valeur, (str, int, float, bool)) else str(valeur)


def creer_demande(*, projet, cible, action, utilisateur, instance=None, donnees=None, libelle=""):
    """Enregistre la demande ; pour une modification, garde l'ancienne et la nouvelle valeur de chaque champ changé."""
    donnees = {k: v for k, v in (donnees or {}).items()}
    changements = []
    if action == DemandeModification.Action.MODIFICATION and instance is not None:
        for champ, nouvelle in donnees.items():
            ancienne = getattr(instance, f"{champ}_id", getattr(instance, champ, None)) if hasattr(instance, champ) else None
            if hasattr(ancienne, "all"):  # relation multiple
                ancienne = sorted(ancienne.values_list("id", flat=True))
            ancienne = _valeur_affichable(ancienne)
            if str(ancienne) != str(nouvelle):
                changements.append({"champ": LIBELLES_CHAMPS.get(champ, champ), "avant": ancienne, "apres": nouvelle})
    return DemandeModification.objects.create(
        projet=projet,
        cible=cible,
        cible_id=instance.pk if instance is not None else None,
        action=action,
        libelle=(libelle or getattr(instance, "libelle", "") or donnees.get("libelle", ""))[:300],
        donnees=donnees,
        changements=changements,
        demandeur=utilisateur,
    )


def _serialiseur(cible):
    from .serializers import ActiviteSerializer, SousActiviteSerializer

    return (ActiviteSerializer, Activite) if cible == DemandeModification.Cible.ACTIVITE else (SousActiviteSerializer, SousActivite)


def traiter_demande(demande, utilisateur, approuver: bool, motif=""):
    """Approuver applique le changement demandé (avec les contrôles habituels) ; rejeter le garde pour mémoire."""
    from .services import supprimer_activite_cascade, supprimer_sous_activite_cascade, synchroniser_projets_associes_activite

    if not peut_approuver(utilisateur):
        raise PermissionDenied("Vous n'avez pas le droit d'approuver.")
    if demande.etat != EtatApprobation.EN_ATTENTE:
        raise PermissionDenied("Cette demande a déjà été traitée.")
    with transaction.atomic():
        if approuver:
            classe_serialiseur, modele = _serialiseur(demande.cible)
            instance = modele.objects.filter(pk=demande.cible_id).first() if demande.cible_id else None
            if demande.action != DemandeModification.Action.CREATION and instance is None:
                raise PermissionDenied("L'élément concerné n'existe plus.")
            if demande.action == DemandeModification.Action.SUPPRESSION:
                (supprimer_activite_cascade if modele is Activite else supprimer_sous_activite_cascade)(instance)
            else:
                serialiseur = classe_serialiseur(instance, data=demande.donnees, partial=instance is not None)
                serialiseur.is_valid(raise_exception=True)
                objet = serialiseur.save()
                if demande.action == DemandeModification.Action.CREATION:
                    demande.cible_id = objet.pk
                if modele is Activite:
                    synchroniser_projets_associes_activite(objet)
        demande.etat = EtatApprobation.APPROUVEE if approuver else EtatApprobation.REJETEE
        demande.traite_par, demande.traite_le = utilisateur, timezone.now()
        demande.motif_rejet = "" if approuver else motif
        demande.save()
    return demande
