"""
Déconnexion après une période d'inactivité (SESSION_INACTIVITE_MIN, 0 = jamais).

- Chaque requête authentifiée note l'heure de la dernière activité du compte dans le cache (clés
  séparées par organisation, apps.organisations.contexte.cle_cache), avec une durée de vie égale à la
  période d'inactivité : sans activité pendant cette période, la clé disparaît.
- Un jeton présenté alors que la clé a disparu est refusé (code « session_inactive ») : l'interface
  ferme la session et renvoie à l'écran de connexion, même si le jeton n'a pas encore expiré.
- La connexion (apps.accounts.double_auth.jetons) note la première activité et écrit la durée dans le
  jeton (marque « inactivite », en minutes) : l'interface y règle son minuteur d'avertissement.
- Une saisie longue sans enregistrement n'est pas une inactivité : l'interface signale l'activité de
  l'utilisateur (clavier, souris) par /auth/activite/.
"""
import time

from django.conf import settings
from django.core.cache import cache

MARQUE = "inactivite"
PREFIXE = "activite:"
# Au plus une écriture dans le cache par minute et par compte.
INTERVALLE_ECRITURE = 60


def minutes() -> int:
    return max(0, int(getattr(settings, "SESSION_INACTIVITE_MIN", 0) or 0))


def _cle(utilisateur) -> str:
    return f"{PREFIXE}{utilisateur.pk}"


def noter(utilisateur, forcer=False):
    """Note l'activité du compte (au plus une fois par minute, sauf à la connexion)."""
    duree = minutes()
    if not duree or utilisateur is None or utilisateur.pk is None:
        return
    maintenant = time.time()
    if not forcer:
        derniere = cache.get(_cle(utilisateur))
        if derniere is not None and maintenant - derniere < INTERVALLE_ECRITURE:
            return
    cache.set(_cle(utilisateur), maintenant, timeout=duree * 60)


def inactif(utilisateur) -> bool:
    """Vrai si le compte n'a eu aucune activité pendant la période d'inactivité."""
    return bool(minutes()) and cache.get(_cle(utilisateur)) is None
