"""
Paiement en ligne de l'abonnement (CinetPay) : l'organisation choisit son offre et paie, et son espace est
créé aussitôt, sans validation d'Expertise-ID. Expertise-ID reçoit un courriel « … s'est inscrite » et
peut suspendre l'espace depuis la console.

1. creer() : enregistre le paiement et demande à CinetPay un lien vers sa page de paiement ;
2. CinetPay prévient la plateforme (notifier()) et ramène l'organisation sur le site (etat()) ;
3. verifier() : le statut est toujours redemandé à CinetPay, jamais cru sur parole ; payé, l'espace est
   créé (activation.lancer) une seule fois, même si la notification et le retour arrivent ensemble.

L'offre Partenariat ne se paie pas en ligne : elle reste transmise à Expertise-ID (inscriptions.choisir_offre).

Stockage supplémentaire (page Stockage de la plateforme) : même parcours (creer_stockage), par tranches de
10 Go ; payé, l'espace de stockage de l'organisation est agrandi aussitôt (quota.py), sans action humaine.
"""
import hmac
import logging
import secrets

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.vocabulaire import v

from . import quota
from .models import Organisation, PaiementAbonnement

logger = logging.getLogger(__name__)

OFFRES_PAYANTES = ("STANDARD_25", "STANDARD_50", "STANDARD", "STOCKAGE_PLUS")
DUREES = (1, 3, 6, 12, 24, 36)  # mois : 1, 3 ou 6 mois, 1, 2 ou 3 ans
# Formation gratuite à partir de cette durée (mois) : 2 ans pour les offres de moins de 50 000 FCFA
# (Standard 25 Go et 50 Go), 1 an pour l'offre Standard (100 Go).
FORMATION = {"STANDARD_25": 24, "STANDARD_50": 24, "STANDARD": 12, "STOCKAGE_PLUS": 12}
TRANCHES_MAX = 20
CLE_JETON = "cinetpay_jeton"


class ErreurCinetPay(Exception):
    pass


def actif() -> bool:
    return bool(settings.CINETPAY_API_KEY and settings.CINETPAY_API_PASSWORD)


def prix_mois(offre: str, usd=False) -> int:
    """Prix d'un mois de l'offre (Standard + stockage : celui de Standard, plus les tranches)."""
    if offre == "STANDARD_25":
        return settings.ABONNEMENT_PRIX_25GO_USD if usd else settings.ABONNEMENT_PRIX_25GO
    if offre == "STANDARD_50":
        return settings.ABONNEMENT_PRIX_50GO_USD if usd else settings.ABONNEMENT_PRIX_50GO
    return settings.ABONNEMENT_PRIX_MOIS_USD if usd else settings.ABONNEMENT_PRIX_MOIS


def formation_offerte(offre: str, mois: int) -> bool:
    return offre in FORMATION and mois >= FORMATION[offre]


def tarifs() -> dict:
    """Mobile money (FCFA, payé en ligne) ; « usd » : prix affichés et payés par carte bancaire ; « offres » : prix
    d'un mois de chaque offre (FCFA et dollars)."""
    return {"paiement": actif(), "devise": settings.ABONNEMENT_DEVISE, "mois": settings.ABONNEMENT_PRIX_MOIS,
            "tranche": settings.ABONNEMENT_PRIX_TRANCHE, "durees": list(DUREES), "tranches_max": TRANCHES_MAX,
            "usd": {"mois": settings.ABONNEMENT_PRIX_MOIS_USD, "tranche": settings.ABONNEMENT_PRIX_TRANCHE_USD},
            "offres": {o: {"mois": prix_mois(o), "usd": prix_mois(o, usd=True)} for o in OFFRES_PAYANTES},
            "formation": FORMATION}


def montant(offre: str, mois: int, tranches: int, usd=False) -> int:
    tranche = settings.ABONNEMENT_PRIX_TRANCHE_USD if usd else settings.ABONNEMENT_PRIX_TRANCHE
    return mois * (prix_mois(offre, usd) + (tranches if offre == "STOCKAGE_PLUS" else 0) * tranche)


