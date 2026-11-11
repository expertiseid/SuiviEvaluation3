"""Essais gratuits non convertis : avertis à J-30, J-15, J-5 et le jour J à 8 h, supprimés le jour J à 20 h."""
from datetime import date, datetime, time

import pytest
from django.core import mail
from django.utils import timezone

from . import essais
from .models import Organisation

pytestmark = pytest.mark.django_db(databases=["default", "central"])

FIN_ESSAI = date(2026, 9, 1)  # suppression prévue : 31/10/2026 (60 jours)


@pytest.fixture
def supprimes(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    liste = []
    monkeypatch.setattr("apps.organisations.gestion.supprimer", lambda org: liste.append(org.sous_domaine))
    return liste


def _org(**champs):
    valeurs = {"nom": "ONG Essai", "sous_domaine": "ong-essai", "base": "org_ong_essai", "offre": "ESSAI",
               "statut": "ACTIVE", "abonnement_fin": FIN_ESSAI, "courriel_contact": "contact@ong-essai.bf"}
    valeurs.update(champs)
    return Organisation.objects.using("central").create(**valeurs)


def _a(jour, heure=time(9, 0)):
    return timezone.make_aware(datetime.combine(jour, heure))


def test_calendrier_complet(supprimes):
    org = _org()
    assert essais.date_suppression(org) == date(2026, 10, 31)
    assert essais.traiter(_a(date(2026, 9, 20))) == {"avertis": [], "supprimes": []}
    for jour, attendu in ((date(2026, 10, 1), "dans 30 jours"), (date(2026, 10, 16), "dans 15 jours"),
                          (date(2026, 10, 26), "dans 5 jours")):
        assert essais.traiter(_a(jour))["avertis"] == ["ong-essai"]
        assert attendu in mail.outbox[-1].subject and mail.outbox[-1].to == ["contact@ong-essai.bf"]
        assert essais.traiter(_a(jour, time(15, 0)))["avertis"] == []  # une seule fois
    # Jour J : rien avant 8 h, dernier avertissement à 8 h, suppression à 20 h.
    assert essais.traiter(_a(date(2026, 10, 31), time(7, 0))) == {"avertis": [], "supprimes": []}
    assert essais.traiter(_a(date(2026, 10, 31), time(8, 0)))["avertis"] == ["ong-essai"]
    assert "ce soir" in mail.outbox[-1].subject
    assert essais.traiter(_a(date(2026, 10, 31), time(19, 0)))["supprimes"] == []
    assert essais.traiter(_a(date(2026, 10, 31), time(20, 0)))["supprimes"] == ["ong-essai"]
    assert supprimes == ["ong-essai"]
    assert len([m for m in mail.outbox if m.to == ["contact@ong-essai.bf"]]) == 4  # puis un mot à Expertise-ID


def test_abonnement_ou_nouvelle_fin_arretent_le_compte_a_rebours(supprimes):
    org = _org()
    essais.traiter(_a(date(2026, 10, 26)))  # J-5 déjà envoyé
    Organisation.objects.using("central").filter(pk=org.pk).update(offre="STANDARD")
    assert essais.traiter(_a(date(2026, 10, 31), time(21, 0))) == {"avertis": [], "supprimes": []}
    # Essai prolongé dans la console : le calendrier repart de la nouvelle fin.
    Organisation.objects.using("central").filter(pk=org.pk).update(offre="ESSAI", abonnement_fin=date(2026, 10, 15))
    assert essais.traiter(_a(date(2026, 10, 31), time(21, 0))) == {"avertis": [], "supprimes": []}
    assert Organisation.objects.using("central").get(pk=org.pk).suppression_essai["date"] == "2026-12-14"
    assert supprimes == []


def test_jamais_sans_dernier_avertissement_8_heures_avant(supprimes):
    """Tâche planifiée interrompue : le dernier avertissement part, la suppression attend 8 heures."""
    _org()
    assert essais.traiter(_a(date(2026, 11, 3), time(10, 0))) == {"avertis": ["ong-essai"], "supprimes": []}
    assert essais.traiter(_a(date(2026, 11, 3), time(17, 0)))["supprimes"] == []
    assert essais.traiter(_a(date(2026, 11, 3), time(18, 0)))["supprimes"] == ["ong-essai"]


def test_demonstration_et_offres_payantes_jamais_concernees(supprimes):
    _org(mode_demo=True)
    _org(sous_domaine="payant", base="org_payant", offre="STANDARD")
    assert essais.traiter(_a(date(2027, 1, 1))) == {"avertis": [], "supprimes": []}
