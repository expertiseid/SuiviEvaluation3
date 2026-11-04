"""Nouvelle version : met à jour la base centrale puis la base de chaque organisation (actives et suspendues)."""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.organisations import contexte
from apps.organisations.models import Organisation


class Command(BaseCommand):
    help = "Applique les migrations à la base centrale et à toutes les bases d'organisations."

    def handle(self, *args, **o):
        call_command("migrate", interactive=False, verbosity=1, stdout=self.stdout)
        echecs = []
        for org in Organisation.objects.using("central").exclude(statut=Organisation.Statut.EN_ATTENTE).order_by("sous_domaine"):
            self.stdout.write(f"— {org.sous_domaine}")
            try:
                with contexte.dans_organisation(org):
                    call_command("migrate", interactive=False, verbosity=0, stdout=self.stdout)
            except Exception as erreur:
                echecs.append(org.sous_domaine)
                self.stderr.write(f"   échec : {type(erreur).__name__}: {erreur}")
        if echecs:
            raise CommandError(f"Échec pour : {', '.join(echecs)}")
        self.stdout.write(self.style.SUCCESS("Toutes les bases sont à jour."))
