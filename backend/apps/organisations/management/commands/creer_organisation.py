"""
Crée l'espace d'une organisation : registre, base PostgreSQL, tables, compte administrateur.

    python manage.py creer_organisation ong-a "ONG A" --admin admin_onga --courriel admin@ong-a.org \
        --mot-de-passe '…' [--activer] [--zones] [--demo]
"""
from django.core.management.base import BaseCommand, CommandError

from apps.organisations import gestion


class Command(BaseCommand):
    help = "Crée l'espace d'une organisation (base, tables, administrateur)."

    def add_arguments(self, parser):
        parser.add_argument("sous_domaine")
        parser.add_argument("nom")
        parser.add_argument("--admin", required=True, help="Identifiant du premier administrateur.")
        parser.add_argument("--courriel", required=True, help="Adresse de l'administrateur (code de connexion).")
        parser.add_argument("--mot-de-passe", required=True)
        parser.add_argument("--activer", action="store_true", help="Ouvrir l'espace tout de suite.")
        parser.add_argument("--zones", action="store_true", help="Installer le référentiel des zones du Burkina Faso.")
        parser.add_argument("--demo", action="store_true", help="Espace de démonstration (visiteur en lecture seule).")

    def handle(self, *args, **o):
        try:
            org = gestion.creer(o["nom"], o["sous_domaine"], courriel=o["courriel"], mode_demo=o["demo"],
                                sortie=self.stdout, zones=o["zones"])
            gestion.creer_administrateur(org, o["admin"], o["courriel"], mot_de_passe=o["mot_de_passe"])
            if o["activer"]:
                gestion.activer(org)
        except gestion.ErreurOrganisation as erreur:
            raise CommandError(str(erreur))
        self.stdout.write(self.style.SUCCESS(f"Espace {org.sous_domaine} créé (base {org.base}, {org.get_statut_display().lower()})."))
