"""Canevas des objectifs d'une période : prérempli, aperçu, import (modes), erreurs, autre langue."""
import datetime
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Activite, Projet, SousActivite

from .models import PeriodePlanification, TranchePlanifiee


@pytest.fixture
def client(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="adm_periode", password="x", role=ROLE_ADMIN))
    return c


@pytest.fixture
def periode(db):
    projet = Projet.objects.create(nom="Projet période", code="PPER-1", date_debut="2026-01-01", date_fin="2027-12-31")
    activite = Activite.objects.create(projet=projet, libelle="Construire des classes", code_activite="A1",
                                       quantite_prevue=10, unite_quantite="classes", budget_alloue=9000)
    SousActivite.objects.create(activite=activite, libelle="Passation des marchés", quantite_prevue=1)
    return PeriodePlanification.objects.create(projet=projet, libelle="T1 2026", date_debut=datetime.date(2026, 1, 1),
                                               date_fin=datetime.date(2026, 3, 31))


def _envoyer(client, url, octets, mode):
    fichier = io.BytesIO(octets)
    fichier.name = "canevas.xlsx"
    return client.post(url, {"fichier": fichier, "mode": mode}, format="multipart")


def _canevas(client, periode, langue="fr"):
    return load_workbook(io.BytesIO(client.get(f"/api/v1/periodes-planification/{periode.id}/canevas/", {"langue": langue}).content))


def _remplir(wb, objectif, budget=None, debut=None, budget_sous_activite=None):
    f = wb.worksheets[0]
    entetes = [c.value for c in f[1]]
    i = 8  # « Objectif de la période » : 9e colonne (après l'identifiant et 7 colonnes grises)
    assert f.cell(row=2, column=1).value.startswith("E") and f.cell(row=3, column=1).value.startswith("S")
    f.cell(row=2, column=i + 1, value=objectif)
    f.cell(row=2, column=i + 2, value=budget)
    f.cell(row=2, column=i + 3, value=debut)
    f.cell(row=3, column=i + 2, value=budget_sous_activite)
    if budget_sous_activite:
        f.cell(row=3, column=i + 1, value=1)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue(), entetes


@pytest.mark.django_db
def test_canevas_prerempli_puis_importe(client, periode):
    base = f"/api/v1/periodes-planification/{periode.id}/canevas/"
    wb = _canevas(client, periode)
    assert wb.sheetnames == ["Objectifs de la période", "Indicateurs", "Instructions"]
    octets, entetes = _remplir(wb, 4, 3000, "2026-02-01", budget_sous_activite=50)
    assert entetes[:4] == ["Identifiant (ne pas modifier)", "Niveau", "Code", "Libellé"]
    # Aperçu : un ajout, une erreur (budget sur une sous-activité), rien d'enregistré.
    apercu = _envoyer(client, base + "apercu/", octets, "ajout").data
    assert apercu["totaux"]["ajout"] == 1 and apercu["totaux"]["erreur"] == 1
    assert TranchePlanifiee.objects.count() == 0
    # Import : l'objectif valide est enregistré, repris dans le canevas suivant.
    assert _envoyer(client, base + "importer/", octets, "ajout").data["totaux"]["ajout"] == 1
    tranche = TranchePlanifiee.objects.get(periode=periode)
    assert (float(tranche.cible), float(tranche.budget), str(tranche.date_debut_prevue)) == (4, 3000, "2026-02-01")
    assert _canevas(client, periode).worksheets[0].cell(row=2, column=9).value == 4
    # Même fichier réimporté : rien à faire ; valeur changée : ignorée en « ajout », remplacée en « mise à jour ».
    assert _envoyer(client, base + "apercu/", octets, "ajout").data["totaux"]["ajout"] == 0
    octets, _ = _remplir(_canevas(client, periode), 6, 3000, "2026-02-01")
    assert _envoyer(client, base + "importer/", octets, "ajout").data["totaux"]["ignoree"] == 1
    assert float(TranchePlanifiee.objects.get(periode=periode).cible) == 4
    assert _envoyer(client, base + "importer/", octets, "mise_a_jour").data["totaux"]["modification"] == 1
    assert float(TranchePlanifiee.objects.get(periode=periode).cible) == 6
    # Date hors période : erreur sur la cellule, rapport d'erreurs avec la feuille « Erreurs ».
    octets, _ = _remplir(_canevas(client, periode), 6, 3000, "2026-07-01")
    apercu = _envoyer(client, base + "apercu/", octets, "mise_a_jour").data
    assert apercu["lignes"][0]["erreurs"][0]["colonne"] == "Début prévu (AAAA-MM-JJ)"
    rapport = load_workbook(io.BytesIO(_envoyer(client, base + "rapport-erreurs/", octets, "mise_a_jour").content))
    assert rapport.sheetnames[0] == "Erreurs"


@pytest.mark.django_db
def test_canevas_rempli_en_arabe(client, periode):
    wb = _canevas(client, periode, "ar")
    assert wb.sheetnames[0] != "Objectifs de la période"  # traduit
    octets, _ = _remplir(wb, 3, 1500)
    r = _envoyer(client, f"/api/v1/periodes-planification/{periode.id}/canevas/importer/", octets, "ajout").data
    assert r["totaux"]["ajout"] == 1 and r["totaux"]["erreur"] == 0, r
    assert float(TranchePlanifiee.objects.get(periode=periode).cible) == 3


@pytest.mark.django_db
def test_exports_word_en_tableaux(client, periode):
    """Suivi du projet et suivi par période en Word : mis en page en tableaux (activités, indicateurs…)."""
    from docx import Document

    projet = periode.projet
    for url in (f"/api/v1/suivi/projets/{projet.id}/exporter/word/", f"/api/v1/periodes-planification/{periode.id}/exporter-suivi/word/"):
        r = client.get(url)
        assert r.status_code == 200, url
        document = Document(io.BytesIO(r.content))
        assert len(document.tables) >= 2  # résumé + activités (au moins)
        textes = [c.text for t in document.tables for ligne in t.rows for c in ligne.cells]
        assert "Construire des classes" in textes and "Passation des marchés" in textes
