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

Droit d'approuver : Administrateur, droit précis « peut approuver » sur le projet, sinon rôle avec « peut
approuver » (apps.projects.droits).
Sans requête (commandes, migrations), rien n'est mis en attente.
"""
from django.db import transaction
from django.db.models.signals import pre_delete, pre_save
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.core.models import EtatApprobation

from .models import Activite, DemandeModification, Projet, SousActivite
from .verrou import _desactive, _projet_id, utilisateur_courant


def doit_faire_approuver(utilisateur) -> bool:
    """
    Ce que saisit l'utilisateur dans le module de la requête doit être approuvé : réglage de sa fiche, ou onglet
    soumis à approbation pour tous (apps.core.approbation_generale).
    """
    from apps.core.approbation_generale import approbation_requise

    return approbation_requise(utilisateur)


def peut_approuver_auteur(approbateur, auteur, droit_objet: bool) -> bool:
    """
    Droit d'approuver ce qu'a saisi `auteur`, compte tenu du droit sur le projet ou la stratégie (`droit_objet`) :
    pour un auteur dont tout doit être approuvé, jamais lui-même ; et s'il a des approbateurs désignés, eux seuls
    (avec l'Administrateur).
    """
    from apps.accounts.constants import ROLE_ADMIN

    if auteur is None:
        return droit_objet
    if approbateur.pk == auteur.pk and approbateur.role != ROLE_ADMIN:
        return False  # personne n'approuve ses propres saisies
    if not getattr(auteur, "saisies_a_approuver", False):
        return droit_objet
    designes = set(auteur.approbateurs.values_list("id", flat=True))
    if designes:
        return approbateur.role == ROLE_ADMIN or approbateur.pk in designes
    return droit_objet


def peut_approuver_projet(utilisateur, projet) -> bool:
    from .droits import droits_projet

    return bool(projet) and droits_projet(utilisateur, projet.id if hasattr(projet, "id") else projet).approuver


def _projet(instance):
    projet_id = _projet_id(instance)
    return Projet.objects.filter(id=projet_id).first() if projet_id else None


def _avant_enregistrement_saisie(sender, instance, **kwargs):
    from .droits import ecriture_deja_accordee

    if _desactive.get() or kwargs.get("raw") or ecriture_deja_accordee():  # raw : sauvegarde ; sinon : approbation en cours
        return
    utilisateur = utilisateur_courant()
    projet = _projet(instance)
    if utilisateur is None or projet is None or not (projet.approbation_realisations or doit_faire_approuver(utilisateur)):
        return
    if peut_approuver_projet(utilisateur, projet) and not doit_faire_approuver(utilisateur):
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
    if utilisateur is not None and projet is not None and (projet.approbation_realisations or doit_faire_approuver(utilisateur)) \
            and (doit_faire_approuver(utilisateur) or not peut_approuver_projet(utilisateur, projet)):
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
    from .droits import ecriture_accordee

    if not peut_approuver_auteur(utilisateur, saisie.saisi_par, peut_approuver_projet(utilisateur, _projet(saisie))):
        raise PermissionDenied("Vous n'avez pas le droit d'approuver cette saisie.")
    with transaction.atomic(), ecriture_accordee():
        saisie.etat_approbation = EtatApprobation.APPROUVEE if approuver else EtatApprobation.REJETEE
        saisie.approbation_par, saisie.approbation_le = utilisateur, timezone.now()
        saisie.motif_rejet = "" if approuver else motif
        saisie.save()
        _resynchroniser(saisie)
    return saisie


# --------------------------------------------------------------------- demandes de planification

def exige_demande(projet, utilisateur) -> bool:
    if projet and doit_faire_approuver(utilisateur):
        return True
    return bool(projet and projet.approbation_planification and not peut_approuver_projet(utilisateur, projet))


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


def peut_traiter_demande(utilisateur, demande) -> bool:
    """Droit d'approuver une demande : de planification, de stratégie ou générique (toute autre modification)."""
    from apps.core.permissions import peut_approuver

    if demande.cible == DemandeModification.Cible.GENERIQUE:
        droit = peut_approuver_projet(utilisateur, demande.projet) if demande.projet_id else peut_approuver(utilisateur)
        return peut_approuver_auteur(utilisateur, demande.demandeur, droit)
    if demande.projet_id is None:
        from apps.strategy.approbation import peut_traiter

        return peut_traiter(utilisateur, demande)
    return peut_approuver_auteur(utilisateur, demande.demandeur, peut_approuver_projet(utilisateur, demande.projet))


def creer_demande(*, projet, cible, action, utilisateur, instance=None, donnees=None, libelle="", document=None, element_id=None):
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
        document=document,
        element_id=element_id,
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

    from .droits import ecriture_accordee

    generique = demande.cible == DemandeModification.Cible.GENERIQUE
    strategie = demande.projet_id is None and not generique
    if generique:
        if not peut_traiter_demande(utilisateur, demande):
            raise PermissionDenied("Vous n'avez pas le droit d'approuver cette demande.")
    elif strategie:
        from apps.strategy.approbation import appliquer, peut_traiter

        if not peut_traiter(utilisateur, demande):
            raise PermissionDenied("Vous n'avez pas le droit d'approuver dans cette stratégie.")
    elif not peut_approuver_auteur(utilisateur, demande.demandeur, peut_approuver_projet(utilisateur, demande.projet)):
        raise PermissionDenied("Vous n'avez pas le droit d'approuver cette demande.")
    if demande.etat != EtatApprobation.EN_ATTENTE:
        raise PermissionDenied("Cette demande a déjà été traitée.")
    with transaction.atomic(), ecriture_accordee():
        if approuver and generique:
            from apps.core.approbation_generale import rejouer

            rejouer(demande)
        elif approuver and strategie:
            appliquer(demande)
        elif approuver:
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
