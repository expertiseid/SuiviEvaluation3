"""Langue des fichiers produits par le serveur : traduction des rapports, exports et modèles d'import."""
import pytest
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from apps.core import langues
from apps.core.langues import en_langue, traduire, traduire_classeur, traduire_html, traduire_modele, vers_francais
from apps.core.models import TraductionCorrigee

CATALOGUE_TEST = {
    "Budget alloué": "Allocated budget",
    "Généré le {0}": "Generated on {0}",
    "Rapport de suivi du projet {0}": "Project monitoring report {0}",
    "Par {0}": "By {0}",
    "En cours": "In progress",
    "Oui": "Yes",
    "Projet": "Project",
}


@pytest.fixture
def catalogue_test(monkeypatch, db):
    monkeypatch.setitem(langues._catalogues, "en", CATALOGUE_TEST)
    monkeypatch.setitem(langues._catalogues, "de", {"Oui": "Ja", "En cours": "Laufend"})
    monkeypatch.setattr(langues, "_modeles", {})
    monkeypatch.setattr(langues, "_corrections", {"valeurs": {}, "instant": 0.0, "fusionnes": {}})
    monkeypatch.setattr(langues, "_inverse", {"index": None, "instant": None})


def test_traduire(catalogue_test):
    # Hors d'une langue active, rien ne change (imports, messages d'erreur).
    assert traduire("Budget alloué") == "Budget alloué"
    with en_langue("en"):
        assert traduire("Budget alloué") == "Allocated budget"
        assert traduire("  Budget alloué ") == "  Allocated budget "
        # Valeurs insérées : retrouvées d'après le modèle, puis remises en place.
        assert traduire("Généré le 29/10/2026") == "Generated on 29/10/2026"
        assert traduire("Rapport de suivi du projet PRJ-1") == "Project monitoring report PRJ-1"
        # Modèle trop court pour être reconnu seul (« Par {0} ») : traduit explicitement.
        assert traduire("Par région") == "Par région"
        assert traduire_modele("Par {0}", "région") == "By région"
        assert traduire("Donnée saisie") == "Donnée saisie"
    with en_langue("xx"):
        assert traduire("Budget alloué") == "Budget alloué"


def test_correction_administrateur_appliquee(catalogue_test):
    TraductionCorrigee.objects.create(langue="en", source="Budget alloué", traduction="Budget allotted")
    with en_langue("en"):
        assert traduire("Budget alloué") == "Budget allotted"


def test_traduire_html(catalogue_test):
    document = (
        "<html><head><style>td { color: red; } /* En cours */</style></head><body>"
        '<h1 title="Projet">Rapport de suivi du projet A &amp; B</h1><td>En cours</td><td>Kaya</td></body></html>'
    )
    with en_langue("en"):
        traduit = traduire_html(document)
    assert "Project monitoring report A &amp; B" in traduit
    assert "<td>In progress</td><td>Kaya</td>" in traduit
    assert 'title="Project"' in traduit
    assert "/* En cours */" in traduit  # styles intacts
    with en_langue("ar"):
        assert traduire_html("<html><body>x</body></html>").startswith('<html dir="rtl" lang="ar"')


def test_vers_francais(catalogue_test):
    assert vers_francais("In progress") == "En cours"
    assert vers_francais(" ja ") == "Oui"
    assert vers_francais("Donnée saisie") == "Donnée saisie"
    assert vers_francais(None) is None


def test_traduire_classeur(catalogue_test):
    wb = Workbook()
    feuille = wb.active
    feuille.title = "Projet"
    feuille.append(["Budget alloué", "=SUM(A1:A2)", 12])
    liste = DataValidation(type="list", formula1='"En cours,Oui"')
    feuille.add_data_validation(liste)
    with en_langue("en"):
        traduire_classeur(wb)
    assert feuille.title == "Project"
    assert [c.value for c in feuille[1]] == ["Allocated budget", "=SUM(A1:A2)", 12]
    assert liste.formula1 == '"In progress,Yes"'
    with en_langue("ar"):
        traduire_classeur(wb)
    assert feuille.sheet_view.rightToLeft
