"""
Contrôle « Je ne suis pas un robot » (Google reCAPTCHA v2, case à cocher) du formulaire d'inscription.

Actif seulement si les deux clés sont réglées (RECAPTCHA_CLE_SITE, RECAPTCHA_CLE_SECRETE, à créer sur
https://www.google.com/recaptcha/admin pour le domaine du site) ; sinon, le champ piège et la limite
d'envois par adresse restent les seules protections.
"""
import json
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework.exceptions import ValidationError

VERIFICATION = "https://www.google.com/recaptcha/api/siteverify"


def cle_site() -> str:
    return getattr(settings, "RECAPTCHA_CLE_SITE", "") if actif() else ""


def actif() -> bool:
    return bool(getattr(settings, "RECAPTCHA_CLE_SITE", "") and getattr(settings, "RECAPTCHA_CLE_SECRETE", ""))


def verifier(jeton, adresse_ip=None):
    """Refuse l'envoi si la case n'a pas été cochée ou si Google ne confirme pas."""
    if not actif():
        return
    if not jeton:
        raise ValidationError({"detail": "Cochez la case « Je ne suis pas un robot »."})
    donnees = {"secret": settings.RECAPTCHA_CLE_SECRETE, "response": str(jeton)}
    if adresse_ip:
        donnees["remoteip"] = adresse_ip
    try:
        with urllib.request.urlopen(VERIFICATION, urllib.parse.urlencode(donnees).encode(), timeout=8) as reponse:
            resultat = json.loads(reponse.read())
    except (OSError, ValueError):
        raise ValidationError({"detail": "Le contrôle anti-robot n'a pas pu être vérifié. Réessayez dans un instant."})
    if not resultat.get("success"):
        raise ValidationError({"detail": "Le contrôle anti-robot a expiré ou n'est pas valide : cochez de nouveau la case."})
