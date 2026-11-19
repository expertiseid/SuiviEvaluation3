"""Exports « comme à l'écran » : images des blocs assemblées en PDF, Word et Excel (apps.dashboard.fidele)."""
import io
import json
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .fidele import decouper, lignes_de_la_grille

URL = "/api/v1/dashboard/consolide/export-ecran/"


def _png(largeur, hauteur, couleur="#1c7ed6"):
    tampon = io.BytesIO()
    Image.new("RGB", (largeur, hauteur), couleur).save(tampon, format="PNG")
    return tampon.getvalue()


def test_grille_et_decoupage():
    blocs = [{"largeur": l, "px": (100, 50), "image": b""} for l in (12, 4, 4, 4, 6, 6, 6)]
    assert [[b["largeur"] for b in ligne] for ligne in lignes_de_la_grille(blocs)] == [[12], [4, 4, 4], [6, 6], [6]]
    # Bloc pleine largeur 3 fois plus haut que la page : 3 morceaux de la même largeur.
    haut = {"largeur": 12, "px": (200, 600), "image": _png(200, 600), "titre": "Liste"}
    morceaux = decouper([[haut]], 1.0)
    assert len(morceaux) == 3 and all(m[0]["px"][0] == 200 for m in morceaux) and sum(m[0]["px"][1] for m in morceaux) == 600
    assert decouper([[haut, haut]], 1.0) == [[haut, haut]]  # plusieurs blocs côte à côte : jamais découpés


@pytest.mark.django_db
def test_export_comme_a_l_ecran():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_ecran", password="x", role=ROLE_ADMIN))

    def envoi(fichier, **plus):
        donnees = {"fichier": fichier, "blocs": json.dumps([{"titre": "Chiffres", "largeur": 12}, {"titre": "Pays", "largeur": 6},
                                                             {"titre": "Bailleurs", "largeur": 6}]),
                   "filtres": json.dumps({"annee": "2026"}), **plus}
        for rang, (l, h) in enumerate(((1200, 200), (600, 400), (600, 2400))):
            donnees[f"image_{rang}"] = SimpleUploadedFile(f"b{rang}.png", _png(l, h), content_type="image/png")
        return client.post(URL, donnees, format="multipart")

    pdf = envoi("pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    word = envoi("docx")
    document = zipfile.ZipFile(io.BytesIO(word.content))
    assert word.status_code == 200 and len([n for n in document.namelist() if n.startswith("word/media/")]) >= 3
    assert "Année 2026" in document.read("word/document.xml").decode()
    excel = envoi("xlsx")
    classeur = zipfile.ZipFile(io.BytesIO(excel.content))
    assert "Comme à l'écran" in classeur.read("xl/workbook.xml").decode()
    assert len([n for n in classeur.namelist() if n.startswith("xl/media/")]) == 3
    # Un bloc seul : son titre devient celui du document.
    seul = client.post(URL, {"fichier": "docx", "titre": "Plaintes et retours", "blocs": json.dumps([{"titre": "Plaintes", "largeur": 12}]),
                             "image_0": SimpleUploadedFile("b.png", _png(800, 300), content_type="image/png")}, format="multipart")
    assert "Plaintes et retours" in zipfile.ZipFile(io.BytesIO(seul.content)).read("word/document.xml").decode()

    assert client.post(URL, {"fichier": "pptx", "blocs": "[]"}, format="multipart").status_code == 400
    assert client.post(URL, {"fichier": "pdf", "blocs": json.dumps([{"titre": "X", "largeur": 12}])}, format="multipart").status_code == 400
    faux = client.post(URL, {"fichier": "pdf", "blocs": json.dumps([{"titre": "X", "largeur": 12}]),
                             "image_0": SimpleUploadedFile("b.png", b"pas une image", content_type="image/png")}, format="multipart")
    assert faux.status_code == 400


@pytest.mark.django_db
def test_exports_dans_la_langue_de_l_utilisateur():
    """L'Excel et le PDF « comme à l'écran » du tableau de bord suivent la langue de l'interface."""
    import io as _io

    from openpyxl import load_workbook

    from apps.core.langues import catalogue

    anglais = APIClient(HTTP_ACCEPT_LANGUAGE="en")
    anglais.force_authenticate(User.objects.create_user(username="adm_en", password="x", role=ROLE_ADMIN))
    classeur = load_workbook(_io.BytesIO(anglais.get("/api/v1/dashboard/consolide/export/", {"fichier": "xlsx"}).content))
    assert classeur.sheetnames[0] == catalogue("en")["Synthèse"]
    word = anglais.post(URL, {"fichier": "docx", "blocs": json.dumps([{"titre": "X", "largeur": 12}]),
                              "image_0": SimpleUploadedFile("b.png", _png(400, 200), content_type="image/png")}, format="multipart")
    assert catalogue("en")["Tableau de bord"] in zipfile.ZipFile(io.BytesIO(word.content)).read("word/document.xml").decode()
