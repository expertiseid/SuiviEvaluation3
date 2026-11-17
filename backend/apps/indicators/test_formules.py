"""Indicateurs calculés par formule (apps.indicators.formules)."""
import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.beneficiaries.models import Beneficiaire, ParticipationProjet
from apps.projects.models import Activite, Projet

from .formules import FormuleInvalide, evaluer, explication, valider
from .models import Indicateur, ValeurIndicateur
from .services import actualisation, taux_indicateur, valeur_actuelle, valeurs_actuelles

PART_FEMMES = {"termes": [{"mesure": "beneficiaires", "filtres": {"sexe": "F"}}, {"mesure": "beneficiaires", "filtres": {}}],
               "expression": "A / B * 100"}


def _projet_avec_beneficiaires():
    projet = Projet.objects.create(nom="P", code="FO-1", date_debut="2026-01-01", date_fin="2026-12-31")
    jeune = datetime.date.today().replace(year=datetime.date.today().year - 20)
    for nom, sexe, naissance in (("a", "F", jeune), ("b", "F", datetime.date(1960, 1, 1)), ("c", "M", jeune), ("d", "F", None)):
        b = Beneficiaire.objects.create(nom=nom, prenom=nom, sexe=sexe, date_naissance=naissance)
        ParticipationProjet.objects.create(beneficiaire=b, projet=projet, date_inscription="2026-02-01")
    return projet


@pytest.mark.django_db
def test_indicateur_calcule_par_formule():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_formules", password="x", role=ROLE_ADMIN))
    projet = _projet_avec_beneficiaires()
    autre = Projet.objects.create(nom="Q", code="FO-2", date_debut="2026-01-01", date_fin="2026-12-31")
    ParticipationProjet.objects.create(beneficiaire=Beneficiaire.objects.create(nom="z", prenom="z", sexe="M"), projet=autre,
                                       date_inscription="2026-02-01")

    reponse = client.post("/api/v1/indicateurs/", {
        "libelle": "Part de femmes", "unite": "%", "valeur_cible": 60, "frequence_collecte": "TRIMESTRIELLE",
        "projet": projet.id, "formule": PART_FEMMES}, format="json")
    assert reponse.status_code == 201, reponse.data
    # Seules les données du projet de l'indicateur comptent : 3 femmes sur 4.
    assert Decimal(reponse.data["valeur_actuelle"]) == Decimal("75.00") and reponse.data["taux_realisation_actuel"] == 125.0
    assert reponse.data["agregation"] == "DERNIERE" and reponse.data["actualisation"]["en_retard"] is False
    assert reponse.data["formule"]["termes"][1]["code"] == "B"
    assert reponse.data["formule_explication"] == ["A = Bénéficiaires uniques (femmes)", "B = Bénéficiaires uniques", "Calcul : A ÷ B × 100"]
    indicateur = Indicateur.objects.get(pk=reponse.data["id"])
    assert valeurs_actuelles([indicateur]) == {indicateur.id: Decimal("75.00")}

    # Aucune saisie possible sur un indicateur calculé.
    refus = client.post("/api/v1/valeurs-indicateurs/", {"indicateur": indicateur.id, "periode_debut": "2026-01-01",
                                                         "periode_fin": "2026-03-31", "valeur_realisee": 10}, format="json")
    assert refus.status_code == 400
    # Formule invalide : message clair.
    invalide = client.patch(f"/api/v1/indicateurs/{indicateur.id}/", {"formule": {
        "termes": [{"mesure": "depenses"}, {"mesure": "beneficiaires"}], "expression": "A + B"}}, format="json")
    assert invalide.status_code == 400 and "FCFA" in str(invalide.data["formule"])

    # Aperçu en direct, limité aux projets visibles.
    apercu = client.post("/api/v1/indicateurs/formules/apercu/", {"formule": PART_FEMMES, "projet": projet.id}, format="json")
    assert apercu.status_code == 200 and Decimal(apercu.data["valeur"]) == Decimal("75.00")
    tous = client.post("/api/v1/indicateurs/formules/apercu/", {"formule": PART_FEMMES}, format="json")
    assert Decimal(tous.data["valeur"]) == Decimal("60.00")  # 3 femmes sur 5 dans les deux projets
    assert client.get("/api/v1/indicateurs/formules/catalogue/").data["modeles"]


