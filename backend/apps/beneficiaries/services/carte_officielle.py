"""
Carte imprimable des bénéficiaires (PDF vectoriel ou PNG), aux formats A0, A1, A3 et A4, sur le
modèle des cartes officielles de la plateforme HIMO : bandeau titre, carte à l'échelle avec
grille de coordonnées, barre d'échelle et nord, panneau (situation, chiffres clés, légende,
tableau des localités) et cartouche (source, projection, édition).

La mise en page est conçue en A0 (841 × 1189 mm) puis mise à l'échelle : tous les formats ont la
même présentation ; l'échelle (1:xxx) est calculée sur la taille réelle de la feuille.
"""
import io
import os
import textwrap
from datetime import datetime

from apps.core.langues import traduire, traduire_figure, traduire_modele
from apps.geo.services.synthese import COURTS

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

PAPIERS = {"A0": (841, 1189), "A1": (594, 841), "A3": (297, 420), "A4": (210, 297)}  # mm (petit, grand côté)
DPI_PNG = {"A0": 150, "A1": 150, "A3": 200, "A4": 200}
ECHELLES = [25, 50, 60, 75, 80, 100, 120, 125, 150, 175, 200, 250, 300, 400, 500, 750, 1000, 1250, 1500, 1750, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000, 7500, 10000]  # milliers
COUCHES = ("points", "regions", "provinces", "communes", "routes", "villages", "noms", "beneficiaires")
# Fonds de carte (tuiles), comme à l'écran ; « aucun » : fond clair uni.
FONDS = {
    "neutre": ("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", "© Esri"),
    # Les serveurs d'OpenStreetMap interdisent le téléchargement de tuiles par une application
    # pour produire des cartes (ils renvoient des tuiles « Access blocked ») : à l'impression, le
    # fond « OpenStreetMap » est la carte routière d'Esri, de même usage et autorisée.
    "osm": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            "Esri World Street Map (© Esri, HERE, Garmin, contributeurs OpenStreetMap)"),
    "satellite": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "Imagerie © Esri, Maxar, Earthstar Geographics"),
    "aucun": None,
}

BLEU = "#0b4f3c"  # vert foncé de la plateforme
C_GPS = "#c2410c"
C_ZONE = "#12b886"
STYLE_ROUTES = {"DEPARTEMENTALE": ("#ca8a04", 1.2, (0, (3, 2)), "Route départementale"),
                "REGIONALE": ("#ea580c", 1.8, "-", "Route régionale"),
                "NATIONALE": ("#dc2626", 2.8, "-", "Route nationale")}


# Carte par zone : mêmes dégradés et classes qu'à l'écran (frontend utils/carteParZone.ts), par
# famille d'indicateurs (catalogue apps.geo.services.synthese).
DEGRADES = {
    "projets": ["#dbeafe", "#93c5fd", "#3b82f6", "#1d4ed8", "#1e3a8a"],
    "beneficiaires": ["#d1fae5", "#6ee7b7", "#10b981", "#047857", "#064e3b"],
    "budget": ["#fef3c7", "#fcd34d", "#f59e0b", "#b45309", "#78350f"],
    "taux": ["#fee2e2", "#fdba74", "#fde047", "#86efac", "#16a34a"],
}
SANS_DONNEE = "#f1f3f5"


def _type(indicateur):
    """Type de valeur de l'indicateur : entier, montant ou pourcentage."""
    from apps.geo.services.synthese import TYPES

    return TYPES.get(indicateur, "entier")


def degrade(indicateur):
    """Les 5 couleurs (du plus faible au plus fort) de la famille de l'indicateur."""
    from apps.geo.services.synthese import FAMILLES

    return DEGRADES[FAMILLES.get(indicateur, "projets")]


def valeur_de(z, indicateur):
    """Valeur d'un indicateur pour une zone de la synthèse."""
    return (z.get("valeurs") or {}).get(indicateur, z.get(indicateur))


def classes_zone(indicateur, zones):
    """Bornes des 5 classes : seuils fixes pour les taux, sinon classes égales jusqu'au maximum."""
    if _type(indicateur) == "pourcentage":
        return [20, 40, 60, 80]
    maximum = max([valeur_de(z, indicateur) or 0 for z in zones] or [0])
    if maximum <= 0:
        return [1, 2, 3, 4]
    bornes = [maximum * k / 5 for k in (1, 2, 3, 4)]
    if _type(indicateur) == "entier":
        import math

        return [max(math.ceil(b), i + 2) for i, b in enumerate(bornes)]
    return bornes


def couleur_zone(indicateur, valeur, bornes):
    """Couleur de la classe d'une valeur (gris sans donnée)."""
    if valeur is None or (_type(indicateur) != "pourcentage" and valeur <= 0):
        return SANS_DONNEE
    i = next((i for i, b in enumerate(bornes) if valeur < b), 4)
    return degrade(indicateur)[i]


def valeur_zone(indicateur, v):
    """Valeur écrite sur la carte : « 45,2 % », « 2,38 Md », « 1 250 »."""
    if v is None:
        return "—"
    if _type(indicateur) == "pourcentage":
        return f"{v:.1f} %".replace(".", ",")
    if _type(indicateur) == "montant":
        return f"{v / 1e9:.2f} Md".replace(".", ",") if v >= 1e9 else (f"{v / 1e6:.1f} M".replace(".", ",") if v >= 1e6 else fr(v))
    return fr(v)


# En-têtes du tableau par zone, plus courts que les libellés courts quand la place manque.
ENTETES_COURTES = {"beneficiaires": "Bénéf."}


def lignes_valeurs(z, indicateurs):
    """Valeurs écrites sur une zone : la valeur seule, ou « libellé court : valeur » s'il y en a plusieurs."""
    if len(indicateurs) == 1:
        return [valeur_zone(indicateurs[0], valeur_de(z, indicateurs[0]))]
    return [f"{traduire(COURTS[i])} : {valeur_zone(i, valeur_de(z, i))}" for i in indicateurs]


