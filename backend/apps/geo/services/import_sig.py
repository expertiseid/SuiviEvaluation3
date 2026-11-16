"""
Import d'une couche SIG pour la carte des bénéficiaires : shapefile (archive .zip avec .shp,
.shx, .dbf et .prj), GeoPackage (.gpkg), GeoJSON ou KML. La projection est lue dans le
fichier et la couche reprojetée en WGS 84 ; les géométries sont simplifiées et seuls quelques
attributs sont gardés, pour un affichage rapide.

Un fichier à plusieurs couches (GeoPackage surtout) donne une couche importée par couche du
fichier, chacune lue, reprojetée et contrôlée séparément ; les tables sans géométrie sont ignorées.
"""
import json
import os
import re
import tempfile
import zipfile

EXTENSIONS = (".shp", ".gpkg", ".geojson", ".json", ".kml")
MAX_OBJETS = 20000
MAX_COLONNES = 8
# Couleurs des couches suivantes d'un fichier à plusieurs couches (mêmes que la fenêtre d'import).
COULEURS = ("#7048e8", "#e8590c", "#1c7ed6", "#c2255c", "#2f9e44", "#f08c00", "#0c8599", "#495057")
# Colonnes reconnues comme nom des objets (écrit sur la carte).
NOMS = ("nom", "name", "libelle", "label", "nom_com", "nom_prov", "nom_reg", "nom_vill", "localite", "village", "commune", "intitule", "designation")


TECHNIQUES = re.compile(r"(?i)^(objectid(_\d+)?|fid|ogc_fid|shape_(leng|le_\d+|area|length)|shape_le_\d+|gid)$")


class ImportSigImpossible(Exception):
    pass


class CoucheVide(ImportSigImpossible):
    """Couche sans objet : ignorée dans un fichier à plusieurs couches."""


def _colonne_des_noms(gdf, attributs) -> str:
    """Attribut qui nomme les objets : nom connu, sinon « nom… »/« name… », sinon texte presque unique."""
    from pandas.api.types import is_string_dtype

    texte = [c for c in attributs if is_string_dtype(gdf[c]) or gdf[c].dtype == object]
    connu = next((c for c in texte if c.lower() in NOMS), None)
    if connu:
        return connu
    candidats = [c for c in texte if c.lower().startswith(("nom", "name", "lib"))] or texte
    candidats = [c for c in candidats if gdf[c].nunique() > len(gdf) / 2]
    return max(candidats, key=lambda c: gdf[c].nunique(), default="")


def _fichier_geo(dossier, fichier):
    """Chemin du fichier lisible : le fichier lui-même, ou le premier trouvé dans l'archive."""
    nom = fichier.name.lower()
    chemin = os.path.join(dossier, os.path.basename(fichier.name) or "couche")
    with open(chemin, "wb") as sortie:
        for morceau in fichier.chunks():
            sortie.write(morceau)
    if nom.endswith(".zip"):
        try:
            with zipfile.ZipFile(chemin) as archive:
                for membre in archive.infolist():
                    base = os.path.basename(membre.filename)
                    if base and not base.startswith(".") and "__MACOSX" not in membre.filename:
                        with open(os.path.join(dossier, base), "wb") as extrait:
                            extrait.write(archive.read(membre))
        except zipfile.BadZipFile:
            raise ImportSigImpossible("Archive .zip illisible.")
        trouves = sorted(f for f in os.listdir(dossier) if f.lower().endswith(EXTENSIONS) and not f.lower().endswith(".zip"))
        shp = [f for f in trouves if f.lower().endswith(".shp")]
        if not (shp or trouves):
            raise ImportSigImpossible("L'archive ne contient ni .shp, ni .gpkg, ni .geojson.")
        return os.path.join(dossier, (shp or trouves)[0])
    if nom.endswith(EXTENSIONS):
        if nom.endswith(".shp"):
            raise ImportSigImpossible("Un shapefile se compose de plusieurs fichiers : envoyez-les ensemble dans une archive .zip.")
        return chemin
    raise ImportSigImpossible("Format non reconnu : .zip (shapefile), .gpkg, .geojson ou .kml.")


def _famille(types) -> str:
    if all(t in ("Point", "MultiPoint") for t in types):
        return "POINT"
    if all(t in ("LineString", "MultiLineString") for t in types):
        return "LIGNE"
    if all(t in ("Polygon", "MultiPolygon") for t in types):
        return "POLYGONE"
    raise ImportSigImpossible("La couche mélange points, lignes et polygones : importez-les séparément.")


def couleurs(premiere, nombre) -> list:
    """La couleur choisie pour la première couche, puis celles de la palette, sans la répéter."""
    suite = [c for c in COULEURS if c.lower() != (premiere or "").lower()]
    return [premiere] + [suite[i % len(suite)] for i in range(nombre - 1)]