# --- API de CinetPay -------------------------------------------------------------------------------

def _adresse_api() -> str:
    # Clé de test : bac à sable (aucun argent réel).
    return "https://api.cinetpay.net" if settings.CINETPAY_API_KEY.startswith("sk_test_") else "https://api.cinetpay.co"


def _appel(methode, chemin, corps=None, jeton=None):
    # Sans « User-Agent », le pare-feu de CinetPay refuse la requête.
    entetes = {"User-Agent": "Expertise-ID-Monitora", "Accept": "application/json"}
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    try:
        reponse = requests.request(methode, _adresse_api() + chemin, json=corps, headers=entetes, timeout=20)
        donnees = reponse.json()
    except (requests.RequestException, ValueError) as erreur:
        raise ErreurCinetPay(f"CinetPay injoignable : {type(erreur).__name__}") from erreur
    if reponse.status_code >= 400 or donnees.get("code") not in (100, 200, 2001, 2002, 2010):
        raise ErreurCinetPay(f"CinetPay : {donnees.get('code')} {donnees.get('status')} {donnees.get('description') or ''}".strip())
    return donnees


def _jeton(nouveau=False) -> str:
    jeton = None if nouveau else cache.get(CLE_JETON)
    if not jeton:
        donnees = _appel("POST", "/v1/oauth/login", {"api_key": settings.CINETPAY_API_KEY,
                                                    "api_password": settings.CINETPAY_API_PASSWORD})
        jeton = donnees.get("access_token") or ""
        if not jeton:
            raise ErreurCinetPay("CinetPay : connexion refusée.")
        cache.set(CLE_JETON, jeton, max(60, int(donnees.get("expires_in") or 3600) - 600))
    return jeton


def _appel_connecte(methode, chemin, corps=None):
    try:
        return _appel(methode, chemin, corps, _jeton())
    except ErreurCinetPay as erreur:
        if "EXPIRED_TOKEN" not in str(erreur) and "INVALID_TOKEN" not in str(erreur):
            raise
        return _appel(methode, chemin, corps, _jeton(nouveau=True))


# --- Parcours ---------------------------------------------------------------------------------------

def creer(demande, offre, mois=1, tranches=0, message="", langue="fr") -> PaiementAbonnement:
    """Paiement de l'offre choisie ; renvoie le paiement, dont le lien vers la page de CinetPay (lien)."""
    from apps.accounts.models import DemandeInscription

    if not actif():
        raise ValidationError({"detail": v("Le paiement en ligne n'est pas disponible : contactez Expertise-ID.")})
    if offre not in OFFRES_PAYANTES:
        raise ValidationError({"offre": v("Choisissez une offre.")})
    if demande.statut in (DemandeInscription.Statut.EN_ACTIVATION, DemandeInscription.Statut.ACTIVEE):
        raise ValidationError({"detail": v("L'abonnement de cette organisation est déjà actif : connectez-vous.")})
    try:
        mois, tranches = int(mois), int(tranches or 0)
    except (TypeError, ValueError):
        raise ValidationError({"detail": v("Durée ou stockage invalide.")})
    if mois not in DUREES or not 0 <= tranches <= TRANCHES_MAX or (offre == "STOCKAGE_PLUS" and tranches < 1):
        raise ValidationError({"detail": v("Durée ou stockage invalide.")})
    if offre != "STOCKAGE_PLUS":
        tranches = 0
    if message.strip():
        demande.message = (demande.message + "\n" + message.strip()).strip()[:2000]
        demande.save(update_fields=["message"])

    paiement = PaiementAbonnement.objects.using("central").create(
        demande=demande, reference=f"M{demande.pk}{secrets.token_hex(8).upper()}"[:30], offre=offre, mois=mois,
        tranches=tranches, montant=montant(offre, mois, tranches), devise=settings.ABONNEMENT_DEVISE,
    )
    prenom, _, nom = demande.contact_nom.strip().partition(" ")
    retour = f"{settings.URL_SITE.rstrip('/')}/inscription.html?paiement={paiement.reference}"
    designation = f"Abonnement {dict(DemandeInscription.Offre.choices)[offre]} - {mois} mois"
    if tranches:
        designation += f" + {tranches * 10} Go"
    return _demander_lien(paiement, designation, demande.courriel, prenom, nom or demande.organisation, retour, langue)


