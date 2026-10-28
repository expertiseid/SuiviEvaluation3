"""
Données de la carte des bénéficiaires (écran et carte imprimable) : points GPS, regroupements
au centre des localités, et filtre facultatif sur une zone (région, province, commune…).
"""
from collections import Counter


def zones_du_sous_arbre(zone) -> set:
    from apps.geo.models import Zone

    ids, a_voir = {zone.id}, [zone.id]
    while a_voir:
        a_voir = [i for i in Zone.objects.filter(parent_id__in=a_voir).values_list("id", flat=True) if i not in ids]
        ids.update(a_voir)
    return ids


def contour_zone(zone):
    """Géométrie GeoJSON de la zone dans les contours chargés (même niveau, même nom), sinon None."""
    from apps.geo.models import LimiteAdministrative
    from apps.geo.services.limites import normaliser_nom

    niveau = zone.niveau_administratif
    limite = LimiteAdministrative.objects.filter(pays=niveau.pays, niveau=niveau.ordre).first()
    if limite is None:
        return None
    cible = normaliser_nom(zone.nom)
    for feature in limite.geojson.get("features", []):
        if normaliser_nom((feature.get("properties") or {}).get("shapeName", "")) == cible:
            return feature.get("geometry")
    return None


def donnees_carte(beneficiaires, zone=None) -> dict:
    """`beneficiaires` : queryset déjà limité (droits, projet) ; `zone` : filtre facultatif."""
    from apps.geo.services.limites import _dans_polygone

    beneficiaires = beneficiaires.select_related("zone")
    if zone is not None:
        ids = zones_du_sous_arbre(zone)
        contour = contour_zone(zone)
        retenus = []
        for b in beneficiaires:
            if b.zone_id in ids:
                retenus.append(b)
            elif b.zone_id is None and contour and b.latitude is not None and b.longitude is not None:
                if _dans_polygone(float(b.latitude), float(b.longitude), contour):
                    retenus.append(b)
        beneficiaires = retenus
    else:
        beneficiaires = list(beneficiaires)

    points, par_zone, non_localises, positions = [], {}, 0, {}

    def position(z):
        depart = z
        while z is not None:
            if z.latitude is not None:
                positions[depart.id] = z
                return z
            z = z.parent
        positions[depart.id] = None
        return None

    for b in beneficiaires:
        if b.latitude is not None and b.longitude is not None:
            points.append({
                "id": b.id, "nom": str(b), "identifiant": b.identifiant, "sexe": b.sexe,
                "lat": float(b.latitude), "lng": float(b.longitude),
            })
            continue
        z = positions[b.zone_id] if b.zone_id in positions else (position(b.zone) if b.zone else None)
        if z is None:
            non_localises += 1
            continue
        groupe = par_zone.setdefault(z.id, {
            "zone": z.id, "nom": z.nom, "lat": float(z.latitude), "lng": float(z.longitude),
            "nombre": 0, "femmes": 0, "hommes": 0,
        })
        groupe["nombre"] += 1
        groupe["femmes" if b.sexe == "F" else "hommes"] += 1
    pays = Counter(b.pays for b in beneficiaires if b.pays).most_common(1)
    return {
        "pays": (zone.niveau_administratif.pays if zone else None) or (pays[0][0] if pays else "BF"),
        "total": len(beneficiaires),
        "femmes": sum(1 for b in beneficiaires if b.sexe == "F"),
        "hommes": sum(1 for b in beneficiaires if b.sexe != "F"),
        "points": points,
        "zones": sorted(par_zone.values(), key=lambda g: -g["nombre"]),
        "non_localises": non_localises,
        "zone_filtre": {
            "id": zone.id, "nom": zone.nom, "niveau": zone.niveau_administratif.nom_niveau,
            "ordre": zone.niveau_administratif.ordre, "contour": contour_zone(zone),
        } if zone else None,
    }
