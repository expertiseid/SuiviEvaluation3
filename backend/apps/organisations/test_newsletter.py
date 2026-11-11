"""Newsletter du site : inscription avec confirmation, désinscription, envoi depuis la console."""
import re

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User

from . import newsletter
from .models import AbonneNewsletter, EnvoiNewsletter

pytestmark = pytest.mark.django_db(databases=["default", "central"])
PUBLIC = "/api/v1/public/site/newsletter/"
CONSOLE = "/api/v1/console/site/newsletter/"


@pytest.fixture(autouse=True)
def courriel(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.URL_SITE = "https://site.test"
    monkeypatch.setattr(newsletter, "PAUSE_ENTRE_ENVOIS", 0)
    monkeypatch.setattr(newsletter, "lancer", lambda envoi: newsletter.diffuser(envoi.pk))
    cache.clear()


def _jeton(message):
    return re.search(r"(?:confirmer|desinscrire)=([\w-]+)", message.body).group(1)


def test_inscription_confirmation_desinscription():
    site = APIClient()
    assert site.post(PUBLIC, {"courriel": "x@b.org", "langue": "fr"}, format="json").status_code == 400  # sans accord
    premiere = site.post(PUBLIC, {"courriel": "Awa@ONG.bf", "langue": "en", "accord": True}, format="json")
    assert premiere.status_code == 200 and mail.outbox[-1].to == ["awa@ong.bf"]
    assert "newsletter.html?confirmer=" in mail.outbox[-1].body
    abonne = AbonneNewsletter.objects.get()
    assert (abonne.statut, abonne.langue) == ("EN_ATTENTE", "en")
    # Pas confirmée : un nouveau lien ; confirmée : rien, mais la même réponse.
    assert site.post(PUBLIC, {"courriel": "awa@ong.bf", "langue": "en", "accord": True}, format="json").data == premiere.data
    assert len(mail.outbox) == 2
    assert site.post(PUBLIC + "confirmer/", {"jeton": _jeton(mail.outbox[-1])}, format="json").status_code == 200
    assert AbonneNewsletter.objects.get().statut == "ACTIF"
    assert site.post(PUBLIC, {"courriel": "awa@ong.bf", "accord": True}, format="json").data == premiere.data
    assert len(mail.outbox) == 2
    assert site.post(PUBLIC + "confirmer/", {"jeton": "inconnu"}, format="json").status_code == 400
    # Bouton « Se désabonner » de la messagerie : POST, jeton dans l'adresse.
    assert site.post(PUBLIC + f"desinscrire/?jeton={abonne.jeton}").status_code == 200
    assert AbonneNewsletter.objects.get().statut == "DESINSCRIT"


def test_envoi_depuis_la_console():
    for courriel, langue, confirme in (("fr@ong.bf", "fr", True), ("en@ong.bf", "en", True), ("attente@ong.bf", "fr", False)):
        a = AbonneNewsletter.objects.create(courriel=courriel, langue=langue, jeton=f"j-{langue}-{confirme}")
        if confirme:
            a.confirme_le = a.cree_le
            a.save()
    assert APIClient().get(CONSOLE + "abonnes/").status_code in (401, 403)
    console = APIClient()
    console.force_authenticate(User.objects.create_superuser(username="op_nl", password="x", email="op@expertise-id.com", role="ADMIN"))
    assert console.get(CONSOLE + "envois/resume/").data == {"actifs": 2, "en_attente": 1, "desinscrits": 0}
    envoi = console.post(CONSOLE + "envois/", {"sujet": "Nouveautés", "contenu": "Bonjour,\n\nVoici les nouveautés.",
                                                "traductions": {"en": {"sujet": "News", "contenu": "Hello,\n\nHere is the news."}}},
                         format="json").data
    # Essai à l'opérateur, dans la langue choisie.
    assert console.post(CONSOLE + f"envois/{envoi['id']}/essai/", {"langue": "en"}, format="json").status_code == 200
    assert mail.outbox[-1].to == ["op@expertise-id.com"] and mail.outbox[-1].subject == "News"
    mail.outbox.clear()
    assert console.post(CONSOLE + f"envois/{envoi['id']}/envoyer/").status_code == 200
    recus = {m.to[0]: m for m in mail.outbox}
    assert set(recus) == {"fr@ong.bf", "en@ong.bf"}  # l'adresse non confirmée ne reçoit rien
    assert recus["en@ong.bf"].subject == "News" and recus["fr@ong.bf"].subject == "Nouveautés"
    assert "desinscrire=j-fr-True" in recus["fr@ong.bf"].body and "List-Unsubscribe" in recus["fr@ong.bf"].extra_headers
    envoi = EnvoiNewsletter.objects.get()
    assert (envoi.statut, envoi.destinataires, envoi.envoyes, envoi.echecs) == ("ENVOYE", 2, 2, 0)
    # Une seule fois, et plus modifiable.
    assert console.post(CONSOLE + f"envois/{envoi.id}/envoyer/").status_code == 400
    assert console.patch(CONSOLE + f"envois/{envoi.id}/", {"sujet": "Autre"}, format="json").status_code == 400
    export = console.get(CONSOLE + "abonnes/exporter/")
    assert export.status_code == 200 and export["Content-Type"].startswith("application/vnd.openxmlformats")
