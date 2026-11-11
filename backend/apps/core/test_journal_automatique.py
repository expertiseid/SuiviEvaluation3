"""Journal d'audit automatique : exports et suppressions de tous les modules, sans doublon avec les plaintes."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Projet

from .models import EvenementAudit


@pytest.fixture
def admin(db):
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="admin_journal", password="x", role=ROLE_ADMIN))
    return client


def test_export_et_suppression_journalises(admin):
    projet = Projet.objects.create(nom="P", code="J-1", date_debut="2026-01-01", date_fin="2026-12-31")
    assert admin.get("/api/v1/beneficiaires/exporter/", {"projet": projet.pk}).status_code == 200
    export = EvenementAudit.objects.get(action="EXPORT")
    assert (export.module, export.objet, export.utilisateur) == ("beneficiaires", "/api/v1/beneficiaires/exporter/", "admin_journal")
    assert export.details == {"parametres": {"projet": str(projet.pk)}}

    assert admin.delete(f"/api/v1/projets/{projet.pk}/").status_code == 204
    suppression = EvenementAudit.objects.get(action="SUPPRESSION")
    assert (suppression.module, suppression.objet) == ("projets", f"/api/v1/projets/{projet.pk}/")


def test_rien_pour_les_lectures_les_echecs_et_les_anonymes(admin):
    assert admin.get("/api/v1/projets/").status_code == 200
    assert admin.delete("/api/v1/projets/999999/").status_code == 404
    assert APIClient().get("/api/v1/beneficiaires/exporter/").status_code == 401
    assert not EvenementAudit.objects.exists()
