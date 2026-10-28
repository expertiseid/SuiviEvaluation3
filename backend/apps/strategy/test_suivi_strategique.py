"""Lot 5 : renseignement propre aux documents stratégiques, à côté du calcul depuis les projets."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Activite, Projet

from .models import CadreStrategique, ElementStrategique, TypeNiveau


@pytest.mark.django_db
def test_suivi_d_un_element_strategique(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_strat", password="x", role=ROLE_ADMIN))
    cadre = CadreStrategique.objects.create(nom="Stratégie ZZ")
    orientation = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Orientation", ordre=1)
    axe_niveau = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Axe", ordre=2, niveau_parent=orientation)
    o1 = ElementStrategique.objects.create(type_niveau=orientation, nom="Accès aux services")
    axe = ElementStrategique.objects.create(type_niveau=axe_niveau, nom="Eau potable", element_parent=o1)

    # Calcul automatique : une activité rattachée à l'axe compte aussi pour l'orientation au-dessus.
    projet = Projet.objects.create(nom="P", code="STR-1", date_debut="2026-01-01", date_fin="2026-12-31")
    parent = Activite.objects.create(projet=projet, libelle="Composante", axe_strategique=axe)
    Activite.objects.create(projet=projet, libelle="Forages", activite_parent=parent, budget_alloue=1000, budget_realise=250)
    suivi = client.get(f"/api/v1/elements-strategiques/{o1.id}/suivi/").data
    assert [p["code"] for p in suivi["calcule"]["projets"]] == ["STR-1"]
    assert suivi["calcule"]["budget_alloue"] == 1000 and suivi["calcule"]["taux_financier"] == 25.0

    # Indicateur propre à l'axe : le rattachement est bien enregistré (il était ignoré auparavant).
    indicateur = client.post("/api/v1/indicateurs/", {
        "libelle": "Taux d'accès national", "unite": "%", "valeur_cible": 80, "frequence_collecte": "ANNUELLE",
        "elements_strategiques": [axe.id],
    }, format="json")
    assert indicateur.status_code == 201 and indicateur.data["elements_strategiques"] == [axe.id]
    valeur = client.post("/api/v1/valeurs-indicateurs/", {
        "indicateur": indicateur.data["id"], "periode_debut": "2025-01-01", "periode_fin": "2025-12-31", "valeur_realisee": 6,
    }, format="json")
    assert valeur.status_code == 201

    # Appréciation avec pièce justificative, téléchargeable par un compte connecté seulement.
    appreciation = client.post("/api/v1/appreciations-strategiques/", {
        "element": axe.id, "libelle_periode": "Année 2025", "periode_debut": "2025-01-01", "periode_fin": "2025-12-31",
        "etat": "MOYEN", "commentaire": "Retard sur l'assainissement",
    }, format="json")
    assert appreciation.status_code == 201 and appreciation.data["saisi_par_nom"] == "adm_strat"
    assert client.post("/api/v1/appreciations-strategiques/", {
        "element": axe.id, "periode_debut": "2025-12-31", "periode_fin": "2025-01-01", "etat": "BON",
    }, format="json").status_code == 400
    piece = client.post("/api/v1/pieces-justificatives/", {
        "fichier": SimpleUploadedFile("rapport.txt", b"contenu"), "nom": "rapport.txt",
        "appreciation_strategique": appreciation.data["id"],
    }, format="multipart")
    assert piece.status_code == 201, piece.data
    assert client.post("/api/v1/pieces-justificatives/", {"fichier": SimpleUploadedFile("x.txt", b"x"), "nom": "x"}, format="multipart").status_code == 400

    suivi = client.get(f"/api/v1/elements-strategiques/{axe.id}/suivi/").data
    assert suivi["indicateurs"][0]["realise"] == 6 and suivi["indicateurs"][0]["saisie_directe"]
    piece_affichee = suivi["appreciations"][0]["pieces"][0]
    assert b"".join(client.get(f"/api/v1{piece_affichee['telechargement']}").streaming_content) == b"contenu"
    assert APIClient().get(f"/api/v1{piece_affichee['telechargement']}").status_code == 401

    vue = {e["nom"]: e for e in client.get(f"/api/v1/cadres-strategiques/{cadre.id}/suivi/").data["elements"]}
    assert vue["Eau potable"]["derniere_appreciation"]["etat"] == "MOYEN" and vue["Eau potable"]["nombre_indicateurs"] == 1

    for fichier, debut in (("pdf", b"%PDF"), ("docx", b"PK")):
        r = client.get(f"/api/v1/rapports/suivi-strategique/{cadre.id}/", {"fichier": fichier})
        assert r.status_code == 200 and r.content.startswith(debut)