def _demander_lien(paiement, designation, courriel, prenom, nom, retour, langue):
    """Demande à CinetPay la page de paiement ; renvoie le paiement, dont le lien (paiement.lien)."""
    try:
        donnees = _appel_connecte("POST", "/v1/payment", {
            "currency": paiement.devise, "merchant_transaction_id": paiement.reference, "amount": paiement.montant,
            "lang": "en" if langue == "en" else "fr", "designation": designation, "client_email": courriel,
            "client_first_name": (prenom or "-").ljust(2, "-")[:255], "client_last_name": (nom or "-").ljust(2, "-")[:255],
            "success_url": retour, "failed_url": retour,
            "notify_url": f"{settings.PLAINTES_URL_PUBLIQUE.rstrip('/')}/api/v1/public/inscription/paiement/notification/",
            "channel": "PUSH",
        })
    except ErreurCinetPay:
        logger.exception("Paiement %s : création refusée par CinetPay.", paiement.reference)
        paiement.statut = PaiementAbonnement.Statut.ECHOUE
        paiement.save(using="central", update_fields=["statut"])
        raise ValidationError({"detail": v("Le paiement n'a pas pu être préparé. Réessayez dans un moment.")})
    paiement.jeton_paiement = donnees.get("payment_token") or ""
    paiement.jeton_notification = donnees.get("notify_token") or ""
    paiement.transaction = donnees.get("transaction_id") or ""
    paiement.save(using="central", update_fields=["jeton_paiement", "jeton_notification", "transaction"])
    paiement.lien = donnees.get("payment_url") or ""
    if not paiement.lien:
        raise ValidationError({"detail": v("Le paiement n'a pas pu être préparé. Réessayez dans un moment.")})
    return paiement


def verifier(paiement) -> PaiementAbonnement:
    """Redemande le statut à CinetPay ; payé, valide l'abonnement (une seule fois)."""
    if paiement.statut != PaiementAbonnement.Statut.EN_ATTENTE:
        return paiement
    try:
        donnees = _appel_connecte("GET", f"/v1/payment/{paiement.reference}")
    except ErreurCinetPay:
        logger.warning("Paiement %s : statut indisponible.", paiement.reference, exc_info=True)
        return paiement
    statut = donnees.get("status")
    if statut == "SUCCESS":
        return _valider(paiement, donnees.get("transaction_id") or paiement.transaction)
    if statut in ("FAILED", "EXPIRED"):
        PaiementAbonnement.objects.using("central").filter(pk=paiement.pk, statut=PaiementAbonnement.Statut.EN_ATTENTE).update(
            statut=PaiementAbonnement.Statut.ECHOUE)
        paiement.refresh_from_db(using="central")
    return paiement


