import pytest
from rest_framework.test import APIClient

from apps.core.permissions import has_global_visibility

from .constants import ROLE_ADMIN, ROLE_ANIMATEUR_TERRAIN, ROLE_CHARGE_SE
from .models import Role, User


@pytest.fixture
def client_admin(db):
    admin = User.objects.create_user(username="admin_roles", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    return client


@pytest.mark.django_db
def test_roles_systeme_crees_par_migration():
    assert Role.objects.filter(systeme=True).count() == 6
    assert Role.objects.get(code=ROLE_CHARGE_SE).visibilite_globale is True
    assert Role.objects.get(code=ROLE_ANIMATEUR_TERRAIN).visibilite_globale is False


@pytest.mark.django_db
def test_admin_cree_un_role_et_l_attribue(client_admin):
    response = client_admin.post("/api/v1/roles/", {"libelle": "Superviseur régional", "visibilite_globale": True})
    assert response.status_code == 201
    assert response.data["code"] == "SUPERVISEUR_REGIONAL"

    response = client_admin.post(
        "/api/v1/utilisateurs/", {"username": "sup1", "password": "x", "role": "SUPERVISEUR_REGIONAL"}
    )
    assert response.status_code == 201
    assert has_global_visibility(User.objects.get(username="sup1"))


@pytest.mark.django_db
def test_role_inconnu_refuse(client_admin):
    response = client_admin.post("/api/v1/utilisateurs/", {"username": "x1", "password": "x", "role": "INEXISTANT"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_suppression_role_systeme_ou_utilise_refusee(client_admin):
    systeme = Role.objects.get(code=ROLE_CHARGE_SE)
    assert client_admin.delete(f"/api/v1/roles/{systeme.id}/").status_code == 400

    role = Role.objects.create(code="STAGIAIRE", libelle="Stagiaire")
    User.objects.create_user(username="stag1", password="x", role="STAGIAIRE")
    assert client_admin.delete(f"/api/v1/roles/{role.id}/").status_code == 400

    User.objects.filter(username="stag1").delete()
    assert client_admin.delete(f"/api/v1/roles/{role.id}/").status_code == 204


@pytest.mark.django_db
def test_seul_l_admin_gere_les_roles():
    animateur = User.objects.create_user(username="anim_roles", password="x", role=ROLE_ANIMATEUR_TERRAIN)
    client = APIClient()
    client.force_authenticate(animateur)
    assert client.get("/api/v1/roles/").status_code == 200
    assert client.post("/api/v1/roles/", {"libelle": "Pirate"}).status_code == 403
