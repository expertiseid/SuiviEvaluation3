"""Périodes de rapportage : ouverture et fermeture de la saisie (voir apps.projects.rapportage)."""
import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User

from .models import Activite, FenetreRapportage, ParametresRapportage, PerimetreFermeture, Projet, SousActivite
from .rapportage import etat_saisie

AUJOURDHUI = timezone.localdate()
JOUR = datetime.timedelta(days=1)


@pytest.fixture
def clients(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_rap", password="x", role=ROLE_ADMIN))
    charge = APIClient()
    charge.force_authenticate(
        User.objects.create_user(username="se_rap", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    )
    return admin, charge


@pytest.fixture
def projet(db):
    projet = Projet.objects.create(nom="P", code="RAP-1", date_debut="2026-01-01", date_fin="2027-12-31", statut="EN_COURS")
    return projet


def _controle(perimetre=PerimetreFermeture.REALISATIONS):
    parametres = ParametresRapportage.courants()
    parametres.controle_actif = True
    parametres.perimetre = perimetre
    parametres.save()


def _point(client, activite):
    return client.post(
        "/api/v1/points-suivi/",
        {"activite": activite.id, "periode_debut": "2026-01-01", "periode_fin": "2026-01-31", "quantite_realisee": 2},
    )


@pytest.mark.django_db
def test_sans_controle_tout_est_ouvert(projet, clients):
    _, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="A", quantite_prevue=10)
    assert etat_saisie(projet).ouverte
    assert _point(charge, activite).status_code == 201


@pytest.mark.django_db
def test_fermeture_des_realisations_seulement(projet, clients):
    admin, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="A", quantite_prevue=10)
    tache = SousActivite.objects.create(activite=activite, libelle="T")
    FenetreRapportage.objects.create(libelle="T4", date_debut=AUJOURDHUI + 10 * JOUR, date_fin=AUJOURDHUI + 20 * JOUR)
    _controle()

    etat = etat_saisie(projet)
    assert not etat.ouverte and "T4" in etat.message
    r = _point(charge, activite)
    assert r.status_code == 403 and "Prochaine période" in str(r.data)
    # Planification toujours modifiable ; avancement d'une tâche = réalisation, refusé.
    assert charge.patch(f"/api/v1/activites/{activite.id}/", {"libelle": "B"}, format="json").status_code == 200
    assert charge.patch(f"/api/v1/sous-activites/{tache.id}/", {"libelle": "T2"}, format="json").status_code == 200
    assert charge.patch(f"/api/v1/sous-activites/{tache.id}/", {"avancement": 50}, format="json").status_code == 403
    # L'administrateur peut toujours corriger.
    assert _point(admin, activite).status_code == 201


@pytest.mark.django_db
def test_fermeture_de_tout_le_projet(projet, clients):
    _, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="A")
    _controle(PerimetreFermeture.TOUT)
    assert charge.patch(f"/api/v1/activites/{activite.id}/", {"libelle": "B"}, format="json").status_code == 403


@pytest.mark.django_db
def test_periode_generale_ouverte(projet, clients):
    _, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="A", quantite_prevue=10)
    FenetreRapportage.objects.create(libelle="En cours", date_debut=AUJOURDHUI - JOUR, date_fin=AUJOURDHUI + JOUR)
    _controle()
    assert etat_saisie(projet).ouverte
    assert _point(charge, activite).status_code == 201


@pytest.mark.django_db
def test_reglages_propres_au_projet(projet, clients):
    admin, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="A", quantite_prevue=10)
    FenetreRapportage.objects.create(libelle="Générale", date_debut=AUJOURDHUI - JOUR, date_fin=AUJOURDHUI + JOUR)

    # Fermé sauf périodes propres : la période générale ne l'ouvre pas (moyen de pression).
    projet.saisie = Projet.Saisie.FERMEE
    projet.save()
    assert not etat_saisie(projet).ouverte
    assert _point(charge, activite).status_code == 403
    FenetreRapportage.objects.create(projet=projet, libelle="Rattrapage", date_debut=AUJOURDHUI, date_fin=AUJOURDHUI)
    assert etat_saisie(projet).ouverte

    # Toujours ouvert, même avec le contrôle général actif et aucune période.
    FenetreRapportage.objects.all().delete()
    _controle()
    projet.saisie = Projet.Saisie.OUVERTE
    projet.save()
    assert _point(charge, activite).status_code == 201

    # Seul l'administrateur règle l'ouverture du projet.
    assert charge.patch(f"/api/v1/projets/{projet.id}/", {"saisie": "FERMEE"}, format="json").status_code == 403
    assert admin.patch(f"/api/v1/projets/{projet.id}/", {"saisie": "FERMEE"}, format="json").status_code == 200
    assert admin.get(f"/api/v1/projets/{projet.id}/").data["etat_saisie"]["ouverte"] is False


@pytest.mark.django_db
def test_api_parametres_et_periodes_reserves_a_l_administrateur(clients):
    admin, charge = clients
    assert charge.patch("/api/v1/parametres-rapportage/", {"controle_actif": True}, format="json").status_code == 403
    assert admin.patch("/api/v1/parametres-rapportage/", {"controle_actif": True}, format="json").data["controle_actif"]
    periode = {"libelle": "T1", "date_debut": "2026-04-01", "date_fin": "2026-04-15"}
    assert charge.post("/api/v1/periodes-rapportage/", periode).status_code == 403
    assert admin.post("/api/v1/periodes-rapportage/", periode).status_code == 201
    assert admin.post("/api/v1/periodes-rapportage/", {**periode, "date_fin": "2026-03-01"}).status_code == 400
