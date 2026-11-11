"""Déconnexion après une période d'inactivité : jeton refusé une fois la période écoulée sans activité."""
import time

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.constants import ROLE_CHARGE_SE
from apps.accounts.double_auth import jetons
from apps.accounts.models import User

from . import inactivite

MOI = "/api/v1/utilisateurs/me/"
ACTIVITE = "/api/v1/session/activite/"


@pytest.fixture
def compte(db, settings):
    settings.SESSION_INACTIVITE_MIN = 30
    cache.clear()
    return User.objects.create_user(username="se_inactif", password="x", role=ROLE_CHARGE_SE)


def _client(jeton):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton}")
    return client


def test_session_active_puis_fermee_apres_inactivite(compte):
    j = jetons(compte)
    assert AccessToken(j["access"])[inactivite.MARQUE] == 30  # minuteur de l'interface
    client = _client(j["access"])
    assert client.get(MOI).status_code == 200
    assert client.post(ACTIVITE).status_code == 204

    # Période écoulée sans activité : la clé a expiré dans le cache.
    cache.delete(f"{inactivite.PREFIXE}{compte.pk}")
    reponse = client.get(MOI)
    assert reponse.status_code == 401 and reponse.data["code"] == "session_inactive"
    # Le renouvellement du jeton ne rouvre pas la session.
    renouvele = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": j["refresh"]}).data["access"]
    assert _client(renouvele).get(MOI).data["code"] == "session_inactive"
    # Nouvelle connexion : session rouverte.
    assert _client(jetons(compte)["access"]).get(MOI).status_code == 200


def test_activite_prolonge_la_session(compte):
    client = _client(jetons(compte)["access"])
    cle = f"{inactivite.PREFIXE}{compte.pk}"
    ancienne = time.time() - 120  # dernière activité notée il y a deux minutes
    cache.set(cle, ancienne, timeout=60)
    assert client.post(ACTIVITE).status_code == 204
    assert cache.get(cle) > ancienne


def test_desactivee_avec_zero(compte, settings):
    settings.SESSION_INACTIVITE_MIN = 0
    client = _client(jetons(compte)["access"])
    cache.clear()
    assert client.get(MOI).status_code == 200
