"""
Reconstruit l'index des comptes (courriel → organisation) à partir de chaque espace.

    python manage.py indexer_comptes
"""
from django.core.management.base import BaseCommand

from apps.organisations import comptes
from apps.organisations.models import CompteOrganisation


class Command(BaseCommand):
    help = "Index des comptes (connexion par courriel) : reconstruction complète."

    def handle(self, *args, **options):
        doublons = comptes.reconstruire()
        for d in doublons:
            self.stdout.write(self.style.WARNING(f"Adresse en double, non indexée : {d}"))
        self.stdout.write(self.style.SUCCESS(f"{CompteOrganisation.objects.using('central').count()} compte(s) indexé(s)."))