def libelles_classes(indicateur, bornes):
    if _type(indicateur) == "entier":
        return ([("1" if bornes[0] - 1 <= 1 else f"1 – {bornes[0] - 1}")]
                + [(f"{b} – {bornes[i + 1] - 1}" if bornes[i + 1] - 1 > b else f"{b}") for i, b in enumerate(bornes[:3])]
                + [f"{bornes[3]} et plus"])
    return ([f"< {valeur_zone(indicateur, bornes[0])}"]
            + [f"{valeur_zone(indicateur, b)} – {valeur_zone(indicateur, bornes[i + 1])}" for i, b in enumerate(bornes[:3])]
            + [f"≥ {valeur_zone(indicateur, bornes[3])}"])


def fr(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def dms(v, pos, neg):
    s, v = (pos if v >= 0 else neg), abs(v)
    deg, mn = int(v), int(round((v - int(v)) * 60))
    if mn == 60:
        deg, mn = deg + 1, 0
    return f"{deg}°{mn:02d}' {s}"


def tronc(s, n):
    s = s or "—"
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


class Placeur:
    """Pose des textes sans chevauchement (repris de la plateforme HIMO)."""

    def __init__(self, fig, ax):
        self.ax = ax
        self.r = fig.canvas.get_renderer()
        self.boites = []
        self.cadre = ax.get_window_extent(self.r)

    def essayer(self, x, y, txt, force=False, **kw):
        t = self.ax.text(x, y, txt, **kw)
        bb = t.get_window_extent(self.r).expanded(1.08, 1.2)
        dedans = bb.x0 >= self.cadre.x0 and bb.x1 <= self.cadre.x1 and bb.y0 >= self.cadre.y0 and bb.y1 <= self.cadre.y1
        if dedans and (force or all(not bb.overlaps(b) for b in self.boites)):
            self.boites.append(bb)
            return t
        t.remove()
        return None


def _gdf(features, crs):
    import geopandas as gpd

    if not features:
        return gpd.GeoDataFrame(geometry=[], crs=4326).to_crs(crs)
    gdf = gpd.GeoDataFrame.from_features(features, crs=4326).to_crs(crs)
    # Contours simplifiés : des polygones peuvent se recouper ; on les répare avant les intersections.
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def _epsg_utm(longitude, latitude):
    zone = int((longitude + 180) // 6) + 1
    return (32600 if latitude >= 0 else 32700) + zone


def _mise_en_page(bornes, court, ecart_panneau):
    """Orientation donnant la plus grande échelle (la carte la plus lisible)."""
    import numpy as np

    minx, miny, maxx, maxy = bornes
    ew, eh = maxx - minx, maxy - miny
    k = court / 841
    meilleur = None
    for ori, (w, h) in {"portrait": (841, 1189), "paysage": (1189, 841)}.items():
        cadre = _cadre(w, h, ecart_panneau)
        den = max(ew * 1000 / (cadre[2] * k), eh * 1000 / (cadre[3] * k))
        ech = next((e * 1000 for e in ECHELLES if e * 1000 >= den), int(np.ceil(den / 1e6) * 1e6))
        if meilleur is None or ech < meilleur[0]:
            meilleur = (ech, ori, w, h, cadre)
    return meilleur


def _cadre(w, h, pw):
    marge, hh, fh = 15, 62, 38
    fx, fy = marge + 12, marge + fh + 18
    return fx, fy, w - marge - pw - 10 - fx, h - marge - hh - 12 - fy


def _ajouter_fond(ax, fond, crs, fenetre_ll, largeur_mm):
    """
    Tuiles du fond choisi sous la carte, à un niveau de zoom adapté à la taille imprimée
    (≈ 200 points par pouce en A4/A3, 100 au-delà, 300 tuiles au plus). Renvoie la mention de source, ou None si le fond n'a pas pu être
    téléchargé (la carte reste produite sur fond clair).
    """
    import math

    import contextily

    url, attribution = FONDS[fond]
    ouest, sud, est, nord = fenetre_ll.bounds
    # Petits formats (A4, A3) : tuiles plus fines (peu nombreuses) ; grands formats : 100 points par pouce.
    pixels = largeur_mm / 25.4 * (200 if largeur_mm < 400 else 100)
    zoom = int(math.floor(math.log2(pixels * 360 / (256 * max(est - ouest, 1e-6)))))
    zoom = max(3, min(zoom, 17))
    # Pas plus de ~300 tuiles (A0 très zoomé) : on descend d'un niveau tant qu'il le faut.
    while zoom > 3:
        n = 2 ** zoom
        tuiles_x = (est - ouest) / 360 * n + 1
        y = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
        tuiles_y = abs(y(sud) - y(nord)) + 1
        if tuiles_x * tuiles_y <= 300:
            break
        zoom -= 1
    if not _tuile_valide(url, zoom, (ouest + est) / 2, (sud + nord) / 2):
        return None
    try:
        contextily.add_basemap(ax, crs=f"EPSG:{crs}", source=url, zoom=zoom, attribution=False, reset_extent=True, zorder=0.5)
    except Exception:  # pas d'accès Internet, service indisponible…
        return None
    return attribution


def _tuile_valide(url, zoom, longitude, latitude) -> bool:
    """
    Le service répond-il vraiment ? Une tuile du centre doit arriver en 200 et être une image :
    certains serveurs renvoient sinon une image d'erreur que la carte afficherait telle quelle.
    """
    import math
    import urllib.request

    n = 2 ** zoom
    x = int((longitude + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(latitude)) + 1 / math.cos(math.radians(latitude))) / math.pi) / 2 * n)
    requete = urllib.request.Request(url.format(z=zoom, x=x, y=y), headers={"User-Agent": "plateforme-suivi-evaluation (carte imprimable)"})
    try:
        with urllib.request.urlopen(requete, timeout=15) as reponse:
            return reponse.status == 200 and reponse.headers.get_content_type().startswith("image/")
    except Exception:
        return False


