"""Lot 5 : rallonges de fonds d'un bailleur, avec motif."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Projet

from .models import Bailleur


@pytest.mark.django_db
def test_rallonge_de_fonds():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_ral", password="x", role=ROLE_ADMIN))
    projet = Projet.objects.create(nom="P", code="RAL-1", date_debut="2026-01-01", date_fin="2026-12-31", fonds_propres=100)
    bailleur = Bailleur.objects.create(nom="Fonds ZZ")
    financement = client.post("/api/v1/financements/", {"projet": projet.id, "bailleur": bailleur.id, "montant_finance": 1000}).data

    # Motif et montant positif obligatoires.
    assert client.post("/api/v1/rallonges-financement/", {"financement": financement["id"], "montant": 500, "date": "2026-06-01", "motif": " "}).status_code == 400
    assert client.post("/api/v1/rallonges-financement/", {"financement": financement["id"], "montant": -5, "date": "2026-06-01", "motif": "x"}).status_code == 400

    r = client.post("/api/v1/rallonges-financement/", {"financement": financement["id"], "montant": 500, "date": "2026-06-01", "motif": "Extension à deux communes"})
    assert r.status_code == 201 and r.data["saisi_par_nom"] == "adm_ral"
    projet.refresh_from_db()
    assert projet.budget_total == 1600 and projet.financement_bailleurs_total == 1500
    f = client.get(f"/api/v1/financements/{financement['id']}/").data
    assert f["montant_total"] == "1500.00" and f["rallonges"][0]["motif"] == "Extension à deux communes"

    # Projet clôturé : plus de rallonge possible.
    Projet.objects.filter(id=projet.id).update(statut=Projet.Statut.CLOTURE)
    assert client.post("/api/v1/rallonges-financement/", {"financement": financement["id"], "montant": 1, "date": "2026-07-01", "motif": "x"}).status_code == 403
    Projet.objects.filter(id=projet.id).update(statut=Projet.Statut.EN_COURS)

    assert client.delete(f"/api/v1/rallonges-financement/{r.data['id']}/").status_code == 204
    projet.refresh_from_db()
    assert projet.budget_total == 1100
