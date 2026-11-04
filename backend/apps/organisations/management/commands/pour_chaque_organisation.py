"""
Lance une commande dans chaque espace actif (tâche planifiée, mise à jour) ; sans plateforme
multi-organisations, la lance une fois, normalement.

    python manage.py pour_chaque_organisation check_deadlines
    python manage.py pour_chaque_organisation migrate --noinput
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.organisations import contexte, gestion


class Command(BaseCommand):
    help = "Exécute une commande dans chaque organisation active."

    def add_arguments(self, parser):
        parser.add_argument("commande")
        parser.add_argument("arguments", nargs="*")

    def handle(self, *args, **o):
        if not contexte.actif():
            call_command(o["commande"], *o["arguments"], stdout=self.stdout)
            return
        echecs = []
        for org in gestion.actives():
            self.stdout.write(f"— {org.sous_domaine}")
            try:
                with contexte.dans_organisation(org):
                    call_command(o["commande"], *o["arguments"], stdout=self.stdout)
            except Exception as erreur:  # une organisation en échec n'empêche pas les autres
                echecs.append(org.sous_domaine)
                self.stderr.write(f"   échec : {type(erreur).__name__}: {erreur}")
        if echecs:
            raise CommandError(f"Échec pour : {', '.join(echecs)}")
