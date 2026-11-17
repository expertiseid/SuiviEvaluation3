"""
Surfaces et longueurs des couches importées, mesurées sur l'ellipsoïde WGS 84 (exactes quelle que
soit la latitude, sans choisir de projection) : hectares pour les polygones, kilomètres pour les lignes.
"""
from pyproj import Geod

GEOD = Geod(ellps="WGS84")


def mesurer(geometries, famille) -> dict:
    """Géométries shapely en WGS 84 → {"surface_ha", "longueur_km"} (None quand sans objet)."""
    if famille == "POLYGONE":
        surface = sum(abs(GEOD.geometry_area_perimeter(g)[0]) for g in geometries if g is not None and not g.is_empty)
        return {"surface_ha": round(surface / 10_000, 2), "longueur_km": None}
    if famille == "LIGNE":
        longueur = sum(GEOD.geometry_length(g) for g in geometries if g is not None and not g.is_empty)
        return {"surface_ha": None, "longueur_km": round(longueur / 1000, 3)}
    return {"surface_ha": None, "longueur_km": None}


def mesurer_geojson(geojson, famille) -> dict:
    from shapely.geometry import shape

    return mesurer([shape(f["geometry"]) for f in geojson.get("features", []) if f.get("geometry")], famille)
