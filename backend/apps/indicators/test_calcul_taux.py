"""Calcul du taux d'un indicateur : sens, progression depuis la référence, dernière valeur, cas limites."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Projet

from .models import Indicateur, ValeurIndicateur
from .services import taux_indicateur, valeur_actuelle, valeurs_actuelles

I = Indicateur


def _ind(**reglages):
    valeurs = {"libelle": "Test", "unite": "%", "valeur_cible": Decimal("100"), "frequence_collecte": "ANNUELLE"}
    return Indicateur(**{**valeurs, **reglages})


@pytest.mark.parametrize("reglages, valeur, attendu", [
    # Calcul historique (réglages par défaut) : réalisé ÷ cible.
    ({}, 50, 50.0),
    ({"valeur_reference": Decimal("20")}, 50, 50.0),  # la référence n'est pas prise en compte par défaut
    # Progression : 20 → cible 120, 50 réalisés en plus (cumulables) : niveau 70, soit la moitié du chemin.
    ({"calcul_taux": I.CalculTaux.PROGRESSION, "valeur_reference": Decimal("20"), "valeur_cible": Decimal("120")}, 50, 50.0),
    # Exemple du document : un taux qui doit baisser de 40 % à 20 %, mesuré à 30 % → moitié du chemin.
    ({"calcul_taux": I.CalculTaux.PROGRESSION, "agregation": I.Agregation.DERNIERE, "sens": I.Sens.BAISSE,
      "valeur_reference": Decimal("40"), "valeur_cible": Decimal("20")}, 30, 50.0),
    # … remonté à 45 % : recul, taux négatif (signalé comme tel).
    ({"calcul_taux": I.CalculTaux.PROGRESSION, "agregation": I.Agregation.DERNIERE,
      "valeur_reference": Decimal("40"), "valeur_cible": Decimal("20")}, 45, -25.0),
    # Plus bas = mieux, sans référence : cible ÷ valeur.
    ({"sens": I.Sens.BAISSE, "valeur_cible": Decimal("20")}, 40, 50.0),
    ({"sens": I.Sens.BAISSE, "valeur_cible": Decimal("20")}, 10, 200.0),
    ({"sens": I.Sens.BAISSE, "valeur_cible": Decimal("0")}, 0, 100.0),
    ({"sens": I.Sens.BAISSE, "valeur_cible": Decimal("0")}, 5, 0.0),
    # Cas limites : non calculables plutôt qu'un chiffre trompeur.
    ({"valeur_cible": Decimal("0")}, 5, None),
    ({"calcul_taux": I.CalculTaux.PROGRESSION, "valeur_reference": Decimal("50"), "valeur_cible": Decimal("50")}, 60, None),
    # Progression demandée sans référence : réalisé ÷ cible.
    ({"calcul_taux": I.CalculTaux.PROGRESSION}, 30, 30.0),
])
def test_taux_selon_les_reglages(reglages, valeur, attendu):
    assert taux_indicateur(_ind(**reglages), Decimal(valeur)) == attendu


@pytest.mark.django_db
def test_derniere_valeur_et_api():
    admin = User.objects.create_user(username="adm_taux", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    projet = Projet.objects.create(nom="P", code="TX-1", date_debut="2026-01-01", date_fin="2027-12-31")
    cree = client.post("/api/v1/indicateurs/", {
        "libelle": "Prévalence de la malnutrition", "unite": "%", "valeur_reference": "40", "valeur_cible": "20",
        "frequence_collecte": "ANNUELLE", "projet": projet.id, "sens": "BAISSE", "calcul_taux": "PROGRESSION",
        "agregation": "DERNIERE",
    }, format="json")
    assert cree.status_code == 201, cree.data
    indicateur = Indicateur.objects.get(pk=cree.data["id"])
    assert cree.data["taux_realisation_actuel"] is None and valeur_actuelle(indicateur) is None  # rien de saisi
    for fin, valeur in (("2026-12-31", "35"), ("2027-12-31", "30")):
        ValeurIndicateur.objects.create(indicateur=indicateur, periode_debut=fin[:4] + "-01-01", periode_fin=fin,
                                        valeur_realisee=Decimal(valeur), saisi_par=admin)
    # Seule la dernière mesure compte (30 %), pas la somme (65).
    assert valeur_actuelle(indicateur) == Decimal("30") and valeurs_actuelles([indicateur]) == {indicateur.pk: Decimal("30")}
    detail = client.get(f"/api/v1/indicateurs/{indicateur.id}/").data
    assert (detail["taux_realisation_actuel"], detail["sens"], detail["agregation"]) == (50.0, "BAISSE", "DERNIERE")
    assert [v["taux_realisation"] for v in sorted(detail["valeurs"], key=lambda v: v["periode_fin"])] == [25.0, 50.0]


@pytest.mark.django_db
def test_indicateur_non_actualise_et_variation():
    import datetime

    from .services import actualisation, variation

    admin = User.objects.create_user(username="adm_actu", password="x", role=ROLE_ADMIN)
    projet = Projet.objects.create(nom="P", code="ACT-1", date_debut="2026-01-01", date_fin="2027-12-31")
    projet.refresh_from_db()  # dates relues en objets date
    ind = Indicateur.objects.create(libelle="Kits distribués", unite="kits", valeur_cible=100, frequence_collecte="TRIMESTRIELLE",
                                    projet=projet)
    # Sans saisie : attendue un trimestre après le début du projet, plus 30 jours de délai de saisie.
    assert actualisation(ind, aujourd_hui=datetime.date(2026, 4, 30))["en_retard"] is False
    retard = actualisation(ind, aujourd_hui=datetime.date(2026, 5, 11))
    assert retard["en_retard"] and retard["jours_de_retard"] == 10 and retard["attendue_le"] == datetime.date(2026, 5, 1)
    for debut, fin, valeur in (("2026-01-01", "2026-03-31", "40"), ("2026-04-01", "2026-06-30", "30")):
        ValeurIndicateur.objects.create(indicateur=ind, periode_debut=debut, periode_fin=fin, valeur_realisee=Decimal(valeur),
                                        saisi_par=admin)
    a_jour = actualisation(ind, aujourd_hui=datetime.date(2026, 10, 15))
    assert a_jour["derniere_saisie"] == datetime.date(2026, 6, 30) and a_jour["en_retard"] is False
    assert actualisation(ind, aujourd_hui=datetime.date(2026, 11, 1))["en_retard"] is True
    assert variation(ind) == {"precedente": Decimal("40"), "derniere": Decimal("30"), "ecart": Decimal("-10"), "pourcent": -25.0}
    # Fin prévue couverte : plus rien n'est attendu.
    ValeurIndicateur.objects.create(indicateur=ind, periode_debut="2027-10-01", periode_fin="2027-12-31", valeur_realisee=5,
                                    saisi_par=admin)
    assert actualisation(ind, aujourd_hui=datetime.date(2029, 1, 1))["en_retard"] is False
