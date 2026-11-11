"""Paiement en ligne de l'abonnement (CinetPay simulé) : lien de paiement, notification, espace créé une seule fois."""
import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import DemandeInscription

from . import paiement
from .models import PaiementAbonnement

PROFIL = {
    "organisation": "ONG Paiement", "type_organisation": "ONG", "pays": "Burkina Faso", "contact_nom": "Awa Kaboré",
    "courriel": "awa@ong-paiement.bf", "telephone": "70000000", "mot_de_passe": "Un-mot-de-passe-solide-2026", "conditions": True,
}


class CinetPaySimule:
    """Remplace les appels à CinetPay ; « statut » est celui renvoyé à la vérification du paiement."""

    def __init__(self):
        self.statut = "INITIATED"
        self.appels = []

    def __call__(self, methode, chemin, corps=None, jeton=None):
        self.appels.append((methode, chemin, corps))
        if chemin == "/v1/oauth/login":
            return {"code": 200, "access_token": "jeton", "expires_in": 82800}
        if chemin == "/v1/payment":
            return {"code": 200, "payment_token": "pt", "notify_token": "nt-secret", "transaction_id": "TR-1",
                    "payment_url": "https://secure.cinetpay.net/checkout/pt"}
        return {"code": 100 if self.statut == "SUCCESS" else 2001, "status": self.statut, "transaction_id": "TR-1"}


