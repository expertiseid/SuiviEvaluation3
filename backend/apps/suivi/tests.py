import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Activite, ObjectifGeneral, ObjectifSpecifique, Projet, SousActivite

from .models import PointSuivi, TranchePlanifiee


@pytest.fixture
def contexte(db):
    admin = User.objects.create_user(username="admin_periode", password="x", role=ROLE_ADMIN)
    projet = Projet.objects.create(nom="Projet P", code="PP-1", date_debut="2026-01-01", date_fin="2027-12-31")
    og = ObjectifGeneral.objects.create(projet=projet, libelle="OG")
    os_ = ObjectifSpecifique.objects.create(objectif_general=og, libelle="OS")
    activite = Activite.objects.create(
        objectif_specifique=os_, libelle="Former", quantite_prevue=1200, budget_alloue=38000000
    )
    sous_activite = SousActivite.objects.create(activite=activite, libelle="Session", quantite_prevue=100)
    client = APIClient()
    client.force_authenticate(admin)
    periode = client.post(
        "/api/v1/periodes-planification/",
        {"projet": projet.id, "libelle": "T1 2026", "date_debut": "2026-01-01", "date_fin": "2026-03-31"},
    ).data
    return {"client": client, "admin": admin, "activite": activite, "sous_activite": sous_activite, "periode": periode}


@pytest.mark.django_db
def test_valeurs_de_periode_reprennent_les_dates_et_calculent_le_realise(contexte):
    client, activite, periode = contexte["client"], contexte["activite"], contexte["periode"]
    PointSuivi.objects.create(
        activite=activite, periode_debut="2026-02-01", periode_fin="2026-02-28",
        quantite_realisee=210, budget_realise=5000000, saisi_par=contexte["admin"],
    )
    # Hors période : ne doit pas être compté.
    PointSuivi.objects.create(
        activite=activite, periode_debut="2026-04-01", periode_fin="2026-04-30",
        quantite_realisee=999, saisi_par=contexte["admin"],
    )

    response = client.post(
        "/api/v1/tranches-planifiees/",
        {"periode": periode["id"], "activite": activite.id, "cible": 300, "budget": 9000000,
         "date_debut_prevue": "2026-02-01", "date_fin_prevue": "2026-03-31"},
    )

    assert response.status_code == 201, response.data
    assert response.data["libelle"] == "T1 2026"
    assert response.data["periode_debut"] == "2026-01-01"
    assert float(response.data["realise"]) == 210
    assert response.data["taux"] == 70.0
    assert float(response.data["budget_realise"]) == 5000000


@pytest.mark.django_db
def test_sous_activite_sans_budget_et_dates_hors_periode_refusees(contexte):
    client, sous_activite, periode = contexte["client"], contexte["sous_activite"], contexte["periode"]

    response = client.post(
        "/api/v1/tranches-planifiees/",
        {"periode": periode["id"], "sous_activite": sous_activite.id, "cible": 40, "budget": 123},
    )
    assert response.status_code == 201, response.data
    assert response.data["budget"] is None

    hors_periode = client.post(
        "/api/v1/tranches-planifiees/",
        {"periode": periode["id"], "activite": contexte["activite"].id, "cible": 1, "date_debut_prevue": "2026-05-01"},
    )
    assert hors_periode.status_code == 400


@pytest.mark.django_db
def test_une_seule_valeur_par_element_et_par_periode(contexte):
    client, activite, periode = contexte["client"], contexte["activite"], contexte["periode"]
    payload = {"periode": periode["id"], "activite": activite.id, "cible": 300}
    assert client.post("/api/v1/tranches-planifiees/", payload).status_code == 201
    assert client.post("/api/v1/tranches-planifiees/", payload).status_code == 400


@pytest.mark.django_db
def test_modifier_la_periode_met_a_jour_ses_valeurs(contexte):
    client, activite, periode = contexte["client"], contexte["activite"], contexte["periode"]
    client.post(
        "/api/v1/tranches-planifiees/",
        {"periode": periode["id"], "activite": activite.id, "cible": 300, "date_fin_prevue": "2026-03-31"},
    )

    response = client.patch(
        f"/api/v1/periodes-planification/{periode['id']}/",
        {"libelle": "Février 2026", "date_debut": "2026-02-01", "date_fin": "2026-02-28"},
    )

    assert response.status_code == 200
    tranche = TranchePlanifiee.objects.get(periode_id=periode["id"])
    assert tranche.libelle == "Février 2026"
    assert str(tranche.periode_fin) == "2026-02-28"
    assert tranche.date_fin_prevue is None  # sortie de la nouvelle période : effacée

    client.delete(f"/api/v1/periodes-planification/{periode['id']}/")
    assert not TranchePlanifiee.objects.filter(periode_id=periode["id"]).exists()


@pytest.mark.django_db
def test_indicateur_planifie_sur_la_periode(contexte):
    from apps.indicators.models import Indicateur, ValeurIndicateur

    client, periode = contexte["client"], contexte["periode"]
    indicateur = Indicateur.objects.create(
        libelle="Taux d'adoption", unite="%", valeur_cible=60, frequence_collecte="TRIMESTRIELLE",
        activite=contexte["activite"],
    )
    ValeurIndicateur.objects.create(
        indicateur=indicateur, periode_debut="2026-01-01", periode_fin="2026-03-31", valeur_realisee=12,
        saisi_par=contexte["admin"],
    )

    response = client.post(
        "/api/v1/tranches-planifiees/",
        {"periode": periode["id"], "indicateur": indicateur.id, "cible": 15, "budget": 5, "date_debut_prevue": "2026-01-10"},
    )

    assert response.status_code == 201, response.data
    assert float(response.data["realise"]) == 12
    assert response.data["taux"] == 80.0
    assert response.data["budget"] is None and response.data["date_debut_prevue"] is None


