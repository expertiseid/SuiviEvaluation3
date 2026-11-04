"""
Fait de l'ancienne installation (à organisation unique) l'espace d'une organisation. Voir
apps/organisations/reprise.py ; à lancer par scripts/reprendre_installation.sh, qui copie d'abord la base.

    python manage.py reprendre_installation expertise-id "Expertise-ID" [--courriel contact@…]
"""
from django.core.management.base import BaseCommand, CommandError

from apps.organisations import gestion, reprise


class Command(BaseCommand):
    help = "Rattache la copie de l'ancienne installation à un espace d'organisation (rechiffrement, fichiers)."

    def add_arguments(self, parser):
        parser.add_argument("sous_domaine")
        parser.add_argument("nom")
        parser.add_argument("--courriel", default="")

    def handle(self, *args, **o):
        try:
            org = reprise.reprendre(o["sous_domaine"], o["nom"], courriel=o["courriel"], sortie=self.stdout)
        except gestion.ErreurOrganisation as erreur:
            raise CommandError(str(erreur))
        self.stdout.write(self.style.SUCCESS(f"Espace {org.sous_domaine} repris (base {org.base}, actif)."))
