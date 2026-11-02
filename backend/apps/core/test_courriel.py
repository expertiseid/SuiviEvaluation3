"""Destinataires de courriel : adresses fictives retirées, liste blanche facultative."""
from unittest import mock

from django.core.mail import EmailMessage
from django.test import override_settings

from apps.core.courriel import EmailBackendFiltre, destinataire_autorise


@override_settings(EMAIL_DESTINATAIRES_AUTORISES="@expertise-id.com, invite@exemple.org")
def test_liste_blanche():
    assert destinataire_autorise("Alex@Expertise-ID.com") and destinataire_autorise("invite@exemple.org")
    assert not destinataire_autorise("demo_admin@example.org")
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", return_value=1) as envoi:
        backend = EmailBackendFiltre()
        retenu = EmailMessage("s", "t", "de@x.org", ["demo@example.org", "alex@expertise-id.com"])
        assert backend.send_messages([retenu, EmailMessage("s", "t", "de@x.org", ["autre@example.org"])]) == 1
        envoyes = envoi.call_args[0][0]
        assert len(envoyes) == 1 and envoyes[0].to == ["alex@expertise-id.com"]


@override_settings(EMAIL_DESTINATAIRES_AUTORISES="")
def test_sans_liste_blanche_toute_adresse_reelle_part():
    assert destinataire_autorise("quiconque@gmail.com") and destinataire_autorise("Alex@Expertise-ID.com")
    for fictive in ("demo@example.org", "a@sous.example.com", "b@poste.test", "c@machine.local", "", "sans-arobase"):
        assert not destinataire_autorise(fictive)
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", return_value=1) as envoi:
        message = EmailMessage("s", "t", "de@x.org", ["demo@example.org", "plaignant@gmail.com"])
        assert EmailBackendFiltre().send_messages([message]) == 1
        assert envoi.call_args[0][0][0].to == ["plaignant@gmail.com"]
        assert EmailBackendFiltre().send_messages([EmailMessage("s", "t", "de@x.org", ["demo@example.org"])]) == 0
