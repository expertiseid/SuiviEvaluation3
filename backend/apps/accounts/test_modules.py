"""Droits par module réglés utilisateur par utilisateur (voir apps.core.modules)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, NIVEAU_ACCES_LECTURE_SEULE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.projects.models import Activite, Projet

from .models import User


def _client_jwt(username):
    """Authentification réelle par jeton : le contrôle des modules se fait avant la vue."""
    client = APIClient()
    jeton = client.post("/api/v1/auth/token/", {"username": username, "password": "x"}).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton}")
    return client


def _point(client, activite, mois):
    return client.post(
        "/api/v1/points-suivi/",
        {"activite": activite.id, "periode_debut": f"2026-{mois}-01", "periode_fin": f"2026-{mois}-28", "quantite_realisee": 1},
        format="json",
    )


@pytest.mark.django_db
def test_droits_par_module_et_par_utilisateur(settings):
    settings.DOUBLE_AUTH_OBLIGATOIRE = False  # connexion par mot de passe seul (second facteur : test_double_auth.py)
    User.objects.create_user(username="adm_mod", password="x", role=ROLE_ADMIN)
    charge = User.objects.create_user(
        username="se_mod", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE,
        acces_modules={"/beneficiaires": "MASQUE", "/projets": "LECTURE"},
    )
    projet = Projet.objects.create(nom="P", code="MOD-1", date_debut="2026-01-01", date_fin="2026-12-31")
    activite = Activite.objects.create(projet=projet, libelle="A", quantite_prevue=10)

    client = _client_jwt("se_mod")
    assert client.get("/api/v1/utilisateurs/me/").data["acces_modules"] == {"/beneficiaires": "MASQUE", "/projets": "LECTURE"}
    assert client.get("/api/v1/beneficiaires/").status_code == 403  # caché : refusé même en lecture
    # Projets en consultation : lecture permise, écriture refusée.
    assert client.get(f"/api/v1/projets/{projet.id}/").status_code == 200
    assert client.patch(f"/api/v1/activites/{activite.id}/", {"libelle": "B"}, format="json").status_code == 403
    # Module non réglé : suit le niveau d'accès (ici écriture).
    assert _point(client, activite, "01").status_code == 201
    assert client.get("/api/v1/documents/").status_code == 200

    # Lecture seule par défaut, mais création permise dans le Suivi.
    charge.niveau_acces = NIVEAU_ACCES_LECTURE_SEULE
    charge.acces_modules = {"/suivi": "ECRITURE"}
    charge.save()
    assert _point(client, activite, "02").status_code == 201
    assert client.post("/api/v1/indicateurs/", {"libelle": "I", "unite": "u"}, format="json").status_code == 403

    admin = _client_jwt("adm_mod")
    assert admin.get("/api/v1/beneficiaires/").status_code == 200
    # Seul l'administrateur règle les droits ; valeurs contrôlées.
    assert client.patch(f"/api/v1/utilisateurs/{charge.id}/", {"acces_modules": {}}, format="json").status_code == 403
    r = admin.patch(f"/api/v1/utilisateurs/{charge.id}/", {"acces_modules": {"/suivi": "TOUT"}}, format="json")
    assert r.status_code == 400