def titre_par_defaut(donnees, couches, par_zone, portee=""):
    """
    Titre et sous-titre selon ce que montre la carte : la carte par zone (« BUDGET PAR
    PROVINCE »), sinon le projet choisi, sinon les bénéficiaires s'ils sont la seule
    information, sinon « carte des interventions ».
    """
    zf = donnees.get("zone_filtre")
    if par_zone:
        # Nom du niveau (donnée) traduit s'il est connu du catalogue (« Région »), comme dans l'interface.
        titre = traduire_modele("{0} par {1}", traduire(par_zone["libelle_court"]), traduire(par_zone["synthese"]["niveau"]["nom"]))
    elif donnees.get("projet"):
        titre = traduire_modele("Projet {0}", donnees["projet"])
    elif couches.get("points") and not couches.get("importees"):
        titre = traduire("Carte des bénéficiaires")
    else:
        titre = traduire("Carte des interventions")
    if portee and not donnees.get("projet"):
        titre += f" — {portee}"
    elements = []
    if donnees.get("projet_nom"):
        elements.append(donnees["projet_nom"])
    if zf:
        elements.append(f"{zf['niveau']} : {zf['nom']}")
    if couches.get("points"):
        elements.append(traduire_modele("{0} bénéficiaire(s)", fr(donnees["total"])))
    if par_zone:
        presents = sum(1 for z in par_zone["synthese"]["zones"] if z["projets"])
        elements.append(traduire_modele("{0} {1}(s) avec au moins un projet", presents, traduire(par_zone["synthese"]["niveau"]["nom"]).lower()))
    elements += [c.nom for c in couches.get("importees", [])][:3]
    return titre.upper(), " · ".join(elements)


