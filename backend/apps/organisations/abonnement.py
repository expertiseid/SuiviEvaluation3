"""
Échéance de l'abonnement d'une organisation (Organisation.abonnement_fin) :

- payé pour N mois, l'abonnement court jusqu'à abonnement_fin ; 7 jours avant, les administrateurs sont
  prévenus ; à la fin, 7 jours de grâce (accès normal, bandeau « à renouveler ») ; ensuite l'accès est
  bloqué (OrganisationMiddleware, code « abonnement_expire ») sauf la page Abonnement, pour payer : le
  paiement rétablit l'accès aussitôt ;
- renouveler la même offre : la nouvelle période s'ajoute à la fin de l'actuelle (rien n'est perdu) ;
- changer d'offre : ce qui reste de la période en cours (prix d'un mois payé × jours restants × 12 / 365) est
  déduit du prix de la nouvelle offre, qui commence aujourd'hui ;
- essai gratuit (offre ESSAI) : 1 mois, sans période de grâce ; à la fin, bloqué jusqu'au choix d'une offre
  payante (un changement d'offre : rien n'est déduit, l'essai n'a rien coûté) ;
- sans date de fin (partenariat, démonstration, espaces ouverts à la main) : pas d'échéance.
"""
import calendar
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.vocabulaire import v

GRACE = 7  # jours d'accès après la fin
PREAVIS = 7  # jours avant la fin : premier rappel
OFFRES_CHANGEMENT = ("STANDARD_25", "STANDARD_50", "STANDARD")
ESSAI = "ESSAI"
DUREE_ESSAI = 1  # mois


def grace(org) -> int:
    """Jours d'accès après la fin : aucun pour l'essai gratuit."""
    return 0 if org.offre == ESSAI else GRACE


def ajouter_mois(jour: date, mois: int) -> date:
    """31 janvier + 1 mois = 28 (ou 29) février."""
    total = jour.month - 1 + mois
    annee, mois_ = jour.year + total // 12, total % 12 + 1
    return date(annee, mois_, min(jour.day, calendar.monthrange(annee, mois_)[1]))


def aujourd_hui() -> date:
    return timezone.localdate()


def etat(org) -> dict:
    """Où en est l'abonnement : ACTIF, BIENTOT (7 derniers jours), GRACE, BLOQUE ou SANS_ECHEANCE."""
    fin = org.abonnement_fin
    if fin is None:
        return {"statut": "SANS_ECHEANCE", "fin": None, "fin_grace": None, "jours_restants": None, "offre": org.offre,
                "essai": org.offre == ESSAI}
    jour = aujourd_hui()
    fin_grace = fin + timedelta(days=grace(org))
    if jour > fin_grace:
        statut = "BLOQUE"
    elif jour > fin:
        statut = "GRACE"
    elif (fin - jour).days < PREAVIS:
        statut = "BIENTOT"
    else:
        statut = "ACTIF"
    return {"statut": statut, "fin": fin, "fin_grace": fin_grace, "jours_restants": (fin - jour).days, "offre": org.offre,
            "essai": org.offre == ESSAI}


def bloque(org) -> bool:
    return bool(org.abonnement_fin) and aujourd_hui() > org.abonnement_fin + timedelta(days=grace(org))


def reste(org) -> tuple[int, int]:
    """(jours restants payés, valeur de ces jours) : déduite lors d'un changement d'offre."""
    if not org.abonnement_fin or not org.abonnement_prix_mois:
        return 0, 0
    jours = max(0, (org.abonnement_fin - aujourd_hui()).days)
    return jours, org.abonnement_prix_mois * jours * 12 // 365  # un mois = 365 / 12 jours


def devis(org, offre, mois) -> dict:
    """Prix à payer : même offre, renouvellement (après la fin actuelle) ; autre offre, ce qui reste est déduit."""
    from . import paiement

    try:
        mois = int(mois)
    except (TypeError, ValueError):
        raise ValidationError({"detail": v("Durée invalide.")})
    if mois not in paiement.DUREES:
        raise ValidationError({"detail": v("Durée invalide.")})
    changement = offre != org.offre
    if changement and offre not in OFFRES_CHANGEMENT:
        raise ValidationError({"offre": v("Choisissez une offre.")})
    if not changement and org.offre == ESSAI:
        raise ValidationError({"offre": v("L'essai gratuit ne se renouvelle pas : choisissez une offre pour continuer.")})
    if not changement and org.offre not in paiement.OFFRES_PAYANTES:
        raise ValidationError({"detail": v("Votre offre ne se renouvelle pas en ligne : contactez Expertise-ID.")})
    prix = paiement.montant(offre, mois, 0)
    jours, valeur = reste(org) if changement else (0, 0)
    a_payer = max(0, prix - valeur)
    jour = aujourd_hui()
    depart = jour if changement or not org.abonnement_fin or org.abonnement_fin < jour else org.abonnement_fin
    return {"offre": offre, "mois": mois, "changement": changement, "prix": prix, "jours_restants": jours,
            "deduction": prix - a_payer, "a_payer": a_payer, "nouvelle_fin": ajouter_mois(depart, mois),
            "possible": a_payer >= settings.PAIEMENT_MINIMUM}


