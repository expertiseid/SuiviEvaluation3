"""Rapports, recommandations, leçons et décisions (API) ; pilotage et qualité des données (tableau de bord)."""
import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.dashboard.qualite import atypiques, qualite
from apps.indicators.models import Indicateur, ValeurIndicateur

from .models import Activite, Apprentissage, EvaluationRisque, Projet, RapportProjet, Recommandation, Risque
from .pilotage import pilotage

J = datetime.date


@pytest.mark.django_db
def test_rapports_recommandations_et_apprentissage():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_pilotage", password="x", role=ROLE_ADMIN))
    projet = Projet.objects.create(nom="P", code="PI-1", date_debut="2026-01-01", date_fin="2026-12-31")
    autre = Projet.objects.create(nom="Q", code="PI-2", date_debut="2026-01-01", date_fin="2026-12-31")

    r1 = client.post("/api/v1/rapports-attendus/", {"projet": projet.id, "libelle": "T1", "echeance": "2026-04-15"}, format="json")
    assert r1.status_code == 201 and r1.data["statut"] == "ATTENDU"
    # Validé sans dates : remis et validé aujourd'hui.
    valide = client.patch(f"/api/v1/rapports-attendus/{r1.data['id']}/", {"statut": "VALIDE"}, format="json").data
    assert valide["date_remise"] == valide["date_validation"] == datetime.date.today().isoformat()
    RapportProjet.objects.create(projet=projet, libelle="T2", echeance=J(2026, 7, 15))  # pas remis
    RapportProjet.objects.create(projet=projet, libelle="T3", echeance=J(2026, 10, 15), statut="RECU", date_remise=J(2026, 10, 10))
    RapportProjet.objects.create(projet=projet, libelle="Final", echeance=J(2027, 1, 31))  # pas encore dû

    rec = client.post("/api/v1/recommandations/", {"projet": projet.id, "libelle": "Renforcer la supervision",
                                                    "rapport": r1.data["id"], "echeance": "2026-09-30"}, format="json")
    assert rec.status_code == 201 and rec.data["code"] == "REC1"
    # Une recommandation ne peut pas pointer vers le rapport d'un autre projet.
    refus = client.post("/api/v1/recommandations/", {"projet": autre.id, "libelle": "X", "rapport": r1.data["id"]}, format="json")
    assert refus.status_code == 400
    Recommandation.objects.create(projet=projet, libelle="Former les relais", statut="REALISEE")
    Recommandation.objects.create(projet=projet, libelle="Abandonnée", statut="ABANDONNEE")
    assert Recommandation.objects.get(libelle="Former les relais").date_mise_en_oeuvre == datetime.date.today()

    decision = client.post("/api/v1/apprentissages/", {"projet": projet.id, "type": "DECISION", "titre": "Recruter un 2e animateur",
                                                       "decideur": "Comité de pilotage", "recommandation": rec.data["id"]}, format="json")
    assert decision.status_code == 201
    Apprentissage.objects.create(projet=projet, type="LECON", titre="Impliquer les chefs coutumiers tôt")

    risque = Risque.objects.create(projet=projet, libelle="Insécurité", probabilite=4, impact=5, mesures_attenuation="Escortes",
                                   date_prochaine_revue=J(2026, 9, 1))
    EvaluationRisque.objects.create(risque=risque, date=J(2026, 10, 1), probabilite=4, impact=5, statut="ACTIF")
    Risque.objects.create(projet=projet, libelle="Inflation", probabilite=2, impact=2)

    p = pilotage([projet.id], aujourd_hui=J(2026, 11, 17))
    ra = p["rapports"]
    assert (ra["total"], ra["attendus_a_date"], ra["recus"], ra["valides"], ra["en_retard"]) == (4, 3, 2, 1, 1)
    assert ra["en_retard_exemples"][0]["libelle"] == "T2" and ra["taux_remis"] == 66.7
    ri = p["risques"]
    assert (ri["ouverts"], ri["par_niveau"]["CRITIQUE"], ri["par_niveau"]["FAIBLE"]) == (2, 1, 1)
    assert (ri["avec_mesures"], ri["suivis"], ri["revue_en_retard"]) == (50.0, 50.0, 1)
    re = p["recommandations"]
    assert (re["retenues"], re["realisees"], re["taux_mise_en_oeuvre"], re["en_retard"]) == (2, 1, 50.0, 1)
    assert p["apprentissage"] == {"lecons": 1, "bonnes_pratiques": 0, "decisions": 1, "lecons_adaptees": 0, "part_lecons_adaptees": 0.0}
    assert (ri["total"], ri["clos"], ri["graves"], ri["graves_avec_mesures"]) == (2, 0, 1, 100.0)
    assert ra["acceptes_premiere_soumission"] == 100.0 and ra["delai_validation_jours"] == 0
    assert re["total"] == 3 and p["partages"] == {"liens": 0, "consultations": 0}

    # Problème survenu le 1er octobre puis maîtrisé le 31 : résolu en 30 jours.
    EvaluationRisque.objects.create(risque=risque, date=J(2026, 10, 1), probabilite=4, impact=5, statut="SURVENU")
    EvaluationRisque.objects.create(risque=risque, date=J(2026, 10, 31), probabilite=2, impact=5, statut="MAITRISE")
    ri = pilotage([projet.id], aujourd_hui=J(2026, 11, 17))["risques"]
    assert (ri["problemes_resolus"], ri["delai_resolution_jours"]) == (1, 30)


def test_valeurs_atypiques():
    assert atypiques([10, 11, 9, 10, 12, 95]) == [5]
    assert atypiques([10, 10, 10, 10]) == []  # aucune dispersion : rien à signaler
    assert atypiques([1, 500, 3]) == []  # trop peu de valeurs


