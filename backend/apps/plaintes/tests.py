"""Lot 1 du mécanisme de plaintes : modèles, contrôles d'activation, règles verrouillées, Excel, droits."""
import io

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User

from .models import Categorie, Circuit, EtapeCircuit, Mecanisme, Priorite

URL = "/api/v1/plaintes/"


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_plaintes", password="x", role=ROLE_ADMIN)


@pytest.fixture
def client(admin):
    c = APIClient()
    c.force_authenticate(admin)
    return c


@pytest.fixture
def standard(client):
    assert client.post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    return Mecanisme.courant()


def _rendre_activable(admin):
    """Ce que l'organisation doit encore faire après le modèle : conservation et points focaux."""
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=admin)


@pytest.mark.django_db
def test_modele_puis_activation_controlee(client, admin, standard):
    """Le modèle installe tout ; l'activation reste bloquée tant que l'organisation n'a pas tranché."""
    assert Circuit.objects.filter(sensible=True, par_defaut=True).exists()
    assert Categorie.objects.filter(verrouillee=True, sensible=True).count() == 2
    assert Priorite.objects.filter(urgente=True).exists()
    controles = client.get(URL + "mecanisme/").data["controles"]
    assert any("conservation" in c for c in controles)
    assert any("Circuit confidentiel" in c and "personne responsable" in c for c in controles)
    r = client.post(URL + "mecanisme/activer/")
    assert r.status_code == 400 and r.data["controles"] and not Mecanisme.courant().actif
    _rendre_activable(admin)
    assert client.get(URL + "mecanisme/").data["controles"] == []
    assert client.post(URL + "mecanisme/activer/").data["actif"] is True
    # Réappliquer le modèle n'ajoute rien (copie par nom, sans doublon).
    ajouts = client.post(URL + "modeles/", {"modele": "standard"}, format="json").data["ajouts"]
    assert ajouts == {"types": 0, "priorites": 0, "categories": 0, "circuits": 0}


@pytest.mark.django_db
def test_regles_verrouillees(client, standard):
    verrouillee = Categorie.objects.filter(verrouillee=True).first()
    assert client.delete(f"{URL}categories/{verrouillee.id}/").status_code == 400
    assert client.patch(f"{URL}categories/{verrouillee.id}/", {"sensible": False}, format="json").status_code == 400
    assert client.patch(f"{URL}categories/{verrouillee.id}/", {"actif": False}, format="json").status_code == 400
    # Renommer reste possible (vocabulaire de l'organisation).
    assert client.patch(f"{URL}categories/{verrouillee.id}/", {"nom": "EAS"}, format="json").status_code == 200
    # Une catégorie sensible ne passe pas par un circuit ordinaire.
    ordinaire = Circuit.objects.get(sensible=False)
    assert client.patch(f"{URL}categories/{verrouillee.id}/", {"circuit": ordinaire.id}, format="json").status_code == 400
    # Circuit confidentiel : jamais confié à un rôle entier.
    sensible = Circuit.objects.get(sensible=True)
    etape = sensible.etapes.first()
    role = ordinaire.etapes.exclude(role=None).first().role
    assert client.patch(f"{URL}etapes/{etape.id}/", {"role": role.id}, format="json").status_code == 400
    # Toujours au moins une priorité urgente active.
    urgente = Priorite.objects.get(urgente=True)
    assert client.patch(f"{URL}priorites/{urgente.id}/", {"actif": False}, format="json").status_code == 400
    assert client.delete(f"{URL}priorites/{urgente.id}/").status_code == 400
    # Trois niveaux de catégories : refusé.
    parent = Categorie.objects.filter(parent__isnull=False).first()
    assert client.post(URL + "categories/", {"nom": "Trop profond", "parent": parent.id}, format="json").status_code == 400


@pytest.mark.django_db
def test_circuit_sans_cloture_bloque_l_activation(client, admin, standard):
    _rendre_activable(admin)
    ordinaire = Circuit.objects.get(sensible=False)
    ordinaire.etapes.filter(est_cloture=True).delete()
    assert any("clôture" in c for c in client.get(URL + "mecanisme/").data["controles"])
    assert client.post(URL + "mecanisme/activer/").status_code == 400


@pytest.mark.django_db
def test_canevas_excel_aller_retour(client, admin, standard):
    contenu = client.get(URL + "canevas/").content
    wb = load_workbook(io.BytesIO(contenu))
    assert wb.sheetnames == ["Mécanisme", "Types de retours", "Priorités", "Circuits", "Catégories", "Instructions"]
    # Réimport tel quel : rien de créé, aucune erreur.
    fichier = io.BytesIO(contenu)
    fichier.name = "p.xlsx"
    rapport = client.post(URL + "canevas/importer/", {"fichier": fichier}, format="multipart").data
    assert rapport["erreurs"] == [] and rapport["crees"] == 0, rapport
    # Ajouts et corrections : conservation, nouvelle sous-catégorie, points focaux du circuit confidentiel.
    reglages = wb["Mécanisme"]
    for ligne in reglages.iter_rows():
        if ligne[0].value.startswith("Conservation"):
            ligne[1].value = 48
    wb["Catégories"].append(["Distribution et assistance", "Articles manquants", "", "Non", "", 10, "Oui"])
    for ligne in wb["Circuits"].iter_rows(min_row=2):
        if ligne[0].value == "Circuit confidentiel":
            ligne[6].value = admin.username
    wb["Catégories"].append(["Inconnue", "Sous", "", "Non", "", "", "Oui"])  # erreur : principale absente
    wb["Priorités"].append(["Basse", "peut-être", 60, "Oui"])  # erreur : Oui / Non attendu
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    sortie.name = "p.xlsx"
    rapport = client.post(URL + "canevas/importer/", {"fichier": sortie}, format="multipart").data
    messages = " ".join(e["message"] for e in rapport["erreurs"])
    assert "Inconnue" in messages and "Oui ou Non" in messages and len(rapport["erreurs"]) == 2, rapport
    assert Categorie.objects.get(nom="Articles manquants").parent.nom == "Distribution et assistance"
    assert Mecanisme.courant().conservation_sensible_mois == 48
    assert client.get(URL + "mecanisme/").data["controles"] == []


@pytest.mark.django_db
def test_droits_du_module(standard):
    """Lecture pour tous ; écriture selon le module « Plaintes et retours »."""
    charge = User.objects.create_user(username="charge_pl", password="x", role=ROLE_CHARGE_SE,
                                      niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE, acces_modules={"/plaintes": "LECTURE"})
    c = APIClient()
    c.force_authenticate(charge)
    assert c.get(URL + "categories/").status_code == 200
    assert c.post(URL + "categories/", {"nom": "Nouvelle"}, format="json").status_code == 403
    assert c.post(URL + "mecanisme/activer/").status_code == 403
    charge.acces_modules = {"/plaintes": "ECRITURE"}
    charge.save()
    assert c.post(URL + "categories/", {"nom": "Nouvelle"}, format="json").status_code == 201
