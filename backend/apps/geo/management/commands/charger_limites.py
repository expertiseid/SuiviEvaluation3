"""
Télécharge les limites administratives d'un pays (geoBoundaries) et place les zones de la
plateforme sur la carte : python manage.py charger_limites BF [--niveaux 1 2 3]
"""
from django.core.management.base import BaseCommand

from apps.geo.services.limites import charger_pays


class Command(BaseCommand):
    help = "Télécharge les limites administratives d'un pays et calcule le centre des zones."

    def add_arguments(self, parser):
        parser.add_argument("pays", help="Code ISO à deux lettres (ex : BF)")
        parser.add_argument("--niveaux", nargs="+", type=int, default=[1, 2, 3])
        parser.add_argument("--recalculer", action="store_true", help="Efface d'abord les positions des zones du pays.")

    def handle(self, *args, **options):
        resultats = charger_pays(options["pays"].upper(), options["niveaux"], recalculer=options["recalculer"])
        completees = resultats.pop("completees")
        for niveau, resultat in resultats.items():
            if isinstance(resultat, int):
                self.stdout.write(f"Niveau {niveau} : {resultat} zone(s) placée(s).")
            else:
                self.stdout.write(self.style.WARNING(f"Niveau {niveau} : {resultat}"))
        self.stdout.write(f"{completees} zone(s) placée(s) au centre de leurs zones enfants.")
