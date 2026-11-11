"""Éléments masqués à un utilisateur : activités (et ce qui est en dessous) et éléments stratégiques."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.indicators.models import Indicateur
from apps.projects.models import Activite, Projet, SousActivite
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau

from .masquage import activites_masquees, elements_masques


@pytest.fixture
def donnees(db):
    projet = Projet.objects.create(nom="P", code="M-1", date_debut="2026-01-01", date_fin="2026-12-31")
    resultat = Activite.objects.create(projet=projet, libelle="Résultat secret", budget_alloue=1000)
    activite = Activite.objects.create(projet=projet, activite_parent=resultat, libelle="Activité secrète", budget_alloue=1000)
    autre = Activite.objects.create(projet=projet, libelle="Activité visible", budget_alloue=500)
    sous = SousActivite.objects.create(activite=activite, libelle="Tâche secrète")
    indicateur = Indicateur.objects.create(activite=activite, libelle="Indicateur secret", unite="u", valeur_cible=10)
    cadre = CadreStrategique.objects.create(nom="Plan")
    niveau = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Axe", ordre=1)
    sous_niveau = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Objectif", ordre=2, niveau_parent=niveau)
    axe = ElementStrategique.objects.create(type_niveau=niveau, nom="Axe secret")
    objectif = ElementStrategique.objects.create(type_niveau=sous_niveau, element_parent=axe, nom="Objectif secret")
    agent = User.objects.create_user(username="agent_masque", password="x", role=ROLE_CHARGE_SE)
    admin = User.objects.create_user(username="admin_masque", password="x", role=ROLE_ADMIN)
    return locals()


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_masquer_un_element_masque_ce_qui_est_en_dessous(donnees):
    d = donnees
    admin = _client(d["admin"])
    reponse = admin.patch(f"/api/v1/utilisateurs/{d['agent'].pk}/", {
        "activites_masquees": [d["resultat"].pk], "elements_masques": [d["axe"].pk]}, format="json")
    assert reponse.status_code == 200
    agent = User.objects.get(pk=d["agent"].pk)
    assert activites_masquees(agent) == {d["resultat"].pk, d["activite"].pk}
    assert elements_masques(agent) == {d["axe"].pk, d["objectif"].pk}

    vue = _client(agent)
    libelles = {a["libelle"] for a in vue.get("/api/v1/activites/", {"projet": d["projet"].pk}).data["results"]}
    assert libelles == {"Activité visible"}
    assert vue.get(f"/api/v1/activites/{d['activite'].pk}/").status_code == 404
    assert vue.get("/api/v1/sous-activites/").data["count"] == 0
    assert "Indicateur secret" not in str(vue.get("/api/v1/indicateurs/").data)
    assert not vue.get("/api/v1/elements-strategiques/arborescence/").data
    # L'Administrateur voit toujours tout ; sa propre fiche ne masque rien.
    assert admin.get("/api/v1/activites/", {"projet": d["projet"].pk}).data["count"] == 3
    assert {"Axe secret", "Objectif secret"} <= {e["nom"] for e in admin.get("/api/v1/elements-strategiques/arborescence/").data}
    assert set(admin.get(f"/api/v1/utilisateurs/{agent.pk}/").data["activites_masquees"]) == {d["resultat"].pk}
