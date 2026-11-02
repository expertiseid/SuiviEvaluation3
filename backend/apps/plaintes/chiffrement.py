"""
Chiffrement des données protégées du mécanisme de plaintes (lot 5) : récits, coordonnées des
plaignants, personnes mises en cause, notes, décisions.

La clé est propre à l'installation (donc à l'organisation), gardée hors du code et hors de la base :
variable d'environnement PLAINTES_CLE_CHIFFREMENT (clé Fernet ; plusieurs clés séparées par des
virgules pour une rotation : la première chiffre, toutes déchiffrent). Sans clé définie (poste de
développement), une clé est dérivée de DJANGO_SECRET_KEY — à ne jamais laisser en production
(avertissement au démarrage, voir apps.plaintes.apps).

Générer une clé : python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models

PREFIXE = "chiffre:"


def cles_configurees() -> list[str]:
    return [c.strip() for c in (getattr(settings, "PLAINTES_CLE_CHIFFREMENT", "") or "").split(",") if c.strip()]


@lru_cache(maxsize=1)
def _fernet():
    cles = cles_configurees()
    if not cles:
        derivee = base64.urlsafe_b64encode(hashlib.sha256(("plaintes:" + settings.SECRET_KEY).encode()).digest())
        cles = [derivee.decode()]
    return MultiFernet([Fernet(c.encode()) for c in cles])


def chiffrer(texte: str) -> str:
    if not texte or texte.startswith(PREFIXE):
        return texte
    return PREFIXE + _fernet().encrypt(texte.encode()).decode()


def dechiffrer(valeur: str) -> str:
    if not valeur or not valeur.startswith(PREFIXE):
        return valeur  # vide, ou ancienne donnée en clair (avant chiffrement)
    try:
        return _fernet().decrypt(valeur[len(PREFIXE):].encode()).decode()
    except InvalidToken:
        # Clé perdue ou changée sans rotation : on ne divulgue rien et on ne plante pas l'écran.
        return "[contenu illisible : clé de chiffrement manquante]"


class TexteChiffre(models.TextField):
    """Texte chiffré en base, en clair dans l'application. Le vide reste vide (filtres « sans décision »)."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return chiffrer(value) if isinstance(value, str) else value

    def from_db_value(self, value, expression, connection):
        return dechiffrer(value) if isinstance(value, str) else value

    def to_python(self, value):
        return dechiffrer(value) if isinstance(value, str) else value
