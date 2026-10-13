import pytest

from .models import Beneficiaire
from .services.duplicate_detection import rechercher_doublons


@pytest.mark.django_db
def test_doublon_detecte_par_piece_identite_exacte():
    b1 = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F", numero_piece_identite="CNIB123")
    b2 = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F", numero_piece_identite="CNIB123")

    resultats = rechercher_doublons(b2)

    assert any(r["candidat"].pk == b1.pk and r["methode"] == "PIECE_IDENTITE" for r in resultats)


@pytest.mark.django_db
def test_beneficiaires_distincts_ne_sont_pas_signales():
    Beneficiaire.objects.create(nom="Sawadogo", prenom="Issa", sexe="M", numero_piece_identite="CNIB999")
    autre = Beneficiaire.objects.create(nom="Ouedraogo", prenom="Fatou", sexe="F", numero_piece_identite="CNIB111")

    resultats = rechercher_doublons(autre)

    assert resultats == []


@pytest.mark.django_db
def test_export_beneficiaires_par_projet_et_global():
    import datetime
    import io

    from openpyxl import load_workbook
    from rest_framework.test import APIClient

    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User
    from apps.projects.models import Projet

    from .models import ParticipationProjet

    admin = User.objects.create_user(username="admin_export_benef", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    projet_a = Projet.objects.create(nom="Projet A", code="PA", date_debut="2026-01-01", date_fin="2026-12-31")
    projet_b = Projet.objects.create(nom="Projet B", code="PB", date_debut="2026-01-01", date_fin="2026-12-31")
    awa = Beneficiaire.objects.create(nom="OUEDRAOGO", prenom="Awa", sexe="F")
    Beneficiaire.objects.create(nom="SAWADOGO", prenom="Issa", sexe="M")
    for projet in (projet_a, projet_b):
        ParticipationProjet.objects.create(beneficiaire=awa, projet=projet, date_inscription=datetime.date(2026, 3, 1))

    reponse = client.get("/api/v1/beneficiaires/exporter/", {"projets": str(projet_a.id)})
    assert reponse.status_code == 200
    wb = load_workbook(io.BytesIO(reponse.content))
    assert wb.sheetnames == ["PA"]
    assert [r[0] for r in wb["PA"].iter_rows(min_row=2, values_only=True)] == ["OUEDRAOGO"]

    wb = load_workbook(io.BytesIO(client.get("/api/v1/beneficiaires/exporter/").content))
    assert wb.sheetnames == ["Tous les bénéficiaires", "PA", "PB", "Sans projet"]
    lignes = list(wb["Tous les bénéficiaires"].iter_rows(min_row=2, values_only=True))
    assert len(lignes) == 2
    assert lignes[0][13] == "PA; PB"

    wb = load_workbook(io.BytesIO(client.get("/api/v1/beneficiaires/exporter/", {"projets": f"{projet_a.id},{projet_b.id}"}).content))
    assert wb.sheetnames == ["Tous les bénéficiaires", "PA", "PB"]  # sans « Sans projet »
    assert len(list(wb["Tous les bénéficiaires"].iter_rows(min_row=2))) == 1

    pdf = client.get("/api/v1/beneficiaires/exporter/", {"projets": str(projet_a.id), "fichier": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
