from django.core.management.base import BaseCommand

from apps.geo.models import NiveauAdministratif, Zone
from apps.geo.referentiel_bf import charger_zones_bf


class Command(BaseCommand):
    help = (
        "Charge les niveaux administratifs (Région > Province > Commune) et les 17 régions / 47 "
        "provinces du Burkina Faso (source : limites administratives officielles) — communes et villages "
        "restent à ajouter librement au fil de la saisie. Les niveaux/zones déjà saisis à la main sont "
        "reconnus et complétés plutôt que dupliqués."
    )

    def handle(self, *args, **options):
        crees = charger_zones_bf(NiveauAdministratif, Zone)
        self.stdout.write(self.style.SUCCESS(f"{crees} zone(s) créée(s) (régions + provinces)."))
