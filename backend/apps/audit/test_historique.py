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


@pytest.mark.django_db
def test_historique_limite_aux_projets_et_indicateurs():
    """Modèle inconnu ou non prévu (bénéficiaires, comptes…) : 404, jamais d'erreur serveur."""
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="u_admin_histo", password="x", role=ROLE_ADMIN))
    for chemin in ("app_label/model_name", "beneficiaries/beneficiaire", "accounts/user", "projects/activite"):
        assert client.get(f"/api/v1/audit/{chemin}/1/historique/").status_code == 404
