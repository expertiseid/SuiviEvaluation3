"""L'historique générique ne doit jamais ouvrir un contournement des règles d'accès des plaintes."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User


@pytest.mark.django_db
def test_historique_des_plaintes_refuse():
    for role in (ROLE_CHARGE_SE, ROLE_ADMIN):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(username=f"u_{role}", password="x", role=role))
        assert client.get("/api/v1/audit/plaintes/dossier/1/historique/").status_code == 404
        assert client.get("/api/v1/audit/PLAINTES/mecanisme/1/historique/").status_code == 404
