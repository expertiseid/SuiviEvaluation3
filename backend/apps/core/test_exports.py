"""Exports désactivés pour certains utilisateurs (apps.core.exports) et export / import global autorisé."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import double_auth
from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.core.models import IdentiteOrganisation


def _client(user):
    """Vrai jeton : le filtre des exports lit l'utilisateur dans le jeton, comme dans la plateforme."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {double_auth.jetons(user)['access']}")
    return client


@pytest.fixture
def comptes(db):
    agent = User.objects.create_user(username="agent_x", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    admin = User.objects.create_user(username="adm_x", password="x", role=ROLE_ADMIN)
    return agent, admin


@pytest.mark.django_db
def test_exports_desactives_pour_un_utilisateur(comptes):
    agent, admin = comptes
    assert _client(agent).get("/api/v1/beneficiaires/exporter/").status_code == 200  # permis par défaut
    assert _client(admin).patch(f"/api/v1/utilisateurs/{agent.id}/", {"peut_exporter": False}, format="json").status_code == 200
    agent = User.objects.get(pk=agent.pk)
    refus = _client(agent).get("/api/v1/beneficiaires/exporter/")
    assert refus.status_code == 403 and refus.json()["code"] == "export_desactive"
    assert _client(agent).get("/api/v1/beneficiaires/exporter/", {"fichier": "pdf"}).status_code == 403
    # La consultation et les modèles d'import vierges restent permis.
    assert _client(agent).get("/api/v1/beneficiaires/").status_code == 200
    assert _client(agent).get("/api/v1/beneficiaires/modele-import/").status_code == 200
    assert _client(admin).get("/api/v1/beneficiaires/exporter/").status_code == 200


@pytest.mark.django_db
def test_export_et_import_global_sur_autorisation(comptes):
    agent, admin = comptes
    assert _client(agent).get("/api/v1/transfert/exporter/").status_code == 403
    assert _client(agent).post("/api/v1/transfert/reprendre/", {"mode": "ajouter", "identifiant": "abcdefgh1"},
                               format="json").status_code == 403
    User.objects.filter(pk=agent.pk).update(export_global=True, import_global=True)
    agent = User.objects.get(pk=agent.pk)
    reponse = _client(agent).get("/api/v1/transfert/exporter/")
    assert reponse.status_code == 200
    b"".join(reponse.streaming_content)
    # Autorisé à importer : ajouter oui (fichier absent ici : 400), remplacer tout l'espace non.
    assert _client(agent).post("/api/v1/transfert/reprendre/", {"mode": "ajouter", "identifiant": "abcdefgh1"},
                               format="json").status_code == 400
    assert _client(agent).post("/api/v1/transfert/reprendre/", {"mode": "remplacer", "identifiant": "abcdefgh1"},
                               format="json").status_code == 403


@pytest.mark.django_db
def test_blocage_des_captures_regle_par_l_administrateur(comptes):
    agent, admin = comptes
    assert APIClient().get("/api/v1/identite/").json()["bloquer_captures"] is False
    assert _client(agent).patch("/api/v1/identite/", {"bloquer_captures": "true"}).status_code == 403
    assert _client(admin).patch("/api/v1/identite/", {"bloquer_captures": "true"}).json()["bloquer_captures"] is True
    assert IdentiteOrganisation.courante().bloquer_captures is True


@pytest.mark.django_db
def test_captures_reglees_pour_un_utilisateur(comptes):
    agent, admin = comptes
    assert _client(agent).get("/api/v1/utilisateurs/me/").json()["captures"] == "ORGANISATION"
    reponse = _client(admin).patch(f"/api/v1/utilisateurs/{agent.id}/", {"captures": "BLOQUEES"}, format="json")
    assert reponse.status_code == 200
    assert User.objects.get(pk=agent.pk).captures == "BLOQUEES"
    assert _client(admin).patch(f"/api/v1/utilisateurs/{agent.id}/", {"captures": "N_IMPORTE"}, format="json").status_code == 400
