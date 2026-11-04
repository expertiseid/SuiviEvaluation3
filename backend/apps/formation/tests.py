"""Cours en ligne : progression, quiz corrigés côté serveur, attestation, fermé en démonstration."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

from .contenu import MODULES, SEUIL_REUSSITE


@pytest.fixture
def client(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="eleve", password="x", role="CHARGE_SE", first_name="Awa", last_name="Kaboré"))
    return c


def _bonnes(module):
    return [q["bonne"] for q in module["quiz"]]


def test_parcours_complet(client):
    sommaire = client.get("/api/v1/formation/").data
    assert sommaire["acces"] is True and sommaire["progression"] == 0 and sommaire["attestation_possible"] is False
    m = MODULES[0]
    lecon = client.get(f"/api/v1/formation/modules/{m['code']}/lecons/{m['lecons'][0]['code']}/").data
    assert lecon["blocs"] and lecon["terminee"] is False and lecon["suivante"] == m["lecons"][1]["code"]
    assert client.post(f"/api/v1/formation/modules/{m['code']}/lecons/{m['lecons'][0]['code']}/").data["terminee"] is True
    # Les questions arrivent sans les bonnes réponses.
    questions = client.get(f"/api/v1/formation/modules/{m['code']}/quiz/").data["questions"]
    assert all("bonne" not in q and "explication" not in q for q in questions)
    # Échec, puis réussite.
    fausses = [(b + 1) % len(q["choix"]) for b, q in zip(_bonnes(m), m["quiz"])]
    echec = client.post(f"/api/v1/formation/modules/{m['code']}/quiz/", {"reponses": fausses}, format="json").data
    assert echec["reussi"] is False and echec["score"] == 0 and echec["corrections"][0]["explication"]
    assert client.post(f"/api/v1/formation/modules/{m['code']}/quiz/", {"reponses": [1]}, format="json").status_code == 400
    # Attestation refusée tant que tous les quiz ne sont pas réussis.
    assert client.get("/api/v1/formation/attestation/").status_code == 403
    for module in MODULES:
        r = client.post(f"/api/v1/formation/modules/{module['code']}/quiz/", {"reponses": _bonnes(module)}, format="json").data
        assert r["reussi"] and r["score"] >= SEUIL_REUSSITE
    sommaire = client.get("/api/v1/formation/").data
    assert sommaire["attestation_possible"] is True and sommaire["progression"] > 0
    pdf = client.get("/api/v1/formation/attestation/")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    numero = client.get("/api/v1/formation/").data["attestation"]["numero"]
    client.get("/api/v1/formation/attestation/")
    assert client.get("/api/v1/formation/").data["attestation"]["numero"] == numero  # délivrée une seule fois


def test_fermee_en_demonstration(client, settings):
    settings.MODE_DEMO = True
    assert client.get("/api/v1/formation/").data["acces"] is False
    m = MODULES[0]
    assert client.get(f"/api/v1/formation/modules/{m['code']}/lecons/{m['lecons'][0]['code']}/").status_code == 403
    assert client.get(f"/api/v1/formation/modules/{m['code']}/quiz/").status_code == 403


def test_contenu_coherent():
    from .contenu import CHAPITRES

    codes = set()
    for m in MODULES:
        assert len(m["quiz"]) == 5 and m["lecons"]
        for q in m["quiz"]:
            assert 0 <= q["bonne"] < len(q["choix"])
        for le in m["lecons"]:
            assert (m["code"], le["code"]) not in codes
            codes.add((m["code"], le["code"]))
            for b in le["blocs"]:
                if b["type"] == "video":
                    assert b["chapitre"] in CHAPITRES
