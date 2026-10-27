"""Canevas de suivi : génération, aperçu, import contrôlé, rapport d'erreurs (voir canevas.py)."""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.indicators.models import Indicateur, ValeurIndicateur
from apps.projects.models import Activite, JalonLivrable, MethodeCalcul, Projet, SousActivite, TauxManuel

from .models import PointSuivi


@pytest.fixture
def contexte(db):
    admin = User.objects.create_user(username="adm_canevas", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    projet = Projet.objects.create(nom="P", code="CAN-1", date_debut="2026-01-01", date_fin="2026-12-31")
    former = Activite.objects.create(projet=projet, libelle="Former", quantite_prevue=100)
    tache = SousActivite.objects.create(activite=former, libelle="Session 1", quantite_prevue=50)
    plaidoyer = Activite.objects.create(projet=projet, libelle="Plaidoyer", methode_calcul=MethodeCalcul.MANUELLE)
    guide = Activite.objects.create(projet=projet, libelle="Guide", methode_calcul=MethodeCalcul.LIVRABLES)
    livrable = JalonLivrable.objects.create(activite=guide, type="LIVRABLE", libelle="Version 1", poids=100)
    indicateur = Indicateur.objects.create(
        libelle="Taux d'adoption", unite="%", valeur_cible=80, frequence_collecte="ANNUELLE", projet=projet
    )
    return {"client": client, "projet": projet, "former": former, "tache": tache, "plaidoyer": plaidoyer,
            "guide": guide, "livrable": livrable, "indicateur": indicateur}


def _canevas(c):
    contenu = c["client"].get(f"/api/v1/suivi/projets/{c['projet'].id}/canevas/").content
    return load_workbook(io.BytesIO(contenu))


def _remplir(feuille, identifiant, **valeurs):
    entetes = [x.value for x in feuille[1]]
    ligne = next(r for r in range(2, feuille.max_row + 1) if feuille.cell(r, 1).value == identifiant)
    for colonne, valeur in valeurs.items():
        feuille.cell(ligne, entetes.index(colonne) + 1).value = valeur
    return ligne


def _ajouter_ligne(feuille, **valeurs):
    entetes = [x.value for x in feuille[1]]
    ligne = feuille.max_row + 1
    for colonne, valeur in valeurs.items():
        feuille.cell(ligne, entetes.index(colonne) + 1).value = valeur
    return ligne


def _envoyer(c, wb, route, mode="ajout"):
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    buffer.name = "canevas.xlsx"
    return c["client"].post(
        f"/api/v1/suivi/projets/{c['projet'].id}/canevas/{route}/", {"fichier": buffer, "mode": mode}, format="multipart"
    )


def _classeur_rempli(c):
    wb = _canevas(c)
    suivi, jalons, indic = wb["Suivi"], wb["Jalons et livrables"], wb["Indicateurs"]
    f, t, p = c["former"], c["tache"], c["plaidoyer"]
    _remplir(suivi, f"E{f.id}", **{"Période début (AAAA-MM-JJ)": "2026-01-01", "Période fin (AAAA-MM-JJ)": "2026-03-31",
                                   "Quantité réalisée sur la période": 30, "Budget réalisé sur la période (FCFA)": 500000})
    _remplir(suivi, f"S{t.id}", **{"Avancement (%)": 40, "Poids (%)": 100})
    _remplir(suivi, f"E{p.id}", **{"Taux manuel (%)": 65, "Période fin (AAAA-MM-JJ)": "2026-03-31"})
    _remplir(jalons, f"J{c['livrable'].id}", **{"Validé (Oui / Non)": "Oui"})
    _remplir(indic, f"I{c['indicateur'].id}", **{"Période début (AAAA-MM-JJ)": "2026-01-01",
                                                 "Période fin (AAAA-MM-JJ)": "2026-12-31", "Valeur réalisée sur la période": 42})
    return wb


@pytest.mark.django_db
def test_apercu_puis_import_puis_reimport_sans_ecrasement(contexte):
    c = contexte
    wb = _classeur_rempli(c)

    apercu = _envoyer(c, wb, "apercu").data
    assert apercu["totaux"] == {"ajout": 5, "modification": 0, "ignoree": 0, "erreur": 0}, apercu
    assert not PointSuivi.objects.exists()  # l'aperçu n'enregistre rien

    import_ = _envoyer(c, wb, "importer").data
    assert import_["totaux"]["ajout"] == 5
    c["former"].refresh_from_db()
    assert float(c["former"].quantite_realisee) == 30  # synchronisé sur les points de suivi
    assert TauxManuel.objects.get(activite=c["plaidoyer"]).taux == 65
    c["livrable"].refresh_from_db()
    assert c["livrable"].valide and c["livrable"].valide_par is not None
    assert ValeurIndicateur.objects.get(indicateur=c["indicateur"]).valeur_realisee == 42
    detail = c["client"].get(f"/api/v1/projets/{c['projet'].id}/").data["activites"]
    assert {e["libelle"]: e["taux_realisation"] for e in detail} == {"Former": 30.0, "Plaidoyer": 65.0, "Guide": 100.0}

    # Même fichier, mode « ajouter » : rien n'est remplacé.
    wb = _classeur_rempli(c)
    _remplir(wb["Suivi"], f"E{c['former'].id}", **{"Quantité réalisée sur la période": 45})
    apercu = _envoyer(c, wb, "importer").data
    assert apercu["totaux"]["modification"] == 0 and apercu["totaux"]["ajout"] == 0
    c["former"].refresh_from_db()
    assert float(c["former"].quantite_realisee) == 30

    # Mode « mettre à jour » : remplacé, avec l'ancienne et la nouvelle valeur, et trace dans l'historique.
    resultat = _envoyer(c, wb, "importer", mode="mise_a_jour").data
    ligne = next(l for l in resultat["lignes"] if l["identifiant"] == f"E{c['former'].id}")
    assert ligne["statut"] == "modification" and "30 → 45" in ligne["actions"][0]
    c["former"].refresh_from_db()
    assert float(c["former"].quantite_realisee) == 45
    assert PointSuivi.objects.get().history.count() == 2


@pytest.mark.django_db
def test_erreurs_signalees_par_cellule_et_rapport(contexte):
    c = contexte
    wb = _canevas(c)
    suivi = wb["Suivi"]
    f, t = c["former"], c["tache"]
    _ajouter_ligne(suivi, **{"Identifiant (ne pas modifier)": "E999999", "Quantité réalisée sur la période": 3,
                             "Période début (AAAA-MM-JJ)": "2026-01-01", "Période fin (AAAA-MM-JJ)": "2026-01-31"})
    _remplir(suivi, f"E{f.id}", **{"Période début (AAAA-MM-JJ)": "2026-02-30", "Quantité réalisée sur la période": 5,
                                   "Taux manuel (%)": 50})
    _remplir(suivi, f"S{t.id}", **{"Budget réalisé sur la période (FCFA)": 10, "Période début (AAAA-MM-JJ)": "2026-01-01",
                                   "Période fin (AAAA-MM-JJ)": "2026-01-31"})
    # Doublon : même élément, même période, deux fois.
    for _ in range(2):
        _ajouter_ligne(suivi, **{"Identifiant (ne pas modifier)": f"E{c['plaidoyer'].id}", "Statut": "En cours",
                                 "Période début (AAAA-MM-JJ)": "2026-01-01", "Période fin (AAAA-MM-JJ)": "2026-01-31"})

    apercu = _envoyer(c, wb, "apercu").data
    erreurs = {(l["identifiant"], e["colonne"]) for l in apercu["lignes"] for e in l["erreurs"]}
    assert ("E999999", "Identifiant (ne pas modifier)") in erreurs
    assert (f"E{f.id}", "Période début (AAAA-MM-JJ)") in erreurs
    assert (f"E{f.id}", "Taux manuel (%)") in erreurs
    assert (f"S{t.id}", "Budget réalisé sur la période (FCFA)") in erreurs
    assert (f"E{c['plaidoyer'].id}", "Identifiant (ne pas modifier)") in erreurs  # le doublon
    assert apercu["totaux"]["ajout"] == 1 and apercu["totaux"]["erreur"] == 4

    rapport = load_workbook(io.BytesIO(_envoyer(c, wb, "rapport-erreurs").content))
    assert rapport.sheetnames[0] == "Erreurs" and rapport["Erreurs"].max_row == 6
    feuille = rapport["Suivi"]
    entetes = [x.value for x in feuille[1]]
    ligne_inconnue = next(r for r in range(2, feuille.max_row + 1) if feuille.cell(r, 1).value == "E999999")
    cellule = feuille.cell(ligne_inconnue, entetes.index("Identifiant (ne pas modifier)") + 1)
    assert cellule.fill.fgColor.rgb.endswith("F8CBAD") and cellule.comment is not None

    # Import : seules les lignes valides sont enregistrées.
    _envoyer(c, wb, "importer")
    assert PointSuivi.objects.count() == 1