@pytest.mark.django_db
def test_mesures_filtres_et_garde_fous():
    admin = User.objects.create_user(username="adm_formules2", password="x", role=ROLE_ADMIN)
    projet = _projet_avec_beneficiaires()
    Activite.objects.create(projet=projet, libelle="A1", statut="REALISEE", date_fin=datetime.date(2026, 3, 31),
                            date_fin_reelle=datetime.date(2026, 3, 20), budget_alloue=1000, budget_realise=400)
    Activite.objects.create(projet=projet, libelle="A2", statut="REALISEE", date_fin=datetime.date(2026, 3, 31),
                            date_fin_reelle=datetime.date(2026, 4, 20), budget_realise=200)
    ids = [projet.id]

    def calcul(mesure, filtres=None, expression="A"):
        return evaluer({"termes": [{"mesure": mesure, "filtres": filtres or {}}], "expression": expression}, ids)["valeur"]

    assert calcul("beneficiaires", {"age_max": 35}) == 2 and calcul("beneficiaires", {"age_min": 60}) == 1
    assert calcul("activites", {"delai": "a_temps"}) == 1 and calcul("activites", {"statut_activite": "REALISEE"}) == 2
    assert calcul("depenses") == 600 and calcul("depenses", expression="A / 3") == Decimal("200.00")
    # Division par zéro : non calculable, jamais un chiffre trompeur.
    zero = evaluer({"termes": [{"mesure": "depenses"}, {"mesure": "plaintes"}], "expression": "A / B"}, ids)
    assert zero["valeur"] is None and zero["non_calculable"]

    # Comparaison entre les deux dernières saisies d'un autre indicateur.
    saisi = Indicateur.objects.create(libelle="Kits", unite="kits", valeur_cible=100, frequence_collecte="TRIMESTRIELLE", projet=projet)
    for debut, fin, valeur in (("2026-01-01", "2026-03-31", 40), ("2026-04-01", "2026-06-30", 50)):
        ValeurIndicateur.objects.create(indicateur=saisi, periode_debut=debut, periode_fin=fin, valeur_realisee=valeur, saisi_par=admin)
    progression = {"termes": [{"mesure": "indicateur", "filtres": {"indicateur": saisi.id, "variante": "derniere"}},
                              {"mesure": "indicateur", "filtres": {"indicateur": saisi.id, "variante": "precedente"}}],
                   "expression": "(A - B) / B * 100"}
    assert evaluer(progression, ids)["valeur"] == Decimal("25.00")
    calcule = Indicateur.objects.create(libelle="Progression", unite="%", valeur_cible=10, frequence_collecte="TRIMESTRIELLE",
                                        projet=projet, formule=valider(progression), agregation="DERNIERE")
    assert valeur_actuelle(calcule) == Decimal("25.00") and taux_indicateur(calcule) == 250.0
    assert actualisation(calcule)["en_retard"] is False
    assert explication(calcule.formule)[0] == "A = Valeur d'un autre indicateur (dernière valeur saisie ; Kits)"

    # Un indicateur calculé ne peut pas servir de terme (pas de boucle) ; expressions refusées.
    for mauvaise in (
        {"termes": [{"mesure": "indicateur", "filtres": {"indicateur": calcule.id}}], "expression": "A"},
        {"termes": [{"mesure": "depenses"}], "expression": "__import__('os')"},
        {"termes": [{"mesure": "depenses"}], "expression": "A ** 2"},
        {"termes": [{"mesure": "depenses"}], "expression": "C"},
        {"termes": [], "expression": "1"},
    ):
        with pytest.raises(FormuleInvalide):
            valider(mauvaise)
