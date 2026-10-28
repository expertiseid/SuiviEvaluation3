"""
Import d'une base topographique nationale au format shapefile (BNDT de l'IGB pour le Burkina
Faso, en WGS84) pour la carte des bénéficiaires : régions, provinces, communes (à la place de
geoBoundaries, car à jour du découpage de 2025), réseau routier et localités nommées.

Les contours sont simplifiés (Douglas-Peucker) et les coordonnées arrondies pour rester légers
à afficher ; les localités vont dans une table (Localite), servie par zone visible.
"""
import os
import tempfile
import zipfile

# Fichiers attendus (nom sans extension, sans tenir compte de la casse) → contenu.
NIVEAUX = {
    1: {"fichier": "adm_region", "nom": "Nom_decret", "parent": None, "libelle": "Région", "tolerance": 0.002},
    2: {"fichier": "adm_province", "nom": "Nom_decret", "parent": "Nom_Region", "libelle": "Province", "tolerance": 0.0015},
    3: {"fichier": "adm_commune", "nom": "Nom_depart", "parent": "Province", "libelle": "Commune", "tolerance": 0.001},
}
FICHIER_ROUTES = "rro_route"
FICHIER_LOCALITES = "hab_localite"
STATUTS_LOCALITES = {"VILLE", "VILLAGE_ADMIN", "VILLAGE"}  # sans l'habitat dispersé, non nommé
SOURCE = "BNDT (IGB)"


class ImportImpossible(Exception):
    pass


def texte(valeur):
    """Les .dbf mêlent UTF-8 et Windows-1252 : lus en latin-1, puis redécodés au mieux."""
    if not isinstance(valeur, str):
        return valeur
    brut = valeur.encode("latin-1")
    try:
        return brut.decode("utf-8").strip()
    except UnicodeDecodeError:
        return brut.decode("cp1252", errors="replace").strip()


def joli_nom(nom: str) -> str:
    """« KOULSÉ » → « Koulsé », « BOBO-DIOULASSO » → « Bobo-Dioulasso » (noms saisis en capitales)."""
    return nom.title() if nom.isupper() else nom


