"""Budgets sans double compte (règle A, voir apps.projects.budgets) et taux à une date (apps.projects.taux)."""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.reports.services import taux_execution_financiere_global
from apps.suivi.models import PeriodePlanification, PointSuivi, TranchePlanifiee
from apps.suivi.services import construire_planification_periode

from .budgets import avertissements_budget, ids_comptes, total_budget
from .models import Activite, JalonLivrable, MethodeCalcul, Projet, TauxManuel
from .taux import ArbreTaux


@pytest.fixture
def projet(db):
    return Projet.objects.create(nom="P", code="B-1", date_debut="2026-01-01", date_fin="2026-12-31")


@pytest.fixture
def point(db):
    from apps.accounts.models import User

    auteur = User.objects.create_user(username="saisie_budget", password="x")

    def creer(activite, debut, fin, **champs):
        return PointSuivi.objects.create(activite=activite, periode_debut=debut, periode_fin=fin, saisi_par=auteur, **champs)

    return creer


def element(projet, parent=None, **champs):
    return Activite.objects.create(projet=projet, activite_parent=parent, libelle=champs.pop("libelle", "E"), **champs)


# --- Règle A ------------------------------------------------------------------------------------

def test_ids_comptes_niveau_le_plus_bas_par_branche():
    # 1 (pilier, 10) → 2 (6), 3 (4) ; 4 (pilier, 5) → 5 (rien) ; 6 → 7 → 8 (2)
    noeuds = [(1, None, 10), (2, 1, 6), (3, 1, 4), (4, None, 5), (5, 4, None), (6, None, 9), (7, 6, 0), (8, 7, 2)]
    assert ids_comptes(noeuds) == {2, 3, 4, 8}


@pytest.mark.django_db
def test_pilier_et_activites_comptes_une_seule_fois(projet):
    pilier = element(projet, libelle="Eau potable", budget_alloue=10_000_000)
    element(projet, pilier, libelle="Forages", budget_alloue=6_000_000, budget_realise=3_000_000)
    element(projet, pilier, libelle="Latrines", budget_alloue=4_000_000, budget_realise=1_000_000)
    activites = Activite.objects.filter(projet=projet)
    assert total_budget(activites, "budget_alloue") == Decimal("10000000")  # pas 20 millions
    assert total_budget(activites, "budget_realise") == Decimal("4000000")
    assert taux_execution_financiere_global(projet) == 40.0
    assert avertissements_budget(activites) == {}  # 6 + 4 = 10 : concordant


@pytest.mark.django_db
def test_avertissements_de_controle(projet):
    trop = element(projet, libelle="Trop", budget_alloue=5_000_000)
    element(projet, trop, budget_alloue=4_000_000)
    element(projet, trop, budget_alloue=3_000_000)
    pas_assez = element(projet, libelle="Pas assez", budget_alloue=10_000_000)
    element(projet, pas_assez, budget_alloue=6_000_000)
    avertissements = avertissements_budget(Activite.objects.filter(projet=projet))
    assert "dépassent" in avertissements[trop.id][0] and "7 000 000 FCFA" in avertissements[trop.id][0]
    assert "4 000 000 FCFA" in avertissements[pas_assez.id][0]
    # Seuls les budgets d'en dessous comptent : 4 + 3 + 6 = 13 millions.
    assert total_budget(Activite.objects.filter(projet=projet), "budget_alloue") == Decimal("13000000")


@pytest.mark.django_db
def test_api_planification_expose_les_avertissements(projet):
    from rest_framework.test import APIClient

    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User

    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_budget", password="x", role=ROLE_ADMIN))
    pilier = element(projet, budget_alloue=1000)
    element(projet, pilier, budget_alloue=1500)
    detail = client.get(f"/api/v1/projets/{projet.id}/").data["activites"]
    racine = next(a for a in detail if a["id"] == pilier.id)
    assert "dépassent" in racine["budget_avertissements"][0]
    assert racine["enfants"][0]["budget_avertissements"] == []


# --- Taux à une date ------------------------------------------------------------------------------

def _dater_historique(objet, *dates):
    """Donne aux enregistrements historiques de l'objet (du plus ancien au plus récent) les dates indiquées."""
    for h, d in zip(objet.history.order_by("history_date", "history_id"), dates):
        h.history_date = timezone.make_aware(datetime.datetime.combine(d, datetime.time(12)))
        h.save()


