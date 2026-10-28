"""
Limites administratives (carte des bénéficiaires) : contours téléchargés depuis geoBoundaries
(www.geoboundaries.org, données ouvertes, version simplifiée), gardés en cache
(LimiteAdministrative), puis utilisés pour placer chaque zone de la plateforme (son centre) en
rapprochant les noms, niveau par niveau (niveau 1 de la source = premier niveau du pays…).

Les découpages récents (ex. les 17 régions du Burkina Faso depuis 2025) peuvent ne pas encore
figurer dans la source : les zones non retrouvées restent sans position, et leurs bénéficiaires
sont placés sur la zone parente ou enfant la plus proche qui en a une (voir apps.beneficiaries).
"""
import json
import unicodedata
import urllib.request
from decimal import Decimal

from ..iso3 import ISO3

API = "https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM{niveau}/"


class LimitesIndisponibles(Exception):
    pass


def _lire_json(url, delai=30):
    requete = urllib.request.Request(url, headers={"User-Agent": "plateforme-suivi-evaluation"})
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def normaliser_nom(nom: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("-", " ").replace("'", " ").split())


def _points(geometrie):
    """Tous les sommets d'un polygone ou multipolygone."""
    coordonnees = geometrie.get("coordinates") or []
    anneaux = coordonnees if geometrie.get("type") == "Polygon" else [a for p in coordonnees for a in p]
    return [point for anneau in anneaux for point in anneau]


def centre(geometrie):
    """Centre approché (milieu du rectangle englobant) : (latitude, longitude)."""
    points = _points(geometrie)
    if not points:
        return None
    longitudes = [p[0] for p in points]
    latitudes = [p[1] for p in points]
    return (min(latitudes) + max(latitudes)) / 2, (min(longitudes) + max(longitudes)) / 2


def telecharger(pays: str, niveau: int):
    """Télécharge (ou renvoie du cache) les contours d'un niveau ; LimitesIndisponibles sinon."""
    from ..models import LimiteAdministrative

    existante = LimiteAdministrative.objects.filter(pays=pays, niveau=niveau).first()
    if existante:
        return existante
    iso3 = ISO3.get(pays.upper())
    if not iso3:
        raise LimitesIndisponibles(f"Pays inconnu : {pays}.")
    try:
        meta = _lire_json(API.format(iso3=iso3, niveau=niveau))
        geojson = _lire_json(meta["simplifiedGeometryGeoJSON"], delai=90)
    except Exception as exc:  # pas d'accès Internet, niveau absent de la source…
        raise LimitesIndisponibles(f"Limites de niveau {niveau} indisponibles pour {pays} ({exc}).")
    return LimiteAdministrative.objects.create(
        pays=pays.upper(),
        niveau=niveau,
        nom_niveau=meta.get("boundaryCanonical", ""),
        annee=str(meta.get("boundaryYearRepresented", "")),
        source=meta.get("simplifiedGeometryGeoJSON", ""),
        geojson=geojson,
    )


def _nom_approche(nom, centres):
    """Orthographe voisine (« Kourittenga » / « Kouritenga ») : le nom le plus proche, s'il l'est assez."""
    from difflib import SequenceMatcher

    meilleur, score = None, 0.0
    for candidat, position in centres.items():
        ratio = SequenceMatcher(None, nom, candidat).ratio()
        if ratio > score:
            meilleur, score = position, ratio
    return meilleur if score >= 0.85 else None


def completer_par_les_enfants(pays) -> int:
    """
    Zones restées sans position (ex. régions créées après la source) : centre moyen de leurs
    zones enfants placées, en remontant niveau par niveau.
    """
    from ..models import Zone

    completees = 0
    for ordre in sorted(set(Zone.objects.filter(niveau_administratif__pays=pays).values_list("niveau_administratif__ordre", flat=True)), reverse=True):
        for zone in Zone.objects.filter(niveau_administratif__pays=pays, niveau_administratif__ordre=ordre, latitude__isnull=True):
            enfants = list(zone.enfants.filter(latitude__isnull=False).values_list("latitude", "longitude"))
            if enfants:
                zone.latitude = Decimal(str(round(sum(float(e[0]) for e in enfants) / len(enfants), 6)))
                zone.longitude = Decimal(str(round(sum(float(e[1]) for e in enfants) / len(enfants), 6)))
                zone.save(update_fields=["latitude", "longitude"])
                completees += 1
    return completees