def simplifier(points, tolerance):
    """Douglas-Peucker (itératif) sur une liste de [lng, lat]."""
    n = len(points)
    if n < 3:
        return points
    garder = [False] * n
    garder[0] = garder[-1] = True
    pile = [(0, n - 1)]
    while pile:
        debut, fin = pile.pop()
        (x1, y1), (x2, y2) = points[debut][:2], points[fin][:2]
        dx, dy = x2 - x1, y2 - y1
        longueur2 = dx * dx + dy * dy
        pire, indice = 0.0, None
        for i in range(debut + 1, fin):
            px, py = points[i][:2]
            if longueur2 == 0:
                d2 = (px - x1) ** 2 + (py - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / longueur2))
                d2 = (px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2
            if d2 > pire:
                pire, indice = d2, i
        if indice is not None and pire > tolerance * tolerance:
            garder[indice] = True
            pile += [(debut, indice), (indice, fin)]
    return [points[i] for i in range(n) if garder[i]]


def _arrondir(points):
    return [[round(p[0], 5), round(p[1], 5)] for p in points]


def geometrie_simplifiee(geometrie, tolerance):
    """Polygone, multipolygone, ligne ou multiligne simplifié ; None s'il ne reste rien."""
    genre, coordonnees = geometrie["type"], geometrie["coordinates"]
    if genre in ("Polygon", "MultiPolygon"):
        polygones = [coordonnees] if genre == "Polygon" else coordonnees
        resultat = []
        for polygone in polygones:
            anneaux = [_arrondir(simplifier(list(a), tolerance)) for a in polygone]
            anneaux = [a for a in anneaux if len(a) >= 4]
            if anneaux:
                resultat.append(anneaux)
        if not resultat:
            return None
        return {"type": "Polygon", "coordinates": resultat[0]} if len(resultat) == 1 else {"type": "MultiPolygon", "coordinates": resultat}
    if genre in ("LineString", "MultiLineString"):
        lignes = [coordonnees] if genre == "LineString" else coordonnees
        lignes = [_arrondir(simplifier(list(l), tolerance)) for l in lignes]
        lignes = [l for l in lignes if len(l) >= 2]
        if not lignes:
            return None
        return {"type": "LineString", "coordinates": lignes[0]} if len(lignes) == 1 else {"type": "MultiLineString", "coordinates": lignes}
    return None


def point_etiquette(geometrie):
    """Où écrire le nom d'une zone : le centre de son plus grand polygone s'il est dedans, sinon un point intérieur."""
    from .limites import _dans_polygone

    polygones = [geometrie["coordinates"]] if geometrie["type"] == "Polygon" else geometrie["coordinates"]
    anneau = max((p[0] for p in polygones), key=len)
    lngs, lats = [p[0] for p in anneau], [p[1] for p in anneau]
    lat, lng = (min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2
    if _dans_polygone(lat, lng, {"type": "Polygon", "coordinates": [anneau]}):
        return round(lat, 5), round(lng, 5)
    # Sinon, sur l'horizontale du centre : milieu du plus long segment intérieur.
    croisements = sorted(
        x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
        for (x1, y1), (x2, y2) in zip(anneau, anneau[1:])
        if (y1 > lat) != (y2 > lat)
    )
    segments = list(zip(croisements[::2], croisements[1::2]))
    if segments:
        gauche, droite = max(segments, key=lambda s: s[1] - s[0])
        return round(lat, 5), round((gauche + droite) / 2, 5)
    return round(anneau[0][1], 5), round(anneau[0][0], 5)


def _lire(chemin):
    """(géométrie GeoJSON, attributs) de chaque objet d'un shapefile."""
    import shapefile

    with shapefile.Reader(chemin, encoding="latin-1") as lecteur:
        for objet in lecteur.iterShapeRecords():
            if objet.shape.shapeType == shapefile.NULL:
                continue
            yield objet.shape.__geo_interface__, {k: texte(v) for k, v in objet.record.as_dict().items()}


def _trouver(dossier):
    """{nom de fichier en minuscules sans extension: chemin sans extension} des .shp du dossier."""
    trouves = {}
    for racine, _, fichiers in os.walk(dossier):
        for fichier in fichiers:
            base, extension = os.path.splitext(fichier)
            if extension.lower() == ".shp":
                trouves[base.lower()] = os.path.join(racine, base)
    return trouves


def _extraire(archive, dossier):
    """Extrait d'un .zip les seuls fichiers utiles (les noms accentués de l'archive sont ignorés)."""
    utiles = {n["fichier"] for n in NIVEAUX.values()} | {FICHIER_ROUTES, FICHIER_LOCALITES}
    with zipfile.ZipFile(archive) as zip_:
        for membre in zip_.infolist():
            base, extension = os.path.splitext(os.path.basename(membre.filename))
            if base.lower() in utiles and extension.lower() in (".shp", ".shx", ".dbf"):
                with open(os.path.join(dossier, base.lower() + extension.lower()), "wb") as sortie:
                    sortie.write(zip_.read(membre))


def importer_limites(fichiers, pays, niveau) -> int:
    from ..models import LimiteAdministrative

    config = NIVEAUX[niveau]
    features = []
    for geometrie, attributs in _lire(fichiers[config["fichier"]]):
        nom = joli_nom(attributs.get(config["nom"]) or "")
        geometrie = geometrie_simplifiee(geometrie, config["tolerance"])
        if not nom or geometrie is None or geometrie["type"] not in ("Polygon", "MultiPolygon"):
            continue
        lat, lng = point_etiquette(geometrie)
        proprietes = {"shapeName": nom, "lat": lat, "lng": lng}
        if config["parent"]:
            proprietes["parent"] = joli_nom(attributs.get(config["parent"]) or "")
        features.append({"type": "Feature", "properties": proprietes, "geometry": geometrie})
    LimiteAdministrative.objects.update_or_create(
        pays=pays,
        niveau=niveau,
        defaults={
            "nom_niveau": config["libelle"],
            "annee": "",
            "source": SOURCE,
            "geojson": {"type": "FeatureCollection", "features": features},
        },
    )
    return len(features)


def importer_routes(chemin, pays) -> int:
    from ..models import CoucheCarte

    features = []
    for geometrie, attributs in _lire(chemin):
        geometrie = geometrie_simplifiee(geometrie, 0.0008)
        if geometrie is None or geometrie["type"] not in ("LineString", "MultiLineString"):
            continue
        proprietes = {"nom": attributs.get("Nom") or "", "classe": (attributs.get("Cl_admin") or "").upper(), "revetue": bool(attributs.get("Revetement"))}
        features.append({"type": "Feature", "properties": proprietes, "geometry": geometrie})
    CoucheCarte.objects.update_or_create(
        pays=pays, cle="routes",
        defaults={"libelle": "Routes", "source": SOURCE, "geojson": {"type": "FeatureCollection", "features": features}},
    )
    return len(features)


def importer_localites(chemin, pays) -> int:
    from ..models import Localite

    localites = []
    for geometrie, attributs in _lire(chemin):
        nom, statut = attributs.get("Nom") or "", (attributs.get("Statut") or "").upper()
        if not nom or statut not in STATUTS_LOCALITES or geometrie["type"] != "Point":
            continue
        lng, lat = geometrie["coordinates"][:2]
        localites.append(Localite(
            pays=pays, nom=joli_nom(nom)[:150], statut=statut,
            commune=joli_nom(attributs.get("Nom_admin") or "")[:150],
            latitude=round(lat, 6), longitude=round(lng, 6),
        ))
    Localite.objects.filter(pays=pays).delete()
    Localite.objects.bulk_create(localites, batch_size=2000)
    return len(localites)


def importer(source, pays="BF", recalculer=False, journal=print) -> dict:
    """
    Importe un dossier ou une archive .zip de shapefiles, puis replace les zones du pays.
    `recalculer` : efface d'abord les positions des zones (sinon seules les zones sans position
    sont placées).
    """
    from django.db import transaction

    from ..models import Zone
    from .limites import completer_par_les_enfants, placer_zones

    pays = pays.upper()
    with tempfile.TemporaryDirectory() as temporaire:
        if os.path.isfile(source) and zipfile.is_zipfile(source):
            _extraire(source, temporaire)
            dossier = temporaire
        elif os.path.isdir(source):
            dossier = source
        else:
            raise ImportImpossible(f"{source} n'est ni un dossier ni une archive .zip.")
        fichiers = _trouver(dossier)
        manquants = [n["fichier"] for n in NIVEAUX.values() if n["fichier"] not in fichiers]
        if manquants:
            raise ImportImpossible(f"Fichiers introuvables : {', '.join(m + '.shp' for m in manquants)}.")

        resultat = {}
        with transaction.atomic():
            for niveau, config in NIVEAUX.items():
                resultat[config["libelle"]] = importer_limites(fichiers, pays, niveau)
                journal(f"{config['libelle']} : {resultat[config['libelle']]} contours.")
            if FICHIER_ROUTES in fichiers:
                resultat["Routes"] = importer_routes(fichiers[FICHIER_ROUTES], pays)
                journal(f"Routes : {resultat['Routes']} tronçons.")
            if FICHIER_LOCALITES in fichiers:
                resultat["Localités"] = importer_localites(fichiers[FICHIER_LOCALITES], pays)
                journal(f"Localités : {resultat['Localités']} villes et villages.")

            from ..models import LimiteAdministrative

            if recalculer:
                Zone.objects.filter(niveau_administratif__pays=pays).update(latitude=None, longitude=None)
            places = sum(placer_zones(limite) for limite in LimiteAdministrative.objects.filter(pays=pays).order_by("niveau"))
            resultat["zones placées"] = places + completer_par_les_enfants(pays)
    return resultat