@pytest.mark.django_db
def test_taux_a_une_date_selon_la_methode(projet, point):
    debut = datetime.date(2026, 1, 5)
    binaire = element(projet, methode_calcul=MethodeCalcul.BINAIRE)
    _dater_historique(binaire, debut)
    point(binaire, "2026-03-01", "2026-03-31", statut="REALISEE")

    jalons = element(projet, methode_calcul=MethodeCalcul.JALONS)
    _dater_historique(jalons, debut)
    jalon = JalonLivrable.objects.create(activite=jalons, type="JALON", libelle="J", poids=100, achevement=40)
    jalon.achevement = 100
    jalon.save()
    _dater_historique(jalon, debut, datetime.date(2026, 5, 10))

    livrables = element(projet, methode_calcul=MethodeCalcul.LIVRABLES)
    JalonLivrable.objects.create(
        activite=livrables, type="LIVRABLE", libelle="L", poids=100, valide=True, date_validation="2026-04-15"
    )

    manuel = element(projet, methode_calcul=MethodeCalcul.MANUELLE)
    TauxManuel.objects.create(activite=manuel, taux=30, date="2026-02-01")
    TauxManuel.objects.create(activite=manuel, taux=70, date="2026-06-01")

    quantite = element(projet, quantite_prevue=100)
    point(quantite, "2026-01-01", "2026-01-31", quantite_realisee=20)
    point(quantite, "2026-05-01", "2026-05-31", quantite_realisee=50)

    attendu = {
        datetime.date(2026, 2, 28): [0.0, 40.0, 0.0, 30.0, 20.0],
        datetime.date(2026, 4, 30): [100.0, 40.0, 100.0, 30.0, 20.0],
        datetime.date(2026, 6, 30): [100.0, 100.0, 100.0, 70.0, 70.0],
    }
    for date, taux in attendu.items():
        arbre = ArbreTaux(projet, a_la_date=date)
        assert [arbre.resultat(e.id).taux for e in (binaire, jalons, livrables, manuel, quantite)] == taux, date
    # Sans date : l'état actuel.
    assert ArbreTaux(projet).resultat(jalons.id).taux == 100.0


# --- Suivi par période ------------------------------------------------------------------------------

@pytest.mark.django_db
def test_periode_en_avancement_et_totaux_sans_double_compte(projet, point):
    pilier = element(projet, libelle="Pilier")
    _dater_historique(pilier, datetime.date(2026, 1, 1))
    guide = element(projet, pilier, libelle="Guide", methode_calcul=MethodeCalcul.LIVRABLES)
    JalonLivrable.objects.create(activite=guide, type="LIVRABLE", libelle="V1", poids=40, valide=True, date_validation="2026-02-10")
    JalonLivrable.objects.create(activite=guide, type="LIVRABLE", libelle="V2", poids=60, valide=True, date_validation="2026-05-10")
    forages = element(projet, pilier, libelle="Forages", quantite_prevue=10)
    point(forages, "2026-01-01", "2026-02-28", quantite_realisee=2, budget_realise=500)

    t1 = PeriodePlanification.objects.create(
        projet=projet, libelle="T1", date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2026, 3, 31)
    )
    TranchePlanifiee.objects.create(periode=t1, activite=guide, cible=50, budget=1000, periode_debut=t1.date_debut, periode_fin=t1.date_fin)
    TranchePlanifiee.objects.create(periode=t1, activite=forages, cible=4, budget=2000, periode_debut=t1.date_debut, periode_fin=t1.date_fin)
    # Budget aussi fixé sur le pilier : détail en dessous, il ne doit pas s'ajouter.
    TranchePlanifiee.objects.create(periode=t1, activite=pilier, cible=40, budget=3000, periode_debut=t1.date_debut, periode_fin=t1.date_fin)

    data = construire_planification_periode(t1)
    lignes = {l["libelle"]: l for l in data["lignes"]}
    assert lignes["Guide"]["mode"] == "avancement" and lignes["Guide"]["unite"] == "%"
    assert lignes["Guide"]["realise_quantite"] == Decimal("40.0")  # V1 seul validé au 31/03
    assert lignes["Guide"]["taux"] == 80.0  # 40 % atteint pour 50 % visé
    assert lignes["Forages"]["mode"] == "quantite" and lignes["Forages"]["taux"] == 50.0
    assert lignes["Pilier"]["mode"] == "avancement"  # niveau agrégé
    assert data["totaux"]["budget_prevu"] == 3000  # 1000 + 2000, pas + 3000 du pilier
    assert data["totaux"]["taux_physique"] == 65.0  # moyenne de Guide (80) et Forages (50), sans le pilier
