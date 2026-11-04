"""Journal d'audit : ajout uniquement (application et base), connexions, droits des comptes, consultation."""
import pytest
from django.db import connection, transaction
from django.db.utils import InternalError
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User

from .audit import A, auditer
from .models import EvenementAudit


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_audit", password="secret-1", role=ROLE_ADMIN)


@pytest.mark.django_db
def test_ajout_uniquement(admin):
    evenement = auditer(admin, A.EXPORT, "Essai")
    with pytest.raises(PermissionError):
        evenement.objet = "modifié"
        evenement.save()
    with pytest.raises(PermissionError):
        evenement.delete()
    with pytest.raises(PermissionError):
        EvenementAudit.objects.all().update(objet="x")
    with pytest.raises(PermissionError):
        EvenementAudit.objects.all().delete()
    for requete in ("update core_evenementaudit set objet = 'x'", "delete from core_evenementaudit"):
        with pytest.raises(InternalError), transaction.atomic(), connection.cursor() as c:
            c.execute(requete)
    assert EvenementAudit.objects.get(pk=evenement.pk).objet == "Essai"


@pytest.mark.django_db
def test_connexions_et_droits(admin, settings):
    settings.DOUBLE_AUTH_OBLIGATOIRE = False  # second facteur : apps/accounts/test_double_auth.py
    client = APIClient()
    assert client.post("/api/v1/auth/token/", {"username": "adm_audit", "password": "secret-1"}).status_code == 200
    assert client.post("/api/v1/auth/token/", {"username": "adm_audit", "password": "faux"}).status_code == 401
    assert EvenementAudit.objects.filter(action=A.CONNEXION, utilisateur_id=admin.pk).exists()
    assert EvenementAudit.objects.get(action=A.CONNEXION_ECHOUEE).details == {"identifiant": "adm_audit"}

    client.force_authenticate(admin)
    compte = User.objects.create_user(username="lecteur_audit", password="x", role=ROLE_CHARGE_SE)
    assert client.patch(f"/api/v1/utilisateurs/{compte.id}/", {"is_active": False}, format="json").status_code == 200
    droits = EvenementAudit.objects.get(action=A.PERMISSION, objet="lecteur_audit")
    assert droits.details == {"operation": "modification", "is_active": [True, False]}
    assert droits.utilisateur_id == admin.pk


@pytest.mark.django_db
def test_consultation_reservee_et_export(admin):
    auditer(admin, A.CONFIGURATION, "Catégorie « Retard »", operation="modification")
    lecteur = User.objects.create_user(username="se_audit", password="x", role=ROLE_CHARGE_SE)
    c = APIClient()
    c.force_authenticate(lecteur)
    assert c.get("/api/v1/journal-audit/").status_code == 403
    c.force_authenticate(admin)
    liste = c.get("/api/v1/journal-audit/", {"action": "CONFIGURATION"})
    assert liste.status_code == 200 and liste.data["results"][0]["objet"] == "Catégorie « Retard »"
    assert c.delete(f"/api/v1/journal-audit/{liste.data['results'][0]['id']}/").status_code == 405
    export = c.get("/api/v1/journal-audit/exporter/")
    assert export.status_code == 200 and export["Content-Type"].startswith("application/vnd.openxml")
    assert EvenementAudit.objects.filter(action=A.EXPORT, objet="Journal d'audit").exists()
