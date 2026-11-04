"""Explorateur de documents : dossiers imbriqués, racine, bibliothèque libre, déplacement."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.projects.models import Projet

from .models import Document, Dossier


@pytest.fixture
def client(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    c = APIClient()
    c.force_authenticate(User.objects.create_user(username="adm_doc", password="x", role=ROLE_ADMIN))
    return c


def _document(client, nom, **champs):
    donnees = {"nom": nom, "fichier": SimpleUploadedFile(f"{nom}.txt", b"contenu"), **{k: v for k, v in champs.items() if v is not None}}
    reponse = client.post("/api/v1/documents/", donnees, format="multipart")
    assert reponse.status_code == 201, reponse.content
    return reponse.data["id"]


def test_explorateur(client):
    projet = Projet.objects.create(nom="P", code="DOC-1", date_debut="2026-01-01", date_fin="2026-12-31")
    racine = client.post("/api/v1/dossiers/", {"nom": "Rapports"}, format="json").data
    sous = client.post("/api/v1/dossiers/", {"nom": "2026", "parent": racine["id"]}, format="json").data
    _document(client, "libre_racine")
    _document(client, "dans_rapports", dossier=racine["id"])
    _document(client, "du_projet", projet=projet.id)

    # Racine de la bibliothèque libre : seulement les documents libres hors dossier.
    libres = client.get("/api/v1/documents/", {"libres": "true", "sans_dossier": "true"}).data["results"]
    assert [d["nom"] for d in libres] == ["libre_racine"]
    assert [d["nom"] for d in client.get("/api/v1/documents/", {"dossier": racine["id"]}).data["results"]] == ["dans_rapports"]
    # Nombre d'éléments de chaque dossier.
    dossiers = {d["nom"]: d for d in client.get("/api/v1/dossiers/", {"libres": "true"}).data}
    assert dossiers["Rapports"]["nombre_documents"] == 1 and dossiers["Rapports"]["nombre_sous_dossiers"] == 1

    # Déplacer et renommer un document (JSON).
    doc = Document.objects.get(nom="libre_racine")
    assert client.patch(f"/api/v1/documents/{doc.id}/", {"dossier": sous["id"], "nom": "renomme"}, format="json").status_code == 200
    doc.refresh_from_db()
    assert doc.dossier_id == sous["id"] and doc.nom == "renomme"
    # Jamais dans le dossier d'un autre projet, ni un dossier dans lui-même.
    dossier_projet = client.post("/api/v1/dossiers/", {"nom": "Projet", "projet": projet.id}, format="json").data
    assert client.patch(f"/api/v1/documents/{doc.id}/", {"dossier": dossier_projet["id"]}, format="json").status_code == 400
    assert client.patch(f"/api/v1/dossiers/{racine['id']}/", {"parent": sous["id"]}, format="json").status_code == 400
    assert client.post("/api/v1/dossiers/", {"nom": "x", "parent": dossier_projet["id"]}, format="json").status_code == 400
    # Supprimer un dossier supprime ses sous-dossiers et leurs documents.
    client.delete(f"/api/v1/dossiers/{racine['id']}/")
    assert not Dossier.objects.filter(nom__in=["Rapports", "2026"]).exists() and not Document.objects.filter(nom="renomme").exists()


def test_tous_les_dossiers_sans_pagination(client):
    """Un dossier libre reste visible même quand les projets ont déjà beaucoup de dossiers."""
    projet = Projet.objects.create(nom="P", code="DOC-2", date_debut="2026-01-01", date_fin="2026-12-31")
    for i in range(30):
        client.post("/api/v1/dossiers/", {"nom": f"A{i:02d}", "projet": projet.id}, format="json")
    client.post("/api/v1/dossiers/", {"nom": "zz libre"}, format="json")
    libres = client.get("/api/v1/dossiers/", {"libres": "true"}).data
    assert [d["nom"] for d in libres] == ["zz libre"]
    assert len(client.get("/api/v1/dossiers/", {"projet": projet.id}).data) == 30


def test_fichier_par_lien_signe(client, settings):
    """Les fichiers ne passent que par un lien signé ; un lien falsifié ou d'un compte inactif est refusé."""
    _document(client, "note")
    lien = client.get("/api/v1/documents/").data["results"][0]["derniere_version"]["fichier"]
    assert "/api/v1/fichiers-documents/" in lien and "/media/" not in lien
    chemin = lien.split("testserver")[1]
    reponse = APIClient().get(chemin)
    assert reponse.status_code == 200 and b"".join(reponse.streaming_content) == b"contenu"
    assert APIClient().get(chemin[:-3] + "xx/").status_code == 404
    User.objects.filter(username="adm_doc").update(is_active=False)
    assert APIClient().get(chemin).status_code == 404


def test_preparer_demo_refuse_hors_demo(db, settings):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    settings.MODE_DEMO = False
    with pytest.raises(CommandError):
        call_command("preparer_demo")


