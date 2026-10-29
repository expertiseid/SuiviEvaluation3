"""Attributs libres de la planification : colonnes « Attribut : … » à l'import, fiche (API), exports."""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Activite, Projet, SousActivite


def _client(langue="fr"):
    client = APIClient(HTTP_ACCEPT_LANGUAGE=langue)
    client.force_authenticate(User.objects.create_user(username=f"adm_attr_{langue}", password="x", role=ROLE_ADMIN))
    return client


def _importer(client, wb):
    fichier = io.BytesIO()
    wb.save(fichier)
    fichier.seek(0)
    fichier.name = "projet.xlsx"
    return client.post("/api/v1/projets/importer/", {"fichier": fichier}, format="multipart").data


@pytest.mark.django_db
@pytest.mark.parametrize("langue", ["fr", "en", "ar"])
def test_colonnes_attributs_a_l_import(langue):
    client = _client(langue)
    wb = load_workbook(io.BytesIO(client.get("/api/v1/projets/modele-import/").content))
    feuille = next(f for f in wb.worksheets if f.max_column >= 15)  # feuille « Planification » (traduite)
    entetes = [c.value for c in feuille[2]]
    prefixe = entetes[4].split(":")[0]  # « Attribut », « Attribute », « سمة » : colonne d'exemple du modèle
    # Un attribut glissé ENTRE deux niveaux, un autre qui remplit un champ connu (« Hypothèses »).
    feuille.insert_cols(2)
    feuille.cell(2, 2).value = f"{prefixe}: Lieu"
    feuille.cell(3, 2).value = "Nord"
    hypotheses = {"fr": "Hypothèses", "en": "Assumptions", "ar": "الافتراضات"}[langue]
    feuille.cell(2, feuille.max_column + 1).value = f"{prefixe} : {hypotheses}"
    ligne_activite = next(r for r in range(3, 8) if feuille.cell(r, 4).value == "A1.1")
    feuille.cell(ligne_activite, feuille.max_column).value = "Pluies normales"
    feuille.cell(ligne_activite + 1, 6).value = "Animateur A"  # colonne d'exemple, ligne de sous-activité

    resultat = _importer(client, wb)
    assert resultat["erreurs"] == []
    assert len(resultat["niveaux"]) == 3  # aucune colonne d'attribut lue comme un niveau
    projet = Projet.objects.get(id=resultat["projet_id"])
    racine = Activite.objects.get(projet=projet, activite_parent=None)
    assert racine.attributs == {"Lieu": "Nord"}
    activite = Activite.objects.get(projet=projet, code_activite="A1.1")
    assert activite.hypotheses == "Pluies normales"
    responsable = entetes[4].split(":", 1)[1].strip()
    assert list(activite.attributs) == [responsable] and activite.attributs[responsable]
    session = SousActivite.objects.filter(activite=activite).order_by("id").first()
    assert session.attributs == {responsable: "Animateur A"}


@pytest.mark.django_db
def test_attributs_par_la_fiche_et_dans_les_exports():
    client = _client()
    projet = Projet.objects.create(nom="P", code="ATT-1", date_debut="2026-01-01", date_fin="2026-12-31")
    activite = Activite.objects.create(projet=projet, libelle="Former")
    sous_activite = SousActivite.objects.create(activite=activite, libelle="Session")
    r = client.patch(f"/api/v1/activites/{activite.id}/", {"attributs": {" Responsable ": " ONG A ", "Vide": ""}}, format="json")
    assert r.status_code == 200 and r.data["attributs"] == {"Responsable": "ONG A"}
    assert client.patch(f"/api/v1/activites/{activite.id}/", {"attributs": ["x"]}, format="json").status_code == 400
    r = client.patch(f"/api/v1/sous-activites/{sous_activite.id}/", {"attributs": {"Lieu": "Kaya"}}, format="json")
    assert r.status_code == 200 and r.data["attributs"] == {"Lieu": "Kaya"}

    classeur = load_workbook(io.BytesIO(client.get(f"/api/v1/suivi/projets/{projet.id}/exporter/excel/").content))
    feuille = classeur["Activités"]
    assert feuille.cell(1, feuille.max_column).value == "Responsable"
    assert feuille.cell(2, feuille.max_column).value == "ONG A"
    cadre = client.get(f"/api/v1/rapports/cadre-logique/{projet.id}/").data
    assert next(l for l in cadre["lignes"] if l["id"] == activite.id)["attributs"] == {"Responsable": "ONG A"}


@pytest.mark.django_db
def test_ordre_des_attributs_du_fichier():
    """Les attributs suivent l'ordre des colonnes du fichier (la base les stocke sans ordre)."""
    client = _client()
    wb = load_workbook(io.BytesIO(client.get("/api/v1/projets/modele-import/").content))
    feuille = wb["Planification"]
    derniere = feuille.max_column + 1
    feuille.cell(2, derniere).value = "Attribut : Lieu"  # après « Attribut : Responsable » (colonne E)
    ligne = next(r for r in range(3, 8) if feuille.cell(r, 3).value == "A1.1")
    feuille.cell(ligne, derniere).value = "Kaya"
    resultat = _importer(client, wb)
    projet = Projet.objects.get(id=resultat["projet_id"])
    assert projet.ordre_attributs == ["Responsable", "Lieu"]

    activite = Activite.objects.get(projet=projet, code_activite="A1.1")
    assert list(client.get(f"/api/v1/activites/{activite.id}/").data["attributs"]) == ["Responsable", "Lieu"]
    # Un attribut ajouté par la fiche se place à la suite.
    client.patch(f"/api/v1/activites/{activite.id}/", {"attributs": {**activite.attributs, "Année": "2026"}}, format="json")
    projet.refresh_from_db()
    assert projet.ordre_attributs == ["Responsable", "Lieu", "Année"]
    classeur = load_workbook(io.BytesIO(client.get(f"/api/v1/suivi/projets/{projet.id}/exporter/excel/").content))
    entetes = [c.value for c in classeur["Activités"][1]]
    assert entetes[-3:] == ["Responsable", "Lieu", "Année"]
