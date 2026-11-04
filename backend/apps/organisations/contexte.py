"""
Plateforme multi-organisations (MULTI_ORGANISATIONS=True) : un seul serveur, une seule adresse, une base
par organisation.

- La base centrale (alias « central », modèles de apps.organisations) tient le registre des organisations
  et l'index des comptes (courriel → organisation), qui permet la connexion par courriel et mot de passe.
- À chaque requête, OrganisationMiddleware retrouve l'organisation (marque « org » du jeton de connexion,
  ou ?org= des pages publiques d'une organisation) et, pour ce fil d'exécution seulement, fait pointer
  la connexion « default » vers SA base : tout l'ORM, les transactions et les requêtes brutes vont à
  cette base, sans rien changer au code des modules. À la fin de la requête, « default » est rétabli.
- dans_organisation(org) fait de même hors requête (commandes, tâche planifiée, tests).
- Hors organisation (connexion, inscription, console, commandes globales, MULTI_ORGANISATIONS=False),
  « default » reste la base centrale : la plateforme se comporte comme une installation unique.
- Ce qui doit rester propre à chaque organisation en dépend aussi : fichiers (stockage.py), clé de
  chiffrement, clés du cache, jetons signés (sel()), jetons de connexion (marque « org »).
"""
import contextvars
from contextlib import contextmanager

from django.conf import settings
from django.db import connections

_courante = contextvars.ContextVar("organisation_courante", default=None)
CENTRALES = {"organisations"}
# Modèles d'autres applications qui appartiennent aussi à la base centrale.
CENTRALES_MODELES = {("accounts", "demandeinscription")}


def est_central(app_label, model_name) -> bool:
    return app_label in CENTRALES or (app_label, model_name) in CENTRALES_MODELES


def actif() -> bool:
    return getattr(settings, "MULTI_ORGANISATIONS", False)


def courante():
    """Organisation de la requête (ou du bloc dans_organisation), sinon None."""
    return _courante.get()


def identifiant() -> str:
    """Sous-domaine de l'organisation courante, « » hors organisation (installation unique)."""
    org = courante()
    return org.sous_domaine if org else ""


def sel(nom: str) -> str:
    """Sel des jetons signés : un jeton émis pour une organisation ne vaut rien chez une autre."""
    org = identifiant()
    return f"{nom}:{org}" if org else nom


def cle_cache(cle, prefixe, version):
    """KEY_FUNCTION du cache : compteurs anti-abus et autres clés séparés par organisation."""
    return f"{prefixe}:{identifiant() or '-'}:{version}:{cle}"


def reglages_base(nom_base: str) -> dict:
    reglages = dict(connections.databases["central"])
    reglages["NAME"] = nom_base
    return reglages


@contextmanager
def dans_organisation(org):
    """Exécute le bloc dans la base de l'organisation (connexion « default » de ce fil uniquement)."""
    from django.db.backends.postgresql.base import DatabaseWrapper

    precedente = connections["default"]
    connexion = DatabaseWrapper(reglages_base(org.base), alias="default")
    jeton = _courante.set(org)
    connections["default"] = connexion
    try:
        yield org
    finally:
        try:
            connexion.close()
        finally:
            connections["default"] = precedente
            _courante.reset(jeton)


def adresse(org=None) -> str:
    """Adresse publique de la plateforme (une seule pour toutes les organisations), sans « / » final."""
    return getattr(settings, "PLAINTES_URL_PUBLIQUE", "").rstrip("/")


def lien_public(chemin: str, org=None) -> str:
    """
    Lien vers une page publique d'une organisation (formulaire ou suivi des plaintes…) : l'adresse de
    la plateforme, plus ?org= pour que la page sache de quelle organisation il s'agit.
    """
    org = org or courante()
    lien = adresse() + chemin
    if actif() and org:
        lien += ("&" if "?" in lien else "?") + f"org={org.sous_domaine}"
    return lien


def parametre_org(org=None) -> str:
    """« org=… » à ajouter aux liens d'API ouverts hors de l'interface (fichiers, logo), sinon « »."""
    org = org or courante()
    return f"org={org.sous_domaine}" if actif() and org else ""


class RouteurOrganisations:
    """Registre des organisations : toujours dans la base centrale ; tout le reste suit « default »."""

    def db_for_read(self, model, **hints):
        # Dans une organisation, « default » est sa base : le registre se lit par la connexion « central ».
        if est_central(model._meta.app_label, model._meta.model_name) and courante() is not None:
            return "central"
        return None

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, **hints):
        if db == "central":
            return False  # même base que « default » hors organisation : migrée une seule fois, par « default »
        if courante() is not None:  # base d'organisation : pas de registre central
            return not est_central(app_label, hints.get("model_name"))
        return True
