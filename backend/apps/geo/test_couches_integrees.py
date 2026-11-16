"""Couches cartographiques intégrées : jamais pour les clients (ils importent les leurs), oui en développement."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .models import LimiteAdministrative


@pytest.fixture
def client(db):
    LimiteAdministrative.objects.create(pays="BF", niveau=1, nom_niveau="Région", source="BNDT", geojson={
        "type": "FeatureCollection", "features": []})
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="adm_couches", password="x", role=ROLE_ADMIN))
    return c


def test_client_sans_couches_integrees(client, settings):
    settings.CARTE_COUCHES_INTEGREES = False
    settings.MODE_DEMO = False
    assert client.get("/api/v1/identite/").data["carte_couches_integrees"] is False
    assert client.get("/api/v1/limites-administratives/", {"pays": "BF", "niveau": 1}).status_code == 404
    assert client.get("/api/v1/localites/", {"pays": "BF", "bbox": "9,-6,15,3"}).data == {"total": 0, "localites": []}
    assert client.get("/api/v1/carte/synthese/", {"pays": "BF", "niveau": 1}).status_code == 404


def test_developpement_avec_couches_integrees(client, settings):
    settings.CARTE_COUCHES_INTEGREES = True
    assert client.get("/api/v1/identite/").data["carte_couches_integrees"] is True
    assert client.get("/api/v1/limites-administratives/", {"pays": "BF", "niveau": 1}).status_code == 200
