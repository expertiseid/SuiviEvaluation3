"""Erreurs de l'API trouvées par l'analyse de sécurité ZAP : réponse claire, jamais d'erreur 500."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.geo.models import NiveauAdministratif, Zone


@pytest.fixture
def admin():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="admin_erreurs", password="x", role=ROLE_ADMIN))
    return client


@pytest.mark.django_db
def test_supprimer_une_zone_qui_contient_d_autres_zones(admin):
    region = NiveauAdministratif.objects.create(pays="BF", nom_niveau="Région", ordre=1)
    province = NiveauAdministratif.objects.create(pays="BF", nom_niveau="Province", ordre=2, niveau_parent=region)
    boucle = Zone.objects.create(niveau_administratif=region, nom="Boucle du Mouhoun")
    Zone.objects.create(niveau_administratif=province, parent=boucle, nom="Banwa")
    reponse = admin.delete(f"/api/v1/zones/{boucle.pk}/")
    assert reponse.status_code == 409
    assert "Suppression impossible" in reponse.json()["detail"]
    assert Zone.objects.filter(pk=boucle.pk).exists()


@pytest.mark.django_db
def test_import_structuration_avec_identifiant_invalide(admin):
    reponse = admin.post("/api/v1/elements-strategiques/importer/", {"cadre_strategique": '<!--#EXEC cmd="ls /"-->'})
    assert reponse.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("methode", ["post", "put", "patch", "delete"])
def test_envoi_sans_barre_finale_repond_404(admin, methode):
    """Une adresse d'envoi sans « / » final répond 404 (pas d'erreur 500 ni de redirection)."""
    reponse = getattr(admin, methode)("/api/v1/activites/" + "A" * 2100)
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_identifiant_non_numerique_repond_404(admin):
    """Un identifiant qui n'est pas un nombre dans une action de dossier répond 404 (pas d'erreur 500)."""
    reponse = admin.get("/api/v1/plaintes/dossiers/" + "A" * 2100 + "/apercu-message/")
    assert reponse.status_code == 404
