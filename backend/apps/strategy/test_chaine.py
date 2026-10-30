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


@pytest.mark.django_db
def test_fiche_document_comme_un_projet(client, chaine):
    """Fiche d'un pilier : bailleurs (créés par leur nom), budget recalculé, dates contrôlées, Excel."""
    from apps.partners.models import Bailleur

    url = f"/api/v1/cadres-strategiques/{chaine['pilier'].id}/"
    r = client.patch(url, {"code": "PS", "statut": "EN_COURS", "date_debut": "2026-01-01", "date_fin": "2028-12-31",
                           "fonds_propres": "1000000", "responsable_nom": "Direction santé", "cible_totale": 5000,
                           "bailleurs": [{"nom": "Banque mondiale", "montant": "4000000"}]}, format="json")
    assert r.status_code == 200, r.data
    assert float(r.data["budget_total"]) == 5000000
    assert [f["bailleur_nom"] for f in r.data["financements"]] == ["Banque mondiale"]
    # Remplacer la liste retire le bailleur absent ; un nom inconnu crée le bailleur.
    r = client.patch(url, {"bailleurs": [{"nom": "banque mondiale", "montant": "1000000"}, {"nom": "AFD", "montant": "2000000"}]}, format="json")
    assert float(r.data["budget_total"]) == 4000000 and len(r.data["financements"]) == 2
    assert Bailleur.objects.filter(nom__iexact="banque mondiale").count() == 1
    assert client.patch(url, {"date_fin": "2025-01-01"}, format="json").status_code == 400
    assert client.patch(url, {"bailleurs": [{"nom": "AFD", "montant": "1"}, {"nom": "afd", "montant": "2"}]}, format="json").status_code == 400
    # Export : colonnes de la fiche ; réimport d'une valeur modifiée.
    wb = load_workbook(io.BytesIO(client.get("/api/v1/cadres-strategiques/chaine/export/").content))
    feuille = wb["Documents"]
    entetes = [c.value for c in feuille[1]]
    ligne = next(r for r in feuille.iter_rows(min_row=2) if r[0].value == "Pilier Santé")
    assert ligne[entetes.index("Code")].value == "PS" and ligne[entetes.index("Statut")].value == "En cours"
    ligne[entetes.index("Statut")].value = "Clôturé"
    ligne[entetes.index("Date de fin")].value = "31/12/2029"
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "chaine.xlsx"
    rapport = client.post("/api/v1/cadres-strategiques/chaine/importer/", {"fichier": sortie}, format="multipart").data
    assert rapport["erreurs"] == []
    pilier = CadreStrategique.objects.get(id=chaine["pilier"].id)
    assert pilier.statut == "CLOTURE" and str(pilier.date_fin) == "2029-12-31" and pilier.code == "PS"


@pytest.mark.django_db
def test_fichier_chaine_importe_depuis_la_page_d_un_document(client, chaine):
    """
    Cas réel : le fichier « un seul pilier » (Instructions en première feuille) importé avec
    « Importer depuis Excel » d'un document : importé comme fichier de la chaîne, jamais les
    consignes comme éléments ; une cellule Maillon vide garde le maillon du document existant.
    """
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Instructions"
    wb.active.append(["Remplir UN SEUL pilier déjà créé sur la plateforme"])
    wb.active.append(["1. Feuille « Maillons » : laisser vide."])
    wb.create_sheet("Maillons").append(["Maillon", "Rubrique du menu"])
    documents = wb.create_sheet("Documents")
    documents.append(["Document", "Maillon", "Document parent", "Élément parent (code)", "Description", "Code", "Statut"])
    documents.append(["Pilier Santé", "", "Programme X", "P2", "", "PS", "En cours"])
    elements = wb.create_sheet("Éléments")
    elements.append(["Document", "Niveau", "Code", "Nom", "Code parent", "Contribue à (code)"])
    elements.append(["Pilier Santé", "Axe", "S2", "Maternités", "", "P2"])
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "un_pilier.xlsx"
    pilier = chaine["pilier"]
    r = client.post("/api/v1/elements-strategiques/importer/", {"fichier": sortie, "cadre_strategique": pilier.id}, format="multipart")
    assert r.status_code == 200 and r.data["erreurs"] == [], r.data
    pilier.refresh_from_db()
    assert pilier.type_document.nom == "Pilier" and pilier.code == "PS" and pilier.element_parent_id == chaine["p2"].id
    assert not TypeNiveau.objects.filter(nom_niveau__startswith="Remplir").exists()
    assert ElementStrategique.objects.get(code="S2").contribue_a_id == chaine["p2"].id


