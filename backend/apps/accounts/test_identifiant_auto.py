"""Création d'un utilisateur sans identifiant : il est tiré de l'adresse courriel."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User


@pytest.mark.django_db
def test_identifiant_tire_du_courriel():
    admin = User.objects.create_user(username="adm_i", password="x", role=ROLE_ADMIN)
    User.objects.create_user(username="awa.kabore", password="x", role=ROLE_CHARGE_SE)
    client = APIClient()
    client.force_authenticate(admin)
    donnees = {"email": "Awa.Kabore@exemple.org", "password": "Motdepasse-solide-2026", "role": ROLE_CHARGE_SE,
               "niveau_acces": "LECTURE_ECRITURE"}
    reponse = client.post("/api/v1/utilisateurs/", donnees, format="json")
    assert reponse.status_code == 201, reponse.data
    assert User.objects.get(email="Awa.Kabore@exemple.org").username == "awa.kabore2"  # « awa.kabore » déjà pris
    # Ni identifiant ni adresse : refusé avec un message clair.
    sans = client.post("/api/v1/utilisateurs/", {**donnees, "email": ""}, format="json")
    assert sans.status_code == 400 and "email" in sans.data
    # Identifiant donné (installation à une seule organisation) : gardé tel quel.
    avec = client.post("/api/v1/utilisateurs/", {**donnees, "email": "issa@exemple.org", "username": "issa_o"}, format="json")
    assert avec.status_code == 201 and User.objects.filter(username="issa_o").exists()
