"""Résultats chiffrés du calcul des taux d'exécution (voir apps.projects.taux)."""
import datetime

import pytest

from .models import (
    Activite,
    JalonLivrable,
    MethodeAgregation,
    MethodeCalcul,
    ParametresCalcul,
    Projet,
    SousActivite,
    TauxManuel,
)
from .taux import ArbreTaux


@pytest.fixture
def projet(db):
    return Projet.objects.create(nom="P", code="T-1", date_debut="2026-01-01", date_fin="2026-12-31")


def element(projet, parent=None, **champs):
    return Activite.objects.create(projet=projet, activite_parent=parent, libelle=champs.pop("libelle", "E"), **champs)


def taux(projet, e):
    return ArbreTaux(projet).resultat(e.id)


# --- Par quantité -------------------------------------------------------------------------

@pytest.mark.django_db
def test_quantite_simple_depassement_et_cible_nulle(projet):
    assert taux(projet, element(projet, quantite_prevue=200, quantite_realisee=50)).taux == 25.0
    assert taux(projet, element(projet, quantite_prevue=100, quantite_realisee=130)).taux == 130.0
    assert taux(projet, element(projet, quantite_prevue=0, quantite_realisee=5)).taux is None
    assert taux(projet, element(projet)).taux is None


# --- Par tâches pondérées ---------------------------------------------------------------------

@pytest.mark.django_db
def test_taches_ponderees(projet):
    e = element(projet, methode_calcul=MethodeCalcul.TACHES)
    SousActivite.objects.create(activite=e, libelle="T1", poids=60, avancement=50)  # 30
    SousActivite.objects.create(activite=e, libelle="T2", poids=40, quantite_prevue=10, quantite_realisee=10)  # 40
    r = taux(projet, e)
    assert r.taux == 70.0 and r.avertissements == []


@pytest.mark.django_db
def test_taches_poids_qui_ne_totalisent_pas_100_et_poids_absents(projet):
    e = element(projet, methode_calcul=MethodeCalcul.TACHES)
    SousActivite.objects.create(activite=e, libelle="T1", poids=30, statut=SousActivite.Statut.TERMINEE)
    SousActivite.objects.create(activite=e, libelle="T2", poids=30)
    r = taux(projet, e)
    assert r.taux == 50.0 and "60 %" in r.avertissements[0]

    sans_poids = element(projet, methode_calcul=MethodeCalcul.TACHES)
    SousActivite.objects.create(activite=sans_poids, libelle="A", avancement=100)
    SousActivite.objects.create(activite=sans_poids, libelle="B", avancement=0)
    SousActivite.objects.create(activite=sans_poids, libelle="C", avancement=50)
    assert taux(projet, sans_poids).taux == 50.0  # poids égaux

    assert taux(projet, element(projet, methode_calcul=MethodeCalcul.TACHES)).taux is None  # aucune tâche


# --- Jalons, livrables, binaire, manuel -------------------------------------------------------

@pytest.mark.django_db
def test_jalons_ponderes(projet):
    e = element(projet, methode_calcul=MethodeCalcul.JALONS)
    JalonLivrable.objects.create(activite=e, type="JALON", libelle="J1", poids=25, achevement=100)
    JalonLivrable.objects.create(activite=e, type="JALON", libelle="J2", poids=75, achevement=40)
    JalonLivrable.objects.create(activite=e, type="LIVRABLE", libelle="ignoré", poids=50, valide=True)
    assert taux(projet, e).taux == 55.0


@pytest.mark.django_db
def test_livrables_valides(projet):
    e = element(projet, methode_calcul=MethodeCalcul.LIVRABLES)
    JalonLivrable.objects.create(activite=e, type="LIVRABLE", libelle="L1", poids=20, valide=True)
    JalonLivrable.objects.create(activite=e, type="LIVRABLE", libelle="L2", poids=80, valide=False)
    assert taux(projet, e).taux == 20.0


@pytest.mark.django_db
def test_binaire(projet):
    assert taux(projet, element(projet, methode_calcul=MethodeCalcul.BINAIRE)).taux == 0.0
    fini = element(projet, methode_calcul=MethodeCalcul.BINAIRE, statut=Activite.Statut.REALISEE)
    assert taux(projet, fini).taux == 100.0


@pytest.mark.django_db
def test_saisie_manuelle_derniere_saisie_jamais_recalculee(projet):
    e = element(projet, methode_calcul=MethodeCalcul.MANUELLE, quantite_prevue=100, quantite_realisee=90)
    assert taux(projet, e).taux is None
    TauxManuel.objects.create(activite=e, taux=35, date=datetime.date(2026, 3, 1))
    TauxManuel.objects.create(activite=e, taux=60, date=datetime.date(2026, 6, 1))
    assert taux(projet, e).taux == 60.0  # pas 90 % (quantités ignorées)


# --- Héritage ----------------------------------------------------------------------------------

@pytest.mark.django_db
def test_heritage_organisation_projet_parent_element(projet):
    parent = element(projet, libelle="Parent")
    feuille = element(projet, parent, statut=Activite.Statut.REALISEE, quantite_prevue=10, quantite_realisee=2)
    assert taux(projet, feuille).methode == MethodeCalcul.QUANTITE  # organisation

    parametres = ParametresCalcul.courants()
    parametres.methode_calcul = MethodeCalcul.BINAIRE
    parametres.save()
    assert taux(projet, feuille).taux == 100.0

    projet.methode_calcul = MethodeCalcul.QUANTITE
    projet.save()
    assert taux(projet, feuille).taux == 20.0  # le projet l'emporte sur l'organisation

    parent.methode_calcul = MethodeCalcul.BINAIRE
    parent.save()
    assert taux(projet, feuille).taux == 100.0  # le parent l'emporte sur le projet

    feuille.methode_calcul = MethodeCalcul.QUANTITE
    feuille.save()
    assert taux(projet, feuille).taux == 20.0  # l'élément l'emporte sur tout


