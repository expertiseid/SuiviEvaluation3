"""Espaces d'essai gratuit non convertis : avertissements, puis suppression (apps.organisations.essais)."""
from django.core.management.base import BaseCommand

from apps.organisations import essais


class Command(BaseCommand):
    help = "Avertit puis supprime les espaces d'essai gratuit terminés depuis 60 jours sans abonnement."

    def handle(self, *args, **options):
        bilan = essais.traiter()
        for sous_domaine in bilan["avertis"]:
            self.stdout.write(f"Avertissement de suppression envoyé : {sous_domaine}")
        for sous_domaine in bilan["supprimes"]:
            self.stdout.write(self.style.WARNING(f"Espace d'essai supprimé : {sous_domaine}"))
