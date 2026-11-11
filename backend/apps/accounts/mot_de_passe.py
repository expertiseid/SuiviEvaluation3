"""
Mot de passe oublié : depuis la page de connexion, on donne son adresse courriel ; un lien pour choisir un
nouveau mot de passe y est envoyé.

- La réponse est toujours la même (« si un compte existe… ») : la page ne révèle pas quelles adresses ont un compte.
- Le lien est valable 1 heure (PASSWORD_RESET_TIMEOUT) et ne sert qu'une fois : le jeton (jeton de Django)
  dépend du mot de passe actuel, il ne vaut plus rien dès que celui-ci a changé.
- Plateforme multi-organisations : l'index des comptes dit dans quel espace chercher le compte ; le lien porte
  le sous-domaine de l'organisation (« sous-domaine~uid.jeton »), comme le jeton d'étape de double_auth.
- Le nouveau mot de passe ne suffit pas pour entrer : la connexion demande toujours le code envoyé par courriel.
- Demandes et changements : au journal d'audit (jamais le lien ni le mot de passe).
"""
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as ErreurDjango
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import ValidationError

from apps.core.audit import A, auditer
from apps.core.vocabulaire import v
from apps.organisations import contexte

LIEN_INVALIDE = "Ce lien n'est plus valable : il a déjà servi ou a expiré. Demandez-en un nouveau."


def _compte(courriel):
    """Compte actif portant cette adresse, dans l'espace courant."""
    from .models import User

    return User.objects.filter(email__iexact=courriel, is_active=True).first()


def demander(courriel, langue=""):
    """Envoie le lien si un compte actif porte cette adresse ; ne dit jamais s'il existe."""
    from apps.core.courriel import adresse_fictive

    courriel = (courriel or "").strip()
    if "@" not in courriel or adresse_fictive(courriel):
        return
    if not contexte.actif():
        utilisateur = _compte(courriel)
        if utilisateur is not None:
            _envoyer(utilisateur, "", langue)
        return
    from apps.organisations import comptes
    from apps.organisations.models import Organisation

    org = comptes.organisation_du_courriel(courriel)
    if org is None or org.statut != Organisation.Statut.ACTIVE:
        return
    with contexte.dans_organisation(org):
        utilisateur = _compte(courriel)
        if utilisateur is not None:
            _envoyer(utilisateur, f"{org.sous_domaine}~", langue)


def _envoyer(utilisateur, prefixe, langue):
    from apps.core.langues import en_langue

    jeton = f"{prefixe}{urlsafe_base64_encode(force_bytes(utilisateur.pk))}.{default_token_generator.make_token(utilisateur)}"
    lien = f"{settings.PLAINTES_URL_PUBLIQUE.rstrip('/')}/nouveau-mot-de-passe?jeton={jeton}"
    with en_langue(utilisateur.langue or langue or "fr"):
        sujet = v("Choisir un nouveau mot de passe — Expertise-ID Monitora")
        texte = (v("Bonjour,\n\nVous avez demandé à changer le mot de passe de votre compte sur la plateforme "
                   "Expertise-ID Monitora. Pour en choisir un nouveau, ouvrez ce lien (valable 1 heure, une seule fois) :")
                 + f"\n\n{lien}\n\n"
                 + v("Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : votre mot de passe reste inchangé."))
    try:
        send_mail(sujet, texte, getattr(settings, "DEFAULT_FROM_EMAIL", None), [utilisateur.email], fail_silently=False)
        auditer(utilisateur, A.MOT_DE_PASSE, utilisateur.username, module="comptes", operation="lien_envoye")
    except Exception as erreur:  # serveur de courriel injoignable : la réponse reste la même
        auditer(utilisateur, A.MOT_DE_PASSE, utilisateur.username, module="comptes", operation="envoi_impossible",
                erreur=type(erreur).__name__)


@contextmanager
def _espace_du_lien(jeton):
    """Se place dans l'espace de l'organisation du lien ; rend « uid.jeton »."""
    from apps.organisations.models import Organisation

    sous_domaine, separateur, reste = (jeton or "").partition("~")
    if not separateur:
        if contexte.actif():
            raise ValidationError({"detail": v(LIEN_INVALIDE)})
        yield jeton or ""
        return
    org = Organisation.objects.using("central").filter(sous_domaine=sous_domaine, statut=Organisation.Statut.ACTIVE).first()
    if org is None or not contexte.actif():
        raise ValidationError({"detail": v(LIEN_INVALIDE)})
    with contexte.dans_organisation(org):
        yield reste


def _utilisateur(jeton):
    from .models import User

    uid, _, signature = jeton.partition(".")
    try:
        pk = int(force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError):
        pk = None
    utilisateur = User.objects.filter(pk=pk, is_active=True).first() if pk else None
    if utilisateur is None or not default_token_generator.check_token(utilisateur, signature):
        raise ValidationError({"detail": v(LIEN_INVALIDE)})
    return utilisateur


def verifier(jeton):
    """Lien encore valable ? Rend l'adresse (masquée) du compte, pour la page."""
    from .double_auth import adresse_masquee

    with _espace_du_lien(jeton) as reste:
        return {"compte": adresse_masquee(_utilisateur(reste).email)}


def changer(jeton, mot_de_passe):
    with _espace_du_lien(jeton) as reste:
        utilisateur = _utilisateur(reste)
        try:
            validate_password(mot_de_passe or "", utilisateur)
        except ErreurDjango as erreur:
            raise ValidationError({"mot_de_passe": list(erreur.messages)})
        utilisateur.set_password(mot_de_passe)
        utilisateur.save(update_fields=["password"])
        auditer(utilisateur, A.MOT_DE_PASSE, utilisateur.username, module="comptes", operation="change")
