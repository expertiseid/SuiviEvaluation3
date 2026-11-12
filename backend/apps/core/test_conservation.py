"""Durée de conservation des bénéficiaires : identité effacée quand tous leurs projets sont échus."""
import datetime

import pytest

from apps.beneficiaries.models import Beneficiaire, ParticipationProjet, SignalementDoublon
from apps.projects.models import Projet

from . import conservation


def _projet(code, fin, mois):
    return Projet.objects.create(nom=code, code=code, date_debut="2020-01-01", date_fin=fin, conservation_beneficiaires_mois=mois)


@pytest.mark.django_db
def test_anonymisation_a_l_echeance():
    aujourdhui = datetime.date(2026, 11, 11)
    echu = _projet("ECHU", "2024-06-30", 12)          # fin + 12 mois = 30/06/2025 : écoulé
    en_cours = _projet("EN-COURS", "2026-12-31", 12)  # pas encore
    sans_duree = _projet("SANS", "2020-12-31", None)  # conservé
    seul = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F", date_naissance="1990-05-12",
                                       telephone="70000001", numero_piece_identite="CNIB1", latitude=12.3, longitude=-1.5)
    seul.telephone = "70000002"
    seul.save()
    double = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F")
    suivi_ailleurs = Beneficiaire.objects.create(nom="Kabore", prenom="Ali", sexe="M")
    sans = Beneficiaire.objects.create(nom="Sawadogo", prenom="Ines", sexe="F")
    for b, p in ((seul, echu), (suivi_ailleurs, echu), (suivi_ailleurs, en_cours), (sans, sans_duree), (double, en_cours)):
        ParticipationProjet.objects.create(beneficiaire=b, projet=p, date_inscription="2024-01-01")
    SignalementDoublon.objects.create(beneficiaire_1=seul, beneficiaire_2=double, methode=SignalementDoublon.Methode.choices[0][0])

    assert conservation.appliquer(aujourdhui) == 1
    seul.refresh_from_db()
    assert (seul.nom, seul.prenom, seul.telephone, seul.numero_piece_identite, seul.latitude) == ("Anonyme", "", "", "", None)
    assert seul.sexe == "F" and seul.date_naissance == datetime.date(1990, 7, 1) and seul.date_anonymisation == aujourdhui
    assert seul.participations.count() == 1  # les statistiques du projet restent justes
    assert not seul.history.exists() and not SignalementDoublon.objects.exists()
    for b in (suivi_ailleurs, sans, double):
        b.refresh_from_db()
        assert b.date_anonymisation is None and b.nom != "Anonyme"
    assert conservation.appliquer(aujourdhui) == 0  # une seule fois


@pytest.mark.django_db
def test_duree_reglee_depuis_la_fiche_projet():
    from rest_framework.test import APIClient

    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User

    projet = _projet("FICHE", "2026-12-31", None)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_conserv", password="x", role=ROLE_ADMIN))
    assert client.patch(f"/api/v1/projets/{projet.pk}/", {"conservation_beneficiaires_mois": 24}, format="json").status_code == 200
    projet.refresh_from_db()
    assert projet.conservation_beneficiaires_mois == 24
