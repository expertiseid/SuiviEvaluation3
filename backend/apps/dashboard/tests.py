import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.partners.models import Partenaire
from apps.projects.models import Projet


@pytest.fixture
def client(db):
    admin = User.objects.create_user(username="admin_dashboard", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    bailleur = Partenaire.objects.create(nom="Bailleur X", type="BAILLEUR")
    Projet.objects.create(
        nom="A", code="A", date_debut="2025-03-01", date_fin="2025-11-30", statut="CLOTURE",
        budget_total=100, fonds_propres=10, partenaire_bailleur=bailleur, cible_femmes=5, pays=["BF"],
    )
    Projet.objects.create(nom="B", code="B", date_debut="2025-06-01", date_fin="2027-12-31", statut="EN_COURS", budget_total=200)
    Projet.objects.create(nom="C", code="C", date_debut="2024-01-01", date_fin="2026-12-31", statut="EN_COURS", budget_total=300)
    return client


def codes(client, **params):
    reponse = client.get("/api/v1/dashboard/consolide/", params)
    assert reponse.status_code == 200, reponse.data
    return sorted(p["code"] for p in reponse.data["projets"])


@pytest.mark.django_db
def test_filtres_par_periode_et_statut(client):
    assert codes(client) == ["A", "B", "C"]
    assert codes(client, annee=2025) == ["A", "B", "C"]  # actifs : chevauchent 2025
    assert codes(client, annee=2025, periode="demarres") == ["A", "B"]
    assert codes(client, annee=2025, periode="demarres_fin_prevue") == ["A"]
    assert codes(client, annee=2025, periode="demarres_termines") == ["A"]
    assert codes(client, annee=2025, periode="demarres", statuts="EN_COURS") == ["B"]
    assert codes(client, date_debut="2025-05-01", date_fin="2025-12-31", periode="demarres") == ["B"]


@pytest.mark.django_db
def test_repartitions_sur_les_projets_filtres(client):
    data = client.get("/api/v1/dashboard/consolide/", {"annee": 2025, "periode": "demarres_termines"}).data
    assert data["budget_detail"]["total"] == 100
    # Pas de financement détaillé : la part hors fonds propres va au bailleur principal.
    assert data["projets_par_bailleur"] == [{"libelle": "Bailleur X", "nombre": 1, "montant": 90, "projets": ["A"]}]
    assert data["projets_par_pays"][0]["libelle"] == "Burkina Faso"
    assert data["cibles"]["femmes"] == 5


@pytest.mark.django_db
def test_filtre_invalide(client):
    assert client.get("/api/v1/dashboard/consolide/", {"annee": "abc"}).status_code == 400
    assert client.get("/api/v1/dashboard/consolide/", {"statuts": "INCONNU"}).status_code == 400


@pytest.mark.django_db
def test_configuration_reservee_aux_roles_autorises(client):
    from apps.accounts.models import Role

    url = "/api/v1/dashboard/configuration/"
    reponse = client.put(url, {"blocs_masques": ["cibles"], "types_graphiques": {"bailleurs": "camembert"}}, format="json")
    assert reponse.status_code == 200 and reponse.data["peut_modifier"] is True  # Administrateur

    Role.objects.get_or_create(code="CHARGE_SE", defaults={"libelle": "Chargé S&E"})
    lecteur = User.objects.create_user(username="lecteur_dashboard", password="x", role="CHARGE_SE")
    autre = APIClient()
    autre.force_authenticate(lecteur)
    lu = autre.get(url).data
    assert lu["blocs_masques"] == ["cibles"] and lu["peut_modifier"] is False  # même configuration pour tous
    assert autre.put(url, {"blocs_masques": []}, format="json").status_code == 403

    Role.objects.filter(code="CHARGE_SE").update(peut_personnaliser_tableau_de_bord=True)
    assert autre.put(url, {"blocs_masques": []}, format="json").status_code == 200
    assert client.put(url, {"types_graphiques": {"x": "inconnu"}}, format="json").status_code == 400
