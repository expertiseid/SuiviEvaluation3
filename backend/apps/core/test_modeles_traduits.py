"""
Modèles d'import téléchargés dans une autre langue : le fichier est traduit (feuilles, en-têtes,
consignes) et se réimporte tel quel, avec le même résultat qu'en français.
"""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Activite, Projet, SousActivite
from apps.strategy.models import CadreStrategique

LANGUES = ["fr", "en", "ar", "es", "de"]


def _client(langue):
    client = APIClient(HTTP_ACCEPT_LANGUAGE=langue)
    client.force_authenticate(User.objects.create_user(username=f"adm_{langue}", password="x", role=ROLE_ADMIN))
    return client


def _aller_retour(client, modele, importer, **champs):
    contenu = client.get("/api/v1" + modele).content
    fichier = io.BytesIO(contenu)
    fichier.name = "modele.xlsx"
    reponse = client.post("/api/v1" + importer, {"fichier": fichier, **champs}, format="multipart")
    assert reponse.status_code == 200, reponse.content
    return load_workbook(io.BytesIO(contenu)), reponse.data


@pytest.mark.django_db
@pytest.mark.parametrize("langue", LANGUES)
def test_modele_projet(langue):
    wb, resultat = _aller_retour(_client(langue), "/projets/modele-import/", "/projets/importer/")
    if langue != "fr":
        assert "Projet" not in wb.sheetnames and "Planification" not in wb.sheetnames
    assert resultat["erreurs"] == []
    assert (resultat["elements_crees"], resultat["sous_activites_creees"], resultat["grilles_alerte_creees"]) == (3, 2, 1)
    projet = Projet.objects.get(id=resultat["projet_id"])
    assert projet.date_debut.isoformat() == "2026-01-01" and projet.budget_total == 100000000
    # Méthode de calcul de l'exemple (« Par tâches pondérées », traduite dans le modèle) reconnue.
    assert Activite.objects.get(projet=projet, code_activite="A1.1").methode_calcul == "TACHES"
    assert SousActivite.objects.filter(activite__projet=projet).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("langue", LANGUES)
def test_modele_indicateurs(langue):
    # L'exemple du modèle rattache l'indicateur au projet de code PRJ-2026-001.
    Projet.objects.create(nom="P", code="PRJ-2026-001", date_debut="2026-01-01", date_fin="2026-12-31")
    _, resultat = _aller_retour(_client(langue), "/indicateurs/modele-import/", "/indicateurs/importer/")
    assert resultat["erreurs"] == []
    assert (resultat["crees"], resultat["grilles_alerte_creees"]) == (1, 1)


@pytest.mark.django_db
@pytest.mark.parametrize("langue", LANGUES)
def test_modele_beneficiaires(langue):
    _, resultat = _aller_retour(_client(langue), "/beneficiaires/modele-import/?pays=BF", "/beneficiaires/importer/")
    assert resultat["erreurs"] == []
    assert resultat["crees"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize("langue", LANGUES)
def test_modele_planification_complete(langue):
    _, resultat = _aller_retour(_client(langue), "/planification/modele-import/", "/planification/importer/")
    assert resultat["erreurs"] == []
    assert resultat["elements_strategiques_crees"] == 2 and resultat["projet_id"] is not None
    assert resultat["elements_crees"] > 0 and resultat["indicateurs_crees"] > 0 and resultat["beneficiaires_crees"] > 0


@pytest.mark.django_db
@pytest.mark.parametrize("langue", LANGUES)
def test_modele_structuration(langue):
    cadre = CadreStrategique.objects.create(nom="Cadre")
    client = _client(langue)
    _, resultat = _aller_retour(
        client, f"/elements-strategiques/modele-import/?cadre_strategique={cadre.id}", "/elements-strategiques/importer/",
        cadre_strategique=cadre.id,
    )
    assert resultat["erreurs"] == []
    assert (resultat["niveaux_crees"], resultat["elements_crees"]) == (2, 3)


@pytest.mark.django_db
@pytest.mark.parametrize("langue", LANGUES)
def test_export_beneficiaires_reimportable(langue):
    """Export traduit : en-têtes dans la langue, données inchangées (« Maraîchage » reste retrouvable)."""
    from apps.beneficiaries.models import Beneficiaire, ParticipationProjet, TypeActiviteBeneficiaire

    projet = Projet.objects.create(nom="P", code="EXP-1", date_debut="2026-01-01", date_fin="2026-12-31")
    maraichage, _ = TypeActiviteBeneficiaire.objects.get_or_create(code="MARAICHAGE", defaults={"libelle": "Maraîchage"})
    beneficiaire = Beneficiaire.objects.create(nom="Traoré", prenom="Awa", sexe="F")
    beneficiaire.types_activite.add(maraichage)
    ParticipationProjet.objects.create(beneficiaire=beneficiaire, projet=projet, date_inscription="2026-02-01")
    wb, resultat = _aller_retour(
        _client(langue), f"/beneficiaires/exporter/?fichier=excel&projets={projet.id}", "/beneficiaires/importer/"
    )
    if langue != "fr":
        assert wb.worksheets[0]["E1"].value != "Nom"
    assert resultat["erreurs"] == [] and resultat["avertissements"] == []
    assert resultat["crees"] == 1
    assert Beneficiaire.objects.exclude(id=beneficiaire.id).get().types_activite.get() == maraichage
