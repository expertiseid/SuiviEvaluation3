"""Durée en jours, « tout le pays », duplication d'éléments, projet clôturé en lecture seule."""
import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.suivi.models import PointSuivi

from .models import Activite, JalonLivrable, MethodeCalcul, Projet, SousActivite


@pytest.fixture
def clients(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_lot1", password="x", role=ROLE_ADMIN))
    charge = APIClient()
    charge.force_authenticate(
        User.objects.create_user(
            username="se_lot1", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE
        )
    )
    return admin, charge


@pytest.fixture
def projet(db):
    return Projet.objects.create(nom="P", code="L1-1", date_debut="2026-01-01", date_fin="2026-12-31")


@pytest.mark.django_db
def test_duree_en_jours_bornes_comprises(projet):
    meme_jour = Activite.objects.create(projet=projet, libelle="Atelier", date_debut="2026-03-10", date_fin="2026-03-10")
    assert meme_jour.nb_jours_planifies == 1
    meme_jour.date_fin = datetime.date(2026, 3, 14)
    meme_jour.save()
    assert meme_jour.nb_jours_planifies == 5


@pytest.mark.django_db
def test_tout_le_pays(projet, clients):
    admin, _ = clients
    r = admin.patch(f"/api/v1/projets/{projet.id}/", {"tout_le_pays": True, "zones": []}, format="json")
    assert r.status_code == 200
    assert admin.get(f"/api/v1/projets/{projet.id}/").data["tout_le_pays"] is True


@pytest.mark.django_db
def test_duplication_copie_la_planification_sans_les_realisations(projet, clients):
    admin, _ = clients
    auteur = User.objects.get(username="adm_lot1")
    pilier = Activite.objects.create(projet=projet, libelle="Pilier", budget_alloue=1000)
    guide = Activite.objects.create(
        projet=projet, activite_parent=pilier, libelle="Guide", methode_calcul=MethodeCalcul.LIVRABLES,
        quantite_prevue=3, quantite_realisee=2, statut=Activite.Statut.EN_COURS,
    )
    JalonLivrable.objects.create(activite=guide, type="LIVRABLE", libelle="V1", poids=100, valide=True, date_validation="2026-02-01")
    SousActivite.objects.create(activite=guide, libelle="Rédaction", poids=100, avancement=80)
    PointSuivi.objects.create(activite=guide, periode_debut="2026-01-01", periode_fin="2026-01-31", quantite_realisee=2, saisi_par=auteur)

    r = admin.post(f"/api/v1/activites/{pilier.id}/dupliquer/")
    assert r.status_code == 201 and r.data["libelle"] == "Pilier (copie)"
    copie = Activite.objects.get(id=r.data["id"])
    assert copie.activite_parent_id is None and copie.budget_alloue == 1000
    copie_guide = copie.enfants.get()
    assert copie_guide.libelle == "Guide" and copie_guide.methode_calcul == MethodeCalcul.LIVRABLES
    assert copie_guide.quantite_prevue == 3 and copie_guide.quantite_realisee is None
    assert copie_guide.statut == Activite.Statut.NON_REALISEE
    livrable = copie_guide.jalons_livrables.get()
    assert livrable.libelle == "V1" and not livrable.valide
    tache = copie_guide.sous_activites.get()
    assert tache.libelle == "Rédaction" and tache.avancement is None
    assert not PointSuivi.objects.filter(activite=copie_guide).exists()
    # L'original n'a pas bougé.
    assert Activite.objects.filter(projet=projet).count() == 4


@pytest.mark.django_db
def test_projet_cloture_en_lecture_seule(projet, clients):
    admin, charge = clients
    activite = Activite.objects.create(projet=projet, libelle="Former", quantite_prevue=10)
    projet.statut = Projet.Statut.CLOTURE
    projet.save()

    assert charge.patch(f"/api/v1/activites/{activite.id}/", {"libelle": "X"}, format="json").status_code == 403
    assert charge.post("/api/v1/activites/", {"projet": projet.id, "libelle": "Nouvelle"}).status_code == 403
    r = charge.post(
        "/api/v1/points-suivi/",
        {"activite": activite.id, "periode_debut": "2026-01-01", "periode_fin": "2026-01-31", "quantite_realisee": 3},
    )
    assert r.status_code == 403 and "clôturé" in str(r.data)
    assert admin.delete(f"/api/v1/activites/{activite.id}/").status_code == 403
    assert admin.patch(f"/api/v1/projets/{projet.id}/", {"nom": "Autre"}, format="json").status_code == 403

    # Rouvrir : réservé à l'administrateur.
    assert charge.patch(f"/api/v1/projets/{projet.id}/", {"statut": "EN_COURS"}, format="json").status_code == 403
    assert admin.patch(f"/api/v1/projets/{projet.id}/", {"statut": "EN_COURS"}, format="json").status_code == 200
    assert charge.patch(f"/api/v1/activites/{activite.id}/", {"libelle": "X"}, format="json").status_code == 200


@pytest.mark.django_db
def test_suppression_complete_d_un_projet_cloture(projet, clients):
    admin, _ = clients
    Activite.objects.create(projet=projet, libelle="A")
    projet.statut = Projet.Statut.CLOTURE
    projet.save()
    assert admin.delete(f"/api/v1/projets/{projet.id}/").status_code == 204
    assert not Projet.objects.filter(id=projet.id).exists()
