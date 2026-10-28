"""Carte : import de couches SIG (shapefile, GeoJSON) et carte imprimable."""
import io
import json
import zipfile

import geopandas as gpd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from shapely.geometry import box

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User
from apps.beneficiaries.models import Beneficiaire

from .models import CoucheImportee, LimiteAdministrative, NiveauAdministratif, Zone


def _shapefile_zip(tmp_path):
    """Shapefile en UTM 30N (projection à convertir) dans une archive .zip."""
    gdf = gpd.GeoDataFrame(
        {"NOM_ZONE": ["Zone A", "Zone B"], "OBJECTID": [1, 2]},
        geometry=[box(400000, 1300000, 420000, 1320000), box(430000, 1300000, 450000, 1320000)],
        crs=32630,
    )
    gdf.to_file(tmp_path / "zones.shp")
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        for extension in ("shp", "shx", "dbf", "prj", "cpg"):
            chemin = tmp_path / f"zones.{extension}"
            if chemin.exists():
                archive.write(chemin, f"zones.{extension}")
    return SimpleUploadedFile("zones.zip", tampon.getvalue())


@pytest.mark.django_db
def test_import_et_carte_imprimable(tmp_path):
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_sig", password="x", role=ROLE_ADMIN))

    r = client.post("/api/v1/couches-importees/", {"fichier": _shapefile_zip(tmp_path), "nom": "Zones ZZ", "couleur": "#e8590c"}, format="multipart")
    assert r.status_code == 201, r.data
    assert r.data["geometrie"] == "POLYGONE" and r.data["nombre_objets"] == 2
    assert r.data["champ_etiquette"] == "NOM_ZONE" and "OBJECTID" not in r.data["colonnes"]  # colonne technique écartée
    ouest, sud, est, nord = r.data["emprise"]
    assert -4.0 < ouest < est < -3.0 and 11.0 < sud < nord < 12.5  # reprojetée en degrés
    geojson = client.get(f"/api/v1/couches-importees/{r.data['id']}/geojson/").data
    assert len(geojson["features"]) == 2
    assert client.patch(f"/api/v1/couches-importees/{r.data['id']}/", {"champ_etiquette": "inconnu"}, format="json").status_code == 400

    points = SimpleUploadedFile("forages.geojson", json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"nom": "Forage 1"}, "geometry": {"type": "Point", "coordinates": [-3.5, 11.5]}},
    ]}).encode())
    forages = client.post("/api/v1/couches-importees/", {"fichier": points}, format="multipart").data
    assert forages["geometrie"] == "POINT" and forages["nom"] == "forages"
    assert client.post("/api/v1/couches-importees/", {"fichier": SimpleUploadedFile("x.txt", b"x")}, format="multipart").status_code == 400

    # Carte imprimable filtrée sur une région, avec les couches importées.
    region = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Région", ordre=1)
    zone = Zone.objects.create(nom="Sud", niveau_administratif=region, latitude=11.5, longitude=-3.5)
    LimiteAdministrative.objects.create(pays="ZZ", niveau=1, source="Test", geojson={"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"shapeName": "Sud"}, "geometry": json.loads(gpd.GeoSeries([box(-4, 11, -3, 12)]).to_json())["features"][0]["geometry"]},
    ]})
    Beneficiaire.objects.create(nom="A", prenom="a", sexe="F", zone=zone, pays="ZZ")
    Beneficiaire.objects.create(nom="B", prenom="b", sexe="M", latitude=11.4, longitude=-3.6, pays="ZZ")  # GPS dans la région
    Beneficiaire.objects.create(nom="C", prenom="c", sexe="M", latitude=14.0, longitude=0.5, pays="ZZ")  # hors région
    carte = client.get("/api/v1/beneficiaires/carte/", {"zone": zone.id}).data
    assert carte["total"] == 2 and carte["femmes"] == 1 and carte["zone_filtre"]["contour"] is not None
    for sortie, debut in (("pdf", b"%PDF"), ("png", b"\x89PNG")):
        r = client.get("/api/v1/beneficiaires/carte/export/", {
            "zone": zone.id, "papier": "A4", "sortie": sortie, "couches": "regions,noms", "importees": f"{CoucheImportee.objects.first().id},{forages['id']}",
        })
        assert r.status_code == 200 and r.content.startswith(debut), sortie
    assert client.get("/api/v1/beneficiaires/carte/export/", {"papier": "B5"}).status_code == 400
