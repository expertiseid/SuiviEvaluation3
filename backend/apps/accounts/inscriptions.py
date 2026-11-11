"""
Inscription d'une organisation depuis la page d'accueil, puis abonnement.

Le profil créé ne donne aucun accès : la page « Vous devez vous abonner avant de continuer » s'affiche
juste après, et à chaque tentative de connexion avec l'identifiant choisi tant que l'abonnement n'est pas
actif. L'offre payée en ligne (apps.organisations.paiement) crée l'espace aussitôt ; Expertise-ID
(COURRIEL_ABONNEMENTS) reçoit alors un seul courriel « Nouvelle inscription ». L'offre Partenariat, qui ne se
paie pas en ligne, lui est transmise pour qu'il la traite. L'organisation reçoit un accusé. Envois limités
par connexion, champ piège.
"""
import logging

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as ErreurDjango
from django.core.mail import send_mail
from rest_framework.exceptions import ValidationError

from apps.core.vocabulaire import v

from .models import DemandeInscription, User

logger = logging.getLogger(__name__)

SEL = "inscription"
# L'adresse courriel sert d'identifiant de connexion (plateforme à adresse unique : courriel + mot de passe).
OBLIGATOIRES = ("organisation", "type_organisation", "pays", "contact_nom", "courriel", "telephone", "mot_de_passe")


def jeton(demande) -> str:
    return signing.dumps({"d": demande.pk}, salt=SEL)


def demande_du_jeton(valeur):
    try:
        contenu = signing.loads(valeur or "", salt=SEL, max_age=30 * 24 * 3600)
    except signing.BadSignature:
        raise ValidationError({"detail": v("Lien expiré : reconnectez-vous avec votre identifiant.")})
    demande = DemandeInscription.objects.filter(pk=contenu.get("d")).first()
    if demande is None:
        raise ValidationError({"detail": v("Lien expiré : reconnectez-vous avec votre identifiant.")})
    return demande


def _texte(donnees, champ, longueur):
    return (donnees.get(champ) or "").strip()[:longueur]


def creer(donnees):
    from apps.core.courriel import adresse_fictive

    erreurs = {c: v("Champ obligatoire.") for c in OBLIGATOIRES if not (donnees.get(c) or "").strip()}
    courriel = _texte(donnees, "courriel", 254)
    if courriel and ("@" not in courriel or adresse_fictive(courriel)):
        erreurs["courriel"] = v("Indiquez une adresse courriel valide : le code de connexion y sera envoyé.")
    identifiant = _texte(donnees, "identifiant", 150) or courriel
    from apps.organisations import comptes, contexte

    deja = (User.objects.filter(username__iexact=identifiant).exists()
            or DemandeInscription.objects.filter(identifiant__iexact=identifiant).exclude(statut=DemandeInscription.Statut.REFUSEE).exists()
            or (contexte.actif() and comptes.courriel_pris(courriel)))
    if identifiant and deja:
        erreurs["courriel" if identifiant == courriel else "identifiant"] = v(
            "Cette adresse courriel est déjà utilisée : connectez-vous, ou utilisez une autre adresse.")
    mot_de_passe = donnees.get("mot_de_passe") or ""
    if mot_de_passe:
        try:
            validate_password(mot_de_passe)
        except ErreurDjango as erreur:
            erreurs["mot_de_passe"] = " ".join(erreur.messages)
    # Identifiant interne de l'espace (nom de sa base) : tiré du nom de l'organisation, jamais demandé.
    sous_domaine = identifiant_espace(_texte(donnees, "organisation", 200)) if contexte.actif() else ""
    if donnees.get("conditions") is not True:
        erreurs["conditions"] = v("Votre accord est nécessaire pour créer le profil.")
    if erreurs:
        raise ValidationError(erreurs)
    demande = DemandeInscription.objects.create(
        organisation=_texte(donnees, "organisation", 200), type_organisation=_texte(donnees, "type_organisation", 60),
        pays=_texte(donnees, "pays", 80), secteur=_texte(donnees, "secteur", 120), taille=_texte(donnees, "taille", 40),
        contact_nom=_texte(donnees, "contact_nom", 200), contact_fonction=_texte(donnees, "contact_fonction", 120),
        courriel=courriel, telephone=_texte(donnees, "telephone", 40), identifiant=identifiant,
        mot_de_passe=make_password(mot_de_passe), message=_texte(donnees, "message", 2000), sous_domaine=sous_domaine,
    )
    _envoyer_accuse(demande)
    return demande


