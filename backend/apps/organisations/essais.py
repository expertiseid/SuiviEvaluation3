"""
Suppression des espaces d'essai gratuit non convertis (RGPD : pas de données gardées sans raison).

À la fin de l'essai (offre ESSAI, abonnement_fin), l'accès est bloqué (abonnement.py). Sans abonnement,
l'espace et toutes ses données (base, fichiers) sont supprimés SUPPRESSION_JOURS jours après la fin de l'essai,
le jour J à HEURE_SUPPRESSION, après quatre avertissements par courriel aux administrateurs et à l'adresse de
contact : 30, 15 et 5 jours avant, puis le jour J à HEURE_DERNIER_AVERTISSEMENT.

- Choisir une offre payante (l'offre n'est plus ESSAI) arrête tout : rien n'est supprimé.
- Si la fin de l'essai change (console), le calendrier repart de la nouvelle date.
- Sécurité : jamais de suppression sans le dernier avertissement envoyé au moins DELAI_MINIMAL plus tôt, même
  si la tâche planifiée a été interrompue ; jamais pour un espace de démonstration.
- Le registre des essais (EssaiGratuit, base centrale) est gardé : une adresse ne refait pas un second essai.

Lancé toutes les heures par la tâche planifiée (manage.py supprimer_essais_expires).
"""
import logging
import os
import shutil
from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

from .abonnement import ESSAI

logger = logging.getLogger(__name__)

SUPPRESSION_JOURS = 60
AVERTISSEMENTS = (30, 15, 5, 0)  # jours avant la suppression ; 0 : le jour J
HEURE_DERNIER_AVERTISSEMENT = time(8, 0)
HEURE_SUPPRESSION = time(20, 0)
DELAI_MINIMAL = timedelta(hours=8)


def date_suppression(org):
    if org.offre != ESSAI or org.abonnement_fin is None or org.mode_demo:
        return None
    return org.abonnement_fin + timedelta(days=SUPPRESSION_JOURS)


def _instant(jour, heure):
    return timezone.make_aware(datetime.combine(jour, heure))


def _niveau_du(jour_suppression, maintenant):
    """Nombre d'avertissements qui devraient être partis à cet instant (0 à 4)."""
    niveau = 0
    for rang, jours in enumerate(AVERTISSEMENTS, start=1):
        heure = HEURE_DERNIER_AVERTISSEMENT if jours == 0 else time(0, 0)
        if maintenant >= _instant(jour_suppression - timedelta(days=jours), heure):
            niveau = rang
    return niveau


def _destinataires(org):
    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User

    from .contexte import dans_organisation

    adresses = {org.courriel_contact} if org.courriel_contact else set()
    try:
        with dans_organisation(org):
            adresses |= set(User.objects.filter(role=ROLE_ADMIN, is_active=True).exclude(email="")
                            .values_list("email", flat=True))
    except Exception:  # base injoignable : l'adresse de contact suffit
        logger.exception("Administrateurs de %s introuvables pour l'avertissement de suppression.", org.sous_domaine)
    return sorted(adresses)


def _avertir(org, jour_suppression, rang):
    from apps.accounts.inscriptions import _envoyer

    jours = AVERTISSEMENTS[rang - 1]
    quand = "ce soir" if jours == 0 else f"dans {jours} jours, le {jour_suppression:%d/%m/%Y}"
    sujet = (f"Dernier avertissement : l'espace {org.nom} sera supprimé ce soir" if jours == 0
             else f"Votre espace d'essai sera supprimé dans {jours} jours")
    lien = f"{settings.PLAINTES_URL_PUBLIQUE.rstrip('/')}/login?suite=/mon-abonnement"
    texte = (
        f"Bonjour,\n\nL'essai gratuit de {org.nom} sur la plateforme Expertise-ID Monitora s'est terminé le "
        f"{org.abonnement_fin:%d/%m/%Y}. Sans abonnement, l'espace de votre organisation et toutes ses données "
        f"(projets, bénéficiaires, plaintes, documents…) seront supprimés définitivement {quand}, à "
        f"{HEURE_SUPPRESSION:%H} h.\n\nPour les garder, connectez-vous et choisissez une offre : {lien}\n\n"
        "Si vous ne souhaitez pas continuer, vous n'avez rien à faire.\n\nExpertise-ID"
    )
    for adresse in _destinataires(org):
        _envoyer(adresse, sujet, texte)


def _effacer_fichiers(org):
    dossier = os.path.join(str(settings.MEDIA_ROOT), "organisations", org.sous_domaine)
    if org.sous_domaine and os.path.isdir(dossier):
        shutil.rmtree(dossier, ignore_errors=True)


def _supprimer(org, jour_suppression):
    from apps.accounts.inscriptions import _envoyer

    from . import gestion

    nom, sous_domaine = org.nom, org.sous_domaine
    gestion.supprimer(org)
    _effacer_fichiers(org)
    _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"Espace d'essai supprimé : {nom}",
             f"Organisation : {nom} ({sous_domaine})\nFin de l'essai : {org.abonnement_fin:%d/%m/%Y}\n"
             f"Supprimé le {jour_suppression:%d/%m/%Y} après quatre avertissements, sans abonnement.")
    logger.info("Espace d'essai %s supprimé (fin de l'essai : %s).", sous_domaine, org.abonnement_fin)


def traiter(maintenant=None) -> dict:
    """Avertissements à envoyer et espaces à supprimer, à cet instant. Renvoie {avertis, supprimes}."""
    from .models import Organisation

    maintenant = maintenant or timezone.now()
    bilan = {"avertis": [], "supprimes": []}
    for org in Organisation.objects.using("central").filter(offre=ESSAI, mode_demo=False).exclude(abonnement_fin=None):
        jour = date_suppression(org)
        suivi = dict(org.suppression_essai or {})
        if suivi.get("date") != jour.isoformat():  # nouvelle fin d'essai : le calendrier repart
            suivi = {"date": jour.isoformat(), "niveau": 0}
        du = _niveau_du(jour, maintenant)
        if du > suivi["niveau"]:
            _avertir(org, jour, du)  # seulement le plus récent, jamais plusieurs à la fois
            suivi.update(niveau=du, dernier=maintenant.isoformat())
            bilan["avertis"].append(org.sous_domaine)
        if suivi != (org.suppression_essai or {}):
            Organisation.objects.using("central").filter(pk=org.pk).update(suppression_essai=suivi)
        dernier = suivi.get("dernier")
        if (suivi["niveau"] == len(AVERTISSEMENTS) and maintenant >= _instant(jour, HEURE_SUPPRESSION)
                and dernier and maintenant - datetime.fromisoformat(dernier) >= DELAI_MINIMAL):
            _supprimer(org, jour)
            bilan["supprimes"].append(org.sous_domaine)
    return bilan