def rendre_carte(donnees, couches, papier="A3", orientation="auto", sortie="pdf", titre_portee="", organisation="", fond="aucun", par_zone=None,
                 etendue="pays", titre="", sous_titre=""):
    """
    `donnees` : celles de l'écran (services.carte_donnees) ; `couches` : {nom: True} parmi COUCHES,
    plus `importees` : [CoucheImportee] à dessiner ; `par_zone` : carte par zone facultative
    ({indicateur, libelle, niveau, synthese} : zones colorées et tableau par zone). Renvoie les
    octets du PDF ou du PNG.
    """
    import geopandas as gpd
    import matplotlib
    import matplotlib.patheffects as pe
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Polygon as MPoly
    from matplotlib.patches import Rectangle
    from pyproj import Transformer
    from shapely.geometry import box, shape

    from apps.geo.models import CoucheCarte, LimiteAdministrative, Localite

    matplotlib.rcParams["font.family"] = ["Arial", "Liberation Sans", "DejaVu Sans"]
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["axes.unicode_minus"] = False

    court = PAPIERS[papier][0]
    k = court / 841

    def F(x):
        return x * k

    def LW(x):
        return max(x * k, 0.25)

    pays = donnees["pays"]
    limites = {l.niveau: l for l in LimiteAdministrative.objects.filter(pays=pays, niveau__in=(1, 2, 3))}
    # Emprise : la zone filtrée ; sinon tout le pays, ou les bénéficiaires si demandé (et localisés).
    positions = [(p["lng"], p["lat"]) for p in donnees["points"]] + [(z["lng"], z["lat"]) for z in donnees["zones"]]
    contour = (donnees.get("zone_filtre") or {}).get("contour")
    ordre_pz = par_zone["synthese"]["niveau"]["ordre"] if par_zone else None
    if contour:
        ouest, sud, est, nord = shape(contour).bounds
    elif etendue == "beneficiaires" and positions and not par_zone:
        xs, ys = zip(*positions)
        ouest, sud, est, nord = min(xs), min(ys), max(xs), max(ys)
    elif 1 in limites:
        ouest, sud, est, nord = _gdf(limites[1].geojson["features"], 4326).total_bounds
    elif positions:
        xs, ys = zip(*positions)
        ouest, sud, est, nord = min(xs), min(ys), max(xs), max(ys)
    else:
        raise ValueError("Rien à cartographier : aucun bénéficiaire localisé ni contour.")
    crs = _epsg_utm((ouest + est) / 2, (sud + nord) / 2)
    vers_m = Transformer.from_crs(4326, crs, always_xy=True)
    vers_ll = Transformer.from_crs(crs, 4326, always_xy=True)
    x0, y0 = vers_m.transform(ouest, sud)
    x1, y1 = vers_m.transform(est, nord)
    tampon = max(8000, 0.06 * max(x1 - x0, y1 - y0))
    bornes = (x0 - tampon, y0 - tampon, x1 + tampon, y1 + tampon)

    pw = 275
    ech, ori, W, H, (fx, fy, fw, fh) = _mise_en_page(bornes, court, pw)
    if orientation in ("portrait", "paysage") and orientation != ori:
        ori = orientation
        W, H = (841, 1189) if ori == "portrait" else (1189, 841)
        fx, fy, fw, fh = _cadre(W, H, pw)
        den = max((bornes[2] - bornes[0]) * 1000 / (fw * k), (bornes[3] - bornes[1]) * 1000 / (fh * k))
        ech = next((e * 1000 for e in ECHELLES if e * 1000 >= den), int(np.ceil(den / 1e6) * 1e6))
    marge, hh, fth = 15, 62, 38
    etendue_x, etendue_y = fw * k * ech / 1000, fh * k * ech / 1000
    cx, cy = (bornes[0] + bornes[2]) / 2, (bornes[1] + bornes[3]) / 2
    ext = (cx - etendue_x / 2, cx + etendue_x / 2, cy - etendue_y / 2, cy + etendue_y / 2)
    fenetre = box(ext[0], ext[2], ext[1], ext[3])
    mm = ech / 1000.0
    fenetre_ll = box(*vers_ll.transform(ext[0], ext[2]), *vers_ll.transform(ext[1], ext[3]))

    fig = Figure(figsize=(W * k / 25.4, H * k / 25.4), dpi=72)
    FigureCanvasAgg(fig)
    ov = fig.add_axes([0, 0, 1, 1], zorder=0)
    ov.set_xlim(0, W), ov.set_ylim(0, H), ov.axis("off")
    ax = fig.add_axes([fx / W, fy / H, fw / W, fh / H], zorder=1)
    ov2 = fig.add_axes([0, 0, 1, 1], zorder=3)
    ov2.set_xlim(0, W), ov2.set_ylim(0, H), ov2.axis("off"), ov2.patch.set_alpha(0)
    ax.set_xlim(ext[0], ext[1]), ax.set_ylim(ext[2], ext[3]), ax.set_aspect("auto")
    ax.set_xticks([]), ax.set_yticks([])
    ax.set_facecolor("#fbfaf6")
    for s in ax.spines.values():
        s.set_visible(False)

    legende = []  # (symbole, couleur, libellé, épaisseur)
    notes = []
    source_fond = None
    if FONDS.get(fond):
        source_fond = _ajouter_fond(ax, fond, crs, fenetre_ll, fw * k)
        ax.set_xlim(ext[0], ext[1]), ax.set_ylim(ext[2], ext[3])
        if source_fond is None:
            notes.append("Fond de carte indisponible (pas d'accès au service de tuiles) : carte produite sur fond clair.")

    def niveau(n):
        return _gdf(limites[n].geojson["features"], crs) if n in limites else None

    # --- fond : limites administratives ---------------------------------------------------
    regions, provinces, communes = niveau(1), niveau(2), niveau(3)
    if regions is not None and not source_fond:
        regions.plot(ax=ax, facecolor="#f1f0ec", edgecolor="none", zorder=1)
    if contour:
        gpd.GeoSeries([shape(contour)], crs=4326).to_crs(crs).plot(ax=ax, facecolor="#e6f4ee", edgecolor="none", alpha=0.35 if source_fond else 1, zorder=1.1)
        legende.append(("rect", "#e6f4ee", f"{donnees['zone_filtre']['niveau']} {donnees['zone_filtre']['nom']}", 1))
    if couches.get("communes") and communes is not None:
        communes.boundary.plot(ax=ax, color="#bdbdb6", linewidth=LW(0.5), zorder=1.3)
        legende.append(("line", "#bdbdb6", "Limite de commune", 0.8))
    if couches.get("provinces") and provinces is not None:
        provinces.boundary.plot(ax=ax, color="#8d6e63", linewidth=LW(1.2), linestyle=(0, (7, 4)), zorder=1.4)
        legende.append(("dash", "#8d6e63", "Limite de province", 1.4))
    if couches.get("regions") and regions is not None:
        regions.boundary.plot(ax=ax, color="#3d3d3d", linewidth=LW(2.2), zorder=1.5)
        legende.append(("line", "#3d3d3d", "Limite de région", 2.2))

    if contour:
        # Hors de la zone choisie : voile blanc, pour que la zone ressorte.
        zone_m = gpd.GeoSeries([shape(contour)], crs=4326).to_crs(crs).make_valid().union_all()
        gpd.GeoSeries([fenetre.difference(zone_m)], crs=crs).plot(ax=ax, facecolor="white", edgecolor="none", alpha=0.35 if source_fond else 0.55, zorder=3.5)
        gpd.GeoSeries([zone_m.boundary], crs=crs).plot(ax=ax, color="#0c8a5f", linewidth=LW(3), zorder=3.6)

    # --- carte par zone (projets, bénéficiaires, budget, taux) -----------------------------
    if par_zone:
        from apps.geo.services.limites import normaliser_nom

        indicateur = par_zone["indicateur"]
        zones_pz = par_zone["synthese"]["zones"]
        bornes = classes_zone(indicateur, zones_pz)
        par_nom = {normaliser_nom(z["nom"]): z for z in zones_pz}
        par_nom.update({normaliser_nom(z["nom_contour"]): z for z in zones_pz if z["nom_contour"]})
        ordre_pz = par_zone["synthese"]["niveau"]["ordre"]
        if ordre_pz in limites:
            contours = [f for f in limites[ordre_pz].geojson["features"] if normaliser_nom(f["properties"].get("shapeName", "")) in par_nom]
            gdf_pz = _gdf(contours, crs)
            if len(gdf_pz):
                gdf_pz["couleur"] = [
                    couleur_zone(indicateur, valeur_de(par_nom[normaliser_nom(n)], indicateur), bornes) for n in gdf_pz["shapeName"]
                ]
                gdf_pz.plot(ax=ax, color=gdf_pz["couleur"], alpha=0.55 if source_fond else 0.8, edgecolor="#374151", linewidth=LW(1), zorder=1.2)
        for couleur_classe, libelle in zip(degrade(indicateur), libelles_classes(indicateur, bornes)):
            legende.append(("rect", couleur_classe, f"{traduire(par_zone['libelle_court'])} : {libelle}", 1))
        legende.append(("rect", SANS_DONNEE, traduire_modele("{0} : aucun", traduire(par_zone["libelle_court"])), 1))

    if couches.get("routes"):
        couche = CoucheCarte.objects.filter(pays=pays, cle="routes").first()
        if couche:
            routes = [f for f in couche.geojson["features"] if shape(f["geometry"]).intersects(fenetre_ll)]
            routes = _gdf(routes, crs)
            for classe, (couleur, lw, ls, libelle) in STYLE_ROUTES.items():
                sous = routes[routes.classe == classe] if len(routes) else routes
                if len(sous):
                    sous.plot(ax=ax, color=couleur, linewidth=LW(lw), linestyle=ls, zorder=2, alpha=0.9)
                    legende.append(("dash" if ls != "-" else "line", couleur, libelle, lw))

    # --- couches importées ---------------------------------------------------------------
    for couche in couches.get("importees", []):
        gdf = _gdf(couche.geojson["features"], crs)
        gdf = gdf[gdf.intersects(fenetre)] if len(gdf) else gdf
        if not len(gdf):
            continue
        if couche.geometrie == "POINT":
            ax.scatter(gdf.geometry.x, gdf.geometry.y, s=60 * k * k, marker="s", c=couche.couleur, edgecolors="white", linewidths=LW(0.9), zorder=4.5)
            legende.append(("carre", couche.couleur, couche.nom, 1))
        elif couche.geometrie == "LIGNE":
            gdf.plot(ax=ax, color=couche.couleur, linewidth=LW(2.4), zorder=2.5)
            legende.append(("line", couche.couleur, couche.nom, 2.4))
        else:
            gdf.plot(ax=ax, facecolor=couche.couleur, alpha=0.18, edgecolor="none", zorder=1.2)
            gdf.boundary.plot(ax=ax, color=couche.couleur, linewidth=LW(1.6), zorder=1.6)
            legende.append(("rect", couche.couleur, couche.nom, 1))
        couche._gdf = gdf  # pour les étiquettes

    # --- bénéficiaires --------------------------------------------------------------------
    # Bénéficiaires (couche « points ») : on peut les retirer, notamment sur une carte par zone.
    if not couches.get("points"):
        donnees = {**donnees, "zones": [], "points": []}
    nb_max = max([z["nombre"] for z in donnees["zones"]] or [1])
    if donnees["zones"]:
        xs, ys = vers_m.transform([z["lng"] for z in donnees["zones"]], [z["lat"] for z in donnees["zones"]])
        tailles = [(16 + 70 * (z["nombre"] / nb_max) ** 0.5) ** 2 * k * k for z in donnees["zones"]]
        ax.scatter(xs, ys, s=tailles, c=C_ZONE, alpha=0.55, edgecolors="#0c8a5f", linewidths=LW(1.6), zorder=5)
        legende.append(("rond", C_ZONE, "Bénéficiaires par localité (taille = nombre)", 1))
    if donnees["points"]:
        xs, ys = vers_m.transform([p["lng"] for p in donnees["points"]], [p["lat"] for p in donnees["points"]])
        ax.scatter(xs, ys, s=30 * k * k, c="#fb923c", edgecolors=C_GPS, linewidths=LW(0.9), zorder=6)
        legende.append(("dot", "#fb923c", "Bénéficiaire positionné par GPS", 1))

    # --- étiquettes -------------------------------------------------------------------------
    pl = Placeur(fig, ax)
    halo = [pe.withStroke(linewidth=LW(3.2), foreground="white")]
    if par_zone:
        def lignes_zone(z):
            """Lignes écrites sur une zone : un indicateur choisi par ligne."""
            return lignes_valeurs(z, par_zone["indicateurs"])

        zones_pz = [z for z in par_zone["synthese"]["zones"]
                    if z["lat"] is not None and any(valeur_de(z, i) not in (None, 0) for i in par_zone["indicateurs"])]
        if zones_pz:
            xs, ys = vers_m.transform([z["lng"] for z in zones_pz], [z["lat"] for z in zones_pz])
            for z, x, y in zip(zones_pz, xs, ys):
                pl.essayer(x, y, "\n".join([z["nom"].upper(), *lignes_zone(z)]), force=True, fontsize=F(14), fontweight="bold", color="#111827",
                           ha="center", va="center", zorder=9,
                           bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#6b7280", lw=LW(0.8), alpha=0.9))
    if donnees["zones"]:
        xs, ys = vers_m.transform([z["lng"] for z in donnees["zones"]], [z["lat"] for z in donnees["zones"]])
        for z, x, y in zip(donnees["zones"], xs, ys):
            pl.essayer(x + 3 * mm, y + 3 * mm, f"{z['nom']} ({z['nombre']})", fontsize=F(14), fontweight="bold",
                       color="#064e3b", ha="left", va="bottom", zorder=8, path_effects=halo)
    if couches.get("beneficiaires") and donnees["points"]:
        if len(donnees["points"]) <= 400:
            xs, ys = vers_m.transform([p["lng"] for p in donnees["points"]], [p["lat"] for p in donnees["points"]])
            for p, x, y in zip(donnees["points"], xs, ys):
                for dx, ha in [(1.8 * mm, "left"), (-1.8 * mm, "right")]:
                    if pl.essayer(x + dx, y, p["nom"], fontsize=F(12), color="#7c2d12", ha=ha, va="center", zorder=8, path_effects=halo):
                        break
        else:
            notes.append(f"{len(donnees['points'])} bénéficiaires positionnés par GPS : trop nombreux pour écrire leurs noms.")
    if couches.get("noms"):
        for niveau_noms, gdf, champ, taille, couleur in (
            (1, regions, "shapeName", 30, "#1f3a5f"), (2, provinces if couches.get("provinces") else None, "shapeName", 20, "#7a5a4d"),
        ):
            # Carte par zone : le nom des zones colorées est déjà écrit avec leur valeur.
            if gdf is None or niveau_noms == ordre_pz:
                continue
            for _, r in gdf.iterrows():
                g = r.geometry.intersection(fenetre)
                if g.is_empty or g.area < 0.04 * fenetre.area * (taille / 30) ** 2 * 0.1:
                    continue
                p = g.representative_point()
                pl.essayer(p.x, p.y, " ".join(str(r[champ]).upper()) if taille >= 30 else str(r[champ]).upper(),
                           fontsize=F(taille), color=couleur, alpha=0.4 if taille >= 30 else 0.7, ha="center", va="center",
                           fontweight="bold" if taille >= 30 else None, zorder=1.6)
        for couche in couches.get("importees", []):
            gdf = getattr(couche, "_gdf", None)
            if gdf is None or not couche.champ_etiquette or couche.champ_etiquette not in gdf.columns or len(gdf) > 300:
                continue
            for _, r in gdf.iterrows():
                p = r.geometry if r.geometry.geom_type == "Point" else r.geometry.intersection(fenetre).representative_point()
                if r[couche.champ_etiquette] and not p.is_empty:
                    pl.essayer(p.x + 2 * mm, p.y, str(r[couche.champ_etiquette]), fontsize=F(12), color=couche.couleur,
                               ha="left", va="center", zorder=7, path_effects=halo)
    if couches.get("villages"):
        o, s_, e, n = fenetre_ll.bounds
        villages = list(Localite.objects.filter(pays=pays, latitude__range=(s_, n), longitude__range=(o, e)).values_list("nom", "statut", "longitude", "latitude")[:4000])
        if villages and len(villages) <= 2500:
            xs, ys = vers_m.transform([v[2] for v in villages], [v[3] for v in villages])
            ax.scatter(xs, ys, s=[(40 if v[1] == "VILLE" else 12) * k * k for v in villages], c="#4c1d95", edgecolors="white", linewidths=LW(0.5), zorder=4)
            legende.append(("dot", "#4c1d95", "Ville ou village", 1))
            if couches.get("noms") and len(villages) <= 600:
                for v, x, y in sorted(zip(villages, xs, ys), key=lambda t: t[0][1] != "VILLE"):
                    pl.essayer(x + 1.6 * mm, y, v[0], fontsize=F(11 if v[1] != "VILLE" else 14), color="#2e1065",
                               ha="left", va="center", zorder=7, path_effects=halo)

    # --- grille de coordonnées, cadre, échelle, nord ---------------------------------------
    coins = [vers_ll.transform(x, y) for x, y in [(ext[0], ext[2]), (ext[1], ext[2]), (ext[0], ext[3]), (ext[1], ext[3])]]
    lo0, lo1 = min(p[0] for p in coins), max(p[0] for p in coins)
    la0, la1 = min(p[1] for p in coins), max(p[1] for p in coins)
    pas = next((s for s in [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5] if (lo1 - lo0) / s <= 7), 10)
    kw = dict(fontsize=F(13), color="#374151")
    for lon in np.arange(np.ceil(lo0 / pas) * pas, lo1, pas):
        lats = np.linspace(la0 - 0.1, la1 + 0.1, 60)
        xs, ys = vers_m.transform(np.full_like(lats, lon), lats)
        ax.plot(xs, ys, color="#4b5563", lw=LW(0.6), ls=(0, (6, 6)), alpha=0.5, zorder=1.8)
        for yy, py, va in [(ext[2], fy - 3, "top"), (ext[3], fy + fh + 3, "bottom")]:
            x = np.interp(yy, ys, xs)
            if ext[0] < x < ext[1]:
                ov2.text(fx + (x - ext[0]) / (ext[1] - ext[0]) * fw, py, dms(lon, "E", "O"), ha="center", va=va, **kw)
    for lat in np.arange(np.ceil(la0 / pas) * pas, la1, pas):
        lons = np.linspace(lo0 - 0.1, lo1 + 0.1, 60)
        xs, ys = vers_m.transform(lons, np.full_like(lons, lat))
        ax.plot(xs, ys, color="#4b5563", lw=LW(0.6), ls=(0, (6, 6)), alpha=0.5, zorder=1.8)
        for xx, px, ha in [(ext[0], fx - 3, "right"), (ext[1], fx + fw + 3, "left")]:
            y = np.interp(xx, xs, ys)
            if ext[2] < y < ext[3]:
                ov2.text(px, fy + (y - ext[2]) / (ext[3] - ext[2]) * fh, dms(lat, "N", "S"), ha="center",
                         va="bottom" if ha == "right" else "top", rotation=90, **kw)
    ov2.add_patch(Rectangle((fx, fy), fw, fh, fill=False, ec="black", lw=LW(2.5)))
    ov2.add_patch(Rectangle((fx - 1.6, fy - 1.6), fw + 3.2, fh + 3.2, fill=False, ec="black", lw=LW(0.8)))

    km = next((v for v in [500, 200, 100, 50, 25, 20, 10, 5, 2, 1] if v * 1e6 / ech <= 135 * k), 1)
    L = km * 1e6 / ech / k
    bx, by = fx + 10, fy + 10
    ov2.add_patch(Rectangle((bx - 6, by - 6), L + 38, 30, fc="white", ec="black", lw=LW(1), alpha=0.93))
    for i in range(4):
        ov2.add_patch(Rectangle((bx + i * L / 4, by + 4), L / 4, 5, fc="black" if i % 2 == 0 else "white", ec="black", lw=LW(1)))
    for i in range(5):
        ov2.text(bx + i * L / 4, by + 11, f"{km * i / 4:g}".replace(".", ","), ha="center", va="bottom", fontsize=F(12))
    ov2.text(bx + L + 4, by + 4, "km", ha="left", va="bottom", fontsize=F(13), fontweight="bold")
    ov2.text(bx, by - 3, f"Échelle 1 : {fr(ech)}", ha="left", va="center", fontsize=F(13), fontweight="bold")
    nx, ny, s = fx + fw - 28, fy + fh - 12, 40
    ov2.add_patch(Rectangle((nx - 20, ny - s - 14), 40, s + 32, fc="white", ec="black", lw=LW(1), alpha=0.93))
    ov2.add_patch(MPoly([(nx, ny), (nx - 9, ny - s), (nx, ny - s * 0.72)], fc="black", ec="black", lw=LW(1)))
    ov2.add_patch(MPoly([(nx, ny), (nx + 9, ny - s), (nx, ny - s * 0.72)], fc="white", ec="black", lw=LW(1)))
    ov2.text(nx, ny + 3, "N", ha="center", va="bottom", fontsize=F(20), fontweight="bold")

    # --- en-tête ------------------------------------------------------------------------------
    haut = H - marge
    titre_auto, sous = titre_par_defaut(donnees, couches, par_zone, titre_portee)
    titre = titre.upper() if titre else titre_auto
    sous = sous_titre or sous
    ov.add_patch(Rectangle((marge, haut - hh), W - 2 * marge, hh, fc=BLEU, ec="none"))
    ov.text(marge + 10, haut - 11, (organisation or traduire("Plateforme de suivi-évaluation")).upper(), color="#ccfbf1", fontsize=F(17), va="center", ha="left")
    fs_titre = 40 if len(titre) <= 62 else 40 * 62 / len(titre)
    ov.text(marge + 10, haut - 29, titre, color="white", fontsize=F(fs_titre), fontweight="bold", va="center", ha="left")
    ov.text(marge + 10, haut - 49, sous, color="#e2e8f0", fontsize=F(22), va="center", ha="left")
    ov.add_patch(Rectangle((W - marge - 64, haut - hh + 8), 56, hh - 16, fc="white", ec="none"))
    ov.text(W - marge - 36, haut - hh / 2 + 9, traduire("Carte").upper(), ha="center", va="center", fontsize=F(15), color=BLEU)
    ov.text(W - marge - 36, haut - hh / 2 - 6, "S&E", ha="center", va="center", fontsize=F(26), fontweight="bold", color=BLEU)

    # --- panneau droit ---------------------------------------------------------------------------
    px0 = W - marge - pw
    cur = fy + fh

    def titre_bloc(y, txt):
        ov.add_patch(Rectangle((px0, y - 11), pw, 11, fc=BLEU, ec="none"))
        ov.text(px0 + 4, y - 5.5, txt, color="white", fontsize=F(17), fontweight="bold", va="center")
        return y - 11

    if regions is not None and len(regions):
        cur = titre_bloc(cur, "SITUATION")
        pays_geom = regions.union_all()
        b = pays_geom.bounds
        iw = pw - 20
        ih = min(iw * (b[3] - b[1]) / (b[2] - b[0]), 150)
        sx0, sy0 = px0 + 10, cur - 8 - ih
        sa = fig.add_axes([sx0 / W, sy0 / H, iw / W, ih / H], zorder=2)
        gpd.GeoSeries([pays_geom], crs=crs).plot(ax=sa, fc="#f3f4f6", ec="#374151", lw=LW(1))
        regions.boundary.plot(ax=sa, color="#9ca3af", lw=LW(0.4))
        if contour:
            gpd.GeoSeries([shape(contour)], crs=4326).to_crs(crs).plot(ax=sa, fc=C_ZONE, ec="#111827", lw=LW(0.8))
        sa.add_patch(Rectangle((ext[0], ext[2]), ext[1] - ext[0], ext[3] - ext[2], fill=False, ec="#dc2626", lw=LW(2.2)))
        sa.set_xlim(b[0], b[2]), sa.set_ylim(b[1], b[3]), sa.set_aspect("equal"), sa.axis("off")
        ov.text(px0 + pw / 2, sy0 - 3, "Emprise de la carte (cadre rouge)", ha="center", va="top", fontsize=F(13), color="#374151")
        cur = sy0 - 12

    cur = titre_bloc(cur - 2, "CHIFFRES CLÉS") - 8
    tw = pw / 3
    localises = donnees["total"] - donnees["non_localises"]
    for i, (v, l) in enumerate([(fr(donnees["total"]), "bénéficiaires"), (fr(donnees.get("femmes", 0)), "femmes"), (fr(donnees.get("hommes", 0)), "hommes")]):
        ov.add_patch(Rectangle((px0 + i * tw + 2, cur - 48), tw - 4, 40, fc="#f1f5f9", ec="#cbd5e1", lw=LW(1)))
        ov.text(px0 + i * tw + tw / 2, cur - 24, v, ha="center", va="center", fontsize=F(32), fontweight="bold", color=BLEU)
        ov.text(px0 + i * tw + tw / 2, cur - 41, l, ha="center", va="center", fontsize=F(14), color="#475569")
    cur -= 58

    cur = titre_bloc(cur, "LÉGENDE") - 5
    for sym, col, libelle, lw in legende:
        y = cur
        if sym == "line":
            ov.plot([px0 + 5, px0 + 30], [y - 5, y - 5], color=col, lw=LW(max(lw, 1.5) * 1.6), solid_capstyle="butt")
        elif sym == "dash":
            ov.plot([px0 + 5, px0 + 30], [y - 5, y - 5], color=col, lw=LW(max(lw, 1.5) * 1.6), ls=(0, (5, 3)))
        elif sym in ("dot", "rond", "carre"):
            ov.scatter([px0 + 17], [y - 5], s=(240 if sym == "rond" else 140) * k * k, c=col, marker="s" if sym == "carre" else "o",
                       edgecolors="#0c8a5f" if sym == "rond" else "white", linewidths=LW(1.2), alpha=0.7 if sym == "rond" else 1)
        else:
            ov.add_patch(Rectangle((px0 + 5, y - 9), 25, 8, fc=col, ec="#555", lw=LW(0.8), alpha=0.6))
        ov.text(px0 + 36, y - 5, tronc(traduire(libelle), 52), va="center", fontsize=F(15))
        cur -= 11.5
    cur -= 4

    H_LIGNE = 10.4
    largeurs = [w * pw / 275 for w in [137, 46, 46, 46]]

    def ligne_tab(y, cellules, gras=False, fond=None):
        if fond:
            ov.add_patch(Rectangle((px0, y - H_LIGNE), pw, H_LIGNE, fc=fond, ec="none"))
        x = px0
        for i, (c, w) in enumerate(zip(cellules, largeurs)):
            a = "left" if i == 0 else "right"
            ov.text(x + 2 if a == "left" else x + w - 2, y - H_LIGNE / 2, str(c), ha=a, va="center", fontsize=F(14),
                    fontweight="bold" if gras else None, color="white" if fond == "#334155" else "#111827")
            x += w
        return y - H_LIGNE

    place = int((cur - fy - 22) / H_LIGNE) - 3
    if par_zone and place > 2:
        indicateur = par_zone["indicateur"]
        cur = titre_bloc(cur, traduire_modele("Par {0}", traduire(par_zone["synthese"]["niveau"]["nom"])).upper())
        # Colonnes : les indicateurs choisis (4 au plus) ; avec un seul, projets, bénéficiaires et
        # cet indicateur (le budget quand c'est déjà le nombre de projets).
        if len(par_zone["indicateurs"]) > 1:
            colonnes = par_zone["indicateurs"][:4]
            if len(par_zone["indicateurs"]) > 4:
                notes.append("Tableau limité aux 4 premiers indicateurs choisis (tous figurent sur la carte).")
        else:
            colonnes = ["projets", "beneficiaires", "budget" if indicateur == "projets" else indicateur]
        largeurs[:] = [w * pw / 275 for w in [275 - 46 * len(colonnes), *[46] * len(colonnes)]]
        cur = ligne_tab(cur, [par_zone["synthese"]["niveau"]["nom"], *[ENTETES_COURTES.get(c, COURTS[c]) for c in colonnes]], True, "#334155")
        lignes = sorted(par_zone["synthese"]["zones"], key=lambda z: -(valeur_de(z, indicateur) or 0))
        lignes = [z for z in lignes if z["projets"] or z["beneficiaires"]]
        if len(lignes) > place:
            notes.append(f"Tableau limité aux {place - 1} premières zones sur {len(lignes)}.")
            lignes = lignes[: place - 1]
        for i, z in enumerate(lignes):
            cur = ligne_tab(cur, [tronc(z["nom"], 34 if len(colonnes) <= 3 else 22), *[valeur_zone(c, valeur_de(z, c)) for c in colonnes]],
                            fond="#f8fafc" if i % 2 == 0 else None)
        largeurs[:] = [w * pw / 275 for w in [137, 46, 46, 46]]
        notes.append("Un projet compte dans chaque zone où il intervient (son budget n'est pas réparti entre les zones).")
    elif donnees["zones"] and place > 2:
        cur = titre_bloc(cur, "BÉNÉFICIAIRES PAR LOCALITÉ")
        cur = ligne_tab(cur, ["Localité", "Femmes", "Hommes", "Total"], True, "#334155")
        lignes = donnees["zones"]
        if len(lignes) > place:
            notes.append(f"Tableau limité aux {place - 1} localités les plus nombreuses sur {len(lignes)}.")
            lignes = lignes[: place - 1]
        for i, z in enumerate(lignes):
            cur = ligne_tab(cur, [tronc(z["nom"], 34), z["femmes"], z["hommes"], z["nombre"]], fond="#f8fafc" if i % 2 == 0 else None)
        if donnees["points"]:
            cur = ligne_tab(cur, ["Positionnés par GPS", "", "", len(donnees["points"])])
        cur = ligne_tab(cur, ["TOTAL LOCALISÉ", "", "", localises], True, "#cbd5e1")
    if donnees["non_localises"] and couches.get("points"):
        notes.append(f"{donnees['non_localises']} bénéficiaire(s) sans localisation ne figurent pas sur la carte.")
    if notes:
        # Traduites avant d'être coupées en lignes (une note coupée ne se retrouve plus au catalogue).
        ov.text(px0, cur - 7, "\n".join(textwrap.fill("• " + traduire(n), 62, subsequent_indent="  ") for n in notes),
                va="top", fontsize=F(13), color="#475569", linespacing=1.3)

    # --- cartouche -------------------------------------------------------------------------------------
    date = datetime.now().strftime("%d/%m/%Y")
    zone_utm = crs % 100
    sources_limites = {l.source for l in limites.values()} or {"—"}
    fond_txt = f"\nFond : {source_fond}" if source_fond else ""
    cases = [
        ("SOURCE DES DONNÉES", f"Plateforme de suivi-évaluation (bénéficiaires)\nLimites : {', '.join(sorted(sources_limites))}{fond_txt}\nÉdition du {date}"),
        ("PROJECTION", f"WGS 84 / UTM zone {zone_utm}{'N' if crs < 32700 else 'S'} (EPSG:{crs})\nGrille : degrés-minutes (WGS 84)\nÉchelle : 1 : {fr(ech)} (format {papier})"),
        ("RÉALISATION", f"{organisation or traduire('Plateforme de suivi-évaluation')}\nCarte générée le {date}"),
        ("NOTE", "Bénéficiaires sans GPS placés au centre de leur localité ;\nlimites administratives à titre indicatif."),
    ]
    ov.add_patch(Rectangle((marge, marge), W - 2 * marge, fth, fc="#f1f5f9", ec="black", lw=LW(1.5)))
    cw = (W - 2 * marge) / len(cases)
    for i, (t, c) in enumerate(cases):
        x = marge + i * cw
        if i:
            ov.plot([x, x], [marge, marge + fth], color="black", lw=LW(1))
        ov.text(x + 5, marge + fth - 6, t, fontsize=F(13), fontweight="bold", color=BLEU, va="center")
        ov.text(x + 5, marge + fth - 12, c, fontsize=F(12), va="top", linespacing=1.35)

    traduire_figure(fig)
    tampon_sortie = io.BytesIO()
    fig.savefig(tampon_sortie, format="png" if sortie == "png" else "pdf", **({"dpi": DPI_PNG[papier]} if sortie == "png" else {}))
    return tampon_sortie.getvalue()