def identifiant_espace(nom: str) -> str:
    """« ONG Éducation Plus » → « ong-education-plus » (ou « …-2 », « …-3 » s'il est déjà pris)."""
    import re
    import unicodedata

    from apps.organisations.models import FORME, RESERVES, Organisation

    base = unicodedata.normalize("NFD", nom or "").encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:34].strip("-") or "organisation"
    if len(base) < 3:
        base = f"{base}-org"
    candidat, n = base, 2
    while (candidat in RESERVES or not FORME.match(candidat)
           or Organisation.objects.using("central").filter(sous_domaine=candidat).exists()
           or DemandeInscription.objects.filter(sous_domaine=candidat).exists()):
        candidat, n = f"{base}-{n}", n + 1
    return candidat


def _envoyer_accuse(demande):
    _envoyer(demande.courriel, "Votre profil a bien été créé",
             f"Bonjour {demande.contact_nom},\n\nLe profil de {demande.organisation} a bien été créé sur la plateforme "
             "Expertise-ID Monitora (connexion avec votre adresse : " + demande.courriel + ").\n\nPour accéder à la plateforme, "
             "choisissez une offre d'abonnement et réglez-la en ligne : votre espace est créé aussitôt.\n\n"
             "Expertise-ID")


def choisir_offre(demande, offre, message="", moyen="", mois=1, tranches=0):
    """Offre transmise à Expertise-ID : Partenariat, ou offre Standard à payer par carte bancaire (moyen « carte »)."""
    if offre not in DemandeInscription.Offre.values:
        raise ValidationError({"offre": v("Choisissez une offre.")})
    complement = []
    if moyen == "carte" and offre != DemandeInscription.Offre.PARTENARIAT:
        from apps.organisations import paiement

        try:
            mois, tranches = int(mois), (int(tranches or 0) if offre == "STOCKAGE_PLUS" else 0)
        except (TypeError, ValueError):
            raise ValidationError({"detail": v("Durée ou stockage invalide.")})
        if mois not in paiement.DUREES or not 0 <= tranches <= paiement.TRANCHES_MAX:
            raise ValidationError({"detail": v("Durée ou stockage invalide.")})
        stockage = f" + {tranches * 10} Go" if tranches else ""
        complement = [f"Paiement par carte bancaire demandé : {paiement.montant(offre, mois, tranches, usd=True)} $ "
                      f"({mois} mois{stockage}). À finaliser avec le client, puis activer l'espace depuis la console.",
                      f"Formation gratuite : {'oui' if paiement.formation_offerte(offre, mois) else 'non'}."]
    if offre == DemandeInscription.Offre.ESSAI:
        return _commencer_essai(demande)
    demande.offre = offre
    if demande.statut == DemandeInscription.Statut.ABONNEMENT_REQUIS:
        demande.statut = DemandeInscription.Statut.OFFRE_CHOISIE
    if message.strip():
        demande.message = (demande.message + "\n" + message.strip()).strip()[:2000]
    demande.save()
    sujet = "Paiement par carte demandé" if complement else f"Offre {demande.get_offre_display()} choisie"
    prevenir_expertise_id(demande, sujet, complement)
    return demande


def essai_deja_utilise(courriel) -> bool:
    from .models import EssaiGratuit

    return EssaiGratuit.objects.using("central").filter(courriel=(courriel or "").strip().lower()).exists()