@pytest.mark.django_db
def test_structuration_ignore_la_feuille_instructions(client, chaine):
    """Modèle de structuration dont la feuille Instructions est passée en premier : elle n'est pas lue."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Instructions"
    wb.active.append(["Consignes"])
    feuille = wb.create_sheet("Plan")
    feuille.append(["Axe"])
    feuille.append(["Prévention"])
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "plan.xlsx"
    r = client.post("/api/v1/elements-strategiques/importer/", {"fichier": sortie, "cadre_strategique": chaine["pilier"].id}, format="multipart")
    assert r.status_code == 200 and r.data["elements_crees"] == 1
    assert not ElementStrategique.objects.filter(nom="Consignes").exists()


@pytest.mark.django_db
def test_modele_fiche_d_un_pilier_comme_un_projet(client, chaine):
    """
    Modèle d'un pilier (comme celui d'un projet) : Fiche préremplie, Financements, Structuration,
    Instructions ; rempli puis réimporté depuis la page du pilier, il met à jour fiche, bailleurs
    et structuration (avec « Contribue à »), sans rien dupliquer au second import.
    """
    from apps.partners.models import StructureOrganisation

    StructureOrganisation.objects.create(nom="Service santé", sigle="SS", type="Service")
    pilier = chaine["pilier"]
    contenu = client.get("/api/v1/elements-strategiques/modele-import/", {"cadre_strategique": pilier.id}).content
    wb = load_workbook(io.BytesIO(contenu))
    assert wb.sheetnames == ["Fiche", "Financements", "Structuration", "Instructions"]
    fiche = wb["Fiche"]
    lignes = {r[0].value: r[1] for r in fiche.iter_rows()}
    assert lignes["Nom du document"].value == "Pilier Santé" and lignes["Rattaché à (nom exact du document au-dessus)"].value == "Programme X"
    lignes["Code"].value = "PS"
    lignes["Statut (En préparation / En cours / Clôturé)"].value = "En cours"
    lignes["Date de début (AAAA-MM-JJ)"].value = "2026-01-01"
    lignes["Fonds propres (FCFA)"].value = 1000
    lignes["Éléments de rattachement (codes séparés par ; — le premier compte)"].value = "P2; P1; INCONNU"
    lignes["Services chargés (sigles ou noms séparés par ;)"].value = "SS; Inconnu"
    lignes["Cible femmes"].value = 300
    wb["Financements"].append(["Banque mondiale", "Institutionnel", 4000])
    structuration = wb["Structuration"]
    assert [c.value for c in structuration[2]][-1] == "Contribue à (code)"
    entetes = [c.value for c in structuration[2] if c.value]
    ligne = [""] * len(entetes)
    ligne[0], ligne[-1] = "S2 — Maternités", "P2"
    structuration.append(ligne)
    sortie = io.BytesIO()
    wb.save(sortie)
    for _ in range(2):
        sortie.seek(0)
        sortie.name = "pilier.xlsx"
        r = client.post("/api/v1/elements-strategiques/importer/", {"fichier": sortie, "cadre_strategique": pilier.id}, format="multipart")
        assert r.status_code == 200 and r.data["erreurs"] == [], r.data
    pilier.refresh_from_db()
    assert (pilier.code, pilier.statut, str(pilier.date_debut), pilier.cible_femmes) == ("PS", "EN_COURS", "2026-01-01", 300)
    assert float(pilier.budget_total) == 5000 and pilier.element_parent_id == chaine["p2"].id
    # Plusieurs éléments : P2 compte, P1 pour information ; un code inconnu est signalé.
    assert [e.code for e in pilier.elements_parents_secondaires.all()] == ["P1"]
    assert any("INCONNU" in a["message"] for a in r.data["avertissements"])
    assert [s.sigle for s in pilier.structures.all()] == ["SS"]
    assert any("Inconnu" in a["message"] for a in r.data["avertissements"])
    assert ElementStrategique.objects.filter(code="S2").count() == 1
    assert ElementStrategique.objects.get(code="S2").contribue_a_id == chaine["p2"].id
    # L'export a le même format, réimportable.
    export = load_workbook(io.BytesIO(client.get(f"/api/v1/cadres-strategiques/{pilier.id}/export/").content))
    assert export.sheetnames == ["Fiche", "Financements", "Structuration", "Instructions"]
    # Un cadre stratégique (premier maillon) garde son modèle simple.
    simple = load_workbook(io.BytesIO(client.get("/api/v1/elements-strategiques/modele-import/", {"cadre_strategique": chaine["cadre"].id}).content))
    assert "Fiche" not in simple.sheetnames


@pytest.mark.django_db
def test_rattachement_a_plusieurs_elements(client, chaine):
    """Un principal qui compte, des secondaires pour information : jamais comptés deux fois."""
    pilier, p1, p2 = chaine["pilier"], chaine["p1"], chaine["p2"]
    url = f"/api/v1/cadres-strategiques/{pilier.id}/"
    r = client.patch(url, {"element_parent": p2.id, "elements_parents_secondaires": [p1.id, p2.id]}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["elements_parents_secondaires"] == [p1.id]  # le principal n'est pas répété
    # Un élément d'un autre document : refusé.
    assert client.patch(url, {"elements_parents_secondaires": [chaine["axe_cadre"].id]}, format="json").status_code == 400
    # Remontée inchangée : l'activité arrive sur P2 seulement (pas de double compte sur P1).
    suivi = {e["code"]: e["nombre_projets"] for e in client.get(f"/api/v1/cadres-strategiques/{chaine['programme'].id}/suivi/").data["elements"]}
    assert suivi == {"P1": 0, "P2": 1}
    rattaches = client.get(f"/api/v1/cadres-strategiques/{chaine['programme'].id}/").data["documents_rattaches"]
    assert rattaches[0]["elements_secondaires_noms"] == [str(p1)]
    # Fichier de la chaîne : « P2; P1 » exporté puis réimporté à l'identique.
    contenu = client.get("/api/v1/cadres-strategiques/chaine/export/").content
    feuille = load_workbook(io.BytesIO(contenu))["Documents"]
    ligne = next(r for r in feuille.iter_rows(min_row=2, values_only=True) if r[0] == "Pilier Santé")
    assert ligne[3] == "P2; P1"
    pilier.elements_parents_secondaires.clear()
    fichier = io.BytesIO(contenu)
    fichier.name = "chaine.xlsx"
    assert client.post("/api/v1/cadres-strategiques/chaine/importer/", {"fichier": fichier}, format="multipart").data["erreurs"] == []
    assert [e.code for e in pilier.elements_parents_secondaires.all()] == ["P1"]


@pytest.mark.django_db
def test_export_tableau_excel_et_pdf(client, chaine):
    """Mode Tableau exporté pour un document de n'importe quel maillon : mêmes lignes qu'à l'écran."""
    Activite.objects.filter(projet=chaine["projet"]).update(date_debut="2026-02-01", date_fin="2026-05-31")
    url = f"/api/v1/cadres-strategiques/{chaine['programme'].id}/tableau/"
    r = client.get(url, {"fichier": "xlsx", "programmation": "trimestres", "annee": 2026})
    assert r.status_code == 200
    lignes = [tuple(l) for l in load_workbook(io.BytesIO(r.content))["Tableau"].iter_rows(values_only=True)]
    entete = next(i for i, l in enumerate(lignes) if l[0] == "Code")
    assert lignes[entete + 1][2:6] == ("T1", "T2", "T3", "T4")
    corps = {l[1].strip(): l for l in lignes[entete + 2:] if l[1]}
    p2 = corps["Axe : Santé"]
    assert p2[0] == "P2" and p2[2:6] == ("X", "X", None, None) and p2[6] == 1000
    assert "Construire des centres (PS-1)" in corps and corps["Axe : Éducation"][6] is None
    # Par dates, et en PDF.
    r = client.get(url, {"fichier": "xlsx", "programmation": "dates"})
    corps = {l[1].strip(): l for l in load_workbook(io.BytesIO(r.content))["Tableau"].iter_rows(values_only=True) if l[1]}
    assert corps["Axe : Santé"][2:4] == ("01/02/2026", "31/05/2026")
    r = client.get(url, {"fichier": "pdf"})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_export_simple_structure(client, chaine):
    """Export simple : les éléments seuls (code, niveau, nom, contribution), sans activités ni chiffres."""
    url = f"/api/v1/cadres-strategiques/{chaine['pilier'].id}/tableau/"
    r = client.get(url, {"fichier": "xlsx", "contenu": "simple"})
    lignes = [tuple(l) for l in load_workbook(io.BytesIO(r.content))["Structure"].iter_rows(values_only=True)]
    entete = lignes.index(("Code", "Niveau", "Élément", "Contribue à"))
    assert lignes[entete + 1] == ("S1", "Axe", "Centres de santé", str(chaine["p2"]))
    assert len(lignes) == entete + 2  # pas d'activité
    r = client.get(url, {"fichier": "pdf", "contenu": "simple"})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_entetes_sans_accent_ni_casse(client, chaine):
    """« Contribue a (code) » (sans accent, en majuscules…) est reconnu, jamais pris pour un niveau."""
    from openpyxl import Workbook

    pilier = chaine["pilier"]
    for entete in ("Contribue a (code)", "CONTRIBUE À  (CODE)"):
        wb = Workbook()
        f = wb.active
        f.title = "Structuration"
        f.append(["Axe", entete])
        f.append(["S9 — Vaccination", "P2"])
        sortie = io.BytesIO()
        wb.save(sortie)
        sortie.seek(0)
        sortie.name = "plan.xlsx"
        r = client.post("/api/v1/elements-strategiques/importer/", {"fichier": sortie, "cadre_strategique": pilier.id}, format="multipart")
        assert r.status_code == 200 and r.data["erreurs"] == [] and r.data["niveaux_crees"] == 0, r.data
        assert ElementStrategique.objects.get(code="S9").contribue_a_id == chaine["p2"].id
        assert not ElementStrategique.objects.filter(nom="P2").exists()
    # Fichier de la chaîne : feuille « Elements » et en-têtes sans accents.
    wb = Workbook()
    wb.active.title = "Documents"
    wb.active.append(["Document", "Maillon", "Document parent", "Element parent (code)"])
    wb.active.append(["Pilier Santé", "Pilier", "Programme X", "P2"])
    elements = wb.create_sheet("Elements")
    elements.append(["Document", "Niveau", "Code", "Nom", "Code parent", "Contribue a (code)"])
    elements.append(["Pilier Santé", "Axe", "S10", "Maternités", "", "P2"])
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "chaine.xlsx"
    rapport = client.post("/api/v1/cadres-strategiques/chaine/importer/", {"fichier": sortie}, format="multipart").data
    assert rapport["erreurs"] == [] and rapport["elements_crees"] == 1
    assert ElementStrategique.objects.get(code="S10").contribue_a_id == chaine["p2"].id
    assert CadreStrategique.objects.get(id=pilier.id).element_parent_id == chaine["p2"].id