@pytest.mark.django_db
def test_qualite_des_donnees():
    admin = User.objects.create_user(username="adm_qualite", password="x", role=ROLE_ADMIN)
    projet = Projet.objects.create(nom="P", code="QU-1", date_debut="2026-01-01", date_fin="2026-12-31")
    Activite.objects.create(projet=projet, libelle="A", date_debut=J(2026, 1, 1), date_fin=J(2026, 6, 30), budget_alloue=100,
                            quantite_prevue=10, quantite_realisee=30)  # sans responsable ; 3 fois le prévu
    ind = Indicateur.objects.create(libelle="Kits", unite="kits", valeur_cible=100, frequence_collecte="TRIMESTRIELLE", projet=projet)
    for mois, valeur in ((1, 10), (2, 11), (3, 9), (4, 10), (5, 12), (6, 95)):
        ValeurIndicateur.objects.create(indicateur=ind, periode_debut=J(2026, mois, 1), periode_fin=J(2026, mois, 28),
                                        valeur_realisee=Decimal(valeur), saisi_par=admin)
    # Saisie de juin enregistrée à temps, les autres (créées aujourd'hui) en retard.
    ValeurIndicateur.objects.filter(periode_fin=J(2026, 6, 28)).update(date_saisie=datetime.datetime(2026, 7, 5, tzinfo=datetime.UTC))

    q = qualite([projet.id])
    assert q["completude"]["activites"]["champs"]["responsable"] == 0.0 and q["completude"]["activites"]["completude"] == 75.0
    assert q["completude"]["indicateurs"]["completude"] == 50.0  # valeur de référence manquante, valeurs saisies
    assert (q["saisies"], q["saisies_a_temps"]) == (6, 1)
    assert q["atypiques"] == 2 and {x["motif"] for x in q["atypiques_exemples"]} == {"indicateur", "quantite"}
    co = q["composantes"]
    assert co["doublons"] is None  # aucun signalement : composante ignorée
    attendu = (co["completude"] * 40 + co["ponctualite"] * 30 + co["plausibilite"] * 15) / 85
    assert q["score"] == round(attendu, 1)


@pytest.mark.django_db
def test_mesures_origine_lecons_et_documents_obligatoires():
    from apps.documents.models import Document

    from .models import DocumentObligatoire, MesureRisque

    admin = User.objects.create_user(username="adm_pil_b", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    projet = Projet.objects.create(nom="P", code="PI-B", date_debut="2026-01-01", date_fin="2026-12-31")
    risque = Risque.objects.create(projet=projet, libelle="Insécurité", probabilite=4, impact=5)

    # Mesures d'atténuation par l'API : une réalisée (date posée d'office), une en retard, une abandonnée (non comptée).
    faite = client.post("/api/v1/mesures-risques/", {"risque": risque.id, "libelle": "Escortes", "statut": "REALISEE"}, format="json")
    assert faite.status_code == 201 and faite.data["date_realisation"] == datetime.date.today().isoformat()
    MesureRisque.objects.create(risque=risque, libelle="Plan d'évacuation", echeance=J(2026, 10, 1))
    MesureRisque.objects.create(risque=risque, libelle="Abandonnée", statut="ABANDONNEE")
    assert len(client.get(f"/api/v1/risques/{risque.id}/").data["mesures"]) == 3

    Recommandation.objects.create(projet=projet, libelle="E1", origine="EVALUATION", statut="REALISEE")
    Recommandation.objects.create(projet=projet, libelle="E2", origine="EVALUATION")
    Recommandation.objects.create(projet=projet, libelle="A1", origine="AUDIT")
    Apprentissage.objects.create(projet=projet, type="LECON", titre="L1", adaptation=True, changement="Horaires revus")
    Apprentissage.objects.create(projet=projet, type="BONNE_PRATIQUE", titre="B1")
    Apprentissage.objects.create(projet=projet, type="DECISION", titre="D1")  # pas une leçon : non comptée

    document = Document.objects.create(nom="Convention signée", projet=projet, cree_par=admin)
    autre = Projet.objects.create(nom="Q", code="PI-C", date_debut="2026-01-01", date_fin="2026-12-31")
    refus = client.post("/api/v1/documents-obligatoires/", {"projet": autre.id, "libelle": "Convention", "document": document.id}, format="json")
    assert refus.status_code == 400  # document d'un autre projet
    ok = client.post("/api/v1/documents-obligatoires/", {"projet": projet.id, "libelle": "Convention", "document": document.id}, format="json")
    assert ok.status_code == 201 and ok.data["disponible"] is True
    DocumentObligatoire.objects.create(projet=projet, libelle="Rapport de démarrage", echeance=J(2026, 3, 31))
    DocumentObligatoire.objects.create(projet=projet, libelle="Audit final", echeance=J(2027, 3, 31))

    p = pilotage([projet.id], aujourd_hui=J(2026, 11, 17))
    ri = p["risques"]
    assert (ri["mesures"], ri["mesures_realisees"], ri["taux_execution_mesures"], ri["mesures_en_retard"]) == (2, 1, 50.0, 1)
    origines = {o["origine"]: o for o in p["recommandations"]["par_origine"]}
    assert origines["EVALUATION"]["taux_mise_en_oeuvre"] == 50.0 and origines["AUDIT"]["realisees"] == 0
    assert (p["apprentissage"]["lecons_adaptees"], p["apprentissage"]["part_lecons_adaptees"]) == (1, 50.0)
    do = p["documents_obligatoires"]
    assert (do["total"], do["disponibles"], do["taux_disponibilite"], do["manquants_echus"]) == (3, 1, 33.3, 1)
    assert do["manquants_exemples"][0]["libelle"] == "Rapport de démarrage"
