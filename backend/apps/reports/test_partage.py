"""Lot 5 : liens de partage publics, en lecture seule et révocables."""
import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHEF_PROJET
from apps.accounts.models import User
from apps.indicators.models import Indicateur
from apps.projects.models import Activite, Projet

from .models import LienPartage


@pytest.mark.django_db
def test_liens_de_partage():
    admin = User.objects.create_user(username="adm_part", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    projet = Projet.objects.create(nom="P", code="PART-1", date_debut="2026-01-01", date_fin="2026-12-31")
    Activite.objects.create(projet=projet, libelle="Forages")
    Indicateur.objects.create(projet=projet, libelle="Taux d'accès", unite="%", valeur_cible=80, frequence_collecte="ANNUELLE")

    lien = client.post("/api/v1/liens-partage/", {"type": "SUIVI_PROJET", "projet": projet.id, "contenu": "INDICATEURS", "libelle": "Bailleur"}, format="json")
    assert lien.status_code == 201 and len(lien.data["jeton"]) >= 40
    assert client.post("/api/v1/liens-partage/", {"type": "SUIVI_PROJET"}, format="json").status_code == 400

    public = APIClient()
    public.credentials(HTTP_AUTHORIZATION="Bearer jeton-perime")  # un jeton invalide du navigateur ne gêne pas
    jeton = lien.data["jeton"]
    description = public.get(f"/api/v1/public/partage/{jeton}/")
    assert description.status_code == 200 and description.data["projet"]["code"] == "PART-1"
    suivi = public.get(f"/api/v1/public/partage/{jeton}/suivi/").data
    assert suivi["activites"] == [] and len(suivi["indicateurs"]) == 1  # indicateurs seulement
    assert public.get(f"/api/v1/public/partage/{jeton}/dashboard/").status_code == 404  # pas ce type de page
    assert public.get(f"/api/v1/public/partage/{jeton}/menu/").status_code == 200
    assert LienPartage.objects.get(jeton=jeton).nombre_consultations == 1
    # Aucune écriture possible par le lien.
    assert public.post(f"/api/v1/public/partage/{jeton}/suivi/", {}).status_code == 405

    # Désactivé ou expiré : plus rien.
    client.patch(f"/api/v1/liens-partage/{lien.data['id']}/", {"actif": False}, format="json")
    assert public.get(f"/api/v1/public/partage/{jeton}/").status_code == 404
    client.patch(f"/api/v1/liens-partage/{lien.data['id']}/", {"actif": True, "expire_le": str(datetime.date.today() - datetime.timedelta(days=1))}, format="json")
    assert public.get(f"/api/v1/public/partage/{jeton}/suivi/").status_code == 404

    # Tableau de bord : projets visibles par le créateur du lien.
    tdb = client.post("/api/v1/liens-partage/", {"type": "TABLEAU_DE_BORD", "projet": projet.id}, format="json").data
    assert tdb["projet"] is None
    assert public.get(f"/api/v1/public/partage/{tdb['jeton']}/dashboard/").data["nombre_projets"] == 1
    assert public.get(f"/api/v1/public/partage/{tdb['jeton']}/configuration/").data["peut_modifier"] is False

    # Un chef de projet ne voit et ne partage que ses projets, et seulement ses liens.
    chef = User.objects.create_user(username="chef_part", password="x", role=ROLE_CHEF_PROJET, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    client_chef = APIClient()
    client_chef.force_authenticate(chef)
    assert client_chef.post("/api/v1/liens-partage/", {"type": "SUIVI_PROJET", "projet": projet.id}, format="json").status_code == 403
    assert client_chef.get("/api/v1/liens-partage/").data["count"] == 0
