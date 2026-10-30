"""Planification d'un projet exportée (tableau complet, simple, canevas) et canevas réimporté."""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .models import Activite, NiveauActivite, Projet, SousActivite


@pytest.fixture
def client(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="adm_export", password="x", role=ROLE_ADMIN))
    return c


@pytest.fixture
def projet(db):
    projet = Projet.objects.create(nom="Projet export", code="PEX-1", date_debut="2026-01-01", date_fin="2027-12-31",
                                   ordre_attributs=["Lieu"])
    NiveauActivite.objects.create(projet=projet, profondeur=0, nom_niveau="Résultat")
    NiveauActivite.objects.create(projet=projet, profondeur=1, nom_niveau="Activité")
    r1 = Activite.objects.create(projet=projet, libelle="Écoles construites", code_activite="R1")
    a1 = Activite.objects.create(projet=projet, activite_parent=r1, libelle="Construire 3 classes", code_activite="A1",
                                 budget_alloue=5000, date_debut="2026-02-01", date_fin="2026-05-31", attributs={"Lieu": "Kaya"})
    SousActivite.objects.create(activite=a1, libelle="Passation des marchés", date_debut="2026-02-01", date_fin="2026-02-28")
    return projet


def _lignes(contenu, feuille):
    return [tuple(l) for l in load_workbook(io.BytesIO(contenu))[feuille].iter_rows(values_only=True)]


@pytest.mark.django_db
def test_exports_planification(client, projet):
    url = f"/api/v1/projets/{projet.id}/planification/export/"
    # Tableau complet : bandeau du résultat (budget remonté), activité, sous-activité, trimestres.
    lignes = _lignes(client.get(url, {"fichier": "xlsx", "annee": 2026}).content, "Planification")
    corps = {l[1].strip(): l for l in lignes if l[1]}
    assert corps["Résultat : Écoles construites"][0] == "R1" and corps["Résultat : Écoles construites"][-2] == 5000
    activite = corps["Construire 3 classes"]
    assert activite[2] == "Kaya" and activite[3:7] == ("X", "X", None, None)
    assert "Sous-activité : Passation des marchés" in corps
    assert client.get(url, {"fichier": "pdf"}).content[:4] == b"%PDF"
    # Export simple : la structure seule.
    lignes = _lignes(client.get(url, {"fichier": "xlsx", "contenu": "simple"}).content, "Structure")
    entete = lignes.index(("Code activité", "Niveau", "Élément"))
    assert [l[1] for l in lignes[entete + 1:]] == ["Résultat", "Activité", "Sous-activité"]
    assert client.get(url, {"fichier": "pdf", "contenu": "simple"}).content[:4] == b"%PDF"


@pytest.mark.django_db
def test_canevas_reimporte_sans_doublon(client, projet):
    contenu = client.get(f"/api/v1/projets/{projet.id}/planification/export/", {"contenu": "canevas"}).content
    wb = load_workbook(io.BytesIO(contenu))
    feuille = wb["Planification"]
    entetes = [c.value for c in feuille[2]]
    assert entetes[:5] == ["Code activité", "Résultat", "Activité", "Attribut : Lieu", "Sous-activité"]
    # Une activité ajoutée sous le résultat, une valeur modifiée.
    ligne = [""] * len(entetes)
    ligne[entetes.index("Activité")], ligne[entetes.index("Budget alloué (FCFA)")] = "Équiper les classes", 2000
    feuille.insert_rows(6)
    for c, valeur in enumerate(ligne, start=1):
        feuille.cell(row=6, column=c, value=valeur or None)
    feuille.cell(row=4, column=entetes.index("Budget alloué (FCFA)") + 1, value=6000)
    sortie = io.BytesIO()
    wb.save(sortie)
    for attendu in (1, 0):  # second import : rien de nouveau
        sortie.seek(0)
        sortie.name = "canevas.xlsx"
        r = client.post(f"/api/v1/projets/{projet.id}/planification/importer/", {"fichier": sortie}, format="multipart")
        assert r.status_code == 200 and r.data["erreurs"] == [] and r.data["elements_crees"] == attendu, r.data
    assert Activite.objects.filter(projet=projet).count() == 3 and SousActivite.objects.count() == 1
    assert float(Activite.objects.get(code_activite="A1").budget_alloue) == 6000
    assert Activite.objects.get(libelle="Équiper les classes").activite_parent.code_activite == "R1"


@pytest.mark.django_db
def test_import_refuse_si_planification_approuvee(projet):
    Projet.objects.filter(id=projet.id).update(approbation_planification=True)
    chef = User.objects.create_user(username="chef_export", password="x", role="CHEF_PROJET")
    projet.utilisateurs_affectes.add(chef)
    c = APIClient()
    c.force_authenticate(chef)
    fichier = io.BytesIO(b"x")
    fichier.name = "x.xlsx"
    r = c.post(f"/api/v1/projets/{projet.id}/planification/importer/", {"fichier": fichier}, format="multipart")
    assert r.status_code == 400 and "approuvés" in str(r.data), r.data
    assert Activite.objects.filter(projet=projet).count() == 2