def _valider(paiement, transaction_cinetpay) -> PaiementAbonnement:
    if paiement.nature == PaiementAbonnement.Nature.STOCKAGE:
        return _valider_stockage(paiement, transaction_cinetpay)
    from apps.accounts import inscriptions
    from apps.accounts.models import DemandeInscription

    from . import activation, contexte

    with transaction.atomic(using="central"):
        paiement = PaiementAbonnement.objects.using("central").select_for_update().get(pk=paiement.pk)
        if paiement.statut == PaiementAbonnement.Statut.PAYE:
            return paiement
        paiement.statut = PaiementAbonnement.Statut.PAYE
        paiement.paye_le = timezone.now()
        paiement.transaction = transaction_cinetpay
        paiement.save(using="central", update_fields=["statut", "paye_le", "transaction"])
        demande = DemandeInscription.objects.using("central").select_for_update().get(pk=paiement.demande_id)
        demande.offre = paiement.offre
        if demande.statut in (DemandeInscription.Statut.ABONNEMENT_REQUIS, DemandeInscription.Statut.OFFRE_CHOISIE):
            demande.statut = DemandeInscription.Statut.OFFRE_CHOISIE
        demande.save(using="central", update_fields=["offre", "statut"])

    espace = contexte.actif() and demande.statut == DemandeInscription.Statut.OFFRE_CHOISIE
    if espace:
        activation.lancer(demande)
    stockage = f" + {paiement.tranches * 10} Go" if paiement.tranches else ""
    inscriptions.prevenir_expertise_id(demande, "Nouvelle inscription", [
        f"Paiement reçu : {paiement.montant:,} {paiement.devise}".replace(",", " ")
        + f" ({paiement.mois} mois{stockage}) · référence {paiement.reference} · transaction {paiement.transaction}",
        f"Formation gratuite : {'oui' if formation_offerte(paiement.offre, paiement.mois) else 'non'}.",
        "L'espace est créé automatiquement. Pour le suspendre : console Expertise-ID, Organisations." if espace
        else "Espace à activer depuis la console Expertise-ID.",
    ])
    return paiement


def notifier(donnees) -> None:
    """Notification de CinetPay : son jeton doit être celui reçu à la création ; le statut est redemandé."""
    reference = str(donnees.get("merchant_transaction_id") or "")[:30]
    recu = str(donnees.get("notify_token") or "")
    paiement = PaiementAbonnement.objects.using("central").filter(reference=reference).first() if reference else None
    if paiement is None or not paiement.jeton_notification or not hmac.compare_digest(paiement.jeton_notification, recu):
        logger.warning("Notification de paiement refusée (référence %r).", reference)
        return
    verifier(paiement)


def etat(reference) -> dict:
    """Retour sur le site après le paiement : statut (redemandé à CinetPay s'il est encore en attente)."""
    paiement = PaiementAbonnement.objects.using("central").select_related("demande").filter(
        reference=str(reference or "")[:30], nature=PaiementAbonnement.Nature.ABONNEMENT).first()
    if paiement is None:
        raise ValidationError({"detail": v("Paiement introuvable.")})
    paiement = verifier(paiement)
    return {"statut": paiement.statut, "organisation": paiement.demande.organisation, "courriel": paiement.demande.courriel,
            "montant": paiement.montant, "devise": paiement.devise}


# --- Stockage supplémentaire ------------------------------------------------------------------------

def montant_stockage(tranches: int, mois: int, usd=False) -> int:
    return mois * tranches * (settings.ABONNEMENT_PRIX_TRANCHE_USD if usd else settings.ABONNEMENT_PRIX_TRANCHE)


def _lire_achat(tranches, mois):
    try:
        tranches, mois = int(tranches), int(mois)
    except (TypeError, ValueError):
        raise ValidationError({"detail": v("Durée ou stockage invalide.")})
    if mois not in DUREES or not 1 <= tranches <= TRANCHES_MAX:
        raise ValidationError({"detail": v("Durée ou stockage invalide.")})
    return tranches, mois


def creer_stockage(org, utilisateur, tranches, mois, langue="fr") -> PaiementAbonnement:
    """Paiement de `tranches` × 10 Go pendant `mois` mois ; renvoie le paiement, dont le lien vers CinetPay."""
    if not actif():
        raise ValidationError({"detail": v("Le paiement en ligne n'est pas disponible : contactez Expertise-ID.")})
    tranches, mois = _lire_achat(tranches, mois)
    paiement = PaiementAbonnement.objects.using("central").create(
        nature=PaiementAbonnement.Nature.STOCKAGE, organisation=org, payeur=utilisateur.email or "",
        reference=f"S{org.pk}{secrets.token_hex(8).upper()}"[:30], offre=org.offre or "", mois=mois, tranches=tranches,
        montant=montant_stockage(tranches, mois), devise=settings.ABONNEMENT_DEVISE,
    )
    retour = f"{settings.PLAINTES_URL_PUBLIQUE.rstrip('/')}/stockage?paiement={paiement.reference}"
    return _demander_lien(paiement, f"Stockage + {tranches * 10} Go - {mois} mois", utilisateur.email or org.courriel_contact,
                          utilisateur.first_name or utilisateur.username, utilisateur.last_name or org.nom, retour, langue)


