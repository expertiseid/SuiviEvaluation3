"""Contrôle de cohérence : avertissements à la saisie et rapport par projet (voir apps.projects.coherence)."""
import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.indicators.models import Indicateur

from .coherence import controler_projet
from .models import Activite, Projet

AUJOURDHUI = timezone.localdate()


@pytest.fixture
def client(db):
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_coh", password="x", role=ROLE_ADMIN))
    return client


@pytest.fixture
def projet(db):
    return Projet.objects.create(nom="P", code="COH-1", date_debut="2026-01-01", date_fin="2026-12-31", budget_total=1000)


def _point(client, activite, debut, fin, **champs):
    return client.post(
        "/api/v1/points-suivi/", {"activite": activite.id, "periode_debut": debut, "periode_fin": fin, **champs}, format="json"
    )


@pytest.mark.django_db
def test_avertissements_a_la_saisie(projet, client):
    activite = Activite.objects.create(
        projet=projet, libelle="Forages", quantite_prevue=10, budget_alloue=500, date_debut="2026-02-01", date_fin="2026-06-30"
    )
    r = _point(client, activite, "2026-03-01", "2026-03-31", quantite_realisee=4)
    assert r.status_code == 201 and r.data["avertissements"] == []

    futur = (AUJOURDHUI + datetime.timedelta(days=30)).isoformat()
    r = _point(client, activite, "2026-03-15", futur, quantite_realisee=8, budget_realise=600)
    textes = " ".join(r.data["avertissements"])
    for attendu in ("futur", "chevauche", "dépasse la quantité prévue", "budget alloué"):
        assert attendu in textes, attendu

    indicateur = Indicateur.objects.create(libelle="Taux", unite="%", valeur_cible=80, frequence_collecte="ANNUELLE", projet=projet)
    r = client.post(
        "/api/v1/valeurs-indicateurs/",
        {"indicateur": indicateur.id, "periode_debut": "2026-01-01", "periode_fin": "2026-03-31", "valeur_realisee": 140},
        format="json",
    )
    assert any("en %" in a for a in r.data["avertissements"])

    # Saisie entièrement en dehors des dates de l'activité.
    r = _point(client, activite, "2026-09-01", "2026-09-30", quantite_realisee=0)
    assert any("dates prévues de l'activité" in a for a in r.data["avertissements"])


@pytest.mark.django_db
def test_rapport_de_coherence_du_projet(projet, client):
    pilier = Activite.objects.create(projet=projet, libelle="Pilier", date_debut="2026-01-01", date_fin="2026-03-31", budget_alloue=900)
    Activite.objects.create(projet=projet, activite_parent=pilier, libelle="Fin avant début", date_debut="2026-03-10", date_fin="2026-03-01", budget_alloue=1200)
    Activite.objects.create(projet=projet, libelle="Hors projet", date_debut="2025-12-01", date_fin="2026-02-01")
    Activite.objects.create(projet=projet, libelle="Sans quantité")

    rapport = client.get(f"/api/v1/projets/{projet.id}/coherence/").data
    projet.refresh_from_db()
    assert rapport == controler_projet(projet)
    messages = {}
    for i in rapport:
        messages[(i["element"], i["gravite"])] = messages.get((i["element"], i["gravite"]), "") + " " + i["message"]
    assert ("Fin avant début", "erreur") in messages
    assert "en dehors de celles du projet" in messages[("Hors projet", "attention")]
    assert "sans quantité prévue" in messages[("Sans quantité", "attention")]
    assert "dépassent le budget de ce niveau" in messages[("Pilier", "attention")]
    assert "dépassent le budget total du projet" in messages[("COH-1", "attention")]
    assert rapport[0]["gravite"] == "erreur"  # les erreurs d'abord
