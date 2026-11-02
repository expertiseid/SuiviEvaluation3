"""Lot 9 : habilitation confidentielle à double validation (scénario 18) et journal d'audit du mécanisme."""
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.core.models import EvenementAudit

from . import habilitations
from .habilitations import habiliter_d_office
from .models import Categorie, Dossier, EtapeCircuit, HabilitationSensible, Mecanisme, TypeRetour
from .reception import dossiers_visibles, recevoir

URL = "/api/v1/plaintes/"


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def _personne(nom, role=ROLE_CHARGE_SE, **champs):
    return User.objects.create_user(username=nom, password="x", role=role, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE,
                                    email=f"{nom}@exemple.bf", **champs)


@pytest.fixture(autouse=True)
def sans_differe(monkeypatch):
    monkeypatch.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())


@pytest.fixture
def admin(db):
    return _personne("adm_hab", role=ROLE_ADMIN)


@pytest.fixture
def point_focal(db):
    return _personne("pf_hab")


@pytest.fixture
def actif(admin, point_focal):
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=12, conservation_sensible_mois=24)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    habiliter_d_office(point_focal)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200


def _sensible():
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Récit confidentiel.",
               "consentement": True, "categorie": Categorie.objects.get(nom="Exploitation et abus sexuels").id}
    return recevoir(donnees, "TELEPHONE")[0]


@pytest.mark.django_db
def test_double_validation(actif, admin, point_focal):
    nouvelle = _personne("nouvelle_hab")
    # Personne ne s'attribue une habilitation ; la demande exige un motif.
    assert _client(point_focal).post(URL + "habilitations/", {"utilisateur": point_focal.id, "motif": "x"},
                                     format="json").status_code == 400
    assert _client(admin).post(URL + "habilitations/", {"utilisateur": nouvelle.id}, format="json").status_code == 400
    # Une personne sans habilitation ne peut ni demander ni consulter.
    assert _client(nouvelle).get(URL + "habilitations/").status_code == 403
    reponse = _client(admin).post(URL + "habilitations/", {"utilisateur": nouvelle.id, "motif": "Point focal PSEA adjoint"},
                                  format="json")
    assert reponse.status_code == 200 and reponse.data["statut"] == "EN_ATTENTE"
    h = HabilitationSensible.objects.get(pk=reponse.data["id"])
    assert not habilitations.est_habilite(nouvelle)
    # Le demandeur ne valide pas sa propre demande ; la personne concernée non plus.
    assert _client(admin).post(f"{URL}habilitations/{h.id}/valider/", {"accepter": True}, format="json").status_code == 403
    assert _client(nouvelle).post(f"{URL}habilitations/{h.id}/valider/", {"accepter": True}, format="json").status_code == 403
    # Une deuxième personne déjà habilitée valide : effet immédiat.
    valide = _client(point_focal).post(f"{URL}habilitations/{h.id}/valider/", {"accepter": True}, format="json")
    assert valide.status_code == 200 and valide.data["statut"] == "ACTIVE" and habilitations.est_habilite(nouvelle)
    operations = list(EvenementAudit.objects.filter(action="HABILITATION").values_list("details__operation", flat=True))
    assert "demande" in operations and "validation" in operations


@pytest.mark.django_db
def test_refus_motive(actif, admin, point_focal):
    nouvelle = _personne("refus_hab")
    h = _client(admin).post(URL + "habilitations/", {"utilisateur": nouvelle.id, "motif": "Demande"}, format="json").data
    assert _client(point_focal).post(f"{URL}habilitations/{h['id']}/valider/", {"accepter": False}, format="json").status_code == 400
    refus = _client(point_focal).post(f"{URL}habilitations/{h['id']}/valider/",
                                      {"accepter": False, "commentaire": "Pas de besoin"}, format="json")
    assert refus.data["statut"] == "REFUSEE" and not habilitations.est_habilite(nouvelle)


