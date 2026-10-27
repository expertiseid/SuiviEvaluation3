import pytest
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_ANIMATEUR_TERRAIN
from apps.accounts.models import User
from apps.strategy.models import CadreStrategique

from .models import Projet


@pytest.fixture
def cadre_strategique(db):
    return CadreStrategique.objects.create(nom="Cadre de test")


@pytest.mark.django_db
def test_animateur_non_affecte_ne_voit_aucun_projet(cadre_strategique):
    Projet.objects.create(
        nom="Projet X", code="PX-1", date_debut="2026-01-01", date_fin="2026-12-31",
        cadre_strategique=cadre_strategique,
    )
    animateur = User.objects.create_user(username="animateur1", password="x", role=ROLE_ANIMATEUR_TERRAIN)

    client = APIClient()
    client.force_authenticate(animateur)
    response = client.get("/api/v1/projets/")

    assert response.status_code == 200
    assert response.data["count"] == 0


@pytest.mark.django_db
def test_animateur_affecte_voit_son_projet(cadre_strategique):
    projet = Projet.objects.create(
        nom="Projet Y", code="PY-1", date_debut="2026-01-01", date_fin="2026-12-31",
        cadre_strategique=cadre_strategique,
    )
    animateur = User.objects.create_user(username="animateur2", password="x", role=ROLE_ANIMATEUR_TERRAIN)
    projet.utilisateurs_affectes.add(animateur)

    client = APIClient()
    client.force_authenticate(animateur)
    response = client.get("/api/v1/projets/")

    assert response.status_code == 200
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_admin_voit_tous_les_projets(cadre_strategique):
    Projet.objects.create(
        nom="Projet A", code="PA-1", date_debut="2026-01-01", date_fin="2026-12-31",
        cadre_strategique=cadre_strategique,
    )
    Projet.objects.create(
        nom="Projet B", code="PB-1", date_debut="2026-01-01", date_fin="2026-12-31",
        cadre_strategique=cadre_strategique,
    )
    admin = User.objects.create_user(username="admin_test", password="x", role=ROLE_ADMIN)

    client = APIClient()
    client.force_authenticate(admin)
    response = client.get("/api/v1/projets/")

    assert response.status_code == 200
    assert response.data["count"] == 2


# --- Planification à niveaux libres -------------------------------------------------