def _couches_geographiques(chemin) -> list:
    """Noms des couches avec géométrie du fichier ([None] : une seule couche, lue sans la nommer)."""
    if chemin.lower().endswith(".shp"):
        return [None]
    import pyogrio

    try:
        couches = pyogrio.list_layers(chemin)
    except Exception as exc:
        raise ImportSigImpossible(f"Fichier illisible ({exc}).")
    noms = [str(nom) for nom, geometrie in couches if geometrie is not None]
    if not noms:
        raise ImportSigImpossible("Le fichier ne contient aucune couche géographique.")
    return noms if len(noms) > 1 else [None]


def _lire(chemin, couche):
    import geopandas as gpd

    options = {"layer": couche} if couche else {}
    try:
        return gpd.read_file(chemin, encoding="utf-8", **options) if chemin.lower().endswith(".shp") else gpd.read_file(chemin, **options)
    except UnicodeDecodeError:
        return gpd.read_file(chemin, encoding="latin-1", **options)
    except Exception as exc:
        raise ImportSigImpossible(f"Fichier illisible ({exc}).")


def lire_couches(fichier) -> tuple:
    """
    Lit chaque couche géographique du fichier : ([(nom de la couche ou None, données à enregistrer)],
    [couches ignorées]). None : fichier à une seule couche. Une couche sans objet (géométries toutes
    vides) d'un fichier qui en a plusieurs est ignorée, et signalée.
    """
    with tempfile.TemporaryDirectory() as dossier:
        chemin = _fichier_geo(dossier, fichier)
        noms = _couches_geographiques(chemin)
        lus = [(nom, _lire(chemin, nom)) for nom in noms]
    couches, ignorees = [], []
    for nom, gdf in lus:
        try:
            couches.append((nom, _preparer(gdf)))
        except CoucheVide:
            if nom is None:
                raise
            ignorees.append(nom)
        except ImportSigImpossible as exc:
            raise ImportSigImpossible(f"Couche « {nom} » : {exc}" if nom else str(exc))
    if not couches:
        raise ImportSigImpossible("Les couches du fichier ne contiennent aucun objet géographique.")
    return couches, ignorees


def _preparer(gdf) -> dict:
    """Reprojette (selon la projection propre à la couche), simplifie et réduit les attributs."""
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if gdf.empty:
        raise CoucheVide("La couche ne contient aucun objet géographique.")
    if len(gdf) > MAX_OBJETS:
        raise ImportSigImpossible(f"Couche trop volumineuse ({len(gdf)} objets, {MAX_OBJETS} au plus).")
    projection = gdf.crs.name if gdf.crs is not None else ""
    if gdf.crs is None:
        ouest, sud, est, nord = gdf.total_bounds
        if not (-180 <= ouest <= est <= 180 and -90 <= sud <= nord <= 90):
            raise ImportSigImpossible("Projection inconnue (fichier .prj absent) : ajoutez le .prj dans l'archive.")
        gdf = gdf.set_crs(4326)
        projection = "WGS 84 (supposée : pas de fichier .prj)"
    gdf = gdf.to_crs(4326)
    famille = _famille(set(gdf.geom_type))

    # Simplification à ~1/2000 de l'emprise (invisible à l'écran), sauf pour les points.
    ouest, sud, est, nord = (float(x) for x in gdf.total_bounds)
    if famille != "POINT":
        gdf["geometry"] = gdf.geometry.simplify(max(est - ouest, nord - sud) / 2000, preserve_topology=True).make_valid()
        gdf = gdf[~gdf.geometry.is_empty]

    # Attributs utiles (sans les colonnes techniques des logiciels SIG).
    attributs = [c for c in gdf.columns if c != "geometry" and not TECHNIQUES.match(c)]
    etiquette = _colonne_des_noms(gdf, attributs)
    gardees = ([etiquette] if etiquette else []) + [c for c in attributs if c != etiquette][: MAX_COLONNES - bool(etiquette)]
    gdf = gdf[gardees + ["geometry"]]
    for colonne in gardees:  # dates, décimaux… : texte, pour le JSON
        gdf[colonne] = gdf[colonne].map(lambda v: None if v is None or v != v else (v if isinstance(v, (int, float, str, bool)) else str(v)))
    geojson = json.loads(gdf.to_json(drop_id=True, to_wgs84=False))
    for feature in geojson["features"]:  # coordonnées arrondies (~1 m)
        feature["geometry"] = _arrondir(feature["geometry"])
    return {
        "geometrie": famille, "projection_source": projection, "colonnes": gardees, "champ_etiquette": etiquette,
        "nombre_objets": len(geojson["features"]), "emprise": [round(ouest, 5), round(sud, 5), round(est, 5), round(nord, 5)],
        "geojson": geojson,
    }


def _arrondir(geometrie):
    def arrondir(c):
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
            return [round(c[0], 5), round(c[1], 5)]
        return [arrondir(x) for x in c]

    return {"type": geometrie["type"], "coordinates": arrondir(geometrie["coordinates"])}
