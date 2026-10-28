"""Lot 5 : rapport financier seul (PDF, Word, Excel) et versions Word des rapports."""
import io
import zipfile
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.partners.models import Bailleur, Financement, RallongeFinancement
from apps.projects.models import Activite, NiveauActivite, Projet
from apps.suivi.models import PointSuivi

from .financier import donnees_financieres, html_rapport_financier
from .word import html_vers_docx


@pytest.fixture
def projet(db):
    auteur = User.objects.create_user(username="saisie_rf", password="x", role=ROLE_ADMIN)
    projet = Projet.objects.create(nom="P", code="RF-1", date_debut="2026-01-01", date_fin="2026-12-31", fonds_propres=100)
    NiveauActivite.objects.create(projet=projet, profondeur=0, nom_niveau="Objectif général")
    NiveauActivite.objects.create(projet=projet, profondeur=1, nom_niveau="Composante")
    racine = Activite.objects.create(projet=projet, libelle="Objectif", budget_alloue=900)
    c1 = Activite.objects.create(projet=projet, libelle="C1", activite_parent=racine, budget_alloue=600)
    c2 = Activite.objects.create(projet=projet, libelle="C2", activite_parent=racine, budget_alloue=300)
    PointSuivi.objects.create(activite=c1, periode_debut="2026-02-01", periode_fin="2026-02-28", budget_realise=200, saisi_par=auteur)
    PointSuivi.objects.create(activite=c1, periode_debut="2026-07-01", periode_fin="2026-07-31", budget_realise=100, saisi_par=auteur)
    PointSuivi.objects.create(activite=c2, periode_debut="2026-08-01", periode_fin="2026-08-31", budget_realise=30, saisi_par=auteur)
    financement = Financement.objects.create(projet=projet, bailleur=Bailleur.objects.create(nom="Fonds ZZ"), montant_finance=700)
    RallongeFinancement.objects.create(financement=financement, montant=200, date="2026-06-01", motif="Nouvelle commune")
    projet.refresh_from_db()  # dates relues en objets date
    return projet


def test_chiffres_du_rapport(projet):
    d = donnees_financieres(projet)
    assert d["cout_total"] == Decimal("1000") and d["total_rallonges"] == Decimal("200")
    # Objectif général unique : les composantes sont le niveau en dessous ; le budget du haut n'est pas recompté.
    assert [(c["libelle"], c["niveau"], c["prevu"], c["depense"]) for c in d["composantes"]] == [
        ("C1", "Composante", Decimal("600"), Decimal("300")), ("C2", "Composante", Decimal("300"), Decimal("30")),
    ]
    assert d["total_prevu"] == Decimal("900") and d["taux_execution"] == 36.7
    assert [(t["libelle"], t["montant"]) for t in d["trimestres"]] == [("T1 2026", 200), ("T3 2026", 130)]
    # Limité à une période : seules les dépenses saisies entre les deux dates.
    d = donnees_financieres(projet, debut=__import__("datetime").date(2026, 7, 1))
    assert d["total_depense"] == Decimal("130")

    html = html_rapport_financier(donnees_financieres(projet), ["rallonges"])
    assert "Nouvelle commune" in html and "Sources de financement" not in html


def test_conversion_word():
    contenu = html_vers_docx(
        '<html><head><style>@page { size: A4 landscape; }</style></head><body><h2>Titre</h2>'
        '<div><span style="margin-right:6px">Code</span><strong>Libellé</strong></div>'
        '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>'
    )
    from docx import Document

    document = Document(io.BytesIO(contenu))
    assert [p.text for p in document.paragraphs[:2]] == ["Titre", "Code Libellé"]
    assert [[c.text for c in ligne.cells] for ligne in document.tables[0].rows] == [["A", "B"], ["1", "2"]]
    assert 'w:orient="landscape"' in zipfile.ZipFile(io.BytesIO(contenu)).read("word/document.xml").decode()


def test_telechargements(projet):
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_rf", password="x", role=ROLE_ADMIN))
    for fichier, debut in (("pdf", b"%PDF"), ("docx", b"PK"), ("xlsx", b"PK")):
        r = client.get(f"/api/v1/rapports/financier/{projet.id}/", {"fichier": fichier, "debut": "2026-01-01"})
        assert r.status_code == 200 and r.content.startswith(debut), fichier
    assert client.get(f"/api/v1/rapports/financier/{projet.id}/", {"sections": "inconnue"}).status_code == 400
    r = client.get(f"/api/v1/suivi/projets/{projet.id}/exporter/word/")
    assert r.status_code == 200 and r["Content-Type"].endswith("wordprocessingml.document")
