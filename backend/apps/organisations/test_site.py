"""Site vitrine : actualités et partenaires gérés par la console Expertise-ID, lus sans compte."""
import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User

pytestmark = pytest.mark.django_db(databases=["default", "central"])


def _png():
    sortie = io.BytesIO()
    Image.new("RGB", (40, 20), "teal").save(sortie, "PNG")
    return SimpleUploadedFile("image.png", sortie.getvalue(), content_type="image/png")


@pytest.fixture
def console(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client = APIClient()
    client.force_authenticate(User.objects.create_superuser(username="op_site", password="x", email="op@expertise-id.com", role="ADMIN"))
    return client


def test_actualites(console):
    publique = console.post("/api/v1/console/site/actualites/", {
        "titre": "Nouvelle version", "resume": "Résumé", "contenu": "Premier paragraphe.\n\nSecond.", "date_publication": "2026-11-04",
        "publiee": "true", "image": _png(),
        "traductions": json.dumps({"en": {"titre": "New version", "inconnu": "x"}, "xx": {"titre": "?"}}),
    }, format="multipart")
    assert publique.status_code == 201, publique.content
    assert publique.data["traductions"] == {"en": {"titre": "New version"}}  # langues et champs prévus seulement
    console.post("/api/v1/console/site/actualites/", {"titre": "Brouillon", "date_publication": "2026-11-05"}, format="json")

    anonyme = APIClient()
    liste = anonyme.get("/api/v1/public/site/actualites/", {"langue": "en"}).data
    assert [a["titre"] for a in liste] == ["New version"]  # le brouillon n'apparaît pas
    assert liste[0]["resume"] == "Résumé"  # pas de traduction : le français
    detail = anonyme.get(f"/api/v1/public/site/actualites/{liste[0]['id']}/").data
    assert detail["contenu"].startswith("Premier paragraphe")
    assert anonyme.get(liste[0]["image"].split("testserver")[1]).status_code == 200
    # Image refusée si ce n'est pas une image.
    faux = SimpleUploadedFile("faux.png", b"pas une image", content_type="image/png")
    assert console.post("/api/v1/console/site/actualites/", {"titre": "X", "date_publication": "2026-11-04", "image": faux},
                        format="multipart").status_code == 400


def test_partenaires_et_droits(console):
    console.post("/api/v1/console/site/partenaires/", {"nom": "Visible", "categorie": "FINANCIER", "logo": _png()}, format="multipart")
    masque = console.post("/api/v1/console/site/partenaires/", {"nom": "Masqué", "visible": False}, format="json").data
    anonyme = APIClient()
    assert [p["nom"] for p in anonyme.get("/api/v1/public/site/partenaires/").data] == ["Visible"]
    assert anonyme.get(f"/api/v1/public/site/images/partenaire/{masque['id']}/").status_code == 404
    # Ni un visiteur ni un administrateur d'organisation ne gèrent le site.
    assert anonyme.get("/api/v1/console/site/partenaires/").status_code in (401, 403)
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_org", password="x", role="ADMIN"))
    assert admin.post("/api/v1/console/site/partenaires/", {"nom": "Intrus"}, format="json").status_code == 403
