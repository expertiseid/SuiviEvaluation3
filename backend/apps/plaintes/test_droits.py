"""Lot 9 : demandes des personnes sur leurs données et registre des traitements."""
import io
from datetime import date

import pytest
from django.db import connection
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.core.models import EvenementAudit

from .droits import un_mois_apres
from .models import DemandeDroits, Mecanisme

URL = "/api/v1/plaintes/demandes-droits/"


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_ddp", password="x", role=ROLE_ADMIN)


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_un_mois_apres():
    assert un_mois_apres(date(2026, 1, 31)) == date(2026, 2, 28)
    assert un_mois_apres(date(2026, 12, 15)) == date(2027, 1, 15)


@pytest.mark.django_db
def test_procedure_tracee(admin):
    lecteur = User.objects.create_user(username="se_ddp", password="x", role=ROLE_CHARGE_SE)
    assert _client(lecteur).get(URL).status_code == 403
    c = _client(admin)
    assert c.post(URL, {"type": "ACCES"}, format="json").status_code == 400
    assert c.post(URL, {"type": "ACCES", "demandeur": "Awa", "numero_dossier": "MGP-0000-99999"}, format="json").status_code == 400
    cree = c.post(URL, {"type": "EFFACEMENT", "demandeur": "Awa Témoin", "contact": "70 11 22 33",
                        "date_reception": "2026-10-10", "description": "Souhaite l'effacement"}, format="json")
    assert cree.status_code == 201 and cree.data["echeance"] == "2026-11-10" and cree.data["statut"] == "RECUE"
    # Coordonnées chiffrées en base.
    with connection.cursor() as curseur:
        curseur.execute("select demandeur, contact from plaintes_demandedroits where id = %s", [cree.data["id"]])
        assert all(valeur.startswith("chiffre:") for valeur in curseur.fetchone())
    pk = cree.data["id"]
    assert c.post(f"{URL}{pk}/traiter/", {"statut": "REFUSEE"}, format="json").status_code == 400
    traite = c.post(f"{URL}{pk}/traiter/", {"statut": "SATISFAITE", "reponse": "Dossier anonymisé le 12/10."}, format="json")
    assert traite.data["statut"] == "SATISFAITE" and traite.data["date_reponse"]
    operations = list(EvenementAudit.objects.filter(action="DROITS_PERSONNES").values_list("details__operation", flat=True))
    assert sorted(operations) == ["enregistrement", "traitement"]
    assert "Awa" not in str(list(EvenementAudit.objects.values_list("objet", "details")))


@pytest.mark.django_db
def test_registre_des_traitements(admin):
    Mecanisme.courant()
    Mecanisme.objects.filter(pk=1).update(responsable_traitement="ONG Exemple, Ouagadougou", conservation_ordinaire_mois=60)
    DemandeDroits.objects.create(type="ACCES", date_reception=date(2026, 10, 1), echeance=date(2026, 11, 1), demandeur="Secret Nom")
    reponse = _client(admin).get(URL + "registre/")
    assert reponse.status_code == 200
    classeur = load_workbook(io.BytesIO(reponse.content))
    registre = {ligne[0]: ligne[1] for ligne in classeur["Registre"].iter_rows(min_row=3, values_only=True)}
    assert registre["Responsable du traitement"] == "ONG Exemple, Ouagadougou"
    assert registre["Conservation des dossiers ordinaires"].startswith("60 mois")
    demandes = list(classeur["Demandes"].iter_rows(min_row=2, values_only=True))
    assert len(demandes) == 1 and demandes[0][1] == "Accès à ses données"
    # Aucune donnée personnelle dans le registre.
    assert "Secret" not in str([list(f.values) for f in classeur.worksheets])
    assert EvenementAudit.objects.filter(action="EXPORT", objet="Registre des traitements").exists()
