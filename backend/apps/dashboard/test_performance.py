"""Performance des indicateurs au tableau de bord (apps.dashboard.performance) et écart à la cible."""
import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import User

from apps.indicators.models import Indicateur, ValeurIndicateur
from apps.projects.models import Activite, NiveauActivite, Projet

from .performance import ecart_a_la_cible, performance

J = datetime.date


def _valeur(indicateur, mois, valeur):
    ValeurIndicateur.objects.create(indicateur=indicateur, periode_debut=J(2026, mois, 1), periode_fin=J(2026, mois, 28),
                                    valeur_realisee=valeur, saisi_par=User.objects.get_or_create(username="saisie_perf")[0])


@pytest.mark.django_db
def test_performance_des_indicateurs():
    projet = Projet.objects.create(nom="P", code="PERF-1", date_debut="2026-01-01", date_fin="2026-12-31")
    NiveauActivite.objects.create(projet=projet, profondeur=0, nom_niveau="Effet")
    NiveauActivite.objects.create(projet=projet, profondeur=1, nom_niveau="Produit")
    effet = Activite.objects.create(projet=projet, libelle="Effet 1")
    produit = Activite.objects.create(projet=projet, libelle="Produit 1", activite_parent=effet)

    # Cumulable : 60 + 50 = 110 sur 100 → atteint ; pas de tendance (une période plus faible reste un progrès).
    kits = Indicateur.objects.create(libelle="Kits", unite="kits", valeur_cible=100, frequence_collecte="MENSUELLE", activite=produit)
    _valeur(kits, 1, 60)
    _valeur(kits, 2, 50)
    # Niveau mesuré, plus bas = mieux : 30 % puis 25 % → en progrès ; reste 5 points pour la cible de 20 %.
    malnutrition = Indicateur.objects.create(libelle="Malnutrition", unite="%", valeur_reference=40, valeur_cible=20,
                                             frequence_collecte="MENSUELLE", sens="BAISSE", agregation="DERNIERE",
                                             calcul_taux="PROGRESSION", activite=effet)
    _valeur(malnutrition, 1, 30)
    _valeur(malnutrition, 2, 25)
    Indicateur.objects.create(libelle="Jamais saisi", unite="u", valeur_cible=5, frequence_collecte="ANNUELLE", projet=projet)

    p = performance(Indicateur.objects.filter(id__in=[kits.id, malnutrition.id]) | Indicateur.objects.filter(projet=projet), [projet.id])
    assert (p["total"], p["renseignes"], p["atteints"], p["avec_taux"]) == (3, 2, 1, 2)
    assert (p["en_progres"], p["en_recul"], p["part_en_progres"]) == (1, 0, 100.0)
    lignes = {x["libelle"]: x for x in p["liste"]}
    assert lignes["Kits"]["ecart"] == Decimal("-10") and lignes["Kits"]["tendance"] is None
    assert lignes["Malnutrition"]["ecart"] == Decimal("5") and lignes["Malnutrition"]["tendance"] == "progres"
    assert lignes["Malnutrition"]["taux"] == 75.0  # (25 − 40) ÷ (20 − 40)
    assert p["liste"][-1]["libelle"] == "Jamais saisi"  # sans taux : en dernier
    niveaux = {x["niveau"]: x for x in p["par_niveau"]}
    assert (niveaux["Produit"]["atteints"], niveaux["Effet"]["atteints"]) == (1, 0)
    assert p["taux_par_projet"] == {"PERF-1": 92.5}
    # Score : taux plafonnés à 100 % (110 → 100) ; poids égaux, puis « Malnutrition » trois fois plus importante.
    assert p["score"] == 87.5 and p["indicateurs_ponderes"] == 0
    Indicateur.objects.filter(pk=malnutrition.pk).update(poids=3)
    p = performance(Indicateur.objects.filter(projet=projet) | Indicateur.objects.filter(activite__projet=projet), [projet.id])
    assert p["score"] == round((100 + 75 * 3) / 4, 1) and p["indicateurs_ponderes"] == 1
    assert p["scores_projets"] == [{"projet": "PERF-1", "score": 81.2, "indicateurs": 3}]

    assert ecart_a_la_cible(kits, None) is None
    assert ecart_a_la_cible(kits, Decimal("40")) == Decimal("60")