def _valider_stockage(paiement, transaction_cinetpay) -> PaiementAbonnement:
    """Payé : l'espace de l'organisation grandit aussitôt de tranches × 10 Go (une seule fois)."""
    from apps.accounts.inscriptions import _envoyer

    with transaction.atomic(using="central"):
        paiement = PaiementAbonnement.objects.using("central").select_for_update().get(pk=paiement.pk)
        if paiement.statut == PaiementAbonnement.Statut.PAYE:
            return paiement
        paiement.statut = PaiementAbonnement.Statut.PAYE
        paiement.paye_le = timezone.now()
        paiement.transaction = transaction_cinetpay
        paiement.save(using="central", update_fields=["statut", "paye_le", "transaction"])
        org = Organisation.objects.using("central").select_for_update().get(pk=paiement.organisation_id)
        avant = quota.limite_go(org) or 0
        org.stockage_go = avant + paiement.tranches * 10
        org.stockage_alerte = 0  # espace agrandi : alertes à nouveau possibles
        org.save(using="central", update_fields=["stockage_go", "stockage_alerte"])
    _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"Stockage ajouté : {org.nom}", "\n".join([
        f"Organisation : {org.nom} ({org.sous_domaine})",
        f"Payé par : {paiement.payeur or '—'}",
        f"Stockage : + {paiement.tranches * 10} Go pendant {paiement.mois} mois · espace passé de {avant} à {org.stockage_go} Go",
        f"Paiement reçu : {paiement.montant:,} {paiement.devise}".replace(",", " ")
        + f" · référence {paiement.reference} · transaction {paiement.transaction}",
        "L'espace a été agrandi automatiquement.",
    ]))
    return paiement


def stockage_par_carte(org, utilisateur, tranches, mois):
    """Carte bancaire : pas de paiement en ligne ; Expertise-ID reçoit la demande (montant en dollars) et finalise."""
    from apps.accounts.inscriptions import _envoyer

    tranches, mois = _lire_achat(tranches, mois)
    _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"Stockage par carte demandé : {org.nom}", "\n".join([
        f"Organisation : {org.nom} ({org.sous_domaine})",
        f"Demandé par : {utilisateur.get_full_name() or utilisateur.username} · {utilisateur.email or '—'}",
        f"Stockage : + {tranches * 10} Go pendant {mois} mois · espace actuel {quota.limite_go(org) or '—'} Go",
        f"Montant : {montant_stockage(tranches, mois, usd=True)} $ HT (à régler par carte bancaire)",
        "Après le paiement : console Expertise-ID, Organisations, colonne Stockage.",
    ]))


def etat_stockage(org, reference) -> dict:
    """Retour sur la page Stockage après le paiement : statut (redemandé à CinetPay s'il est encore en attente)."""
    paiement = PaiementAbonnement.objects.using("central").filter(
        reference=str(reference or "")[:30], organisation=org, nature=PaiementAbonnement.Nature.STOCKAGE).first()
    if paiement is None:
        raise ValidationError({"detail": v("Paiement introuvable.")})
    paiement = verifier(paiement)
    return {"statut": paiement.statut, "tranches": paiement.tranches, "mois": paiement.mois,
            "montant": paiement.montant, "devise": paiement.devise}


def achats_stockage(org) -> list:
    return [{"date": p.paye_le, "tranches": p.tranches, "mois": p.mois, "montant": p.montant, "devise": p.devise}
            for p in PaiementAbonnement.objects.using("central").filter(
                organisation=org, nature=PaiementAbonnement.Nature.STOCKAGE, statut=PaiementAbonnement.Statut.PAYE
            ).order_by("-paye_le")[:50]]
