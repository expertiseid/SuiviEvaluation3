import pytest

from .vocabulaire import adapter_texte

ACTION = {"projet": {"singulier": "action", "pluriel": "actions", "feminin": True}}
PROGRAMME = {"cadre_strategique": {"singulier": "PROGRAMME", "pluriel": "PROGRAMMES", "feminin": False}}
MESURE = {"indicateur": {"singulier": "mesure", "pluriel": "mesures", "feminin": True}}


@pytest.mark.parametrize(
    "vocabulaire, texte, attendu",
    [
        (ACTION, "Projets", "Actions"),
        (ACTION, "Nouveau projet", "Nouvelle action"),
        (ACTION, "Supprimer le projet", "Supprimer l'action"),
        (ACTION, "Aucun projet ne correspond", "Aucune action ne correspond"),
        (ACTION, "Code du projet", "Code de l'action"),
        (ACTION, "Rattaché au projet", "Rattaché à l'action"),
        (ACTION, "Ce projet n'a pas de budget", "Cette action n'a pas de budget"),
        (ACTION, "Liste des projets", "Liste des actions"),
        (ACTION, "PROJETS", "ACTIONS"),
        (ACTION, "Chef de projet", "Chef d'action"),
        (ACTION, "Le code exact d'un projet", "Le code exact d'une action"),
        (PROGRAMME, "Cadres stratégiques", "PROGRAMMES"),
        (PROGRAMME, "Choisir le cadre stratégique", "Choisir le PROGRAMME"),
        (MESURE, "Supprimer l'indicateur", "Supprimer la mesure"),
        (MESURE, "Nom de l’indicateur", "Nom de la mesure"),
        (MESURE, "Taux par indicateur", "Taux par mesure"),
        # Mots qui contiennent le terme sans être le terme : inchangés.
        (ACTION, "Projeter la courbe", "Projeter la courbe"),
        # Sans vocabulaire choisi : texte inchangé.
        ({}, "Nouveau projet", "Nouveau projet"),
    ],
)
def test_adapter_texte(vocabulaire, texte, attendu):
    assert adapter_texte(texte, vocabulaire) == attendu


@pytest.fixture
def vocabulaire_action(db):
    from apps.dashboard.models import ConfigurationMenu

    from .vocabulaire import oublier_vocabulaire

    configuration = ConfigurationMenu.courante()
    configuration.vocabulaire = {
        "projet": {"singulier": "action", "pluriel": "actions", "feminin": True},
        "indicateur": {"singulier": "mesure", "pluriel": "mesures", "feminin": True},
    }
    configuration.save()
    oublier_vocabulaire()
    yield
    oublier_vocabulaire()


def test_modele_projet_adapte_puis_reimporte(vocabulaire_action):
    """Le modèle porte le vocabulaire de l'organisation, et se réimporte tel quel."""
    import io

    from openpyxl import load_workbook

    from apps.projects.import_excel import generer_modele_import_projet, importer_projet
    from apps.projects.models import Projet

    wb = load_workbook(io.BytesIO(generer_modele_import_projet()))
    assert "Action" in wb.sheetnames and "Projet" not in wb.sheetnames
    champs = {ligne[0].value: ligne[0] for ligne in wb["Action"].iter_rows() if ligne[0].value}
    assert "Code de l'action" in champs and "Code du projet" not in champs
    champs["Code de l'action"].offset(column=1).value = "VOC-1"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    resultat = importer_projet(buffer)

    assert resultat["erreurs"] == [], resultat["erreurs"]
    assert Projet.objects.filter(code="VOC-1").exists()


def test_import_indicateur_avec_le_terme_de_l_organisation(vocabulaire_action):
    """« Action » dans la colonne de rattachement désigne le projet."""
    from apps.indicators.import_excel import _resoudre_rattachement
    from apps.projects.models import Projet

    projet = Projet.objects.create(nom="P", code="VOC-2", date_debut="2026-01-01", date_fin="2026-12-31")
    assert _resoudre_rattachement(projet, "Action", "") == {"projet": projet}
