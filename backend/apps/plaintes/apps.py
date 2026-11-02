from django.apps import AppConfig
from django.core.checks import Warning, register


class PlaintesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.plaintes"
    label = "plaintes"
    verbose_name = "Plaintes et retours"

    def ready(self):
        register(verifier_cle_chiffrement)
        from . import pieces  # noqa: F401  (effacement des fichiers des pièces supprimées)


def verifier_cle_chiffrement(app_configs, **kwargs):
    """En production, les données protégées doivent être chiffrées avec une clé propre (hors du code)."""
    from django.conf import settings

    from .chiffrement import cles_configurees

    if settings.DEBUG or cles_configurees():
        return []
    return [Warning(
        "PLAINTES_CLE_CHIFFREMENT n'est pas définie : les données protégées des plaintes sont chiffrées avec une "
        "clé dérivée de DJANGO_SECRET_KEY.",
        hint="Générez une clé Fernet et définissez PLAINTES_CLE_CHIFFREMENT (voir apps/plaintes/chiffrement.py).",
        id="plaintes.W001",
    )]
