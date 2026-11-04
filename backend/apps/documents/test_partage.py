"""Partage d'un document par lien : droits, expiration, mot de passe, nombre d'ouvertures, révocation."""
from datetime import timedelta
from urllib.parse import urlparse

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.core.models import EvenementAudit

from .models import LienDocument


@pytest.fixture
def client(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="adm_partage", password="x", role=ROLE_ADMIN))
    return c


def _document(client, nom, contenu=b"%PDF-1.4 rapport"):
    reponse = client.post("/api/v1/documents/", {"nom": nom, "fichier": SimpleUploadedFile(nom, contenu)}, format="multipart")
    assert reponse.status_code == 201, reponse.content
    return reponse.data["id"]


def _dans(jours=7):
    return (timezone.now() + timedelta(days=jours)).isoformat()


def _chemin(url):
    morceaux = urlparse(url)
    return f"{morceaux.path}?{morceaux.query}"


def test_consulter_seulement(client):
    doc = _document(client, "rapport.pdf")
    lien = client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "CONSULTER", "expire_le": _dans(), "libelle": "Bailleur"},
                       format="json")
    assert lien.status_code == 201, lien.content
    jeton = lien.data["jeton"]
    assert EvenementAudit.objects.filter(action="PARTAGE", objet="rapport.pdf").exists()

    anonyme = APIClient()
    description = anonyme.get(f"/api/v1/public/document-partage/{jeton}/").data
    assert description["etat"] == "ACTIF" and description["document"] == "rapport.pdf" and description["mot_de_passe"] is False
    ouvert = anonyme.post(f"/api/v1/public/document-partage/{jeton}/", {}, format="json").data
    assert ouvert["apercu_url"] and ouvert["telechargement_url"] is None
    apercu = anonyme.get(_chemin(ouvert["apercu_url"]))
    assert apercu.status_code == 200 and apercu["Content-Disposition"].startswith("inline")
    # Le téléchargement n'est pas permis : aucune adresse n'est remise, et l'adresse signée ne se falsifie pas.
    from django.core import signing

    from apps.organisations.contexte import sel

    from .partage import SEL

    lien_id = LienDocument.objects.get(jeton=jeton).pk
    version = LienDocument.objects.get(jeton=jeton).document.derniere_version.pk
    faux = signing.dumps({"l": lien_id, "v": version, "m": "telechargement"}, salt=sel(SEL))
    assert anonyme.get(f"/api/v1/public/document-partage/{jeton}/fichier/", {"cle": faux}).status_code == 404
    assert anonyme.get(_chemin(ouvert["apercu_url"]) + "x").status_code == 404
    assert LienDocument.objects.get(jeton=jeton).nombre_ouvertures == 1


def test_telecharger_mot_de_passe_et_limite(client):
    doc = _document(client, "budget.xlsx", b"PK tableur")
    # Un tableur ne s'affiche pas dans un navigateur : « consulter seulement » est refusé.
    refus = client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "CONSULTER", "expire_le": _dans()}, format="json")
    assert refus.status_code == 400 and "droit" in refus.data
    jeton = client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "TELECHARGER", "expire_le": _dans(), "mot_de_passe": "secret-42",
                                                            "ouvertures_max": 1}, format="json").data["jeton"]
    anonyme = APIClient()
    assert anonyme.post(f"/api/v1/public/document-partage/{jeton}/", {"mot_de_passe": "faux"}, format="json").status_code == 403
    ouvert = anonyme.post(f"/api/v1/public/document-partage/{jeton}/", {"mot_de_passe": "secret-42"}, format="json").data
    assert ouvert["apercu_url"] is None
    fichier = anonyme.get(_chemin(ouvert["telechargement_url"]))
    assert fichier.status_code == 200 and fichier["Content-Disposition"].startswith("attachment")
    # Une seule ouverture permise : la suivante est refusée.
    assert anonyme.post(f"/api/v1/public/document-partage/{jeton}/", {"mot_de_passe": "secret-42"}, format="json").status_code == 410


def test_expiration_et_revocation(client):
    doc = _document(client, "note.pdf")
    assert client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "CONSULTER", "expire_le": _dans(-1)}, format="json").status_code == 400
    assert client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "CONSULTER", "expire_le": _dans(400)}, format="json").status_code == 400
    cree = client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "TELECHARGER", "expire_le": _dans()}, format="json").data
    anonyme = APIClient()
    ouvert = anonyme.post(f"/api/v1/public/document-partage/{cree['jeton']}/", {}, format="json").data

    # Révocation : effet immédiat, y compris sur une adresse de fichier déjà remise.
    assert client.post(f"/api/v1/documents/{doc}/liens/{cree['id']}/revoquer/").data["etat"] == "REVOQUE"
    assert anonyme.get(_chemin(ouvert["telechargement_url"])).status_code == 404
    assert anonyme.post(f"/api/v1/public/document-partage/{cree['jeton']}/", {}, format="json").status_code == 410

    # Expiré : plus d'ouverture.
    autre = client.post(f"/api/v1/documents/{doc}/liens/", {"droit": "TELECHARGER", "expire_le": _dans()}, format="json").data
    LienDocument.objects.filter(pk=autre["id"]).update(expire_le=timezone.now() - timedelta(minutes=1))
    assert anonyme.get(f"/api/v1/public/document-partage/{autre['jeton']}/").data["etat"] == "EXPIRE"
    assert anonyme.post(f"/api/v1/public/document-partage/{autre['jeton']}/", {}, format="json").status_code == 410
    assert [lien["etat"] for lien in client.get(f"/api/v1/documents/{doc}/liens/").data] == ["EXPIRE", "REVOQUE"]
    # Jeton inconnu ; lecteur sans droit d'écriture.
    assert anonyme.get("/api/v1/public/document-partage/inconnu/").status_code == 404
    lecteur = APIClient()
    lecteur.force_authenticate(User.objects.create_user(username="lecteur_partage", password="x", role="CHARGE_SE", niveau_acces="LECTURE_SEULE"))
    assert lecteur.post(f"/api/v1/documents/{doc}/liens/", {"droit": "TELECHARGER", "expire_le": _dans()}, format="json").status_code == 403
