"""Export de la liste des projets (page Projets) : Excel, Word, PDF, limité aux projets visibles et affichés."""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Projet


@pytest.mark.django_db
def test_export_de_la_liste_des_projets():
    admin = User.objects.create_user(username="adm_l", password="x", role=ROLE_ADMIN)
    p1 = Projet.objects.create(nom="Puits du Nord", code="PN-1", date_debut="2026-01-01", date_fin="2027-12-31",
                               statut="EN_COURS", budget_total=1500000, chef_de_projet_nom="Awa Kaboré")
    Projet.objects.create(nom="Écoles du Sud", code="ES-2", date_debut="2026-01-01", date_fin="2026-12-31", statut="CLOTURE")
    client = APIClient()
    client.force_authenticate(admin)

    reponse = client.get("/api/v1/projets/exporter-liste/", {"fichier": "xlsx"})
    assert reponse.status_code == 200
    feuille = load_workbook(io.BytesIO(reponse.content)).active
    lignes = [[c.value for c in ligne] for ligne in feuille.iter_rows()]
    assert lignes[0][0] == "Projet" and len(lignes) == 4  # entête, 2 projets, total
    assert ["Puits du Nord", "PN-1"] == lignes[[l[0] for l in lignes].index("Puits du Nord")][:2]
    assert lignes[-1][6] == 1500000

    filtre = client.get("/api/v1/projets/exporter-liste/", {"fichier": "xlsx", "projets": str(p1.id)})
    assert load_workbook(io.BytesIO(filtre.content)).active.max_row == 3

    word = client.get("/api/v1/projets/exporter-liste/", {"fichier": "docx"})
    assert word.status_code == 200 and word.content[:2] == b"PK" and "projets_" in word["Content-Disposition"]
    pdf = client.get("/api/v1/projets/exporter-liste/", {"fichier": "pdf"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