def _commencer_essai(demande):
    """Essai gratuit : une fois par adresse courriel ; l'espace est créé aussitôt (1 mois, 100 Mo)."""
    from django.db import IntegrityError

    from apps.organisations import activation, contexte

    from .models import EssaiGratuit

    if not contexte.actif():
        raise ValidationError({"offre": v("L'essai gratuit n'est pas proposé sur cette installation.")})
    if demande.statut not in (DemandeInscription.Statut.ABONNEMENT_REQUIS, DemandeInscription.Statut.OFFRE_CHOISIE):
        raise ValidationError({"offre": v("Une offre est déjà en cours pour ce profil.")})
    erreur = v("Cette adresse courriel a déjà bénéficié de l'essai gratuit d'un mois. Choisissez une offre pour continuer.")
    if essai_deja_utilise(demande.courriel):
        raise ValidationError({"offre": erreur})
    try:
        EssaiGratuit.objects.using("central").create(courriel=demande.courriel.strip().lower(), organisation=demande.organisation)
    except IntegrityError:  # deux demandes en même temps pour la même adresse
        raise ValidationError({"offre": erreur})
    demande.offre = DemandeInscription.Offre.ESSAI
    demande.save(using="central", update_fields=["offre"])
    prevenir_expertise_id(demande, "Essai gratuit commencé", ["Espace créé automatiquement : 1 mois, 100 Mo."])
    activation.lancer(demande)
    return demande


def demande_pour(identifiant, mot_de_passe):
    """Profil créé depuis l'accueil correspondant à ces identifiants (hors demandes refusées), sinon None."""
    from django.db.models import Q

    valeur = (identifiant or "").strip()
    demande = DemandeInscription.objects.filter(Q(identifiant__iexact=valeur) | Q(courriel__iexact=valeur)).exclude(
        statut=DemandeInscription.Statut.REFUSEE).first() if valeur else None
    if demande and check_password(mot_de_passe or "", demande.mot_de_passe):
        return demande
    return None


def resume(demande):
    from apps.organisations import paiement

    return {"reference": jeton(demande), "organisation": demande.organisation, "statut": demande.statut,
            "offre": demande.offre, "contact": (_adresses(getattr(settings, "COURRIEL_ABONNEMENTS", "")) or [""])[0],
            "espace": adresse_connexion(demande), "tarifs": paiement.tarifs()}


def adresse_connexion(demande):
    """Organisation activée (plateforme multi-organisations) : page de connexion, sinon « »."""
    from apps.organisations import contexte

    if not (contexte.actif() and demande.statut == DemandeInscription.Statut.ACTIVEE):
        return ""
    return contexte.adresse() + "/login"


def _adresses(valeur):
    """« a@x.com, b@x.com » → [a@x.com, b@x.com] (COURRIEL_ABONNEMENTS peut prévenir plusieurs personnes)."""
    return [a.strip() for a in (valeur or "").split(",") if a.strip()]


def _envoyer(adresse, sujet, texte):
    destinataires = _adresses(adresse)
    if not destinataires:
        return
    try:
        send_mail(sujet, texte, getattr(settings, "DEFAULT_FROM_EMAIL", None), destinataires)
    except Exception:  # l'inscription ne doit pas échouer pour un courriel ; l'erreur reste dans le journal
        logger.exception("Courriel « %s » non envoyé à %s.", sujet, ", ".join(destinataires))


def prevenir_expertise_id(demande, sujet, complement=()):
    lignes = [
        f"Organisation : {demande.organisation} ({demande.type_organisation}, {demande.pays})",
        f"Secteur : {demande.secteur or '—'} · Taille : {demande.taille or '—'}",
        f"Contact : {demande.contact_nom} ({demande.contact_fonction or '—'})",
        f"Courriel : {demande.courriel} · Téléphone : {demande.telephone}",
        f"Identifiant choisi : {demande.identifiant}",
        f"Offre : {demande.get_offre_display() or 'pas encore choisie'}",
        f"Message : {demande.message or '—'}",
        *complement,
    ]
    _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"{sujet} : {demande.organisation}", "\n".join(lignes))