@pytest.mark.django_db
def test_sans_habilitation_pas_de_dossier_confidentiel(actif, admin, point_focal):
    """Responsable d'étape mais sans habilitation en vigueur : aucun accès, aucune désignation possible."""
    dossier = _sensible()
    assert dossiers_visibles(point_focal).filter(pk=dossier.pk).exists()
    intrus = _personne("intrus_hab")
    etape = EtapeCircuit.objects.filter(circuit__sensible=True).first()
    refus = _client(admin).patch(f"{URL}etapes/{etape.id}/", {"responsable": intrus.id}, format="json")
    assert refus.status_code == 400 and "responsable" in refus.data
    EtapeCircuit.objects.filter(pk=etape.pk).update(responsable=intrus)  # contournement direct de la base
    assert not dossiers_visibles(intrus).filter(pk=dossier.pk).exists()
    assert not dossiers_visibles(intrus).filter(sensible=True).exists()


@pytest.mark.django_db
def test_retrait_immediat(actif, admin, point_focal):
    dossier = _sensible()
    Dossier.objects.filter(pk=dossier.pk).update(responsable=point_focal)
    h = HabilitationSensible.objects.get(utilisateur=point_focal, statut="ACTIVE")
    assert _client(admin).post(f"{URL}habilitations/{h.id}/retirer/", {}, format="json").status_code == 400
    assert _client(admin).post(f"{URL}habilitations/{h.id}/retirer/", {"motif": "Départ"}, format="json").status_code == 200
    # Effet à la requête suivante ; le dossier qui lui était confié est à réaffecter.
    assert _client(point_focal).get(f"{URL}dossiers/{dossier.id}/").status_code == 404
    dossier.refresh_from_db()
    assert dossier.responsable is None and dossier.actions.filter(type="AFFECTATION").exists()
    assert any("n'a pas (ou plus) d'habilitation" in e for e in _client(admin).get(URL + "mecanisme/").data["controles"])


@pytest.mark.django_db
def test_premiere_habilitation_par_courriel_et_delai(admin):
    """Aucune deuxième personne pour valider : code par courriel, puis 24 heures de délai."""
    pf = _personne("premiere_hab")
    reponse = _client(admin).post(URL + "habilitations/", {"utilisateur": pf.id, "motif": "Premier point focal"}, format="json")
    assert reponse.status_code == 200 and reponse.data["premiere"] and reponse.data["peut_confirmer"]
    code = mail.outbox[-1].body.split(" : ")[1].split()[0]
    h = reponse.data["id"]
    assert _client(admin).post(f"{URL}habilitations/{h}/confirmer/", {"code": "000000"}, format="json").status_code == 400
    assert _client(admin).post(f"{URL}habilitations/{h}/confirmer/", {"code": code.lower()}, format="json").data["statut"] == "EN_DELAI"
    assert not habilitations.est_habilite(pf)
    HabilitationSensible.objects.filter(pk=h).update(active_le=timezone.now() - timedelta(minutes=1))
    assert habilitations.est_habilite(pf)
    assert habilitations.activer_echues() == 1 and HabilitationSensible.objects.get(pk=h).statut == "ACTIVE"


@pytest.mark.django_db
def test_journal_audit_du_mecanisme(actif, admin, point_focal):
    dossier = _sensible()
    _client(point_focal).get(f"{URL}dossiers/{dossier.id}/")
    _client(point_focal).get(f"{URL}dossiers/{dossier.id}/")  # même personne, moins de 10 minutes : une seule trace
    assert EvenementAudit.objects.filter(action="CONSULTATION_SENSIBLE", objet=dossier.numero).count() == 1
    assert EvenementAudit.objects.filter(action="DOSSIER", objet=dossier.numero, details__type="RECEPTION").exists()
    priorite = _client(admin).get(URL + "priorites/").data[0]
    _client(admin).patch(f"{URL}priorites/{priorite['id']}/", {"delai_jours": 9}, format="json")
    evenement = EvenementAudit.objects.filter(action="CONFIGURATION").first()
    assert evenement.details["operation"] == "modification" and evenement.details["champs"] == ["delai_jours"]
    # Le journal ne contient jamais le récit.
    assert not EvenementAudit.objects.filter(details__icontains="Récit confidentiel").exists()
    assert "Récit confidentiel" not in str(list(EvenementAudit.objects.values_list("objet", "details")))
