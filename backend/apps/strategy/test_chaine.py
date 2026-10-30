"""Chaîne des documents stratégiques : rattachements, avertissements, remontée, import Excel."""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Activite, Projet

from .models import CadreStrategique, ElementStrategique, TypeDocument, TypeNiveau


@pytest.fixture
def client(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="adm_chaine", password="x", role=ROLE_ADMIN))
    return c


def _document(nom, maillon, parent=None, element_parent=None):
    document = CadreStrategique.objects.create(nom=nom, type_document=maillon, document_parent=parent, element_parent=element_parent)
    niveau = TypeNiveau.objects.create(cadre_strategique=document, nom_niveau="Axe", ordre=1)
    return document, niveau


@pytest.fixture
def chaine(db):
    """Cadre → Programme → Pilier (3 maillons), un axe chacun, le pilier contribue à l'axe 2 du programme."""
    TypeDocument.objects.all().delete()
    cadre_t = TypeDocument.objects.create(nom="Cadre stratégique", nom_pluriel="Cadres", ordre=1)
    programme_t = TypeDocument.objects.create(nom="Programme", nom_pluriel="Programmes", ordre=2)
    pilier_t = TypeDocument.objects.create(nom="Pilier", nom_pluriel="Piliers", ordre=3)
    cadre, n_cadre = _document("Cadre national", cadre_t)
    axe_cadre = ElementStrategique.objects.create(type_niveau=n_cadre, code="AXE1", nom="Capital humain")
    programme, n_prog = _document("Programme X", programme_t, cadre, axe_cadre)
    p1 = ElementStrategique.objects.create(type_niveau=n_prog, code="P1", nom="Éducation")
    p2 = ElementStrategique.objects.create(type_niveau=n_prog, code="P2", nom="Santé")
    pilier, n_pil = _document("Pilier Santé", pilier_t, programme)
    axe_pilier = ElementStrategique.objects.create(type_niveau=n_pil, code="S1", nom="Centres de santé", contribue_a=p2)
    projet = Projet.objects.create(nom="Projet santé", code="PS-1", date_debut="2026-01-01", date_fin="2026-12-31",
                                   cadre_strategique=pilier, element_strategique=axe_pilier)
    Activite.objects.create(projet=projet, libelle="Construire des centres", budget_alloue=1000)
    return {"types": (cadre_t, programme_t, pilier_t), "cadre": cadre, "programme": programme, "pilier": pilier,
            "axe_cadre": axe_cadre, "p1": p1, "p2": p2, "axe_pilier": axe_pilier, "projet": projet}


@pytest.mark.django_db
def test_remontee_sur_toute_la_chaine(client, chaine):
    """L'activité du projet du pilier arrive sur P2 du programme (contribution), et sur l'axe du cadre."""
    programme = client.get(f"/api/v1/cadres-strategiques/{chaine['programme'].id}/recap-axes/").data
    assert [(a["libelle"], a["axe"]) for a in programme["activites"]] == [("Construire des centres", chaine["p2"].id)]
    cadre = client.get(f"/api/v1/cadres-strategiques/{chaine['cadre'].id}/recap-axes/").data
    assert [a["axe"] for a in cadre["activites"]] == [chaine["axe_cadre"].id]
    recap = client.get(f"/api/v1/cadres-strategiques/{chaine['cadre'].id}/recap/").data
    assert [(p["code"], p["via_document"]) for p in recap["projets"]] == [("PS-1", "Pilier Santé")]
    suivi = {e["code"]: e["nombre_projets"] for e in client.get(f"/api/v1/cadres-strategiques/{chaine['programme'].id}/suivi/").data["elements"]}
    assert suivi == {"P1": 0, "P2": 1}


