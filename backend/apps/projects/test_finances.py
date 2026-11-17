"""Budget et efficience (apps.projects.finances)."""
import datetime
from decimal import Decimal

import pytest

from apps.beneficiaries.models import Beneficiaire, ParticipationProjet
from apps.partners.models import Bailleur, Financement, RallongeFinancement

from .finances import finances
from .models import Activite, Projet

J = datetime.date


@pytest.mark.django_db
def test_budget_et_efficience():
    projet = Projet.objects.create(nom="P", code="FI-1", date_debut="2026-01-01", date_fin="2026-12-31",
                                   budget_total=1500, fonds_propres=100)
    groupe = Activite.objects.create(projet=projet, libelle="R1", budget_alloue=999)  # contrôle : détaillé en dessous, pas compté
    # 1 000 alloués, révisés à 1 200 ; 900 engagés ; 600 dépensés ; 10 unités prévues, 5 réalisées.
    a = Activite.objects.create(projet=projet, activite_parent=groupe, libelle="A", statut="EN_COURS", budget_alloue=1000,
                                budget_revise=1200, budget_engage=900, budget_realise=600, quantite_prevue=10, quantite_realisee=5,
                                unite_quantite="puits", date_debut=J(2026, 1, 1), date_fin=J(2026, 12, 31))
    # Dépassement : 300 dépensés pour 200 prévus ; réalisée.
    Activite.objects.create(projet=projet, activite_parent=groupe, libelle="B", statut="REALISEE", budget_alloue=200,
                            budget_realise=300, date_debut=J(2026, 1, 1), date_fin=J(2026, 3, 31))
    bailleur = Bailleur.objects.create(nom="Bailleur F")
    financement = Financement.objects.create(projet=projet, bailleur=bailleur, montant_finance=1000, montant_recu=400)
    RallongeFinancement.objects.create(financement=financement, montant=200, date="2026-06-01", motif="Rallonge")
    for nom in ("x", "y", "z"):
        b = Beneficiaire.objects.create(nom=nom, prenom=nom, sexe="F")
        ParticipationProjet.objects.create(beneficiaire=b, projet=projet, date_inscription="2026-02-01")

    f = finances([projet.id], aujourd_hui=J(2026, 7, 1))
    assert (f["budget_initial"], f["budget_revise"], f["engage"], f["depense"]) == (1200, 1400, 900, 900)
    assert (f["solde_non_engage"], f["reste_a_depenser"]) == (500, 500)
    assert (f["taux_engagement"], f["taux_execution"]) == (64.3, 64.3)
    # Attendu au 1er juillet : la moitié de 1 200 (A, ~ 49,6 %) + les 200 de B (terminée).
    assert 790 <= f["depense_attendue_a_date"] <= 800 and f["ecart_a_date"] == 900 - f["depense_attendue_a_date"]
    assert (f["financements_acquis"], f["financements_recus"], f["taux_decaissement"]) == (1200, 400, 33.3)
    assert f["besoin_de_financement"] == 200  # 1 500 − 100 de fonds propres − 1 200 acquis
    assert (f["lignes_budgetees"], f["lignes_en_depassement"], f["part_lignes_en_depassement"]) == (2, 1, 50.0)
    assert (f["cout_par_beneficiaire"], f["cout_par_activite_realisee"]) == (300, 300)
    assert f["couts_unitaires"] == [{"code": "", "libelle": "A", "unite": "puits", "prevu": Decimal("120"), "reel": Decimal("120"),
                                     "ecart_pourcent": 0.0, "projet": "FI-1"}]
    assert f["par_projet"][0]["code"] == "FI-1" and f["par_projet"][0]["engage"] == 900
    # Rien d'engagé ni de reçu saisi : taux inconnus, pas 0 %.
    Activite.objects.filter(projet=projet).update(budget_engage=None)
    Financement.objects.filter(pk=financement.pk).update(montant_recu=None)
    vide = finances([projet.id], aujourd_hui=J(2026, 7, 1))
    assert vide["taux_engagement"] is None and vide["taux_decaissement"] is None
