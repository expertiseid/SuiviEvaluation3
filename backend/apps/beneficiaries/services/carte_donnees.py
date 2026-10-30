"""
Données de la carte des bénéficiaires (écran et carte imprimable) : points GPS, regroupements
au centre des localités, et filtre facultatif sur une ou plusieurs zones (région, province, commune…).
"""
from collections import Counter

from ..serializers import calculer_age, tranche_age_de


# Bénéficiaires listés par localité (au-delà, la liste est tronquée : voir l'écran Bénéficiaires).
LISTE_MAX = 300


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


def contour_des_zones(zones):
    """Contour réunissant ceux des zones (GeoJSON), ou None si aucune n'a de contour chargé."""
    contours = [c for c in (contour_zone(z) for z in zones) if c]
    if len(contours) <= 1:
        return contours[0] if contours else None
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    return mapping(unary_union([shape(c) for c in contours]))


def zone_filtre(zones):
    """Description du filtre de zone(s) pour l'écran et la carte imprimée (None sans filtre)."""
    if not zones:
        return None
    niveaux = {z.niveau_administratif.nom_niveau for z in zones}
    return {
        "id": zones[0].id if len(zones) == 1 else None,
        "ids": [z.id for z in zones],
        "nom": ", ".join(z.nom for z in zones),
        "niveau": niveaux.pop() if len(niveaux) == 1 else "Zones",
        "ordre": min(z.niveau_administratif.ordre for z in zones),
        "contour": contour_des_zones(zones),
    }


def donnees_carte(beneficiaires, zones=None) -> dict:
    """`beneficiaires` : queryset déjà limité (droits, projets) ; `zones` : filtre facultatif (liste)."""
    from apps.geo.services.limites import _dans_polygone

    zones = list(zones or [])
    beneficiaires = beneficiaires.select_related("zone").prefetch_related("participations__projet")
    if zones:
        ids = set().union(*(zones_du_sous_arbre(z) for z in zones))
        contours = [c for c in (contour_zone(z) for z in zones) if c]
        retenus = []
        for b in beneficiaires:
            if b.zone_id in ids:
                retenus.append(b)
            elif b.zone_id is None and contours and b.latitude is not None and b.longitude is not None:
                if any(_dans_polygone(float(b.latitude), float(b.longitude), c) for c in contours):
                    retenus.append(b)
        beneficiaires = retenus
    else:
        beneficiaires = list(beneficiaires)

    points, par_zone, non_localises, positions = [], {}, 0, {}

    def fiche(b):
        """Ce qu'on montre d'un bénéficiaire sur la carte (survol, liste, carte imprimée)."""
        return {
            "id": b.id, "nom": str(b), "identifiant": b.identifiant, "sexe": b.sexe,
            "tranche_age": tranche_age_de(calculer_age(b.date_naissance)), "telephone": b.telephone,
            "projets": sorted({p.projet.code for p in b.participations.all()}), "localite": b.zone.nom if b.zone else "",
        }

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
            points.append({**fiche(b), "lat": float(b.latitude), "lng": float(b.longitude)})
            continue
        z = positions[b.zone_id] if b.zone_id in positions else (position(b.zone) if b.zone else None)
        if z is None:
            non_localises += 1
            continue
        groupe = par_zone.setdefault(z.id, {
            "zone": z.id, "nom": z.nom, "lat": float(z.latitude), "lng": float(z.longitude),
            "nombre": 0, "femmes": 0, "hommes": 0, "beneficiaires": [],
        })
        groupe["nombre"] += 1
        if len(groupe["beneficiaires"]) < LISTE_MAX:
            groupe["beneficiaires"].append(fiche(b))
        groupe["femmes" if b.sexe == "F" else "hommes"] += 1
    pays = Counter(b.pays for b in beneficiaires if b.pays).most_common(1)
    return {
        "pays": (zones[0].niveau_administratif.pays if zones else None) or (pays[0][0] if pays else "BF"),
        "total": len(beneficiaires),
        "femmes": sum(1 for b in beneficiaires if b.sexe == "F"),
        "hommes": sum(1 for b in beneficiaires if b.sexe != "F"),
        "points": points,
        "zones": sorted(par_zone.values(), key=lambda g: -g["nombre"]),
        "non_localises": non_localises,
        "zone_filtre": zone_filtre(zones),
    }


def projets_des_zones(zones, projets_visibles) -> list:
    """
    Projets (visibles) qui interviennent dans l'une des zones ou une zone en dessous : par leurs zones
    d'intervention, « tout le pays », ou parce qu'ils ont des bénéficiaires qui y habitent —
    avec le nombre de ces bénéficiaires (pour filtrer la carte projet par projet).
    """
    from django.db.models import Count, Q

    from apps.projects.models import Projet

    from ..models import ParticipationProjet

    ids = set().union(*(zones_du_sous_arbre(z) for z in zones))
    pays = zones[0].niveau_administratif.pays
    par_projet = dict(
        ParticipationProjet.objects.filter(projet_id__in=projets_visibles, beneficiaire__zone_id__in=ids)
        .values("projet").annotate(n=Count("beneficiaire", distinct=True)).values_list("projet", "n")
    )
    projets = Projet.objects.filter(id__in=projets_visibles).filter(
        Q(zones__id__in=ids) | Q(id__in=par_projet) | Q(tout_le_pays=True, pays__contains=[pays])
    ).distinct().order_by("code")
    return [
        {"id": p.id, "code": p.code, "nom": p.nom, "statut": p.statut, "beneficiaires": par_projet.get(p.id, 0)}
        for p in projets
    ]