@pytest.mark.django_db
def test_rattachements_controles_et_sauts_signales(client, chaine):
    cadre_t, programme_t, pilier_t = chaine["types"]
    # Un pilier rattaché directement au cadre : accepté, avec un avertissement de saut.
    r = client.post("/api/v1/cadres-strategiques/", {"nom": "Pilier direct", "type_document": pilier_t.id,
                                                       "document_parent": chaine["cadre"].id}, format="json")
    assert r.status_code == 201 and "Programme" in r.data["alertes_chaine"][0]
    # Un programme rattaché à un pilier (maillon en dessous) : refusé.
    r = client.post("/api/v1/cadres-strategiques/", {"nom": "Mauvais", "type_document": programme_t.id,
                                                       "document_parent": chaine["pilier"].id}, format="json")
    assert r.status_code == 400
    # Élément de rattachement qui n'appartient pas au document parent : refusé.
    r = client.post("/api/v1/cadres-strategiques/", {"nom": "Mauvais 2", "type_document": pilier_t.id,
                                                       "document_parent": chaine["programme"].id,
                                                       "element_parent": chaine["axe_cadre"].id}, format="json")
    assert r.status_code == 400
    # Contribution vers un élément d'un maillon en dessous : refusée ; saut : avertissement.
    r = client.patch(f"/api/v1/elements-strategiques/{chaine['p1'].id}/", {"contribue_a": chaine["axe_pilier"].id}, format="json")
    assert r.status_code == 400
    r = client.patch(f"/api/v1/elements-strategiques/{chaine['axe_pilier'].id}/", {"contribue_a": chaine["axe_cadre"].id}, format="json")
    assert r.status_code == 200 and any("sauté" in m for m in r.data["alertes_chaine"])
    # Le projet n'est pas au dernier maillon s'il est rattaché au programme : signalé par la cohérence.
    Projet.objects.filter(id=chaine["projet"].id).update(cadre_strategique=chaine["programme"], element_strategique=None)
    messages = [i["message"] for i in client.get(f"/api/v1/projets/{chaine['projet'].id}/coherence/").data]
    assert any("Pilier" in m and "sauté" in m for m in messages)
    # Liste par maillon.
    assert [d["nom"] for d in client.get("/api/v1/cadres-strategiques/", {"type_document": programme_t.id}).data["results"]] == ["Programme X"]


@pytest.mark.django_db
def test_chaine_excel_aller_retour(client, chaine):
    contenu = client.get("/api/v1/cadres-strategiques/chaine/export/").content
    wb = load_workbook(io.BytesIO(contenu))
    assert {"Maillons", "Documents", "Éléments"} <= set(wb.sheetnames)
    # On repart de zéro sur les liens, puis on réimporte le fichier exporté.
    ElementStrategique.objects.update(contribue_a=None)
    CadreStrategique.objects.update(document_parent=None, element_parent=None)
    fichier = io.BytesIO(contenu)
    fichier.name = "chaine.xlsx"
    rapport = client.post("/api/v1/cadres-strategiques/chaine/importer/", {"fichier": fichier}, format="multipart").data
    assert rapport["erreurs"] == [] and rapport["documents_crees"] == 0
    assert CadreStrategique.objects.get(id=chaine["programme"].id).element_parent_id == chaine["axe_cadre"].id
    assert ElementStrategique.objects.get(id=chaine["axe_pilier"].id).contribue_a_id == chaine["p2"].id
    # Nouveau document dans le fichier, qui saute un maillon : créé, rattaché, avertissement.
    wb = load_workbook(io.BytesIO(contenu))
    wb["Documents"].append(["Pilier Eau", "Pilier", "Cadre national", "AXE1", ""])
    wb["Éléments"].append(["Pilier Eau", "Axe", "E1", "Forages", "", "AXE1"])
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "chaine.xlsx"
    rapport = client.post("/api/v1/cadres-strategiques/chaine/importer/", {"fichier": sortie}, format="multipart").data
    assert rapport["erreurs"] == [] and rapport["documents_crees"] == 1 and rapport["elements_crees"] == 1
    assert any("Programme" in a["message"] for a in rapport["avertissements"])
    eau = CadreStrategique.objects.get(nom="Pilier Eau")
    assert eau.document_parent_id == chaine["cadre"].id and eau.type_document.nom == "Pilier"
    assert ElementStrategique.objects.get(code="E1").contribue_a_id == chaine["axe_cadre"].id
