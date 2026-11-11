"""Fichiers téléversés rangés par organisation : MEDIA_ROOT/organisations/<sous-domaine>/…"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from . import contexte, quota


def racine_fichiers(base: str) -> str:
    """Dossier de l'organisation courante sous `base` (inchangé hors organisation)."""
    org = contexte.identifiant()
    return os.path.join(base, "organisations", org) if org else base


class StockageOrganisation(FileSystemStorage):
    """Comme le stockage par défaut, mais à la racine propre à l'organisation de la requête."""

    @property
    def base_location(self):
        return racine_fichiers(str(settings.MEDIA_ROOT))

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def _save(self, name, content):
        # Espace de stockage de l'organisation (quota.py) : refus avant d'écrire s'il serait dépassé.
        taille = getattr(content, "size", 0) or 0
        quota.verifier(taille)
        nom = super()._save(name, content)
        quota.ajouter(taille)
        return nom

    def delete(self, name):
        # Fichier effacé (suppression définitive, corbeille vidée…) : l'espace occupé est remesuré.
        super().delete(name)
        quota.oublier()
