"""Contrôle « Je ne suis pas un robot » (reCAPTCHA) du formulaire d'inscription."""
import io
import json
from unittest import mock

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from .test_accueil import PROFIL

URL = "/api/v1/public/inscription/"


@pytest.fixture(autouse=True)
def reglages(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.RECAPTCHA_CLE_SITE = ""
    settings.RECAPTCHA_CLE_SECRETE = ""
    cache.clear()
    yield
    cache.clear()


def _google(succes):
    reponse = mock.MagicMock()
    reponse.__enter__.return_value = io.BytesIO(json.dumps({"success": succes}).encode())
    return mock.patch("apps.accounts.controle_robot.urllib.request.urlopen", return_value=reponse)


@pytest.mark.django_db(databases=["default", "central"])
def test_sans_cles_pas_de_controle():
    client = APIClient()
    assert client.get(URL + "controle/").data == {"recaptcha": ""}
    assert client.post(URL, PROFIL, format="json").status_code == 201


@pytest.mark.django_db(databases=["default", "central"])
def test_avec_cles_la_case_est_exigee_et_verifiee(settings):
    settings.RECAPTCHA_CLE_SITE = "cle-publique"
    settings.RECAPTCHA_CLE_SECRETE = "cle-secrete"
    client = APIClient()
    assert client.get(URL + "controle/").data == {"recaptcha": "cle-publique"}
    sans = client.post(URL, PROFIL, format="json")
    assert sans.status_code == 400 and "robot" in str(sans.data)
    with _google(False):
        assert client.post(URL, {**PROFIL, "recaptcha": "jeton"}, format="json").status_code == 400
    with _google(True) as appel:
        assert client.post(URL, {**PROFIL, "recaptcha": "jeton"}, format="json").status_code == 201
        envoye = appel.call_args.args[1].decode()
        assert "secret=cle-secrete" in envoye and "response=jeton" in envoye


@pytest.mark.django_db(databases=["default", "central"])
def test_choix_de_l_offre_et_paiement_exigent_aussi_la_case(settings):
    client = APIClient()
    reference = client.post(URL, PROFIL, format="json").data["reference"]  # profil créé avant l'activation du contrôle
    settings.RECAPTCHA_CLE_SITE = "cle-publique"
    settings.RECAPTCHA_CLE_SECRETE = "cle-secrete"
    choix = {"reference": reference, "offre": "STANDARD", "moyen": "carte", "mois": 12}
    for adresse in (URL + "offre/", URL + "paiement/"):
        refus = client.post(adresse, choix, format="json")
        assert refus.status_code == 400 and "robot" in str(refus.data)
    with _google(True):
        assert client.post(URL + "offre/", {**choix, "recaptcha": "jeton"}, format="json").status_code == 200
