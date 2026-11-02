"""Lot 7 : modèles de messages multilingues, accusé de réception automatique, envoi par courriel et SMS,
aucun détail confidentiel, statut d'envoi au journal."""
import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User

from . import messages
from .models import ActionDossier, Categorie, Dossier, EtapeCircuit, Mecanisme, ModeleMessage, TypeRetour
from .reception import recevoir

URL = "/api/v1/plaintes/"


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_msg", password="x", role=ROLE_ADMIN)


@pytest.fixture
def actif(admin):
    pf = User.objects.create_user(username="pf_msg", password="x", role=ROLE_CHARGE_SE)
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120,
                                          signature_messages="L'équipe du projet")
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=pf)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200


def _dossier(categorie="Retard", **champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Récit très personnel.",
               "consentement": True, "categorie": Categorie.objects.get(nom=categorie).id, "nom": "Awa",
               "courriel": "awa@example.org", "telephone": "70000000", "mode_reponse": "COURRIEL", "langue": "fr"}
    donnees.update(champs)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
        return recevoir(donnees, "FORMULAIRE", public=True)[0]


@pytest.mark.django_db
def test_modeles_installes_dans_les_cinq_langues(actif):
    assert ModeleMessage.objects.count() == 6 * 5
    assert messages.installer_modeles() == 0  # rien en double, rien d'écrasé


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_accuse_de_reception_automatique(actif):
    mail.outbox = []
    d = _dossier()
    assert len(mail.outbox) == 1
    assert d.numero in mail.outbox[0].subject and "Awa" in mail.outbox[0].body and "/plainte/suivi" in mail.outbox[0].body
    assert "Récit" not in mail.outbox[0].body and "L'équipe du projet" in mail.outbox[0].body
    action = ActionDossier.objects.get(dossier=d, objet="ACCUSE_RECEPTION")
    assert action.details["statut_envoi"] == "ENVOYE" and action.canal == "COURRIEL"
    # En anglais pour un dépôt en anglais ; rien pour un anonyme ou sans réponse souhaitée.
    mail.outbox = []
    _dossier(langue="en")
    assert mail.outbox[-1].subject.startswith("Your feedback")
    _dossier(anonyme=True)
    _dossier(mode_reponse="AUCUN")
    assert len(mail.outbox) == 1
    Mecanisme.objects.filter(pk=1).update(accuse_reception_auto=False)
    _dossier()
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_sms_simule_puis_passerelle(actif, admin):
    d = _dossier(mode_reponse="SMS")
    action = ActionDossier.objects.get(dossier=d, objet="ACCUSE_RECEPTION")
    assert action.canal == "SMS" and action.details["statut_envoi"] == "SIMULE"
    envois = []

    class Reponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with override_settings(PLAINTES_SMS_URL="https://passerelle.test/sms", PLAINTES_SMS_JETON="secret"), \
            pytest.MonkeyPatch.context() as m:
        m.setattr("urllib.request.urlopen", lambda requete, timeout: envois.append(requete) or Reponse())
        r = _client(admin).post(f"{URL}dossiers/{d.id}/envoyer-message/", {"objet": "PRISE_EN_CHARGE", "canal": "SMS"}, format="json")
    assert r.status_code == 200 and envois and envois[0].headers["Authorization"] == "Bearer secret"
    assert ActionDossier.objects.filter(dossier=d, objet="PRISE_EN_CHARGE").get().details["statut_envoi"] == "ENVOYE"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_decision_et_confidentialite(actif, admin):
    d = _dossier()
    c = _client(admin)
    assert "objet" in c.post(f"{URL}dossiers/{d.id}/envoyer-message/", {"objet": "DECISION", "canal": "COURRIEL"}, format="json").data
    c.post(f"{URL}dossiers/{d.id}/decider/", {"decision": "La pompe sera réparée lundi."}, format="json")
    apercu = c.get(f"{URL}dossiers/{d.id}/apercu-message/?objet=DECISION&canal=COURRIEL").data
    assert "La pompe sera réparée lundi." in apercu["texte"]
    r = c.post(f"{URL}dossiers/{d.id}/envoyer-message/", {"objet": "DECISION", "canal": "COURRIEL",
                                                         "texte": apercu["texte"] + "\nMerci."}, format="json")
    assert r.data["statut"] == "REPONDU" and mail.outbox[-1].body.endswith("Merci.")
    # Dossier confidentiel : jamais la décision ni le récit dans le message.
    s = _dossier(categorie="Exploitation et abus sexuels")
    Dossier.objects.filter(pk=s.pk).update(decision="Détail sensible de la décision")
    s.refresh_from_db()
    sujet, texte, _ = messages.rediger(s, "DECISION", "COURRIEL")
    assert "Détail sensible" not in texte and "Récit" not in texte and "confidentielle" in texte
    # Anonyme ou sans coordonnée : refusé.
    a = _dossier(anonyme=True)
    assert c.post(f"{URL}dossiers/{a.id}/envoyer-message/", {"objet": "CLOTURE", "canal": "SMS"}, format="json").status_code == 400
