"""
Contrôle des échéances des dossiers de plaintes : rappels, retards, escalades (au plus un rappel
par dossier et par jour). Lancé par la tâche horaire (check_deadlines) ; --recalculer recalcule
d'abord les échéances de tous les dossiers ouverts. Efface aussi les fichiers de pièces jointes
orphelins (pieces.effacer_fichiers_orphelins).
"""
from django.core.management.base import BaseCommand

from apps.plaintes import delais, pieces


class Command(BaseCommand):
    help = "Vérifie les échéances des dossiers de plaintes et envoie rappels et escalades."

    def add_arguments(self, parser):
        parser.add_argument("--recalculer", action="store_true", help="Recalcule d'abord toutes les échéances.")

    def handle(self, *args, **options):
        if options["recalculer"]:
            delais.recalculer_ouverts()
        signales = delais.verifier_echeances()
        self.stdout.write(self.style.SUCCESS(f"{signales} dossier(s) de plaintes signalé(s)."))
        effaces = pieces.effacer_fichiers_orphelins()
        if effaces:
            self.stdout.write(f"{effaces} fichier(s) de pièces jointes orphelin(s) effacé(s).")
