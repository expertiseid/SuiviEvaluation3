"""Effacement définitif : supprimer un projet ou un bénéficiaire ne laisse ni historique ni fichier."""
import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.beneficiaries.models import Beneficiaire
from apps.documents.models import DocumentVersion
from apps.projects.models import Activite, Projet


@pytest.fixture
def admin(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_effacement", password="x", role=ROLE_ADMIN))
    return client


def test_projet_supprime_sans_historique_ni_fichier(admin, django_capture_on_commit_callbacks):
    projet = Projet.objects.create(nom="Projet confidentiel", code="EFF-1", date_debut="2026-01-01", date_fin="2026-12-31")
    projet.nom = "Projet confidentiel (modifié)"
    projet.save()
    activite = Activite.objects.create(projet=projet, libelle="Distribution aux ménages", budget_alloue=100)
    reponse = admin.post("/api/v1/documents/", {"nom": "liste.pdf", "projet": projet.pk,
                                                "fichier": SimpleUploadedFile("liste.pdf", b"%PDF-1.4 noms")}, format="multipart")
    assert reponse.status_code == 201, reponse.content
    fichier = DocumentVersion.objects.get(document_id=reponse.data["id"]).fichier.name
    assert default_storage.exists(fichier)
    assert Projet.history.filter(id=projet.pk).count() == 2

    with django_capture_on_commit_callbacks(execute=True):
        assert admin.delete(f"/api/v1/projets/{projet.pk}/").status_code == 204

    assert not Projet.history.filter(id=projet.pk).exists()
    assert not Activite.history.filter(id=activite.pk).exists()
    assert not default_storage.exists(fichier)


def test_beneficiaire_supprime_sans_historique(admin, django_capture_on_commit_callbacks):
    beneficiaire = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F", numero_piece_identite="CNIB-EFF")
    beneficiaire.telephone = "70000000"
    beneficiaire.save()
    autre = Beneficiaire.objects.create(nom="Ouedraogo", prenom="Ali", sexe="M")
    with django_capture_on_commit_callbacks(execute=True):
        assert admin.delete(f"/api/v1/beneficiaires/{beneficiaire.pk}/").status_code == 204
    assert not Beneficiaire.history.filter(id=beneficiaire.pk).exists()
    assert Beneficiaire.history.filter(id=autre.pk).exists()  # les autres gardent leur historique


def test_echec_de_suppression_ne_efface_rien(admin):
    from apps.core.effacement import effacement_definitif

    projet = Projet.objects.create(nom="P", code="EFF-2", date_debut="2026-01-01", date_fin="2026-12-31")
    with pytest.raises(RuntimeError):
        with effacement_definitif():
            Projet.objects.filter(pk=projet.pk).delete()
            raise RuntimeError("échec")
    assert Projet.objects.filter(pk=projet.pk).exists() and Projet.history.filter(id=projet.pk).exists()
