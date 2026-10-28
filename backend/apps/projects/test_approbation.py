"""Circuit d'approbation activable par projet (voir apps.projects.approbation)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import Role, User
from apps.core.models import EtatApprobation
from apps.suivi.models import PointSuivi

from .models import Activite, DemandeModification, Projet
from .taux import ArbreTaux


@pytest.fixture
def clients(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_appro", password="x", role=ROLE_ADMIN))
    charge = APIClient()
    charge.force_authenticate(
        User.objects.create_user(
            username="se_appro", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE
        )
    )
    return admin, charge


@pytest.fixture
def projet(db):
    return Projet.objects.create(
        nom="P", code="APP-1", date_debut="2026-01-01", date_fin="2026-12-31", statut="EN_COURS",
        approbation_realisations=True, approbation_planification=True,
    )


def _point(client, activite, quantite=3, mois="01"):
    return client.post(
        "/api/v1/points-suivi/",
        {"activite": activite.id, "periode_debut": f"2026-{mois}-01", "periode_fin": f"2026-{mois}-28", "quantite_realisee": quantite},
    )


@pytest.mark.django_db
def test_saisie_en_attente_ne_compte_qu_une_fois_approuvee(projet, clients):
    admin, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="Forages", quantite_prevue=10)

    assert _point(charge, activite).status_code == 201
    point = PointSuivi.tous.get()
    assert point.etat_approbation == EtatApprobation.EN_ATTENTE
    activite.refresh_from_db()
    assert activite.quantite_realisee is None and ArbreTaux(projet).resultat(activite.id).taux == 0.0

    liste = charge.get("/api/v1/approbations/").data
    assert not liste["peut_approuver"] and liste["saisies"][0]["valeur"] == "3"

    # Rejet : motif obligatoire, montré à l'auteur.
    assert admin.post(f"/api/v1/approbations/saisies/point/{point.id}/", {"approuver": False}, format="json").status_code == 400
    admin.post(f"/api/v1/approbations/saisies/point/{point.id}/", {"approuver": False, "motif": "Période erronée"}, format="json")
    assert charge.get("/api/v1/approbations/").data["saisies"][0]["motif_rejet"] == "Période erronée"

    # Corrigée par l'auteur : de nouveau en attente ; approuvée : elle compte.
    charge.patch(f"/api/v1/points-suivi/{point.id}/", {"quantite_realisee": 4}, format="json")
    point.refresh_from_db()
    assert point.etat_approbation == EtatApprobation.EN_ATTENTE and point.motif_rejet == ""
    assert charge.post(f"/api/v1/approbations/saisies/point/{point.id}/", {"approuver": True}, format="json").status_code == 403
    assert admin.post(f"/api/v1/approbations/saisies/point/{point.id}/", {"approuver": True}, format="json").status_code == 200
    activite.refresh_from_db()
    assert float(activite.quantite_realisee) == 4 and ArbreTaux(projet).resultat(activite.id).taux == 40.0

    # Tableau de bord du suivi : la saisie approuvée compte ; une saisie en attente est listée sans compter.
    assert _point(charge, activite, quantite=5, mois="02").status_code == 201
    tableau = charge.get(f"/api/v1/suivi/projets/{projet.id}/dashboard/").data["activites"][0]
    assert tableau["saisies_en_attente"] == 1
    assert [(h["etat_approbation"], float(h["quantite_cumulee"])) for h in tableau["historique"]] == [
        ("APPROUVEE", 4.0), ("EN_ATTENTE", 4.0)
    ]
    PointSuivi.tous.filter(etat_approbation=EtatApprobation.EN_ATTENTE).delete()

    # Une saisie approuvée ne peut être supprimée que par un approbateur.
    assert charge.delete(f"/api/v1/points-suivi/{point.id}/").status_code == 403
    assert admin.delete(f"/api/v1/points-suivi/{point.id}/").status_code == 204


@pytest.mark.django_db
def test_role_approbateur_et_saisie_d_un_approbateur(projet, clients):
    admin, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="A", quantite_prevue=10)
    _point(admin, activite)
    assert PointSuivi.tous.get().etat_approbation == EtatApprobation.APPROUVEE

    Role.objects.filter(code=ROLE_CHARGE_SE).update(peut_approuver=True)
    PointSuivi.tous.all().delete()
    _point(charge, activite)
    assert PointSuivi.tous.get().etat_approbation == EtatApprobation.APPROUVEE


@pytest.mark.django_db
def test_demandes_de_modification_de_la_planification(projet, clients):
    admin, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="Former", quantite_prevue=10)

    # Modification : rien ne change avant approbation ; ancienne et nouvelle valeur gardées.
    r = charge.patch(f"/api/v1/activites/{activite.id}/", {"quantite_prevue": 25}, format="json")
    assert r.status_code == 202 and "approbation" in r.data["message"]
    activite.refresh_from_db()
    assert activite.quantite_prevue == 10
    demande = DemandeModification.objects.get()
    assert demande.changements == [{"champ": "Quantité prévue", "avant": "10", "apres": 25}]
    assert admin.post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": True}, format="json").status_code == 200
    activite.refresh_from_db()
    assert activite.quantite_prevue == 25

    # Ajout puis suppression.
    r = charge.post("/api/v1/activites/", {"projet": projet.id, "libelle": "Nouvelle"}, format="json")
    assert r.status_code == 202 and not Activite.objects.filter(libelle="Nouvelle").exists()
    demande = DemandeModification.objects.get(action="CREATION")
    admin.post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": True}, format="json")
    nouvelle = Activite.objects.get(libelle="Nouvelle")
    assert charge.delete(f"/api/v1/activites/{nouvelle.id}/").status_code == 202
    demande = DemandeModification.objects.get(action="SUPPRESSION")
    admin.post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": False, "motif": "À garder"}, format="json")
    assert Activite.objects.filter(id=nouvelle.id).exists()
    assert charge.get("/api/v1/approbations/").data["demandes"][0]["motif_rejet"] == "À garder"

    # Données invalides refusées tout de suite ; duplication réservée aux approbateurs.
    assert charge.patch(f"/api/v1/activites/{activite.id}/", {"quantite_prevue": "abc"}, format="json").status_code == 400
    assert charge.post(f"/api/v1/activites/{activite.id}/dupliquer/").status_code == 403
    # L'administrateur modifie directement.
    assert admin.patch(f"/api/v1/activites/{activite.id}/", {"libelle": "Former (admin)"}, format="json").status_code == 200


@pytest.mark.django_db
def test_options_d_approbation_reservees_a_l_administrateur(projet, clients):
    admin, charge = clients
    assert charge.patch(f"/api/v1/projets/{projet.id}/", {"approbation_realisations": False}, format="json").status_code == 403
    assert admin.patch(f"/api/v1/projets/{projet.id}/", {"approbation_realisations": False}, format="json").status_code == 200
