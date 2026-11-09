"""
Disque commun des fichiers (Volume agrandi tout seul) : prévient Expertise-ID quand il approche de son
plafond ou se remplit malgré tout (quota.alerter_disque). Une fois pour toute la plateforme, toutes les heures :

    python manage.py surveiller_disque
"""
from django.core.management.base import BaseCommand

from apps.organisations import quota


class Command(BaseCommand):
    help = "Prévient Expertise-ID si le disque commun des fichiers approche de son plafond ou se remplit."

    def handle(self, *args, **options):
        quota.alerter_disque()
