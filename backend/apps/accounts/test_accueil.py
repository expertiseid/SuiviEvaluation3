"""Page d'accueil : inscription d'une organisation, abonnement requis, démonstration, identité."""
import io

import pytest
from django.core import mail
from django.core.cache import cache
from PIL import Image
from rest_framework.test import APIClient

from .constants import ROLE_ADMIN
from .models import DemandeInscription, User

PROFIL = {
    "organisation": "ONG Exemple", "type_organisation": "ONG", "pays": "Burkina Faso", "contact_nom": "Awa Kaboré",
    "courriel": "awa@ong-exemple.bf", "telephone": "70000000", "identifiant": "ong_exemple",
    "mot_de_passe": "Un-mot-de-passe-solide-2026", "conditions": True,
}


@pytest.fixture(autouse=True)
def reglages(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.COURRIEL_ABONNEMENTS = "abonnements@expertise-id.com"
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db(databases=["default", "central"])  # tarifs : offre la plus achetée (base centrale)
def test_inscription_puis_abonnement_requis():
    client = APIClient()
    assert client.post("/api/v1/public/inscription/", {**PROFIL, "conditions": False}, format="json").status_code == 400
    assert client.post("/api/v1/public/inscription/", {**PROFIL, "mot_de_passe": "123"}, format="json").status_code == 400
    assert client.post("/api/v1/public/inscription/", {**PROFIL, "courriel": "x@example.org"}, format="json").status_code == 400
    reponse = client.post("/api/v1/public/inscription/", PROFIL, format="json")
    assert reponse.status_code == 201 and reponse.data["statut"] == "ABONNEMENT_REQUIS"
    demande = DemandeInscription.objects.get()
    assert demande.mot_de_passe != PROFIL["mot_de_passe"]  # empreinte seulement
    # Un seul courriel : l'accusé. Expertise-ID n'est prévenu qu'au paiement (ou à l'offre Partenariat).
    assert [tuple(m.to) for m in mail.outbox] == [("awa@ong-exemple.bf",)]
    # Identifiant déjà pris.
    assert client.post("/api/v1/public/inscription/", {**PROFIL, "courriel": "b@ong.bf"}, format="json").status_code == 400
    # Connexion avec ces identifiants : page d'abonnement, pas de jetons.
    connexion = client.post("/api/v1/auth/token/", {"username": "ong_exemple", "password": PROFIL["mot_de_passe"]})
    assert connexion.status_code == 403 and connexion.data["code"] == "abonnement_requis"
    assert client.post("/api/v1/auth/token/", {"username": "ong_exemple", "password": "faux"}).status_code == 401
    # Offre choisie avec la référence.
    offre = client.post("/api/v1/public/inscription/offre/", {"reference": reponse.data["reference"], "offre": "STANDARD"}, format="json")
    assert offre.data["statut"] == "OFFRE_CHOISIE" and "Standard" in mail.outbox[-1].subject
    assert client.post("/api/v1/public/inscription/offre/", {"reference": "faux", "offre": "STANDARD"}, format="json").status_code == 400


@pytest.mark.django_db
def test_mode_demo(settings):
    client = APIClient()
    settings.MODE_DEMO = False
    assert client.post("/api/v1/public/demo/").status_code == 403
    settings.MODE_DEMO = True
    jetons = client.post("/api/v1/public/demo/").data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons['access']}")
    moi = client.get("/api/v1/utilisateurs/me/").data
    assert moi["est_demo"] is True and moi["role"] == ROLE_ADMIN
    # Il voit tout, mais rien ne s'enregistre.
    assert client.get("/api/v1/projets/").status_code == 200
    refus = client.post("/api/v1/dossiers/", {"nom": "essai"}, format="json")
    assert refus.status_code == 403 and refus.json()["code"] == "mode_demo"
    assert client.patch("/api/v1/utilisateurs/me/", {"langue": "en"}, format="json").status_code == 403
    assert APIClient().post("/api/v1/auth/token/refresh/", {"refresh": jetons["refresh"]}).status_code == 200


@pytest.mark.django_db
def test_identite_et_logo():
    public = APIClient()
    assert public.get("/api/v1/identite/").data["logo"] is None
    admin = User.objects.create_user(username="adm_id", password="x", role=ROLE_ADMIN)
    from .double_auth import jetons

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons(admin)['access']}")
    image = io.BytesIO()
    Image.new("RGB", (40, 20), "teal").save(image, "PNG")
    image.name = "logo.png"
    image.seek(0)
    reponse = client.patch("/api/v1/identite/", {"nom": "ONG Exemple", "logo": image}, format="multipart")
    assert reponse.status_code == 200 and reponse.data["nom"] == "ONG Exemple" and reponse.data["logo"]
    assert public.get("/api/v1/identite/logo/")["Content-Type"] == "image/png"
    faux = io.BytesIO(b"<svg onload=alert(1)>")
    faux.name = "logo.png"
    assert client.patch("/api/v1/identite/", {"logo": faux}, format="multipart").status_code == 400
    assert public.patch("/api/v1/identite/", {"nom": "x"}, format="multipart").status_code == 403


@pytest.mark.django_db
def test_demo_fermee(settings):
    """DEMO_OUVERTE=False (par défaut) : plus de bouton « Essayer la démo », connexion du visiteur refusée."""
    settings.DEMO_OUVERTE = False
    settings.MODE_DEMO = True
    assert APIClient().get("/api/v1/identite/").data["demo_disponible"] is False
    assert APIClient().post("/api/v1/public/demo/").status_code == 403
