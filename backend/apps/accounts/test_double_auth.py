"""Double authentification par courriel : un code à chaque connexion, pour tous les comptes."""
import re
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import EvenementAudit

from .constants import ROLE_ADMIN, ROLE_CHARGE_SE
from .models import CodeConnexion, User

TOKEN = "/api/v1/auth/token/"
ETAPE = "/api/v1/auth/double-authentification/"
MOI = "/api/v1/utilisateurs/me/"


@pytest.fixture(autouse=True)
def courriel_de_test(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def compte(db):
    return User.objects.create_user(username="se_otp", password="mdp-sur-1", role=ROLE_CHARGE_SE,
                                    email="agent@expertise-id.com")


def _connecter(username="se_otp", password="mdp-sur-1"):
    return APIClient().post(TOKEN, {"username": username, "password": password})


def _dernier_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


@pytest.mark.django_db
def test_code_envoye_a_chaque_connexion(compte):
    etape = _connecter().data
    # Pas de jetons après le mot de passe : un code est parti à l'adresse du compte.
    assert etape["double_authentification"] == "code" and "access" not in etape
    assert etape["destination"] == "ag•••@expertise-id.com"
    assert mail.outbox[-1].to == ["agent@expertise-id.com"]
    code = _dernier_code()
    assert code in mail.outbox[-1].subject
    # Seule l'empreinte est gardée.
    assert code not in CodeConnexion.objects.get().empreinte
    client = APIClient()
    reponse = client.post(ETAPE + "code/", {"jeton": etape["jeton"], "code": code})
    assert reponse.status_code == 200 and reponse.data["access"]
    # Usage unique ; et un nouveau code à la connexion suivante.
    assert client.post(ETAPE + "code/", {"jeton": etape["jeton"], "code": code}).status_code == 403
    _connecter()
    assert len(mail.outbox) == 2
    assert EvenementAudit.objects.filter(action="CONNEXION", details__second_facteur=True).count() == 1


@pytest.mark.django_db
def test_essais_limites_et_expiration(compte):
    etape = _connecter().data
    client = APIClient()
    for restants in (4, 3, 2, 1):
        reponse = client.post(ETAPE + "code/", {"jeton": etape["jeton"], "code": "000000"})
        assert reponse.status_code == 400 and str(restants) in str(reponse.data["code"])
    assert client.post(ETAPE + "code/", {"jeton": etape["jeton"], "code": "000000"}).status_code == 403
    # Même le bon code ne passe plus.
    assert client.post(ETAPE + "code/", {"jeton": etape["jeton"], "code": _dernier_code()}).status_code == 403
    assert EvenementAudit.objects.filter(action="CONNEXION_ECHOUEE", details__etape="second_facteur").count() == 5
    # Code expiré au bout de 10 minutes.
    etape = _connecter().data
    CodeConnexion.objects.filter(utilise=False).update(expire_le=timezone.now() - timedelta(seconds=1))
    assert client.post(ETAPE + "code/", {"jeton": etape["jeton"], "code": _dernier_code()}).status_code == 403
    assert client.post(ETAPE + "code/", {"jeton": "faux", "code": "123456"}).status_code == 403


@pytest.mark.django_db
def test_nouveau_code(compte):
    etape = _connecter().data
    ancien = _dernier_code()
    client = APIClient()
    # Une minute d'intervalle entre deux envois.
    assert client.post(ETAPE + "renvoyer/", {"jeton": etape["jeton"]}).status_code == 400
    plus_tard = timezone.now() + timedelta(minutes=2)
    with mock.patch("django.utils.timezone.now", return_value=plus_tard):
        renvoi = client.post(ETAPE + "renvoyer/", {"jeton": etape["jeton"]}).data
        nouveau = _dernier_code()
        assert len(mail.outbox) == 2
        # L'ancien code est annulé, le nouveau fonctionne.
        if ancien != nouveau:
            assert client.post(ETAPE + "code/", {"jeton": renvoi["jeton"], "code": ancien}).status_code == 400
        assert client.post(ETAPE + "code/", {"jeton": renvoi["jeton"], "code": nouveau}).status_code == 200


@pytest.mark.django_db
def test_compte_sans_adresse_reelle(db):
    User.objects.create_user(username="demo_otp", password="mdp-sur-1", role=ROLE_ADMIN, email="demo@example.org")
    User.objects.create_user(username="vide_otp", password="mdp-sur-1", role=ROLE_CHARGE_SE)
    for nom in ("demo_otp", "vide_otp"):
        reponse = _connecter(nom)
        assert reponse.status_code == 400 and "adresse courriel" in str(reponse.data["detail"])
    assert not mail.outbox and not CodeConnexion.objects.exists()


@pytest.mark.django_db
def test_jeton_sans_code_refuse(compte):
    """Une session ouverte sans le code (par exemple avant la mise en place) est refusée."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(compte).access_token}")
    reponse = client.get(MOI)
    assert reponse.status_code == 401 and reponse.data["code"] == "double_authentification_requise"
    from .double_auth import jetons

    j = jetons(compte)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {j['access']}")
    assert client.get(MOI).status_code == 200
    renouvele = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": j["refresh"]}).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {renouvele}")
    assert client.get(MOI).status_code == 200


@pytest.mark.django_db
def test_mot_de_passe_faux_aucun_code(compte):
    assert _connecter(password="faux").status_code == 401
    assert not mail.outbox


@pytest.mark.django_db
def test_courriel_dans_la_langue_du_compte(compte):
    compte.langue = "en"
    compte.save(update_fields=["langue"])
    _connecter()
    assert mail.outbox[-1].subject.startswith("Your login code: ") and "valid for 10 minutes" in mail.outbox[-1].body
