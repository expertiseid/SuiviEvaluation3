"""
Peuple des points de suivi (apps.suivi.PointSuivi) sur les activités et
sous-activités des deux projets de démonstration créés par seed_demo_arfa,
pour que le nouveau module Suivi ait un historique à afficher (évolution
dans le temps) plutôt qu'un simple instantané. Rejouable : repart d'une
table vide à chaque exécution.

Chaque quantité/budget ci-dessous est ce qui a été accompli PENDANT cette
période précise (un delta, pas un cumul) — la somme des points d'une même
activité/sous-activité doit retomber sur la valeur déjà posée par
seed_demo_arfa, ce que la synchronisation en fin de script vérifie (elle
est censée ne rien changer, elle sert de garde-fou de cohérence).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.projects.models import Activite, SousActivite
from apps.suivi.models import PointSuivi
from apps.suivi.services import synchroniser_activite_depuis_suivi, synchroniser_sous_activite_depuis_suivi

User = get_user_model()

# code_activite -> [(periode_debut, periode_fin, quantite_realisee, budget_realise, statut), ...]
POINTS_ACTIVITE = {
    "A1.1.1": [
        (date(2024, 3, 15), date(2024, 12, 31), Decimal("210"), Decimal("7000000"), "EN_COURS"),
        (date(2025, 1, 1), date(2025, 12, 31), Decimal("330"), Decimal("11000000"), "EN_COURS"),
    ],
    "A1.1.2": [
        (date(2024, 4, 15), date(2024, 12, 31), Decimal("30"), Decimal("6000000"), "EN_COURS"),
        (date(2025, 1, 1), date(2025, 12, 31), Decimal("65"), Decimal("15000000"), "EN_COURS"),
    ],
    "A1.2.1": [
        (date(2024, 6, 1), date(2024, 12, 31), Decimal("4"), Decimal("3000000"), "EN_COURS"),
        (date(2025, 1, 1), date(2025, 12, 31), Decimal("7"), Decimal("6000000"), "EN_COURS"),
    ],
    "A1.2.2": [
        (date(2025, 1, 15), date(2025, 12, 31), Decimal("3"), Decimal("4000000"), "NON_REALISEE"),
    ],
    "A2.1.1": [
        (date(2025, 5, 1), date(2025, 12, 31), Decimal("18"), Decimal("12000000"), "EN_COURS"),
    ],
    "A2.1.2": [
        (date(2025, 6, 1), date(2025, 12, 31), Decimal("14"), Decimal("22000000"), "EN_COURS"),
    ],
    "A2.2.1": [
        (date(2025, 4, 15), date(2025, 12, 31), Decimal("9"), Decimal("5000000"), "EN_COURS"),
        (date(2026, 1, 1), date(2026, 6, 30), Decimal("8"), Decimal("4000000"), "EN_COURS"),
    ],
    # A2.2.2 : pas encore démarrée (NON_REALISEE, 0 partout) — aucun point de
    # suivi n'existe encore, volontairement, pour montrer ce cas dans le
    # dashboard (courbe vide, juste la cible en repère).
}

# libellé exact de la sous-activité -> [(periode_debut, periode_fin, quantite_realisee, statut), ...]
POINTS_SOUS_ACTIVITE = {
    "Organisation de sessions de formation pratique en champs-écoles paysans": [
        (date(2024, 3, 15), date(2024, 12, 31), Decimal("7"), "EN_COURS"),
        (date(2025, 1, 1), date(2025, 12, 31), Decimal("11"), "EN_COURS"),
    ],
    "Réalisation de chantiers communautaires d'aménagement CES/DRS": [
        (date(2024, 4, 15), date(2024, 12, 31), Decimal("30"), "EN_COURS"),
        (date(2025, 1, 1), date(2025, 12, 31), Decimal("65"), "EN_COURS"),
    ],
    "Accompagnement à l'élaboration des textes statutaires et à l'enregistrement légal": [
        (date(2024, 6, 1), date(2025, 12, 31), Decimal("11"), "EN_COURS"),
    ],
    "Mise en place d'un système de warrantage / boutique d'intrants communautaire": [
        (date(2025, 1, 15), date(2025, 12, 31), Decimal("3"), "PLANIFIEE"),
    ],
    "Octroi de kits de démarrage et accompagnement des groupements d'AGR": [
        (date(2025, 5, 1), date(2025, 12, 31), Decimal("18"), "EN_COURS"),
    ],
    "Aménagement et équipement de périmètres maraîchers": [
        (date(2025, 6, 1), date(2025, 12, 31), Decimal("14"), "EN_COURS"),
    ],
    "Organisation de sessions de dialogue communautaire et de reddition de comptes": [
        (date(2025, 4, 15), date(2025, 12, 31), Decimal("9"), "EN_COURS"),
        (date(2026, 1, 1), date(2026, 6, 30), Decimal("8"), "EN_COURS"),
    ],
}


class Command(BaseCommand):
    help = "Peuple des points de suivi de démonstration sur les activités/sous-activités existantes."

    def handle(self, *args, **options):
        saisi_par = User.objects.filter(username="demo_charge_se").first() or User.objects.filter(
            username="demo_admin"
        ).first()
        if saisi_par is None:
            self.stderr.write("Aucun utilisateur demo_charge_se/demo_admin trouvé — abandon.")
            return

        PointSuivi.tous.all().delete()

        for activite in Activite.objects.filter(code_activite__in=POINTS_ACTIVITE.keys()):
            for periode_debut, periode_fin, quantite, budget, statut in POINTS_ACTIVITE[activite.code_activite]:
                PointSuivi.objects.create(
                    activite=activite,
                    periode_debut=periode_debut,
                    periode_fin=periode_fin,
                    quantite_realisee=quantite,
                    budget_realise=budget,
                    statut=statut,
                    saisi_par=saisi_par,
                )
            synchroniser_activite_depuis_suivi(activite)

        for sous_activite in SousActivite.objects.filter(libelle__in=POINTS_SOUS_ACTIVITE.keys()):
            for periode_debut, periode_fin, quantite, statut in POINTS_SOUS_ACTIVITE[sous_activite.libelle]:
                PointSuivi.objects.create(
                    sous_activite=sous_activite,
                    periode_debut=periode_debut,
                    periode_fin=periode_fin,
                    quantite_realisee=quantite,
                    statut=statut,
                    saisi_par=saisi_par,
                )
            synchroniser_sous_activite_depuis_suivi(sous_activite)

        self.stdout.write(self.style.SUCCESS(f"{PointSuivi.objects.count()} points de suivi créés."))
