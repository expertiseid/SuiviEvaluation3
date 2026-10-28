"""Import d'une base topographique en shapefiles (fichiers fabriqués avec pyshp)."""
import shapefile
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .models import CoucheCarte, LimiteAdministrative, Localite, NiveauAdministratif, Zone
from .services.bndt import importer, simplifier


def _carre(lng, lat, cote):
    return [[[lng, lat], [lng, lat + cote], [lng + cote, lat + cote], [lng + cote, lat], [lng, lat]]]


def _ecrire(dossier, nom, genre, champs, objets):
    with shapefile.Writer(str(dossier / nom), shapeType=genre, encoding="utf-8") as w:
        for champ in champs:
            w.field(champ, "C", size=80)
        for geometrie, valeurs in objets:
            if genre == shapefile.POLYGON:
                w.poly(geometrie)
            elif genre == shapefile.POLYLINE:
                w.line(geometrie)
            else:
                w.point(*geometrie)
            w.record(*valeurs)


def test_simplification():
    ligne = [[0, 0], [1, 0.0001], [2, 0], [3, 1]]
    assert simplifier(ligne, 0.001) == [[0, 0], [2, 0], [3, 1]]


@pytest.mark.django_db
def test_import_bndt(tmp_path):
    _ecrire(tmp_path, "ADM_region", shapefile.POLYGON, ["Nom_decret"], [(_carre(0, 10, 4), ["KOULSÉ"])])
    _ecrire(tmp_path, "ADM_Province", shapefile.POLYGON, ["Nom_decret", "Nom_Region"], [(_carre(0, 10, 2), ["KOOSIN", "KOULSÉ"])])
    _ecrire(tmp_path, "ADM_commune", shapefile.POLYGON, ["Nom_depart", "Province"], [(_carre(0.5, 10.5, 0.5), ["GOURCI", "KOOSIN"])])
    _ecrire(tmp_path, "RRO_Route", shapefile.POLYLINE, ["Nom", "Cl_admin"], [([[[0, 10], [1, 11], [2, 12]]], ["N1", "NATIONALE"])])
    _ecrire(tmp_path, "HAB_Localite", shapefile.POINT, ["Nom", "Statut", "Nom_admin"], [
        ((0.7, 10.7), ["GOURCY", "VILLE", "GOURCI"]),
        ((0.8, 10.6), ["", "HABITAT_DISPERSE", ""]),  # habitat dispersé : ignoré
    ])
    region = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Région", ordre=1)
    province = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Province", ordre=2, niveau_parent=region)
    commune = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Commune", ordre=3, niveau_parent=province)
    koulse = Zone.objects.create(nom="Koulse", niveau_administratif=region)
    kossin = Zone.objects.create(nom="Kossin", niveau_administratif=province, parent=koulse)
    gourcy = Zone.objects.create(nom="Gourcy", niveau_administratif=commune, parent=kossin)

    resultat = importer(str(tmp_path), "ZZ", journal=lambda *_: None)
    assert resultat["zones placées"] == 3  # orthographes voisines comprises (Kossin/Koosin, Gourcy/Gourci)
    gourcy.refresh_from_db()
    assert round(float(gourcy.latitude), 2) == 10.75
    regions = LimiteAdministrative.objects.get(pays="ZZ", niveau=1)
    assert regions.source == "BNDT (IGB)" and regions.geojson["features"][0]["properties"]["shapeName"] == "Koulsé"
    assert CoucheCarte.objects.get(pays="ZZ", cle="routes").geojson["features"][0]["properties"]["classe"] == "NATIONALE"
    assert list(Localite.objects.values_list("nom", "commune")) == [("Gourcy", "Gourci")]

    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_bndt", password="x", role=ROLE_ADMIN))
    r = client.get("/api/v1/localites/", {"pays": "ZZ", "bbox": "10,0,11,1"})
    assert r.status_code == 200 and r.data["total"] == 1 and r.data["localites"][0]["nom"] == "Gourcy"
    assert client.get("/api/v1/localites/", {"pays": "ZZ", "bbox": "0,0,1,1"}).data["total"] == 0
    assert client.get("/api/v1/couches-carte/", {"pays": "ZZ", "cle": "routes"}).status_code == 200
    assert client.get("/api/v1/couches-carte/", {"pays": "ZZ", "cle": "pistes"}).status_code == 404
    assert client.get("/api/v1/limites-administratives/", {"pays": "ZZ", "niveau": 1}).data["source"] == "BNDT (IGB)"