@pytest.fixture
def admin_client(db):
    admin = User.objects.create_user(username="admin_niveaux", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    return client


def _classeur_planification(entetes, lignes):
    wb = Workbook()
    feuille = wb.active
    feuille.append(entetes)
    for ligne in lignes:
        feuille.append(ligne)
    return wb


@pytest.mark.django_db
def test_import_planification_avec_niveaux_personnalises():
    """Les noms et le nombre des niveaux viennent des colonnes du fichier, sans niveau imposé."""
    from .import_excel import importer_planification
    from .models import Activite, NiveauActivite, SousActivite

    projet = Projet.objects.create(nom="Projet N", code="PN-1", date_debut="2026-01-01", date_fin="2026-12-31")
    wb = _classeur_planification(
        ["Résultat", "Pilier", "Code", "Activité", "Sous-activité", "Quantité prévue", "Budget alloué (FCFA)"],
        [
            ["Résultat 1", "", "", "", "", "", ""],
            ["", "Pilier 1", "", "", "", "", ""],
            ["", "", "A1", "Former", "", 100, 5000],
            ["", "", "", "", "Session 1", 40, ""],
            ["", "Pilier 2", "", "", "", "", ""],
            ["", "", "A2", "Équiper", "", 10, 2000],
            ["", "", "", "Orpheline sans pilier ?", "", "", ""],
        ],
    )
    resultat = importer_planification(wb.active, projet)

    assert resultat["erreurs"] == []
    assert resultat["niveaux"] == ["Résultat", "Pilier", "Activité"]
    assert resultat["elements_crees"] == 6
    assert list(NiveauActivite.objects.filter(projet=projet).values_list("nom_niveau", flat=True)) == [
        "Résultat", "Pilier", "Activité",
    ]
    former = Activite.objects.get(projet=projet, libelle="Former")
    assert former.activite_parent.libelle == "Pilier 1"
    assert former.activite_parent.activite_parent.libelle == "Résultat 1"
    assert former.code_activite == "A1" and float(former.budget_alloue) == 5000
    assert SousActivite.objects.get(libelle="Session 1").activite == former
    # La dernière ligne se rattache au dernier pilier renseigné au-dessus.
    assert Activite.objects.get(libelle="Orpheline sans pilier ?").activite_parent.libelle == "Pilier 2"


@pytest.mark.django_db
def test_import_planification_un_seul_niveau():
    from .import_excel import importer_planification
    from .models import Activite

    projet = Projet.objects.create(nom="Projet S", code="PS-1", date_debut="2026-01-01", date_fin="2026-12-31")
    wb = _classeur_planification(["Activité", "Quantité prévue"], [["Former", 10], ["Équiper", 5]])
    resultat = importer_planification(wb.active, projet)

    assert resultat["erreurs"] == [] and resultat["niveaux"] == ["Activité"]
    assert set(Activite.objects.filter(projet=projet, activite_parent__isnull=True).values_list("libelle", flat=True)) == {
        "Former", "Équiper",
    }


@pytest.mark.django_db
def test_element_enfant_herite_du_projet_de_son_parent(admin_client):
    projet = Projet.objects.create(nom="Projet E", code="PE-1", date_debut="2026-01-01", date_fin="2026-12-31")
    autre = Projet.objects.create(nom="Autre", code="PE-2", date_debut="2026-01-01", date_fin="2026-12-31")

    racine = admin_client.post("/api/v1/activites/", {"projet": projet.id, "libelle": "Résultat 1"}).data
    enfant = admin_client.post("/api/v1/activites/", {"activite_parent": racine["id"], "libelle": "Pilier 1"})
    assert enfant.status_code == 201
    assert enfant.data["projet"] == projet.id

    # Un parent d'un autre projet est refusé.
    refuse = admin_client.post(
        "/api/v1/activites/", {"projet": autre.id, "activite_parent": racine["id"], "libelle": "Intrus"}
    )
    assert refuse.status_code == 400

    detail = admin_client.get(f"/api/v1/projets/{projet.id}/").data
    assert [a["libelle"] for a in detail["activites"]] == ["Résultat 1"]
    assert [e["libelle"] for e in detail["activites"][0]["enfants"]] == ["Pilier 1"]


@pytest.mark.django_db
def test_rattachement_du_projet_a_un_element_du_cadre(admin_client, cadre_strategique):
    from apps.strategy.models import ElementStrategique, TypeNiveau

    niveau = TypeNiveau.objects.create(cadre_strategique=cadre_strategique, nom_niveau="Programme", ordre=1)
    programme = ElementStrategique.objects.create(type_niveau=niveau, nom="Programme 2")
    autre_cadre = CadreStrategique.objects.create(nom="Autre cadre")
    niveau_autre = TypeNiveau.objects.create(cadre_strategique=autre_cadre, nom_niveau="Pilier", ordre=1)
    pilier = ElementStrategique.objects.create(type_niveau=niveau_autre, nom="Pilier 1")

    # Choisir l'élément suffit : le cadre du projet est déduit.
    reponse = admin_client.post(
        "/api/v1/projets/",
        {"nom": "Projet R", "code": "PR-1", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
         "element_strategique": programme.id},
    )
    assert reponse.status_code == 201, reponse.data
    projet = Projet.objects.get(code="PR-1")
    assert projet.cadre_strategique == cadre_strategique and projet.element_strategique == programme
    assert admin_client.get(f"/api/v1/projets/{projet.id}/").data["element_strategique_libelle"] == "Programme : Programme 2"

    # Un élément d'un autre cadre que celui du projet est refusé.
    refuse = admin_client.patch(f"/api/v1/projets/{projet.id}/", {"element_strategique": pilier.id})
    assert refuse.status_code == 400



@pytest.mark.django_db
def test_modele_planification_reimporte_tel_quel_avec_niveaux_renommes():
    """La légende au-dessus des en-têtes ne gêne pas l'import ; renommer les en-têtes jaunes renomme les niveaux."""
    import io

    from openpyxl import load_workbook

    from .import_excel import COULEUR_NIVEAU, generer_modele_import_projet, importer_planification
    from .models import Activite, NiveauActivite

    wb = load_workbook(io.BytesIO(generer_modele_import_projet()))
    feuille = wb["Planification"]
    entetes = {c.value: c for c in feuille[2]}
    assert entetes["Objectif général"].fill.fgColor.rgb.endswith(COULEUR_NIVEAU)
    assert entetes["Objectif général"].comment is not None
    assert entetes["Sous-activité"].comment is None
    entetes["Objectif général"].value = "Résultat"
    entetes["Objectif spécifique"].value = "Pilier"

    projet = Projet.objects.create(nom="Projet M", code="PM-1", date_debut="2026-01-01", date_fin="2026-12-31")
    resultat = importer_planification(feuille, projet)

    assert resultat["erreurs"] == []
    assert resultat["niveaux"] == ["Résultat", "Pilier", "Activité"]
    assert list(NiveauActivite.objects.filter(projet=projet).values_list("nom_niveau", flat=True)) == [
        "Résultat", "Pilier", "Activité",
    ]
    activite = Activite.objects.get(projet=projet, code_activite="A1.1")
    assert activite.activite_parent.activite_parent.activite_parent is None


@pytest.mark.django_db
def test_modele_planification_methode_et_poids():
    """Colonnes « Méthode de calcul » et « Poids (%) » du canevas : lues à l'import, valeur inconnue signalée."""
    import io

    from openpyxl import load_workbook

    from .import_excel import generer_modele_import_projet, importer_planification
    from .models import Activite, MethodeCalcul
    from .taux import ArbreTaux

    wb = load_workbook(io.BytesIO(generer_modele_import_projet()))
    feuille = wb["Planification"]
    entetes = [c.value for c in feuille[2]]
    feuille.cell(row=feuille.max_row + 1, column=entetes.index("Activité") + 1, value="Plaidoyer")
    feuille.cell(row=feuille.max_row, column=entetes.index("Méthode de calcul") + 1, value="au doigt mouillé")

    projet = Projet.objects.create(nom="Projet C", code="PC-1", date_debut="2026-01-01", date_fin="2026-12-31")
    resultat = importer_planification(feuille, projet)

    former = Activite.objects.get(projet=projet, code_activite="A1.1")
    assert former.methode_calcul == MethodeCalcul.TACHES
    assert [float(sa.poids) for sa in former.sous_activites.all()] == [60.0, 40.0]
    assert ArbreTaux(projet).resultat(former.id).methode == MethodeCalcul.TACHES
    assert Activite.objects.get(projet=projet, libelle="Plaidoyer").methode_calcul == ""
    assert any("au doigt mouillé" in e["message"] for e in resultat["erreurs"])
