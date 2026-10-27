import io

import pytest
from openpyxl import Workbook, load_workbook

from .models import CadreStrategique, ElementStrategique, TypeNiveau
from .services import generer_modele_import, importer_structuration_depuis_feuille


def _feuille(lignes):
    wb = Workbook()
    for ligne in lignes:
        wb.active.append(ligne)
    return wb.active


def _chaine(cadre):
    return [
        (n.nom_niveau, n.niveau_parent.nom_niveau if n.niveau_parent else None)
        for n in TypeNiveau.objects.filter(cadre_strategique=cadre).order_by("ordre")
    ]


@pytest.mark.django_db
def test_colonne_inseree_au_milieu_cree_le_niveau_a_sa_position():
    cadre = CadreStrategique.objects.create(nom="Cadre")
    importer_structuration_depuis_feuille(_feuille([["Plan", "Axe"], ["P1", ""], ["", "A1"]]), cadre)

    resultat = importer_structuration_depuis_feuille(
        _feuille([["Plan", "Programme", "Axe"], ["P1", "", ""], ["", "Prog 1", ""], ["", "", "A2"]]), cadre
    )

    assert resultat["erreurs"] == []
    assert _chaine(cadre) == [("Plan", None), ("Programme", "Plan"), ("Axe", "Programme")]
    assert ElementStrategique.objects.get(nom="A2").element_parent.nom == "Prog 1"
    # A1, saisi avant l'insertion et absent du fichier, garde son ancien parent : c'est signalé.
    assert len(resultat["avertissements"]) == 1 and "Programme" in resultat["avertissements"][0]["message"]


@pytest.mark.django_db
def test_colonne_ajoutee_a_gauche_devient_le_niveau_le_plus_haut():
    cadre = CadreStrategique.objects.create(nom="Cadre")
    importer_structuration_depuis_feuille(_feuille([["Axe"], ["A1"]]), cadre)
    importer_structuration_depuis_feuille(_feuille([["Plan", "Axe"], ["P1", ""], ["", "A2"]]), cadre)
    assert _chaine(cadre) == [("Plan", None), ("Axe", "Plan")]


@pytest.mark.django_db
def test_modele_avec_legende_se_reimporte_et_accepte_des_colonnes_en_plus():
    cadre = CadreStrategique.objects.create(nom="Cadre")
    wb = load_workbook(io.BytesIO(generer_modele_import(cadre)))
    feuille = wb["Structuration"]
    assert str(feuille["A1"].value).startswith("En jaune")
    assert feuille["A2"].comment is not None
    # Une colonne de niveau en plus, à droite.
    feuille["C2"] = "Pilier"
    feuille.append(["", "", "Pilier 1"])

    resultat = importer_structuration_depuis_feuille(feuille, cadre)

    assert resultat["erreurs"] == []
    assert [nom for nom, _ in _chaine(cadre)] == ["Orientation stratégique", "Axe d'intervention", "Pilier"]
    assert ElementStrategique.objects.get(nom="Pilier 1").element_parent.type_niveau.nom_niveau == "Axe d'intervention"
