"""
Importe une base topographique nationale en shapefiles (BNDT du Burkina Faso, WGS84) pour la
carte des bénéficiaires : python manage.py importer_bndt chemin/WGS84.zip [--pays BF] [--recalculer]
"""
from django.core.management.base import BaseCommand, CommandError

from apps.geo.services.bndt import ImportImpossible, importer


class Command(BaseCommand):
    help = "Importe régions, provinces, communes, routes et localités (shapefiles) et place les zones."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Archive .zip ou dossier contenant ADM_region.shp, ADM_Province.shp…")
        parser.add_argument("--pays", default="BF")
        parser.add_argument("--recalculer", action="store_true", help="Replace aussi les zones déjà positionnées.")

    def handle(self, *args, **options):
        try:
            resultat = importer(options["source"], options["pays"], options["recalculer"], journal=self.stdout.write)
        except ImportImpossible as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"{resultat['zones placées']} zone(s) placée(s) sur la carte."))