@pytest.mark.django_db
def test_manuel_sur_un_parent_ne_se_propage_pas(projet):
    parent = element(projet, methode_calcul=MethodeCalcul.MANUELLE)
    feuille = element(projet, parent, quantite_prevue=10, quantite_realisee=5)
    TauxManuel.objects.create(activite=parent, taux=80, date=datetime.date(2026, 1, 1))
    arbre = ArbreTaux(projet)
    assert arbre.resultat(parent.id).taux == 80.0
    assert arbre.resultat(feuille.id).taux == 50.0


# --- Agrégation --------------------------------------------------------------------------------

@pytest.fixture
def arbre_deux_feuilles(projet):
    parent = element(projet, libelle="Objectif")
    a = element(projet, parent, quantite_prevue=100, quantite_realisee=150, budget_alloue=1000, poids=25)  # 150 %
    b = element(projet, parent, quantite_prevue=100, quantite_realisee=20, budget_alloue=3000, poids=75)  # 20 %
    element(projet, parent)  # non calculable : ignoré
    return parent, a, b


@pytest.mark.django_db
def test_agregation_moyenne_plafonnee(projet, arbre_deux_feuilles):
    parent, a, _ = arbre_deux_feuilles
    arbre = ArbreTaux(projet)
    assert arbre.resultat(a.id).taux == 150.0  # taux réel affiché
    assert arbre.resultat(parent.id).taux == 60.0  # (100 + 20) / 2 : plafonné à 100 dans la moyenne
    assert arbre.taux_projet().taux == 60.0

    parametres = ParametresCalcul.courants()
    parametres.plafonner_agregation = False
    parametres.save()
    assert ArbreTaux(projet).resultat(parent.id).taux == 85.0


@pytest.mark.django_db
def test_agregation_ponderee_budget_et_poids(projet, arbre_deux_feuilles):
    parent, _, _ = arbre_deux_feuilles
    parent.methode_agregation = MethodeAgregation.PONDEREE_BUDGET
    parent.save()
    assert ArbreTaux(projet).resultat(parent.id).taux == 40.0  # (100×1000 + 20×3000) / 4000

    parent.methode_agregation = MethodeAgregation.PONDEREE_POIDS
    parent.save()
    assert ArbreTaux(projet).resultat(parent.id).taux == 40.0  # (100×25 + 20×75) / 100


@pytest.mark.django_db
def test_projet_sans_element_calculable(projet):
    element(projet)
    assert ArbreTaux(projet).taux_projet().taux is None


# --- API ----------------------------------------------------------------------------------------

@pytest.fixture
def clients(db):
    from rest_framework.test import APIClient

    from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
    from apps.accounts.models import User

    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_taux", password="x", role=ROLE_ADMIN))
    charge = APIClient()
    charge.force_authenticate(
        User.objects.create_user(
            username="se_taux", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE
        )
    )
    return admin, charge


@pytest.mark.django_db
def test_api_livrable_valide_garde_auteur_et_date(projet, clients):
    admin, _ = clients
    e = element(projet, methode_calcul=MethodeCalcul.LIVRABLES)
    livrable = admin.post("/api/v1/jalons-livrables/", {"activite": e.id, "type": "LIVRABLE", "libelle": "Rapport", "poids": 100}).data
    r = admin.patch(f"/api/v1/jalons-livrables/{livrable['id']}/", {"valide": True}, format="json")
    assert r.data["valide_par"] is not None and r.data["date_validation"] is not None
    detail = admin.get(f"/api/v1/projets/{projet.id}/").data["activites"][0]
    assert detail["taux_realisation"] == 100.0 and detail["methode_calcul_effective"] == "LIVRABLES"
    r = admin.patch(f"/api/v1/jalons-livrables/{livrable['id']}/", {"valide": False}, format="json")
    assert r.data["valide_par"] is None and r.data["date_validation"] is None


@pytest.mark.django_db
def test_api_taux_manuel_borne_entre_0_et_100(projet, clients):
    admin, _ = clients
    e = element(projet, methode_calcul=MethodeCalcul.MANUELLE)
    assert admin.post("/api/v1/taux-manuels/", {"activite": e.id, "taux": 120, "date": "2026-05-01"}).status_code == 400
    r = admin.post("/api/v1/taux-manuels/", {"activite": e.id, "taux": 45, "date": "2026-05-01"})
    assert r.status_code == 201 and r.data["saisi_par"] is not None
    assert admin.get(f"/api/v1/activites/{e.id}/").data["taux_realisation"] == 45.0


@pytest.mark.django_db
def test_api_parametres_calcul_reserves_a_l_administrateur(clients):
    admin, charge = clients
    assert charge.get("/api/v1/parametres-calcul/").data["methode_calcul"] == "QUANTITE"
    assert charge.patch("/api/v1/parametres-calcul/", {"methode_calcul": "BINAIRE"}, format="json").status_code == 403
    r = admin.patch("/api/v1/parametres-calcul/", {"methode_agregation": "PONDEREE_BUDGET"}, format="json")
    assert r.status_code == 200 and r.data["methode_agregation"] == "PONDEREE_BUDGET"