def _dans_polygone(lat, lng, geometrie) -> bool:
    """Le point est-il dans le polygone (ou un des polygones) ? Lancer de rayon sur l'anneau extérieur."""
    coordonnees = geometrie.get("coordinates") or []
    polygones = [coordonnees] if geometrie.get("type") == "Polygon" else coordonnees
    for polygone in polygones:
        anneau = polygone[0] if polygone else []
        dedans = False
        for (x1, y1), (x2, y2) in zip(anneau, anneau[1:] + anneau[:1]):
            if (y1 > lat) != (y2 > lat) and lng < (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1:
                dedans = not dedans
        if dedans:
            return True
    return False


def _geometries(pays, niveau):
    """{nom normalisé: géométrie} d'un niveau déjà chargé (vide sinon)."""
    from ..models import LimiteAdministrative

    limite = LimiteAdministrative.objects.filter(pays=pays, niveau=niveau).first()
    if limite is None:
        return {}
    return {
        normaliser_nom((f.get("properties") or {}).get("shapeName", "")): f.get("geometry") or {}
        for f in limite.geojson.get("features", [])
    }


def _coherente(zone, position, geometries_parents) -> bool:
    """
    La position trouvée par le nom est-elle plausible ? Elle doit tomber dans le contour de la
    zone parente (ou à moins de ~150 km de son centre si ce contour est inconnu) : certaines
    sources associent des noms à de mauvais contours.
    """
    parent = zone.parent
    if parent is None:
        return True
    geometrie = geometries_parents.get(normaliser_nom(parent.nom))
    if geometrie:
        return _dans_polygone(position[0], position[1], geometrie)
    if parent.latitude is not None:
        return abs(float(parent.latitude) - position[0]) < 1.4 and abs(float(parent.longitude) - position[1]) < 1.4
    return True


def placer_zones(limite) -> int:
    """Centre des zones du niveau correspondant, retrouvées par leur nom ; renvoie le nombre placé."""
    from ..models import Zone

    centres = {}
    for feature in limite.geojson.get("features", []):
        nom = (feature.get("properties") or {}).get("shapeName", "")
        position = centre(feature.get("geometry") or {})
        if nom and position:
            centres[normaliser_nom(nom)] = position
    geometries_parents = _geometries(limite.pays, limite.niveau - 1)
    places = 0
    zones = Zone.objects.filter(niveau_administratif__pays=limite.pays, niveau_administratif__ordre=limite.niveau)
    for zone in zones.select_related("parent"):
        position = centres.get(normaliser_nom(zone.nom)) or _nom_approche(normaliser_nom(zone.nom), centres)
        if position and not _coherente(zone, position, geometries_parents):
            position = None
        if position and (zone.latitude is None or zone.longitude is None):
            zone.latitude, zone.longitude = (Decimal(str(round(x, 6))) for x in position)
            zone.save(update_fields=["latitude", "longitude"])
            places += 1
    return places


def charger_pays(pays: str, niveaux=(1, 2, 3), recalculer=False) -> dict:
    """
    Télécharge les niveaux demandés et place les zones ; {niveau: nombre placé ou message}.
    `recalculer` : efface d'abord les positions des zones du pays (y compris saisies à la main).
    """
    from ..models import Zone

    if recalculer:
        Zone.objects.filter(niveau_administratif__pays=pays).update(latitude=None, longitude=None)
    resultat = {}
    for niveau in niveaux:
        try:
            resultat[niveau] = placer_zones(telecharger(pays, niveau))
        except LimitesIndisponibles as exc:
            resultat[niveau] = str(exc)
    resultat["completees"] = completer_par_les_enfants(pays)
    return resultat