def test_selection_corbeille_restaurer_vider(client, tmp_path):
    import io
    import zipfile

    rapports = client.post("/api/v1/dossiers/", {"nom": "Rapports"}, format="json").data
    annee = client.post("/api/v1/dossiers/", {"nom": "2026", "parent": rapports["id"]}, format="json").data
    a = _document(client, "a", dossier=rapports["id"])
    b = _document(client, "b", dossier=annee["id"])
    seul = _document(client, "seul")
    autre = _document(client, "autre")

    # Téléchargement de la sélection : un zip avec l'arborescence des dossiers.
    reponse = client.get("/api/v1/documents/telecharger-selection/", {"dossiers": str(rapports["id"]), "documents": str(seul)})
    assert reponse.status_code == 200
    noms = zipfile.ZipFile(io.BytesIO(b"".join(reponse.streaming_content))).namelist()
    assert {"seul.txt", "Rapports/a.txt", "Rapports/2026/b.txt"} <= set(noms)

    # Suppression : le document « a » à part, puis le dossier avec le reste, et « seul » en même temps.
    assert client.delete(f"/api/v1/documents/{a}/").status_code == 204
    assert client.post("/api/v1/documents/supprimer-selection/", {"dossiers": [rapports["id"]], "documents": [seul]},
                       format="json").data["nombre"] == 2
    assert [d["nom"] for d in client.get("/api/v1/documents/", {"libres": "true"}).data["results"]] == ["autre"]
    assert client.get("/api/v1/dossiers/").data == []
    corbeille = client.get("/api/v1/documents/corbeille/").data
    assert [d["nom"] for d in corbeille["dossiers"]] == ["Rapports"]
    assert corbeille["dossiers"][0]["nombre_elements"] == 2  # « 2026 » et « b »
    assert sorted(d["nom"] for d in corbeille["documents"]) == ["a", "seul"]
    # Ce qui est parti avec un dossier ne se restaure pas seul.
    assert client.post("/api/v1/documents/corbeille/restaurer/", {"documents": [b]}, format="json").data["nombre"] == 0

    # Restaurer le dossier : il revient avec « 2026 » et « b » ; « a », supprimé à part, reste à la corbeille.
    client.post("/api/v1/documents/corbeille/restaurer/", {"dossiers": [rapports["id"]]}, format="json")
    assert {d["nom"] for d in client.get("/api/v1/dossiers/").data} == {"Rapports", "2026"}
    assert [d["nom"] for d in client.get("/api/v1/documents/", {"dossier": annee["id"]}).data["results"]] == ["b"]
    assert sorted(d["nom"] for d in client.get("/api/v1/documents/corbeille/").data["documents"]) == ["a", "seul"]
    # Restaurer « a » : son dossier est revenu, il y retourne.
    client.post("/api/v1/documents/corbeille/restaurer/", {"documents": [a]}, format="json")
    assert Document.objects.get(pk=a).dossier_id == rapports["id"]

    # Vider le dossier : définitif, fichiers compris ; « seul », supprimé à part, reste à la corbeille, à la racine.
    fichier_b = Document.objects.get(pk=b).derniere_version.fichier
    chemin_b = fichier_b.path
    client.delete(f"/api/v1/documents/{seul}/")
    client.delete(f"/api/v1/dossiers/{rapports['id']}/")
    assert client.post("/api/v1/documents/corbeille/vider/", {"dossiers": [rapports["id"]]}, format="json").data["nombre"] == 1
    assert not Dossier.tous.filter(pk__in=[rapports["id"], annee["id"]]).exists()
    assert not Document.tous.filter(pk__in=[a, b]).exists()
    import os

    assert not os.path.exists(chemin_b)
    assert [d["nom"] for d in client.get("/api/v1/documents/corbeille/").data["documents"]] == ["seul"]
    client.post("/api/v1/documents/corbeille/vider/", {"tout": True}, format="json")
    corbeille = client.get("/api/v1/documents/corbeille/").data
    assert corbeille["dossiers"] == [] and corbeille["documents"] == []
    assert Document.tous.filter(pk=autre, supprime_le__isnull=True).exists()


def test_corbeille_suit_la_visibilite_des_projets(db, settings, tmp_path):
    from apps.accounts.constants import ROLE_CHEF_PROJET

    settings.MEDIA_ROOT = tmp_path
    projet = Projet.objects.create(nom="P", code="DOC-C", date_debut="2026-01-01", date_fin="2026-12-31")
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_c", password="x", role=ROLE_ADMIN))
    doc = _document(admin, "du_projet", projet=projet.id)
    admin.delete(f"/api/v1/documents/{doc}/")
    autre = APIClient()
    autre.force_authenticate(User.objects.create_user(username="chef_c", password="x", role=ROLE_CHEF_PROJET))
    assert autre.get("/api/v1/documents/corbeille/").data["documents"] == []
    assert autre.post("/api/v1/documents/corbeille/vider/", {"documents": [doc]}, format="json").status_code == 400
    assert Document.tous.filter(pk=doc).exists()


def test_corbeille_videe_apres_30_jours(client):
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone

    vieux = _document(client, "vieux")
    recent = _document(client, "recent")
    client.delete(f"/api/v1/documents/{vieux}/")
    client.delete(f"/api/v1/documents/{recent}/")
    Document.tous.filter(pk=vieux).update(supprime_le=timezone.now() - timedelta(days=31))
    Document.tous.filter(pk=recent).update(supprime_le=timezone.now() - timedelta(days=29))
    call_command("check_deadlines")
    assert not Document.tous.filter(pk=vieux).exists()
    assert Document.tous.filter(pk=recent).exists()
    ligne = client.get("/api/v1/documents/corbeille/").data["documents"][0]
    assert (ligne["supprime_definitivement_le"] - ligne["supprime_le"]).days == 30