@pytest.mark.django_db
@pytest.mark.parametrize("langue", ["ar", "en", "es", "de"])
def test_canevas_traduit_rempli_dans_la_langue(client, chaine, langue):
    """
    Canevas d'un pilier exporté dans une autre langue (feuilles, libellés, choix traduits ; données
    gardées), rempli dans cette langue puis réimporté : tout est reconnu — y compris une traduction
    partagée par plusieurs textes français (« Closed » = « Clos », « Clôturé »…).
    """
    from apps.core.langues import en_langue, traduire
    from apps.partners.models import Bailleur

    pilier = chaine["pilier"]
    with en_langue(langue):
        wb = load_workbook(io.BytesIO(client.get(f"/api/v1/cadres-strategiques/{pilier.id}/export/", {"langue": langue}).content))
        cloture, consortium, oui, fondation = traduire("Clôturé"), traduire("En consortium"), traduire("Oui"), traduire("Fondation")
    fiche, financements, structuration = wb.worksheets[:3]
    assert fiche.title == traduire_en(langue, "Fiche") and fiche["A1"].value == traduire_en(langue, "Nom du document")
    assert fiche["B1"].value == "Pilier Santé"  # donnée gardée telle quelle
    ligne = {r[0].value: r[1] for r in fiche.iter_rows()}
    ligne[traduire_en(langue, "Statut (En préparation / En cours / Clôturé)")].value = cloture
    ligne[traduire_en(langue, "Type de mise en œuvre (Direct / En consortium)")].value = consortium
    ligne[traduire_en(langue, "Tout le pays (Oui / Non)")].value = oui
    financements.append(["Fondation locale", fondation, 2500])
    entetes = [c.value for c in structuration[1]]
    assert entetes[-1] == traduire_en(langue, "Contribue à (code)")
    structuration.append(["S7 — Vaccination", "P2"])
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "pilier.xlsx"
    r = client.post("/api/v1/elements-strategiques/importer/", {"fichier": sortie, "cadre_strategique": pilier.id}, format="multipart")
    assert r.status_code == 200 and r.data["erreurs"] == [], r.data
    pilier.refresh_from_db()
    assert (pilier.statut, pilier.type_mise_en_oeuvre, pilier.tout_le_pays) == ("CLOTURE", "CONSORTIUM", True)
    assert Bailleur.objects.get(nom="Fondation locale").type == "FONDATION"
    assert ElementStrategique.objects.get(code="S7").contribue_a_id == chaine["p2"].id


def traduire_en(langue, texte):
    from apps.core.langues import en_langue, traduire

    with en_langue(langue):
        return traduire(texte)
