"""Lot 5 : chiffrement, personnes mises en cause et circuit alternatif, marquage et levée, assistance,
export motivé, conservation et suspension légale (scénarios 6, 7 et 13)."""
import datetime

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE, ROLE_CHEF_PROJET
from apps.accounts.models import User
from apps.notifications.models import Notification

from .habilitations import habiliter_d_office
from . import confidentiel
from .controles import controler_activation
from .models import ActionDossier, Categorie, Circuit, Dossier, EtapeCircuit, Mecanisme, Prestataire, TypeRetour
from .reception import recevoir

URL = "/api/v1/plaintes/"


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_conf", password="x", role=ROLE_ADMIN)


@pytest.fixture
def point_focal(db):
    return User.objects.create_user(username="pf_conf", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def referent(db):
    """Point focal du circuit alternatif (direction, référent extérieur…)."""
    return User.objects.create_user(username="ref_conf", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def agent(db):
    return User.objects.create_user(username="agent_conf", password="x", role=ROLE_CHEF_PROJET,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def actif(admin, point_focal, referent):
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=12, conservation_sensible_mois=24)
    mecanisme = Mecanisme.courant()
    EtapeCircuit.objects.filter(circuit__sensible=True).exclude(circuit=mecanisme.circuit_alternatif).update(responsable=point_focal)
    EtapeCircuit.objects.filter(circuit=mecanisme.circuit_alternatif).update(responsable=referent)
    habiliter_d_office(point_focal, referent)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200


def _dossier(categorie="Retard", saisi_par=None, **champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Récit très confidentiel.",
               "consentement": True, "categorie": Categorie.objects.get(nom=categorie).id, "nom": "Awa Témoin",
               "telephone": "70112233", "mode_reponse": "TELEPHONE"}
    donnees.update(champs)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
        return recevoir(donnees, "TELEPHONE", saisi_par=saisi_par)[0]


@pytest.mark.django_db
def test_donnees_protegees_chiffrees_en_base(actif, admin):
    d = _dossier()
    _client(admin).post(f"{URL}dossiers/{d.id}/noter/", {"texte": "Note sensible"}, format="json")
    with connection.cursor() as c:
        c.execute("select description, nom, telephone from plaintes_dossier where id = %s", [d.id])
        brut = c.fetchone()
        c.execute("select texte from plaintes_actiondossier where dossier_id = %s and type = 'NOTE'", [d.id])
        note = c.fetchone()[0]
        c.execute("select description from plaintes_historicaldossier where id = %s", [d.id])
        historique = [r[0] for r in c.fetchall()]
    assert all(v.startswith("chiffre:") and "Awa" not in v and "Récit" not in v for v in brut)
    assert note.startswith("chiffre:") and all(h.startswith("chiffre:") for h in historique)
    lu = _client(admin).get(f"{URL}dossiers/{d.id}/").data
    assert lu["description"] == "Récit très confidentiel." and lu["nom"] == "Awa Témoin"


@pytest.mark.django_db
def test_mise_en_cause_et_circuit_alternatif(actif, admin, point_focal, referent, agent):
    """Scénario 7 : le dossier visant un point focal part au circuit alternatif ; la personne visée n'y a aucun accès."""
    d = _dossier(saisi_par=agent, mis_en_cause_utilisateurs=[point_focal.id], mis_en_cause_libre="Un chauffeur du partenaire")
    d.refresh_from_db()
    assert d.sensible and d.circuit == Mecanisme.courant().circuit_alternatif
    assert _client(point_focal).get(f"{URL}dossiers/{d.id}/").status_code == 404
    assert _client(point_focal).get(URL + "dossiers/").data["count"] == 0
    assert _client(referent).get(f"{URL}dossiers/{d.id}/").status_code == 200
    assert not Notification.objects.filter(destinataire=point_focal).exists()
    assert "responsable" in _client(admin).post(f"{URL}dossiers/{d.id}/affecter/", {"responsable": point_focal.id}, format="json").data
    # Même un Administrateur mis en cause perd l'accès.
    d2 = _dossier(saisi_par=agent)
    _client(referent).post(f"{URL}dossiers/{d2.id}/mettre-en-cause/", {"utilisateurs": [admin.id]}, format="json")
    assert _client(admin).get(f"{URL}dossiers/{d2.id}/").status_code == 404
    # Activation : un circuit alternatif valide est obligatoire.
    Mecanisme.objects.filter(pk=1).update(circuit_alternatif=None)
    assert any("alternatif" in c for c in controler_activation(Mecanisme.courant()))


@pytest.mark.django_db
def test_marquage_manuel_et_levee_motivee(actif, admin, point_focal):
    lecteur = User.objects.create_user(username="lecteur_conf", password="x", role=ROLE_CHARGE_SE,
                                       acces_modules={"/plaintes": "LECTURE"})
    d = _dossier()
    c = APIClient()  # vrai jeton : le contrôle des modules passe avant l'authentification DRF
    from apps.accounts.double_auth import jetons

    c.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons(lecteur)['access']}")  # jeton réel, code par courriel franchi
    assert c.post(f"/api/v1/plaintes-signaler/{d.id}/", {"motif": "Intimidation"}, format="json").data == {
        "numero": d.numero, "visible": False}
    d.refresh_from_db()
    assert d.sensible and d.circuit.sensible and d.actions.filter(type=ActionDossier.Type.SENSIBILITE).exists()
    assert c.get(f"{URL}dossiers/{d.id}/").status_code == 404
    # Levée : seulement une personne habilitée, avec un motif.
    assert _client(lecteur).post(f"{URL}dossiers/{d.id}/lever-sensibilite/", {"motif": "x"}, format="json").status_code in (400, 403, 404)
    assert "motif" in _client(point_focal).post(f"{URL}dossiers/{d.id}/lever-sensibilite/", {}, format="json").data
    r = _client(point_focal).post(f"{URL}dossiers/{d.id}/lever-sensibilite/", {"motif": "Signalement sans objet"}, format="json")
    assert r.status_code == 200 and r.data["sensible"] is False and not r.data["circuit_nom"].startswith("Circuit confidentiel")
    # Catégorie sensible : la levée est refusée.
    s = _dossier(categorie="Exploitation et abus sexuels")
    assert _client(point_focal).post(f"{URL}dossiers/{s.id}/lever-sensibilite/", {"motif": "x"}, format="json").status_code == 400


@pytest.mark.django_db
def test_assistance_et_export_motive(actif, admin, point_focal):
    s = _dossier(categorie="Exploitation et abus sexuels")
    p = Prestataire.objects.create(nom="Centre d'écoute", type="PSYCHOSOCIAL")
    c = _client(point_focal)
    assert "consentement" in c.post(f"{URL}dossiers/{s.id}/assistance/", {"prestataire": p.id}, format="json").data
    r = c.post(f"{URL}dossiers/{s.id}/assistance/", {"prestataire": p.id, "consentement": True, "date": "2026-11-02"}, format="json")
    assert r.data["referencements"][0]["prestataire"] == "Centre d'écoute"
    action = ActionDossier.objects.get(dossier=s, type=ActionDossier.Type.ASSISTANCE)
    assert action.texte == "" and action.details["prestataire"] == "Centre d'écoute"
    # Export d'un dossier confidentiel : motif et confirmation exigés, tracé au journal.
    assert "motif" in c.post(f"{URL}dossiers/{s.id}/exporter/", {}, format="json").data
    assert "confirmation" in c.post(f"{URL}dossiers/{s.id}/exporter/", {"motif": "Transmission au comité"}, format="json").data
    r = c.post(f"{URL}dossiers/{s.id}/exporter/", {"motif": "Transmission au comité", "confirmation": True}, format="json")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf" and r.content[:4] == b"%PDF"
    assert ActionDossier.objects.get(dossier=s, type=ActionDossier.Type.EXPORT).texte == "Transmission au comité"


@pytest.mark.django_db
def test_conservation_suspension_et_anonymisation(actif, admin, point_focal):
    d = _dossier()
    _client(admin).post(f"{URL}dossiers/{d.id}/cloturer/", {"issue": "RESOLU", "motif": "Réglé", "retour_donne": True,
                                                            "decision": "Réparation faite"}, format="json")
    Dossier.objects.filter(pk=d.pk).update(date_cloture=datetime.date(2024, 1, 15))  # conservation 12 mois écoulée
    assert [x.pk for x in confidentiel.a_anonymiser()] == [d.pk]
    assert _client(admin).get(URL + "dossiers/?vue=a_anonymiser").data["count"] == 1
    # Suspension légale : réservée à l'Administrateur, elle bloque l'anonymisation.
    assert _client(point_focal).post(f"{URL}dossiers/{d.id}/suspendre/", {"motif": "Plainte en justice"}, format="json").status_code == 400
    _client(admin).post(f"{URL}dossiers/{d.id}/suspendre/", {"motif": "Plainte en justice"}, format="json")
    assert confidentiel.a_anonymiser() == []
    assert _client(admin).post(f"{URL}dossiers/{d.id}/anonymiser/", {"confirmation": True}, format="json").status_code == 400
    _client(admin).post(f"{URL}dossiers/{d.id}/suspendre/", {"motif": "Procédure close", "suspendre": False}, format="json")
    # Anonymisation : confirmation exigée, contenu et historique détaillé supprimés, statistiques gardées.
    assert "confirmation" in _client(admin).post(f"{URL}dossiers/{d.id}/anonymiser/", {}, format="json").data
    r = _client(admin).post(f"{URL}dossiers/{d.id}/anonymiser/", {"confirmation": True}, format="json")
    assert r.status_code == 200 and r.data["anonymise"] and r.data["nom"] == "" and r.data["decision"] == ""
    d.refresh_from_db()
    assert "Récit" not in d.description and d.statut == "CLOTURE" and d.categorie.nom == "Retard" and d.numero
    assert not ActionDossier.objects.filter(dossier=d).exclude(texte="").exists()
    assert d.history.count() == 0


@pytest.mark.django_db
def test_effacement_definitif(actif, admin, point_focal):
    """Droit à l'effacement : Administrateur seulement, numéro recopié, bloqué par la suspension légale ; rien ne reste."""
    from apps.core.models import EvenementAudit

    d = _dossier()
    _client(admin).post(f"{URL}dossiers/{d.id}/noter/", {"texte": "Note"}, format="json")
    effacer = f"{URL}dossiers/{d.id}/effacer/"
    assert _client(point_focal).post(effacer, {"raison": "ERREUR_SAISIE", "numero": d.numero}, format="json").status_code == 400
    erreurs = _client(admin).post(effacer, {"raison": "INVENTEE", "numero": "MGP-0000"}, format="json").data
    assert set(erreurs) == {"raison", "numero"}
    _client(admin).post(f"{URL}dossiers/{d.id}/suspendre/", {"motif": "Plainte en justice"}, format="json")
    assert _client(admin).post(effacer, {"raison": "DEMANDE_PERSONNE", "numero": d.numero}, format="json").status_code == 400
    _client(admin).post(f"{URL}dossiers/{d.id}/suspendre/", {"motif": "Procédure close", "suspendre": False}, format="json")

    reponse = _client(admin).post(effacer, {"raison": "DEMANDE_PERSONNE", "numero": d.numero.lower()}, format="json")
    assert reponse.status_code == 200 and reponse.data == {"numero": d.numero, "efface": True}
    assert not Dossier.objects.filter(pk=d.id).exists() and not ActionDossier.objects.filter(dossier_id=d.id).exists()
    assert not Dossier.history.filter(id=d.id).exists()
    trace = EvenementAudit.objects.get(action="SUPPRESSION", objet=d.numero)
    assert trace.details == {"raison": "DEMANDE_PERSONNE"} and trace.module == "plaintes"


@pytest.mark.django_db
def test_anonymisation_automatique_et_preuve_du_consentement(actif, admin):
    """Option du mécanisme : à l'échéance, anonymisation sans intervention ; le consentement accepté est gardé."""
    d = _dossier(consentement=True)
    assert d.consentement_le is not None and d.consentement_texte  # phrase par défaut
    Mecanisme.objects.filter(pk=1).update(texte_consentement="Clause de l'organisation.")
    assert _dossier(consentement=True).consentement_texte == "Clause de l'organisation."

    _client(admin).post(f"{URL}dossiers/{d.id}/cloturer/", {"issue": "RESOLU", "motif": "Réglé", "retour_donne": True,
                                                            "decision": "Réparation faite"}, format="json")
    Dossier.objects.filter(pk=d.pk).update(date_cloture=datetime.date(2024, 1, 15))
    assert confidentiel.anonymiser_automatiquement() == 0  # option désactivée par défaut
    Mecanisme.objects.filter(pk=1).update(anonymisation_automatique=True)
    assert confidentiel.anonymiser_automatiquement() == 1
    d.refresh_from_db()
    assert d.anonymise and d.nom == "" and d.history.count() == 0
    assert confidentiel.anonymiser_automatiquement() == 0  # une seule fois