@pytest.fixture
def cinetpay(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.COURRIEL_ABONNEMENTS = "abonnements@expertise-id.com"
    settings.CINETPAY_API_KEY, settings.CINETPAY_API_PASSWORD = "sk_test_cle", "mot-de-passe"
    settings.ABONNEMENT_PRIX_MOIS, settings.ABONNEMENT_PRIX_TRANCHE = 50000, 3000
    settings.URL_SITE = "https://monitora.exemple"
    simule = CinetPaySimule()
    monkeypatch.setattr(paiement, "_appel", simule)
    cache.clear()
    yield simule
    cache.clear()


def _profil(client):
    return client.post("/api/v1/public/inscription/", PROFIL, format="json").data["reference"]


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_paiement_puis_inscription(cinetpay):
    client = APIClient()
    reference = _profil(client)
    # Un seul courriel à la création : l'accusé à l'organisation, rien encore pour Expertise-ID.
    assert [m.to for m in mail.outbox] == [["awa@ong-paiement.bf"]]
    for mauvais in ({"offre": "PARTENARIAT"}, {"offre": "STANDARD", "mois": 5}, {"offre": "STOCKAGE_PLUS", "mois": 1, "tranches": 0}):
        assert client.post("/api/v1/public/inscription/paiement/", {"reference": reference, **mauvais}, format="json").status_code == 400

    reponse = client.post("/api/v1/public/inscription/paiement/",
                          {"reference": reference, "offre": "STOCKAGE_PLUS", "mois": 12, "tranches": 2}, format="json")
    assert reponse.status_code == 200 and reponse.data["lien"].startswith("https://secure.cinetpay.net/")
    assert reponse.data["montant"] == 12 * (50000 + 2 * 3000)
    envoi = cinetpay.appels[-1][2]
    assert envoi["currency"] == "XOF" and envoi["success_url"].startswith("https://monitora.exemple/inscription.html?paiement=")
    ref = reponse.data["paiement"]

    # Retour sur le site avant la confirmation : en attente, aucun espace.
    assert client.get(f"/api/v1/public/inscription/paiement/{ref}/").data["statut"] == "EN_ATTENTE"
    # Notification au jeton faux : ignorée, même si CinetPay dit « payé ».
    cinetpay.statut = "SUCCESS"
    client.post("/api/v1/public/inscription/paiement/notification/", {"merchant_transaction_id": ref, "notify_token": "faux"}, format="json")
    assert PaiementAbonnement.objects.get(reference=ref).statut == "EN_ATTENTE"
    # Vraie notification, puis retour sur le site : validé une seule fois, un seul courriel à Expertise-ID.
    client.post("/api/v1/public/inscription/paiement/notification/", {"merchant_transaction_id": ref, "notify_token": "nt-secret"}, format="json")
    assert client.get(f"/api/v1/public/inscription/paiement/{ref}/").data["statut"] == "PAYE"
    vers_expertise = [m for m in mail.outbox if m.to == ["abonnements@expertise-id.com"]]
    assert len(vers_expertise) == 1 and vers_expertise[0].subject == "Nouvelle inscription : ONG Paiement"
    assert "672 000 XOF" in vers_expertise[0].body
    demande = DemandeInscription.objects.get()
    assert demande.offre == "STOCKAGE_PLUS" and demande.statut == "OFFRE_CHOISIE"


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_paiement_cree_l_espace(cinetpay, monkeypatch):
    from . import activation, contexte

    lances = []
    monkeypatch.setattr(contexte, "actif", lambda: True)
    monkeypatch.setattr(activation, "lancer", lambda demande: lances.append(demande.pk))
    client = APIClient()
    reference = _profil(client)
    ref = client.post("/api/v1/public/inscription/paiement/", {"reference": reference, "offre": "STANDARD", "mois": 1}, format="json").data["paiement"]
    cinetpay.statut = "SUCCESS"
    for _ in range(2):
        client.get(f"/api/v1/public/inscription/paiement/{ref}/")
    assert lances == [DemandeInscription.objects.get().pk]
    assert "créé automatiquement" in mail.outbox[-1].body


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_paiement_echoue(cinetpay):
    client = APIClient()
    ref = client.post("/api/v1/public/inscription/paiement/", {"reference": _profil(client), "offre": "STANDARD", "mois": 1},
                      format="json").data["paiement"]
    cinetpay.statut = "FAILED"
    assert client.get(f"/api/v1/public/inscription/paiement/{ref}/").data["statut"] == "ECHOUE"
    assert DemandeInscription.objects.get().statut == "ABONNEMENT_REQUIS"
    assert client.get("/api/v1/public/inscription/paiement/inconnu/").status_code == 400


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_sans_cle_pas_de_paiement(cinetpay, settings):
    settings.CINETPAY_API_KEY = ""
    client = APIClient()
    reference = _profil(client)
    assert client.post("/api/v1/public/inscription/", {**PROFIL, "courriel": "b@ong.bf"}, format="json").data["tarifs"]["paiement"] is False
    assert client.post("/api/v1/public/inscription/paiement/", {"reference": reference, "offre": "STANDARD", "mois": 1}, format="json").status_code == 400


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_tarifs_publics(cinetpay):
    tarifs = APIClient().get("/api/v1/public/inscription/tarifs/").data
    assert tarifs["paiement"] is True and tarifs["mois"] == 50000 and tarifs["tranche"] == 3000 and tarifs["devise"] == "XOF"


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_carte_bancaire_transmise_a_expertise_id(cinetpay):
    """Carte bancaire : pas de paiement en ligne, Expertise-ID reçoit la demande (montant en dollars) et finalise."""
    client = APIClient()
    assert client.get("/api/v1/public/inscription/tarifs/").data["usd"] == {"mois": 86, "tranche": 5}
    reponse = client.post("/api/v1/public/inscription/offre/", {"reference": _profil(client), "offre": "STOCKAGE_PLUS",
                                                                "moyen": "carte", "mois": 12, "tranches": 1}, format="json")
    assert reponse.status_code == 200 and reponse.data["statut"] == "OFFRE_CHOISIE"
    courriel = mail.outbox[-1]
    assert courriel.to == ["abonnements@expertise-id.com"] and courriel.subject == "Paiement par carte demandé : ONG Paiement"
    assert "1092 $ (12 mois + 10 Go)" in courriel.body and "Sous-domaine" not in courriel.body
    assert not PaiementAbonnement.objects.exists() and not [a for a in cinetpay.appels if a[1] == "/v1/payment"]


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_offres_25_et_50_go(cinetpay, settings):
    """Standard 25 Go (20 000 FCFA / 34 $) et Standard 50 Go (30 000 FCFA / 52 $) : payées comme Standard."""
    settings.ABONNEMENT_PRIX_25GO, settings.ABONNEMENT_PRIX_50GO = 20000, 30000
    client = APIClient()
    assert client.get("/api/v1/public/inscription/tarifs/").data["offres"]["STANDARD_25"] == {"mois": 20000, "usd": 34}
    reponse = client.post("/api/v1/public/inscription/paiement/", {"reference": _profil(client), "offre": "STANDARD_50", "mois": 12,
                                                                     "tranches": 3}, format="json")
    assert reponse.status_code == 200 and reponse.data["montant"] == 12 * 30000  # pas de tranches hors « Standard + stockage »
    assert "Standard 50 Go" in cinetpay.appels[-1][2]["designation"]


def test_formation_gratuite():
    """Formation gratuite : 2 ans pour Standard 25 Go et 50 Go, 1 an pour Standard (100 Go)."""
    assert not paiement.formation_offerte("STANDARD_25", 12) and paiement.formation_offerte("STANDARD_25", 24)
    assert not paiement.formation_offerte("STANDARD_50", 12) and paiement.formation_offerte("STANDARD_50", 36)
    assert not paiement.formation_offerte("STANDARD", 6) and paiement.formation_offerte("STANDARD", 12)
    assert not paiement.formation_offerte("PARTENARIAT", 36)
    assert paiement.DUREES == (1, 3, 6, 12, 24, 36)


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_offre_la_plus_populaire(cinetpay, settings):
    """Sans achat : l'offre du réglage ; ensuite la plus achetée (Standard + stockage compte pour Standard)."""
    settings.ABONNEMENT_OFFRE_POPULAIRE = "STANDARD_50"
    client = APIClient()
    assert client.get("/api/v1/public/inscription/tarifs/").data["populaire"] == "STANDARD_50"

    def achat(offre, statut=PaiementAbonnement.Statut.PAYE):
        PaiementAbonnement.objects.using("central").create(reference=f"R{PaiementAbonnement.objects.using('central').count()}",
                                                           offre=offre, montant=1, devise="XOF", statut=statut)

    achat("STANDARD_25")
    assert client.get("/api/v1/public/inscription/tarifs/").data["populaire"] == "STANDARD_25"
    achat("STANDARD")
    achat("STOCKAGE_PLUS")
    achat("STANDARD_25", PaiementAbonnement.Statut.ECHOUE)  # non payé : ne compte pas
    assert client.get("/api/v1/public/inscription/tarifs/").data["populaire"] == "STANDARD"


@pytest.mark.django_db(transaction=True, databases=["default", "central"])
def test_essai_gratuit_une_seule_fois(cinetpay, monkeypatch):
    """Essai gratuit : espace créé sans paiement ; une adresse n'y a droit qu'une fois, même profil supprimé."""
    from apps.accounts.models import EssaiGratuit

    from . import activation, contexte

    lances = []
    monkeypatch.setattr(contexte, "actif", lambda: True)
    monkeypatch.setattr(activation, "lancer", lambda demande: lances.append(demande.pk))
    client = APIClient()
    reponse = client.post("/api/v1/public/inscription/offre/", {"reference": _profil(client), "offre": "ESSAI"}, format="json")
    demande = DemandeInscription.objects.get()
    assert reponse.status_code == 200 and lances == [demande.pk] and demande.offre == "ESSAI"
    assert EssaiGratuit.objects.using("central").filter(courriel="awa@ong-paiement.bf").exists()
    assert mail.outbox[-1].subject.startswith("Essai gratuit commencé")
    assert not PaiementAbonnement.objects.exists()
    # Profil supprimé puis recréé avec la même adresse (en majuscules) : plus d'essai, une offre à choisir.
    demande.delete()
    reference = client.post("/api/v1/public/inscription/", {**PROFIL, "courriel": "AWA@ong-paiement.bf"}, format="json").data["reference"]
    refus = client.post("/api/v1/public/inscription/offre/", {"reference": reference, "offre": "ESSAI"}, format="json")
    assert refus.status_code == 400 and "déjà bénéficié" in refus.data["offre"]
    assert len(lances) == 1