def appliquer(org, paiement_abonnement) -> None:
    """Paiement validé (renouvellement ou changement d'offre) : nouvelle échéance, accès rétabli."""
    from . import paiement, quota

    d = devis(org, paiement_abonnement.offre, paiement_abonnement.mois)
    if d["changement"]:
        # Stockage acheté en plus : gardé par-dessus l'espace de la nouvelle offre.
        avant = quota.OFFRE_GO.get(org.offre) or 0
        en_plus = float(org.stockage_go) - avant if org.stockage_go else 0
        org.stockage_go = quota.OFFRE_GO[d["offre"]] + en_plus if en_plus > 0 else None
        org.stockage_alerte = 0
        org.offre = d["offre"]
    org.abonnement_fin = d["nouvelle_fin"]
    org.abonnement_prix_mois = paiement.prix_mois(org.offre)
    org.abonnement_alerte = 0
    org.save(using="central", update_fields=["offre", "stockage_go", "stockage_alerte", "abonnement_fin",
                                             "abonnement_prix_mois", "abonnement_alerte"])


def premiere_periode(org, paiement_abonnement) -> None:
    """Espace créé après le paiement de l'inscription : la période commence le jour du paiement."""
    debut = timezone.localdate(paiement_abonnement.paye_le) if paiement_abonnement.paye_le else aujourd_hui()
    org.abonnement_fin = ajouter_mois(debut, paiement_abonnement.mois)
    org.abonnement_prix_mois = paiement_abonnement.montant // max(1, paiement_abonnement.mois)
    org.save(using="central", update_fields=["abonnement_fin", "abonnement_prix_mois"])


def periode_essai(org) -> None:
    """Espace d'essai créé : gratuit pendant 1 mois à partir d'aujourd'hui."""
    org.abonnement_fin = ajouter_mois(aujourd_hui(), DUREE_ESSAI)
    org.abonnement_prix_mois = 0
    org.save(using="central", update_fields=["abonnement_fin", "abonnement_prix_mois"])


ALERTES_ESSAI = {
    1: ("Votre essai gratuit se termine bientôt",
        "L'essai gratuit de votre organisation se termine le {fin}. Choisissez une offre depuis la page Abonnement pour "
        "continuer sans interruption : vos données sont conservées."),
    3: ("Votre essai gratuit est terminé",
        "L'essai gratuit de votre organisation est terminé : l'accès est bloqué. Vos données sont conservées 60 jours, "
        "puis supprimées : choisissez une offre depuis la page Abonnement pour continuer."),
}

ALERTES = {
    1: ("Votre abonnement se termine bientôt",
        "L'abonnement de votre organisation se termine le {fin}. Renouvelez-le depuis la page Abonnement pour continuer sans interruption."),
    2: ("Votre abonnement est terminé",
        "L'abonnement de votre organisation s'est terminé le {fin}. Vous gardez l'accès jusqu'au {grace} : renouvelez-le "
        "depuis la page Abonnement, sinon l'accès sera bloqué."),
    3: ("Accès à la plateforme bloqué",
        "L'abonnement de votre organisation n'a pas été renouvelé : l'accès est bloqué. Il est rétabli dès le paiement, "
        "depuis la page Abonnement."),
}


def alerter(org=None) -> None:
    """Toutes les heures (check_deadlines, dans l'espace de l'organisation) : rappels aux administrateurs."""
    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.inscriptions import _envoyer
    from apps.notifications.models import Notification
    from apps.notifications.services import notifier_par_role

    from . import contexte
    from .models import Organisation

    org = org or contexte.courante()
    org = Organisation.objects.using("central").filter(pk=org.pk).first() if org else None
    if org is None or org.abonnement_fin is None:
        return
    statut = etat(org)["statut"]
    niveau = {"BIENTOT": 1, "GRACE": 2, "BLOQUE": 3}.get(statut, 0)
    if niveau <= org.abonnement_alerte:
        return
    Organisation.objects.using("central").filter(pk=org.pk).update(abonnement_alerte=niveau)
    essai = org.offre == ESSAI
    titre, message = (ALERTES_ESSAI if essai else ALERTES)[niveau]
    message = message.format(fin=org.abonnement_fin.strftime("%d/%m/%Y"),
                             grace=(org.abonnement_fin + timedelta(days=GRACE)).strftime("%d/%m/%Y"))
    notifier_par_role([ROLE_ADMIN], Notification.Type.ABONNEMENT, titre, message, lien="/mon-abonnement")
    if niveau == 3 and essai:
        _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"Essai gratuit terminé : {org.nom}",
                 f"Organisation : {org.nom} ({org.sous_domaine})\nFin de l'essai : {org.abonnement_fin:%d/%m/%Y}\n"
                 "L'accès est bloqué jusqu'au choix d'une offre payante (page Abonnement de l'organisation).")
    elif niveau == 3:
        _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"Accès bloqué (abonnement non renouvelé) : {org.nom}",
                 f"Organisation : {org.nom} ({org.sous_domaine})\nFin de l'abonnement : {org.abonnement_fin:%d/%m/%Y}\n"
                 "L'accès est bloqué jusqu'au paiement (page Abonnement de l'organisation), ou jusqu'à ce que la date "
                 "soit changée dans la console.")
