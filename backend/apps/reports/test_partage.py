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


@pytest.mark.django_db
def test_lien_protege_par_un_mot_de_passe():
    from django.core.cache import cache

    cache.clear()  # essais limités par adresse, partagés entre les tests
    admin = User.objects.create_user(username="adm_mdp", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    Projet.objects.create(nom="P", code="MDP-1", date_debut="2026-01-01", date_fin="2026-12-31")
    trop_court = client.post("/api/v1/liens-partage/", {"type": "TABLEAU_DE_BORD", "mot_de_passe": "abc"}, format="json")
    assert trop_court.status_code == 400 and "mot_de_passe" in trop_court.data
    lien = client.post("/api/v1/liens-partage/", {"type": "TABLEAU_DE_BORD", "libelle": "Comité", "mot_de_passe": "Sahel-2026"},
                       format="json").data
    assert lien["protege"] is True and "mot_de_passe" not in lien
    assert LienPartage.objects.get(id=lien["id"]).mot_de_passe.startswith(("pbkdf2", "argon2", "bcrypt"))  # haché
    jeton = lien["jeton"]

    public = APIClient()
    # Sans le mot de passe : ni la description, ni les chiffres ; aucune consultation comptée.
    refus = public.get(f"/api/v1/public/partage/{jeton}/")
    assert refus.status_code == 403 and refus.data["code"] == "mot_de_passe_requis" and refus.data["libelle"] == "Comité"
    assert public.get(f"/api/v1/public/partage/{jeton}/dashboard/").status_code == 403
    assert LienPartage.objects.get(id=lien["id"]).nombre_consultations == 0
    assert public.post(f"/api/v1/public/partage/{jeton}/acces/", {"mot_de_passe": "faux"}, format="json").status_code == 403
    acces = public.post(f"/api/v1/public/partage/{jeton}/acces/", {"mot_de_passe": "Sahel-2026"}, format="json").data["acces"]
    public.credentials(HTTP_X_ACCES_PARTAGE=acces)
    assert public.get(f"/api/v1/public/partage/{jeton}/").status_code == 200
    assert public.get(f"/api/v1/public/partage/{jeton}/dashboard/").data["nombre_projets"] == 1
    # L'accès d'un lien ne vaut pas pour un autre lien protégé.
    autre = client.post("/api/v1/liens-partage/", {"type": "TABLEAU_DE_BORD", "mot_de_passe": "Sahel-2026"}, format="json").data
    assert public.get(f"/api/v1/public/partage/{autre['jeton']}/dashboard/").status_code == 403

    # Nouveau mot de passe : l'accès accordé avec l'ancien ne vaut plus ; « » retire la protection.
    client.patch(f"/api/v1/liens-partage/{lien['id']}/", {"mot_de_passe": "Nouveau-2027"}, format="json")
    assert public.get(f"/api/v1/public/partage/{jeton}/dashboard/").status_code == 403
    assert client.patch(f"/api/v1/liens-partage/{lien['id']}/", {"libelle": "Comité 2"}, format="json").data["protege"] is True
    assert client.patch(f"/api/v1/liens-partage/{lien['id']}/", {"mot_de_passe": ""}, format="json").data["protege"] is False
    assert APIClient().get(f"/api/v1/public/partage/{jeton}/dashboard/").status_code == 200

    # Essais en série : bloqués après 10 par minute.
    for _ in range(10):
        APIClient().post(f"/api/v1/public/partage/{autre['jeton']}/acces/", {"mot_de_passe": "x"}, format="json")
    assert APIClient().post(f"/api/v1/public/partage/{autre['jeton']}/acces/", {"mot_de_passe": "Sahel-2026"},
                            format="json").status_code == 429
    cache.clear()
