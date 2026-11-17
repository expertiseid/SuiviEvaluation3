"""Avancement et retards des activités de terrain (apps.projects.avancement)."""
import datetime

import pytest

from .avancement import avancement
from .models import Activite, JalonLivrable, Projet

AUJOURD_HUI = datetime.date(2026, 6, 30)
J = datetime.date


@pytest.mark.django_db
def test_avancement_et_retards():
    projet = Projet.objects.create(nom="P", code="AV-1", date_debut="2026-01-01", date_fin="2027-12-31")
    groupe = Activite.objects.create(projet=projet, libelle="Résultat 1")  # regroupement : pas compté
    commun = {"projet": projet, "activite_parent": groupe, "budget_alloue": 1000}
    # Terminée à temps (prévue fin mars, finie le 20 mars, commencée le 1er janvier).
    a_temps = Activite.objects.create(**commun, libelle="A", statut="REALISEE", date_debut=J(2026, 1, 1), date_fin=J(2026, 3, 31),
                                      date_debut_reelle=J(2026, 1, 1), date_fin_reelle=J(2026, 3, 20))
    # Terminée en retard de 10 jours.
    Activite.objects.create(**commun, libelle="B", statut="REALISEE", date_debut=J(2026, 1, 1), date_fin=J(2026, 4, 30),
                            date_debut_reelle=J(2026, 1, 11), date_fin_reelle=J(2026, 5, 10))
    # En cours, échéance dépassée de 30 jours : en retard.
    Activite.objects.create(**commun, libelle="C", statut="EN_COURS", date_debut=J(2026, 2, 1), date_fin=J(2026, 5, 31))
    # Pas démarrée alors qu'elle aurait dû ; échéance à venir.
    Activite.objects.create(**commun, libelle="D", date_debut=J(2026, 6, 1), date_fin=J(2026, 12, 31))
    # Sans dates ni budget ni responsable.
    Activite.objects.create(projet=projet, activite_parent=groupe, libelle="E")
    JalonLivrable.objects.create(activite=a_temps, type="JALON", libelle="J1", achevement=100, date_prevue=J(2026, 3, 1))
    JalonLivrable.objects.create(activite=a_temps, type="JALON", libelle="J2", achevement=0, date_prevue=J(2026, 4, 1))

    a = avancement([projet.id], aujourd_hui=AUJOURD_HUI)
    assert (a["prevues"], a["demarrees"], a["terminees"]) == (5, 3, 2)
    assert (a["taux_demarrage"], a["taux_achevement"]) == (60.0, 40.0)
    # Échéance passée : A, B, C ; terminées parmi elles : A, B.
    assert (a["attendues_a_date"], a["taux_execution_a_date"]) == (3, 66.7)
    assert (a["en_retard"], a["part_en_retard"], a["retard_moyen_jours"]) == (1, 20.0, 30.0)
    assert a["demarrage_en_retard"] == 1  # D
    assert (a["terminees_dans_les_delais"], a["retard_moyen_a_l_achevement_jours"]) == (50.0, 10.0)
    assert a["duree_moyenne_realisation_jours"] == round((78 + 119) / 2, 1)
    assert (a["sans_responsable"], a["sans_calendrier"], a["sans_budget"]) == (5, 1, 1)
    assert a["jalons"] == {"total": 2, "atteints": 1, "part_atteints": 50.0, "en_retard": 1}
    assert [r["libelle"] for r in a["activites_en_retard"]] == ["C"] and a["activites_en_retard"][0]["jours"] == 30
    assert a["par_projet"][0]["code"] == "AV-1" and a["par_projet"][0]["en_retard"] == 1
