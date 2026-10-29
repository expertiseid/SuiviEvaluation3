"""Lot 6 : langues de l'interface (langue par utilisateur, par défaut, traductions corrigées)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User


@pytest.mark.django_db
def test_langues():
    anonyme = APIClient()
    r = anonyme.get("/api/v1/traductions/", {"langue": "en"})
    assert r.status_code == 200 and r.data["langue_defaut"] == "fr" and {l["code"] for l in r.data["langues"]} == {"fr", "en", "ar", "es", "de"}

    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_lang", password="x", role=ROLE_ADMIN))
    # Langue par défaut de l'organisation.
    assert admin.put("/api/v1/interface/menu/", {"langue_defaut": "en"}, format="json").status_code == 200
    assert admin.put("/api/v1/interface/menu/", {"langue_defaut": "xx"}, format="json").status_code == 400
    assert anonyme.get("/api/v1/traductions/").data["langue_defaut"] == "en"

    # Correction d'une traduction : une seule par texte et par langue.
    admin.post("/api/v1/traductions-corrigees/", {"langue": "en", "source": "Projets", "traduction": "Projects"}, format="json")
    admin.post("/api/v1/traductions-corrigees/", {"langue": "en", "source": "Projets", "traduction": "Programmes"}, format="json")
    assert anonyme.get("/api/v1/traductions/", {"langue": "en"}).data["corrections"] == {"Projets": "Programmes"}
    assert admin.post("/api/v1/traductions-corrigees/", {"langue": "fr", "source": "Projets", "traduction": "x"}, format="json").status_code == 400

    # Un utilisateur choisit sa langue ; il ne peut pas corriger les traductions.
    charge = APIClient()
    charge.force_authenticate(User.objects.create_user(username="se_lang", password="x", role=ROLE_CHARGE_SE))
    assert charge.patch("/api/v1/utilisateurs/me/", {"langue": "ar"}, format="json").data["langue"] == "ar"
    assert charge.patch("/api/v1/utilisateurs/me/", {"langue": "zz"}, format="json").status_code == 400
    assert charge.post("/api/v1/traductions-corrigees/", {"langue": "en", "source": "A", "traduction": "B"}, format="json").status_code == 403


@pytest.mark.django_db
def test_traductions_emplacements_import_journal():
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_lang2", password="x", role=ROLE_ADMIN))
    url = "/api/v1/traductions-corrigees/"
    source = 'Supprimer l\'utilisateur "{0}" ?'

    # Les emplacements {0}, {1}… doivent être conservés tels quels.
    r = admin.post(url, {"langue": "en", "source": source, "traduction": "Delete the user?"}, format="json")
    assert r.status_code == 400 and "{0}" in str(r.data["traduction"])
    assert admin.post(url, {"langue": "en", "source": source, "traduction": 'Delete "{1}"?'}, format="json").status_code == 400
    assert admin.post(url, {"langue": "en", "source": source, "traduction": 'Remove user "{0}"?'}, format="json").status_code == 201

    # Import : tout ou rien, une traduction nulle retire la correction.
    r = admin.post(url + "importer/", {"langue": "en", "lignes": [
        {"source": "Projets", "traduction": "Programmes"},
        {"source": source, "traduction": "Remove user?"},
    ]}, format="json")
    assert r.status_code == 400 and len(r.data["lignes"]) == 1
    assert [c["source"] for c in admin.get(url, {"langue": "en"}).data] == [source]
    r = admin.post(url + "importer/", {"langue": "en", "lignes": [
        {"source": "Projets", "traduction": "Programmes"},
        {"source": source, "traduction": None},
    ]}, format="json")
    assert r.data == {"corrigees": 1, "retirees": 1}
    corrections = admin.get(url, {"langue": "en"}).data
    assert [(c["source"], c["traduction"], c["modifie_par_nom"]) for c in corrections] == [("Projets", "Programmes", "adm_lang2")]
    assert admin.post(url + "importer/", {"langue": "fr", "lignes": []}, format="json").status_code == 400

    # Journal : chaque correction et chaque retrait, avec son auteur ; réservé à l'Administrateur.
    journal = admin.get(url + "journal/", {"langue": "en"}).data
    assert [(j["type"], j["source"]) for j in journal] == [("retrait", source), ("correction", "Projets"), ("correction", source)]
    assert all(j["utilisateur"] == "adm_lang2" for j in journal)
    charge = APIClient()
    charge.force_authenticate(User.objects.create_user(username="se_lang2", password="x", role=ROLE_CHARGE_SE))
    assert charge.get(url + "journal/").status_code == 403
