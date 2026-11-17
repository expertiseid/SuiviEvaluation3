"""
Bénéficiaires et territoires (tableau de bord) : bénéficiaires directs, ménages et indirects, couverture
de la cible et de la population, maintien, abandon et paquet complet, satisfaction, écarts entre
territoires, zones ciblées sans bénéficiaire, bénéficiaires hors des zones du projet, coordonnées non
valides, surfaces et longueurs des couches importées, plaintes pour 1 000 bénéficiaires et plaintes
récurrentes.

Un « parcours » est la participation d'un bénéficiaire à un projet (toutes ses activités) : il est
abandonné si une de ses participations l'est, complet si toutes sont terminées. Quelques requêtes pour
tous les projets.
"""
from collections import defaultdict

EXEMPLES_MAX = 20


def _pourcent(partie, total):
    return round(partie / total * 100, 1) if total else None


def _emprise(geojson):
    """[ouest, sud, est, nord] de toutes les coordonnées d'un GeoJSON."""
    xs, ys = [], []

    def parcourir(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for sous in c or []:
                parcourir(sous)

    for f in geojson.get("features", []) if isinstance(geojson, dict) else []:
        parcourir((f.get("geometry") or {}).get("coordinates"))
    return [min(xs), min(ys), max(xs), max(ys)] if xs else None


_EMPRISES = {}


def emprises_pays(pays):
    """Emprise de chaque pays d'après ses limites administratives chargées (le niveau le plus haut)."""
    from apps.geo.models import LimiteAdministrative

    resultat = {}
    for code in set(pays):
        limite = (LimiteAdministrative.objects.filter(pays=code).order_by("niveau")
                  .only("id", "updated_at").first())
        if limite is None:
            continue
        cle = (limite.id, limite.updated_at)
        if _EMPRISES.get(code, (None,))[0] != cle:
            geojson = LimiteAdministrative.objects.values_list("geojson", flat=True).get(pk=limite.pk)
            _EMPRISES[code] = (cle, _emprise(geojson))
        if _EMPRISES[code][1]:
            resultat[code] = _EMPRISES[code][1]
    return resultat


def coordonnees_valides(lat, lon, emprise=None, marge=0.5):
    """Coordonnées plausibles : dans les bornes, pas (0, 0), et dans l'emprise du pays si elle est connue."""
    if lat is None or lon is None:
        return True
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return False
    if emprise:
        ouest, sud, est, nord = emprise
        return ouest - marge <= lon <= est + marge and sud - marge <= lat <= nord + marge
    return True


def beneficiaires_territoires(projet_ids) -> dict:
    from apps.geo.models import CoucheImportee, Zone
    from apps.plaintes.models import Dossier
    from apps.projects.models import Projet

    from .models import Beneficiaire, ParticipationProjet

    projets = {p["id"]: p for p in Projet.objects.filter(id__in=projet_ids).values(
        "id", "code", "cible_totale", "beneficiaires_indirects", "tout_le_pays")}
    zones = {z["id"]: z for z in Zone.objects.values(
        "id", "parent_id", "nom", "population", "niveau_administratif__ordre", "niveau_administratif__pays",
        "niveau_administratif__nom_niveau", "latitude", "longitude")}
    enfants = defaultdict(list)
    for z in zones.values():
        if z["parent_id"]:
            enfants[z["parent_id"]].append(z["id"])

    ancetres_memo = {}

    def ancetres(zone_id):
        """La zone et toutes celles qui la contiennent."""
        if zone_id not in ancetres_memo:
            chaine, courant = [], zone_id
            while courant and courant in zones and courant not in chaine:
                chaine.append(courant)
                courant = zones[courant]["parent_id"]
            ancetres_memo[zone_id] = set(chaine)
        return ancetres_memo[zone_id]

    population_memo = {}

    def population(zone_id):
        """Population saisie, sinon somme de celles des zones qu'elle contient."""
        if zone_id not in population_memo:
            propre = zones[zone_id]["population"]
            if propre is not None:
                population_memo[zone_id] = propre
            else:
                sous = [population(e) for e in enfants.get(zone_id, [])]
                sous = [p for p in sous if p is not None]
                population_memo[zone_id] = sum(sous) if sous else None
        return population_memo[zone_id]

    participations = list(ParticipationProjet.objects.filter(projet_id__in=projet_ids).values(
        "beneficiaire_id", "projet_id", "statut", "satisfaction", "beneficiaire__sexe", "beneficiaire__zone_id",
        "beneficiaire__taille_menage"))

    # Bénéficiaires directs, ménages et indirects.
    personnes = {}
    for p in participations:
        personnes[p["beneficiaire_id"]] = p
    directs = len(personnes)
    tailles = [p["beneficiaire__taille_menage"] for p in personnes.values() if p["beneficiaire__taille_menage"]]
    indirects_saisis = [p["beneficiaires_indirects"] for p in projets.values() if p["beneficiaires_indirects"] is not None]
    if indirects_saisis:
        indirects, source_indirects = sum(indirects_saisis), "projets"
    elif tailles:
        indirects, source_indirects = sum(t - 1 for t in tailles), "menages"
    else:
        indirects, source_indirects = None, None

    # Parcours (bénéficiaire × projet) : abandon, paquet complet, satisfaction.
    parcours = defaultdict(list)
    for p in participations:
        parcours[(p["beneficiaire_id"], p["projet_id"])].append(p["statut"])
    abandons = {cle for cle, statuts in parcours.items() if "ABANDON" in statuts}
    complets = {cle for cle, statuts in parcours.items() if all(s == "TERMINE" for s in statuts)}
    statuts_saisis = any(p["statut"] != "EN_COURS" for p in participations)
    notes = [p["satisfaction"] for p in participations if p["satisfaction"]]

    # Couverture de la cible des projets.
    par_projet = defaultdict(set)
    for p in participations:
        par_projet[p["projet_id"]].add(p["beneficiaire_id"])
    avec_cible = [pid for pid, p in projets.items() if p["cible_totale"]]
    cible = sum(projets[pid]["cible_totale"] for pid in avec_cible)
    atteints = sum(len(par_projet.get(pid, ())) for pid in avec_cible)

    # Comparaison des territoires (premier niveau administratif : régions…).
    def territoire(zone_id):
        if zone_id is None:
            return None
        return next((a for a in ancetres(zone_id) if zones[a]["niveau_administratif__ordre"] == 1), None)

    par_territoire = defaultdict(lambda: {"beneficiaires": set(), "femmes": set(), "parcours": set(), "abandons": set()})
    for p in participations:
        t = territoire(p["beneficiaire__zone_id"])
        if t is None:
            continue
        ligne = par_territoire[t]
        ligne["beneficiaires"].add(p["beneficiaire_id"])
        if p["beneficiaire__sexe"] == Beneficiaire.Sexe.FEMININ:
            ligne["femmes"].add(p["beneficiaire_id"])
        cle = (p["beneficiaire_id"], p["projet_id"])
        ligne["parcours"].add(cle)
        if cle in abandons:
            ligne["abandons"].add(cle)
    territoires = []
    for t, ligne in par_territoire.items():
        nb, pop = len(ligne["beneficiaires"]), population(t)
        territoires.append({
            "zone": zones[t]["nom"], "pays": zones[t]["niveau_administratif__pays"], "beneficiaires": nb,
            "part_femmes": _pourcent(len(ligne["femmes"]), nb), "population": pop,
            "pour_1000_habitants": round(nb / pop * 1000, 2) if pop else None,
            "taux_abandon": _pourcent(len(ligne["abandons"]), len(ligne["parcours"])) if statuts_saisis else None,
        })
    territoires.sort(key=lambda t: -t["beneficiaires"])

    def ecart(cle):
        valeurs = [t[cle] for t in territoires if t[cle] is not None]
        if len(valeurs) < 2:
            return None
        haut = max(territoires, key=lambda t: t[cle] if t[cle] is not None else float("-inf"))
        bas = min(territoires, key=lambda t: t[cle] if t[cle] is not None else float("inf"))
        return {"plus_haut": haut["zone"], "valeur_haute": haut[cle], "plus_bas": bas["zone"], "valeur_basse": bas[cle],
                "rapport": round(haut[cle] / bas[cle], 1) if bas[cle] else None, "difference": round(haut[cle] - bas[cle], 1)}

    # Zones ciblées sans bénéficiaire, bénéficiaires hors des zones du projet.
    ciblees = defaultdict(set)
    for projet_id, zone_id in Projet.zones.through.objects.filter(projet_id__in=projet_ids).values_list("projet_id", "zone_id"):
        if not projets[projet_id]["tout_le_pays"]:
            ciblees[projet_id].add(zone_id)
    zones_beneficiaires = defaultdict(set)
    for p in participations:
        if p["beneficiaire__zone_id"]:
            zones_beneficiaires[p["projet_id"]].add(p["beneficiaire__zone_id"])
    sans_beneficiaire, total_ciblees = [], 0
    for projet_id, cibles in ciblees.items():
        couvertes = set().union(*(ancetres(z) for z in zones_beneficiaires.get(projet_id, ()))) if zones_beneficiaires.get(projet_id) else set()
        for z in cibles:
            total_ciblees += 1
            if z not in couvertes:
                sans_beneficiaire.append({"projet": projets[projet_id]["code"], "zone": zones[z]["nom"],
                                          "niveau": zones[z]["niveau_administratif__nom_niveau"]})
    # Sans identifiant de bénéficiaire (le tableau de bord peut être partagé par lien) : projet, zone, nombre.
    hors_zone, hors_zone_vus = defaultdict(int), set()
    for p in participations:
        cibles, z = ciblees.get(p["projet_id"]), p["beneficiaire__zone_id"]
        cle = (p["beneficiaire_id"], p["projet_id"])
        if not cibles or z is None or cle in hors_zone_vus:
            continue
        dans = ancetres(z)
        # Une zone plus large qu'une zone ciblée (région saisie, commune ciblée) n'est pas « hors zone ».
        if not (dans & cibles) and not any(z in ancetres(c) for c in cibles):
            hors_zone_vus.add(cle)
            hors_zone[(projets[p["projet_id"]]["code"], zones[z]["nom"])] += 1

    # Coordonnées non valides (bénéficiaires des projets et centres des zones).
    beneficiaires_gps = list(Beneficiaire.objects.filter(participations__projet_id__in=projet_ids, latitude__isnull=False)
                             .distinct().values("pays", "latitude", "longitude"))
    emprises = emprises_pays([b["pays"] for b in beneficiaires_gps] + [z["niveau_administratif__pays"] for z in zones.values()])
    gps_invalides = sum(1 for b in beneficiaires_gps if not coordonnees_valides(b["latitude"], b["longitude"], emprises.get(b["pays"])))
    zones_invalides = [z["nom"] for z in zones.values() if z["latitude"] is not None
                       and not coordonnees_valides(z["latitude"], z["longitude"], emprises.get(z["niveau_administratif__pays"]))]

    # Plaintes rapportées aux bénéficiaires, plaintes récurrentes (liées à d'autres dossiers).
    dossiers = Dossier.objects.filter(projet_id__in=projet_ids)
    nb_dossiers = dossiers.count()
    recurrents = dossiers.filter(dossiers_lies__isnull=False).distinct().count() if nb_dossiers else 0

    return {
        "directs": directs,
        "menages": len(tailles), "personnes_des_menages": sum(tailles),
        "indirects": indirects, "source_indirects": source_indirects,
        "cible": cible or None, "couverture_cible": _pourcent(atteints, cible),
        "parcours": len(parcours), "statuts_saisis": statuts_saisis,
        "abandons": len(abandons) if statuts_saisis else None,
        "taux_abandon": _pourcent(len(abandons), len(parcours)) if statuts_saisis else None,
        "taux_maintien": _pourcent(len(parcours) - len(abandons), len(parcours)) if statuts_saisis else None,
        "taux_paquet_complet": _pourcent(len(complets), len(parcours)) if statuts_saisis else None,
        "satisfaction_moyenne": round(sum(notes) / len(notes), 1) if notes else None,
        "satisfaction_reponses": len(notes), "part_satisfaits": _pourcent(sum(1 for n in notes if n >= 4), len(notes)),
        "territoires": territoires,
        "ecart_couverture": ecart("pour_1000_habitants"), "ecart_femmes": ecart("part_femmes"),
        "zones_ciblees": total_ciblees, "zones_sans_beneficiaire": len(sans_beneficiaire),
        "zones_sans_beneficiaire_exemples": sorted(sans_beneficiaire, key=lambda z: (z["projet"], z["zone"]))[:EXEMPLES_MAX],
        "hors_zone": len(hors_zone_vus),
        "hors_zone_exemples": [{"projet": projet, "zone": zone, "beneficiaires": n}
                               for (projet, zone), n in sorted(hors_zone.items(), key=lambda e: -e[1])[:EXEMPLES_MAX]],
        "coordonnees_renseignees": len(beneficiaires_gps), "coordonnees_invalides": gps_invalides,
        "zones_coordonnees_invalides": len(zones_invalides),
        "couches": [{"nom": c["nom"], "geometrie": c["geometrie"], "objets": c["nombre_objets"], "surface_ha": c["surface_ha"],
                     "longueur_km": c["longueur_km"]}
                    for c in CoucheImportee.objects.values("nom", "geometrie", "nombre_objets", "surface_ha", "longueur_km")],
        "plaintes": nb_dossiers,
        "plaintes_pour_1000": round(nb_dossiers / directs * 1000, 1) if directs else None,
        "taux_plaintes_recurrentes": _pourcent(recurrents, nb_dossiers),
    }
