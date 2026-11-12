"""Zones administratives installées automatiquement selon le pays (inscription, pays de l'organisation, projet)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .models import InstallationZones, LimiteAdministrative, NiveauAdministratif, Zone
from .services import installation


def _carre(x, y, cote):
    return {"type": "Polygon", "coordinates": [[[x, y], [x + cote, y], [x + cote, y + cote], [x, y + cote], [x, y]]]}


def _limite(pays, niveau, nom_niveau, entites):
    LimiteAdministrative.objects.create(pays=pays, niveau=niveau, nom_niveau=nom_niveau, source="test", geojson={
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"shapeName": n}, "geometry": g} for n, g in entites]})


@pytest.fixture
def ghana(db, settings):
    """Contours d'un pays fictif déjà en cache : deux régions, trois districts (pas de niveau 3)."""
    settings.ZONES_INSTALLATION = "synchrone"
    _limite("GH", 1, "Region", [("Nord", _carre(0, 10, 10)), ("Sud", _carre(0, 0, 10))])
    _limite("GH", 2, "Districts", [("Tamale", _carre(2, 12, 2)), ("Bolga", _carre(5, 15, 2)), ("Accra", _carre(3, 3, 2))])

    def sans_niveau_3(pays, niveau):
        existante = LimiteAdministrative.objects.filter(pays=pays, niveau=niveau).first()
        if existante is None:
            raise installation.LimitesIndisponibles("absent")
        return existante

    import apps.geo.services.installation as module

    module.telecharger = sans_niveau_3
    yield
    from .services.limites import telecharger

    module.telecharger = telecharger


def test_installation_d_un_pays_avec_hierarchie(ghana):
    assert installation.code_pays("Ghana") == "GH" and installation.code_pays("États-Unis") == "US"
    assert installation.installer_pays("GH") == 5
    niveaux = list(NiveauAdministratif.objects.filter(pays="GH").values_list("ordre", "nom_niveau"))
    assert niveaux == [(1, "Région"), (2, "District")]
    assert Zone.objects.get(nom="Tamale").parent.nom == "Nord" and Zone.objects.get(nom="Accra").parent.nom == "Sud"
    assert InstallationZones.objects.get(pays="GH").statut == "TERMINE"
    # Déjà installé : jamais modifié (les corrections de l'organisation sont gardées).
    Zone.objects.filter(nom="Bolga").update(nom="Bolgatanga")
    assert installation.installer_pays("GH") == 0 and Zone.objects.filter(nom="Bolgatanga").exists()


def test_ajout_par_l_api_et_par_un_projet(ghana):
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_pays", password="x", role=ROLE_ADMIN))
    reponse = client.post("/api/v1/pays-zones/", {"pays": ["GH"]}, format="json")
    assert reponse.status_code == 200 and {"pays": "GH", "zones": 5, "statut": "TERMINE", "message": ""} in reponse.data
    # Projet dans un pays sans zones : elles s'installent ; pays inconnu de la source : échec signalé.
    reponse = client.post("/api/v1/projets/", {"nom": "P", "code": "GH-1", "date_debut": "2026-01-01",
                                               "date_fin": "2026-12-31", "pays": ["BF", "ZZ"]}, format="json")
    assert reponse.status_code == 201, reponse.data
    assert NiveauAdministratif.objects.filter(pays="BF").exists()
    assert InstallationZones.objects.get(pays="ZZ").statut == "ECHEC"
