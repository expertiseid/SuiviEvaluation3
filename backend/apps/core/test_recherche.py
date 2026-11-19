"""Recherche dans toute la plateforme (apps.core.recherche) : sans accents, limitée à ce que l'utilisateur voit."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.beneficiaries.models import Beneficiaire
from apps.projects.models import Projet


def _cles(reponse):
    return {g["cle"]: [r["titre"] for r in g["resultats"]] for g in reponse.json()["groupes"]}


@pytest.mark.django_db
def test_recherche_globale():
    admin = User.objects.create_user(username="adm_r", password="x", role=ROLE_ADMIN)
    projet = Projet.objects.create(nom="Écoles du Sahel", code="ES-9", date_debut="2026-01-01", date_fin="2026-12-31", statut="EN_COURS")
    Beneficiaire.objects.create(nom="Kaboré", prenom="Awa", sexe="F")
    client = APIClient()
    client.force_authenticate(admin)

    assert client.get("/api/v1/recherche/", {"q": "e"}).json() == {"groupes": []}  # trop court
    trouve = _cles(client.get("/api/v1/recherche/", {"q": "ecoles sahel"}))  # sans accents, mots dans le désordre
    assert trouve["projets"] == ["Écoles du Sahel"]
    assert _cles(client.get("/api/v1/recherche/", {"q": "KABORE"}))["beneficiaires"] == ["Kaboré Awa"]
    assert _cles(client.get("/api/v1/recherche/", {"q": "es-9"}))["projets"] == ["Écoles du Sahel"]

    # Bénéficiaires masqués pour cet utilisateur : la catégorie n'est pas cherchée.
    agent = User.objects.create_user(username="agent_r", password="x", role=ROLE_CHARGE_SE,
                                     acces_modules={"/beneficiaires": "MASQUE"})
    client.force_authenticate(agent)
    assert "beneficiaires" not in _cles(client.get("/api/v1/recherche/", {"q": "kabore"}))
    assert projet.pk