@pytest.mark.django_db
def test_exports_excel_et_pdf_de_la_periode(contexte):
    client, activite, periode = contexte["client"], contexte["activite"], contexte["periode"]
    client.post("/api/v1/tranches-planifiees/", {"periode": periode["id"], "activite": activite.id, "cible": 300})

    excel = client.get(f"/api/v1/periodes-planification/{periode['id']}/exporter/excel/")
    assert excel.status_code == 200
    assert excel["Content-Type"].startswith("application/vnd.openxmlformats")

    pdf = client.get(f"/api/v1/periodes-planification/{periode['id']}/exporter/pdf/")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_objectifs_de_periode_a_definir_par_l_utilisateur(contexte):
    client, activite, sous_activite, periode = (
        contexte["client"], contexte["activite"], contexte["sous_activite"], contexte["periode"]
    )
    activite.date_debut, activite.date_fin = "2026-01-01", "2026-12-31"
    activite.save()
    sous_activite.date_debut, sous_activite.date_fin = "2026-06-01", "2026-06-30"
    sous_activite.save()
    PointSuivi.objects.create(
        activite=activite, periode_debut="2026-02-01", periode_fin="2026-02-28",
        quantite_realisee=50, budget_realise=1000000, saisi_par=contexte["admin"],
    )

    data = client.get(f"/api/v1/periodes-planification/{periode['id']}/valeurs/").data
    lignes = {(l["type"], l.get("id")): l for l in data["lignes"]}

    # Aucun calcul automatique : objectifs à définir, mais réalisé déjà visible.
    ligne_activite = lignes[("activite", activite.id)]
    assert ligne_activite["source"] == "a_definir"
    assert ligne_activite["prevu_quantite"] is None and ligne_activite["prevu_budget"] is None
    assert float(ligne_activite["realise_quantite"]) == 50
    assert ligne_activite["dans_dates_globales"] is True
    assert lignes[("sous_activite", sous_activite.id)]["dans_dates_globales"] is False

    client.post(
        "/api/v1/tranches-planifiees/",
        {"periode": periode["id"], "activite": activite.id, "cible": 500, "budget": 2000000},
    )
    data = client.get(f"/api/v1/periodes-planification/{periode['id']}/valeurs/").data
    ligne_activite = next(l for l in data["lignes"] if l["type"] == "activite")
    assert ligne_activite["source"] == "saisi"
    assert float(ligne_activite["prevu_quantite"]) == 500
    assert ligne_activite["taux"] == 10.0
    assert data["totaux"]["nb_definis"] == 1


@pytest.mark.django_db
def test_saisie_sur_une_periode_actualise_le_suivi_global(contexte):
    client, activite, periode = contexte["client"], contexte["activite"], contexte["periode"]

    client.post(
        "/api/v1/points-suivi/",
        {"activite": activite.id, "periode_debut": "2026-01-01", "periode_fin": "2026-03-31",
         "quantite_realisee": 300, "budget_realise": 9000000, "statut": "EN_COURS"},
    )
    activite.refresh_from_db()
    assert float(activite.quantite_realisee) == 300
    assert float(activite.budget_realise) == 9000000
    assert str(activite.date_debut_reelle) == "2026-01-01"
    assert activite.date_fin_reelle is None  # pas encore réalisée

    client.post(
        "/api/v1/points-suivi/",
        {"activite": activite.id, "periode_debut": "2026-04-01", "periode_fin": "2026-06-30",
         "quantite_realisee": 900, "statut": "REALISEE"},
    )
    activite.refresh_from_db()
    assert float(activite.quantite_realisee) == 1200
    assert activite.statut == "REALISEE"
    assert str(activite.date_fin_reelle) == "2026-06-30"

    # Le réalisé de la période ne compte que la saisie faite dans ses dates.
    data = client.get(f"/api/v1/periodes-planification/{periode['id']}/valeurs/").data
    ligne = next(l for l in data["lignes"] if l["type"] == "activite")
    assert float(ligne["realise_quantite"]) == 300


@pytest.mark.django_db
def test_suivi_par_periode_saisies_taux_et_exports(contexte):
    client, activite, periode = contexte["client"], contexte["activite"], contexte["periode"]
    client.post("/api/v1/tranches-planifiees/", {"periode": periode["id"], "activite": activite.id, "cible": 400, "budget": 8000000})
    for debut, fin, quantite in (("2026-01-01", "2026-01-31", 100), ("2026-02-01", "2026-02-28", 100), ("2026-04-01", "2026-04-30", 50)):
        client.post(
            "/api/v1/points-suivi/",
            {"activite": activite.id, "periode_debut": debut, "periode_fin": fin, "quantite_realisee": quantite, "budget_realise": 1000000},
        )

    data = client.get(f"/api/v1/periodes-planification/{periode['id']}/valeurs/").data
    ligne = next(l for l in data["lignes"] if l["type"] == "activite")
    assert [str(s["periode_debut"]) for s in ligne["saisies"]] == ["2026-01-01", "2026-02-01"]  # avril hors période
    assert data["totaux"]["taux_physique"] == 50.0
    assert data["totaux"]["taux_financier"] == 25.0

    excel = client.get(f"/api/v1/periodes-planification/{periode['id']}/exporter-suivi/excel/")
    assert excel.status_code == 200
    pdf = client.get(f"/api/v1/periodes-planification/{periode['id']}/exporter-suivi/pdf/")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
