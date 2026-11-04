"""Liste les organisations du registre : sous-domaine, nom, état, base."""
from django.core.management.base import BaseCommand

from apps.organisations.models import Organisation


class Command(BaseCommand):
    help = "Liste les organisations de la plateforme."

    def handle(self, *args, **o):
        for org in Organisation.objects.using("central").order_by("sous_domaine"):
            self.stdout.write(f"{org.sous_domaine:24} {org.get_statut_display():24} {org.base:28} {org.nom}")
