"""
Couches cartographiques intégrées à la plateforme (limites des régions, provinces, communes ; villes et
villages) : leur utilisation dépend des droits accordés par leurs producteurs. Pour les clients, la carte
s'ouvre donc sur une simple carte du monde, et chaque organisation importe ses propres couches (SHP,
GeoPackage…) avec « Importer une couche ».

Activées seulement sur un poste de développement (CARTE_COUCHES_INTEGREES) et pour la démonstration.
"""
from django.conf import settings


def couches_integrees() -> bool:
    if getattr(settings, "CARTE_COUCHES_INTEGREES", False):
        return True
    from apps.organisations import contexte

    org = contexte.courante()
    if org is not None and getattr(org, "mode_demo", False):
        return True
    from apps.accounts.demo import actif

    return bool(actif())


MESSAGE = "Couches cartographiques intégrées non disponibles : importez vos propres couches (SHP, GeoPackage…)."
