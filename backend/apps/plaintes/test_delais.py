"""Lot 4 du mécanisme de plaintes : échéances, jours ouvrés, rappels, retards, escalade, notifications."""
import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE, ROLE_CHEF_PROJET, ROLE_COORDO_GENERAL
from apps.accounts.models import User
from apps.notifications.models import Notification

from .habilitations import habiliter_d_office
from . import delais
from .models import ActionDossier, Categorie, Dossier, EtapeCircuit, JourFerie, Mecanisme, Priorite, TypeRetour
from .reception import recevoir

URL = "/api/v1/plaintes/"
LUNDI = datetime.date(2026, 11, 2)


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_delais", password="x", role=ROLE_ADMIN)


@pytest.fixture
def coordo(db):
    return User.objects.create_user(username="coordo_delais", password="x", role=ROLE_COORDO_GENERAL,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def gestionnaire(db):
    return User.objects.create_user(username="gest_delais", password="x", role=ROLE_CHEF_PROJET,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def point_focal(db):
    return User.objects.create_user(username="pf_delais", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def actif(admin, point_focal):
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    habiliter_d_office(point_focal)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200


def _dossier(categorie="Retard", date_reception=None, **champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Récit détaillé du problème.",
               "consentement": True, "categorie": Categorie.objects.get(nom=categorie).id,
               "date_reception": (date_reception or timezone.localdate()).isoformat()}
    donnees.update(champs)
    with pytest.MonkeyPatch.context() as m:  # notifications envoyées immédiatement (pas d'attente du commit)
        m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
        return recevoir(donnees, "TELEPHONE")[0]


def test_jours_ouvres(db):
    JourFerie.objects.create(date=datetime.date(2026, 11, 4), libelle="Férié de test")
    # Lundi + 3 jours ouvrés : mardi, (mercredi férié), jeudi, vendredi.
    assert delais.ajouter_jours(LUNDI, 3, True) == datetime.date(2026, 11, 6)
    # Vendredi + 1 jour ouvré : lundi suivant.
    assert delais.ajouter_jours(datetime.date(2026, 11, 6), 1, True) == datetime.date(2026, 11, 9)
    assert delais.ajouter_jours(LUNDI, 3, False) == datetime.date(2026, 11, 5)


@pytest.mark.django_db
def test_echeances_du_dossier_et_de_l_etape(actif, admin):
    Categorie.objects.filter(nom="Retard").update(delai_jours=20)
    d = _dossier(date_reception=LUNDI)
    # Le plus court entre catégorie (20) et priorité ; sans priorité : la catégorie.
    assert d.echeance == LUNDI + datetime.timedelta(days=20)
    assert d.echeance_etape == LUNDI + datetime.timedelta(days=1)  # étape « Réception » : 1 jour
    urgente = Priorite.objects.get(urgente=True)  # 3 jours
    _client(admin).post(f"{URL}dossiers/{d.id}/classer/", {"priorite": urgente.id}, format="json")
    d.refresh_from_db()
    assert d.echeance == LUNDI + datetime.timedelta(days=3)
    # Paramétrage : délai d'une priorité modifié → échéances des dossiers ouverts recalculées.
    _client(admin).patch(f"{URL}priorites/{urgente.id}/", {"delai_jours": 5}, format="json")
    d.refresh_from_db()
    assert d.echeance == LUNDI + datetime.timedelta(days=5)
    # Jours ouvrés activés.
    _client(admin).patch(URL + "mecanisme/", {"jours_ouvres": True}, format="json")
    d.refresh_from_db()
    assert d.echeance == datetime.date(2026, 11, 9)


@pytest.mark.django_db
def test_retard_rappel_unique_et_escalade(actif, admin, coordo, gestionnaire):
    d = _dossier(date_reception=timezone.localdate() - datetime.timedelta(days=60))
    _client(admin).post(f"{URL}dossiers/{d.id}/affecter/", {"responsable": gestionnaire.id}, format="json")
    Notification.objects.all().delete()
    assert _client(admin).get(URL + "dossiers/?vue=en_retard").data["count"] == 1
    assert delais.verifier_echeances() == 1
    d.refresh_from_db()
    assert d.en_retard and d.actions.filter(type=ActionDossier.Type.RETARD).count() == 1
    destinataires = set(Notification.objects.values_list("destinataire__username", flat=True))
    assert {"gest_delais", "coordo_delais", "adm_delais"} <= destinataires  # gestionnaire + escalade
    # Rejoué le même jour : aucun rappel en double, pas de second retard au journal.
    nombre = Notification.objects.count()
    assert delais.verifier_echeances() == 0 and Notification.objects.count() == nombre
    assert d.actions.filter(type=ActionDossier.Type.RETARD).count() == 1
    # Sans escalade : seul le gestionnaire est relancé (le lendemain).
    Mecanisme.objects.filter(pk=1).update(escalade_active=False)
    Notification.objects.all().delete()
    delais.verifier_echeances(timezone.localdate() + datetime.timedelta(days=1))
    assert set(Notification.objects.values_list("destinataire__username", flat=True)) == {"gest_delais"}


@pytest.mark.django_db
def test_echeance_proche_et_prolongation(actif, admin, coordo, gestionnaire):
    Categorie.objects.filter(nom="Retard").update(delai_jours=10)
    d = _dossier(date_reception=timezone.localdate() - datetime.timedelta(days=9))
    EtapeCircuit.objects.filter(circuit=d.circuit).update(delai_jours=None)
    d = Dossier.objects.get(pk=d.pk)
    delais.recalculer(d)
    _client(admin).post(f"{URL}dossiers/{d.id}/affecter/", {"responsable": gestionnaire.id}, format="json")
    Notification.objects.all().delete()
    assert delais.verifier_echeances() == 1
    assert list(Notification.objects.values_list("destinataire__username", flat=True)) == ["gest_delais"]
    assert "proche" in Notification.objects.get().titre
    # Prolongation : rôle autorisé, nombre de jours et motif exigés, tracée au journal.
    r = _client(gestionnaire).post(f"{URL}dossiers/{d.id}/prolonger/", {"jours": 10, "motif": "x"}, format="json")
    assert r.status_code == 400
    assert {"jours", "motif"} <= set(_client(coordo).post(f"{URL}dossiers/{d.id}/prolonger/", {}, format="json").data)
    ancienne = Dossier.objects.get(pk=d.pk).echeance
    r = _client(coordo).post(f"{URL}dossiers/{d.id}/prolonger/", {"jours": 10, "motif": "Attente du partenaire"}, format="json")
    assert r.status_code == 200 and r.data["jours_prolongation"] == 10
    assert Dossier.objects.get(pk=d.pk).echeance == ancienne + datetime.timedelta(days=10)
    assert d.actions.filter(type=ActionDossier.Type.PROLONGATION).exists()


@pytest.mark.django_db
def test_notifications_d_evenements_et_confidentialite(actif, admin, coordo, gestionnaire, point_focal):
    Notification.objects.all().delete()
    d = _dossier(priorite=Priorite.objects.get(urgente=True).id)
    titres = list(Notification.objects.values_list("titre", flat=True))
    assert any(d.numero in t and "urgent" in t for t in titres)  # superviseurs prévenus aussitôt
    Notification.objects.all().delete()
    with pytest.MonkeyPatch.context() as m:
        m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
        _client(admin).post(f"{URL}dossiers/{d.id}/affecter/", {"responsable": gestionnaire.id}, format="json")
    n = Notification.objects.get(destinataire=gestionnaire)
    assert d.numero in n.titre and n.lien == f"/plaintes/dossiers/{d.id}" and "Récit" in n.message
    # Dossier confidentiel : notifications neutres, seulement aux habilités.
    Notification.objects.all().delete()
    s = _dossier(categorie="Exploitation et abus sexuels")
    notes = Notification.objects.all()
    assert notes and all("confidentiel" in n.titre and "Récit" not in n.message for n in notes)
    assert set(notes.values_list("destinataire__username", flat=True)) <= {"pf_delais", "adm_delais"}
    assert s.sensible
