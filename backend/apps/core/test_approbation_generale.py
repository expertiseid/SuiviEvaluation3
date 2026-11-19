"""Approbation de toute modification, par onglet ou par personne (apps.core.approbation_generale)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import double_auth
from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import Role, User
from apps.beneficiaries.models import Beneficiaire
from apps.core.models import EtatApprobation, IdentiteOrganisation
from apps.indicators.models import Indicateur, ValeurIndicateur
from apps.projects.models import DemandeModification, Projet, Risque


def _client(user):
    """Vrai jeton : la requête traverse tous les filtres, comme dans la plateforme."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {double_auth.jetons(user)['access']}")
    return client


@pytest.fixture
def monde(db):
    Role.objects.update_or_create(code="APPROB_G", defaults={"libelle": "Approbateur", "peut_approuver": True, "visibilite_globale": True})
    projet = Projet.objects.create(nom="P", code="AG-1", date_debut="2026-01-01", date_fin="2026-12-31", statut="EN_COURS")
    agent = User.objects.create_user(username="agent_g", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    approbateur = User.objects.create_user(username="appr_g", password="x", role="APPROB_G", niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    admin = User.objects.create_user(username="adm_g", password="x", role=ROLE_ADMIN)
    return projet, agent, approbateur, admin


def _approuver(client, demande_id):
    return client.post(f"/api/v1/approbations/demandes/{demande_id}/", {"approuver": True}, format="json")


@pytest.mark.django_db
def test_onglets_soumis_a_approbation_pour_tous(monde):
    projet, agent, approbateur, admin = monde
    assert _client(agent).put("/api/v1/approbations/reglages/", {"modules_a_approuver": ["/beneficiaires"]},
                              format="json").status_code == 403
    reglage = _client(admin).put("/api/v1/approbations/reglages/", {"modules_a_approuver": ["/beneficiaires", "/indicateurs"]},
                                 format="json")
    assert reglage.status_code == 200 and reglage.data["modules_a_approuver"] == ["/beneficiaires", "/indicateurs"]

    # Bénéficiaire : rien n'est créé, la demande attend ; une saisie invalide est refusée tout de suite.
    reponse = _client(agent).post("/api/v1/beneficiaires/", {"nom": "Kaboré", "prenom": "Rasmata", "sexe": "F"}, format="json")
    assert reponse.status_code == 202 and not Beneficiaire.objects.filter(nom="Kaboré").exists()
    assert _client(agent).post("/api/v1/beneficiaires/", {"nom": "Sans sexe"}, format="json").status_code == 400
    demande = DemandeModification.objects.get(pk=reponse.json()["demande_approbation"])
    assert demande.cible == "generique" and demande.demandeur == agent
    assert _client(agent).get("/api/v1/approbations/").data["demandes"][0]["approuvable"] is False  # pas ses propres saisies
    liste = _client(approbateur).get("/api/v1/approbations/").data
    ligne = next(d for d in liste["demandes"] if d["id"] == demande.id)
    assert ligne["approuvable"] and {"champ": "nom", "valeur": "Kaboré"} in ligne["valeurs"]
    assert _approuver(_client(agent), demande.id).status_code == 403
    assert _approuver(_client(approbateur), demande.id).status_code == 200
    beneficiaire = Beneficiaire.objects.get(nom="Kaboré")
    assert beneficiaire.history.first().history_user == agent  # appliqué au nom de son auteur

    # Modification et suppression passent aussi par une demande ; l'Administrateur, lui, enregistre directement.
    assert _client(agent).patch(f"/api/v1/beneficiaires/{beneficiaire.id}/", {"prenom": "Awa"}, format="json").status_code == 202
    beneficiaire.refresh_from_db()
    assert beneficiaire.prenom == "Rasmata"
    assert _client(admin).post("/api/v1/beneficiaires/", {"nom": "Zongo", "prenom": "Ali", "sexe": "M"}, format="json").status_code == 201

    # Indicateur rattaché au projet : demande ; sa valeur saisie reste « en attente » (circuit des réalisations).
    reponse = _client(agent).post("/api/v1/indicateurs/", {"libelle": "Kits", "unite": "kits", "valeur_cible": 100,
                                                           "frequence_collecte": "TRIMESTRIELLE", "projet": projet.id}, format="json")
    assert reponse.status_code == 202
    assert DemandeModification.objects.get(pk=reponse.json()["demande_approbation"]).projet == projet
    indicateur = Indicateur.objects.create(libelle="Puits", unite="puits", valeur_cible=10, frequence_collecte="ANNUELLE", projet=projet)
    valeur = _client(agent).post("/api/v1/valeurs-indicateurs/", {"indicateur": indicateur.id, "periode_debut": "2026-01-01",
                                                                  "periode_fin": "2026-03-31", "valeur_realisee": 3}, format="json")
    assert valeur.status_code == 201
    assert ValeurIndicateur.tous.get(pk=valeur.data["id"]).etat_approbation == EtatApprobation.EN_ATTENTE

    # Un autre onglet (risques) n'est pas concerné ; une simple lecture (export) non plus.
    assert _client(agent).post("/api/v1/risques/", {"projet": projet.id, "libelle": "Pluies"}, format="json").status_code == 201
    export = _client(agent).post("/api/v1/indicateurs/formules/apercu/", {"formule": {"termes": [], "expression": ""}}, format="json")
    assert export.status_code != 202


@pytest.mark.django_db
def test_une_personne_pour_certains_onglets(monde):
    projet, agent, approbateur, admin = monde
    IdentiteOrganisation.courante()  # aucun onglet soumis pour tous
    reglage = _client(admin).patch(f"/api/v1/utilisateurs/{agent.id}/", {
        "saisies_a_approuver": True, "modules_a_approuver": ["/beneficiaires"], "approbateurs": [admin.id]}, format="json")
    assert reglage.status_code == 200, reglage.data
    agent = User.objects.get(pk=agent.pk)
    reponse = _client(agent).post("/api/v1/beneficiaires/", {"nom": "Ouédraogo", "prenom": "Issa", "sexe": "M"}, format="json")
    assert reponse.status_code == 202
    # Approbateur désigné : l'Administrateur ; l'autre approbateur (par son rôle) ne peut pas.
    assert _approuver(_client(approbateur), reponse.json()["demande_approbation"]).status_code == 403
    assert _approuver(_client(admin), reponse.json()["demande_approbation"]).status_code == 200
    assert Beneficiaire.objects.filter(nom="Ouédraogo").exists()
    # Hors des onglets choisis : enregistré directement.
    assert _client(agent).post("/api/v1/risques/", {"projet": projet.id, "libelle": "Pluies"}, format="json").status_code == 201
    assert Risque.objects.filter(libelle="Pluies").exists()
