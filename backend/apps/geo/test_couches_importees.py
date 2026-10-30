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
    assert carte["projets_zone"] == [] and carte["zones"][0]["beneficiaires"][0]["nom"] == "A a"
    for sortie, debut in (("pdf", b"%PDF"), ("png", b"\x89PNG")):
        r = client.get("/api/v1/beneficiaires/carte/export/", {
            "zone": zone.id, "papier": "A4", "sortie": sortie, "couches": "regions,noms,beneficiaires", "fond": "aucun", "importees": f"{CoucheImportee.objects.first().id},{forages['id']}",
        })
        assert r.status_code == 200 and r.content.startswith(debut), sortie
    assert client.get("/api/v1/beneficiaires/carte/export/", {"papier": "B5"}).status_code == 400
    assert client.get("/api/v1/beneficiaires/carte/export/", {"fond": "inconnu"}).status_code == 400


@pytest.mark.django_db
def test_synthese_par_zone():
    """Projets d'une région comptés dans ses provinces ; bénéficiaires selon leur localité."""
    from apps.beneficiaries.models import ParticipationProjet
    from apps.projects.models import Projet

    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_synth", password="x", role=ROLE_ADMIN))
    region = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Région", ordre=1)
    province = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Province", ordre=2, niveau_parent=region)
    nord = Zone.objects.create(nom="Nord", niveau_administratif=region)
    sud = Zone.objects.create(nom="Sud", niveau_administratif=region)
    p1 = Zone.objects.create(nom="P1", niveau_administratif=province, parent=nord)
    p2 = Zone.objects.create(nom="P2", niveau_administratif=province, parent=nord)
    regional = Projet.objects.create(nom="Régional", code="SYN-1", date_debut="2026-01-01", date_fin="2026-12-31", budget_total=1000, pays=["ZZ"])
    regional.zones.add(nord)
    local = Projet.objects.create(nom="Local", code="SYN-2", date_debut="2026-01-01", date_fin="2026-12-31", budget_total=500, pays=["ZZ"])
    local.zones.add(p2)
    b = Beneficiaire.objects.create(nom="A", prenom="a", sexe="F", zone=p1, pays="ZZ")
    ParticipationProjet.objects.create(beneficiaire=b, projet=local, date_inscription="2026-02-01")  # bénéficiaire hors des zones du projet : il y compte aussi

    regions = {z["nom"]: z for z in client.get("/api/v1/carte/synthese/", {"pays": "ZZ", "niveau": 1}).data["zones"]}
    assert (regions["Nord"]["projets"], regions["Nord"]["budget"], regions["Nord"]["beneficiaires"]) == (2, 1500, 1)
    assert regions["Sud"]["projets"] == 0
    provinces = {z["nom"]: z for z in client.get("/api/v1/carte/synthese/", {"pays": "ZZ", "niveau": 2, "zone": nord.id}).data["zones"]}
    assert [p["code"] for p in provinces["P1"]["liste_projets"]] == ["SYN-1", "SYN-2"] and provinces["P1"]["femmes"] == 1
    assert [p["code"] for p in provinces["P2"]["liste_projets"]] == ["SYN-1", "SYN-2"]
    # Indicateurs du catalogue dans `valeurs` ; plusieurs projets et plusieurs zones à la fois.
    from apps.partners.models import Bailleur, Financement

    bailleur = Bailleur.objects.create(nom="Bailleur Z")
    Financement.objects.create(projet=regional, bailleur=bailleur, montant_finance=800)
    Financement.objects.create(projet=local, bailleur=bailleur, montant_finance=300)
    nord_valeurs = {z["nom"]: z for z in client.get("/api/v1/carte/synthese/", {"pays": "ZZ", "niveau": 1}).data["zones"]}["Nord"]["valeurs"]
    assert (nord_valeurs["financements"], nord_valeurs["bailleurs"], nord_valeurs["femmes"]) == (1100, 1, 1)
    seul = client.get("/api/v1/carte/synthese/", {"pays": "ZZ", "niveau": 2, "projet": f"{local.id}", "zone": f"{p1.id},{p2.id}"}).data["zones"]
    assert sorted(z["nom"] for z in seul) == ["P1", "P2"] and all(z["projets"] == 1 for z in seul)
    deux = client.get("/api/v1/carte/synthese/", {"pays": "ZZ", "niveau": 1, "projet": f"{local.id},{regional.id}", "zone": f"{nord.id},{sud.id}"}).data["zones"]
    assert {z["nom"]: z["projets"] for z in deux} == {"Nord": 2, "Sud": 0}
    carte = client.get("/api/v1/beneficiaires/carte/", {"zone": f"{p1.id},{p2.id}"}).data
    assert carte["total"] == 1 and carte["zone_filtre"]["nom"] == "P1, P2" and {p["code"] for p in carte["projets_zone"]} == {"SYN-2"}
    def contour(nom, ouest, sud):
        geometrie = json.loads(gpd.GeoSeries([box(ouest, sud, ouest + 1, sud + 1)]).to_json())["features"][0]["geometry"]
        return {"type": "Feature", "properties": {"shapeName": nom}, "geometry": geometrie}

    LimiteAdministrative.objects.create(pays="ZZ", niveau=1, source="Test", geojson={"type": "FeatureCollection", "features": [
        contour("Nord", -4, 12), contour("Sud", -4, 11),
    ]})
    r = client.get("/api/v1/beneficiaires/carte/export/", {"papier": "A4", "sortie": "png", "par_zone": "budget", "niveau_zone": 1})
    assert r.status_code == 200 and "carte_budget_par_r" in r["Content-Disposition"]
    assert client.get("/api/v1/beneficiaires/carte/export/", {"par_zone": "inconnu"}).status_code == 400
    # Plusieurs indicateurs à l'impression ; filtres du tableau de bord sur les projets retenus.
    r = client.get("/api/v1/beneficiaires/carte/export/", {"papier": "A4", "sortie": "png", "par_zone": "projets,financements,femmes", "niveau_zone": 1})
    assert r.status_code == 200
    Projet.objects.filter(id=local.id).update(statut="CLOTURE")
    filtre = {z["nom"]: z for z in client.get("/api/v1/carte/synthese/", {"pays": "ZZ", "niveau": 1, "statuts": "CLOTURE"}).data["zones"]}
    assert filtre["Nord"]["projets"] == 1 and filtre["Nord"]["valeurs"]["projets_clotures"] == 1
    carte = client.get("/api/v1/beneficiaires/carte/", {"statuts": "EN_PREPARATION"}).data
    assert carte["total"] == 0 and carte["projets_retenus"] == [regional.id]
    assert client.get("/api/v1/beneficiaires/carte/", {"statuts": "CLOTURE"}).data["total"] == 1
