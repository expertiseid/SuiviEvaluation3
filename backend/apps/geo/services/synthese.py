"""
Synthèse par zone pour la carte (régions, provinces ou communes) : projets présents,
bénéficiaires, budget et taux d'exécution, pour colorer les zones et détailler chacune.

Un projet est présent dans une zone s'il intervient dans cette zone, dans une zone plus large
qui la contient (un projet régional couvre ses provinces), dans une zone qu'elle contient, ou
s'il intervient sur tout le pays ; ou encore s'il a des bénéficiaires qui y habitent.
Le budget d'une zone est celui des projets présents (un projet sur plusieurs zones compte dans
chacune : c'est le budget engagé dans la zone, pas une répartition).
"""
from collections import defaultdict
from decimal import Decimal

INDICATEURS = {
    "projets": "Nombre de projets",
    "beneficiaires": "Bénéficiaires",
    "budget": "Budget des projets présents (FCFA)",
    "taux_physique": "Exécution physique moyenne (%)",
    "taux_financier": "Exécution financière moyenne (%)",
}


def synthese_par_zone(pays, ordre, projets_visibles, projet=None, dans_zone=None) -> dict:
    """
    `ordre` : niveau des zones (1 = régions…) ; `projet` : limiter à un projet ;
    `dans_zone` : limiter aux zones situées dans cette zone (ou elle-même).
    """
    from apps.beneficiaries.models import ParticipationProjet
    from apps.projects.models import Projet
    from apps.reports.services import taux_execution_financiere_global, taux_execution_physique_global

    from ..models import LimiteAdministrative, NiveauAdministratif, Zone
    from .limites import normaliser_nom

    niveau = NiveauAdministratif.objects.filter(pays=pays, ordre=ordre).first()
    if niveau is None:
        return {"niveau": None, "zones": []}
    zones = list(Zone.objects.filter(niveau_administratif__pays=pays).select_related("niveau_administratif"))
    parent = {z.id: z.parent_id for z in zones}
    ordre_de = {z.id: z.niveau_administratif.ordre for z in zones}
    enfants = defaultdict(list)
    for z in zones:
        enfants[z.parent_id].append(z.id)

    def ancetre_au_niveau(zid):
        while zid is not None and ordre_de.get(zid, 0) > ordre:
            zid = parent.get(zid)
        return zid if zid is not None and ordre_de.get(zid) == ordre else None

    def descendants_au_niveau(zid):
        resultat, pile = [], [zid]
        while pile:
            courant = pile.pop()
            if ordre_de.get(courant) == ordre:
                resultat.append(courant)
            elif ordre_de.get(courant, 0) < ordre:
                pile.extend(enfants.get(courant, []))
        return resultat

    cibles = {z.id: z for z in zones if z.niveau_administratif.ordre == ordre}
    if dans_zone is not None:
        if dans_zone.niveau_administratif.ordre <= ordre:
            garder = set(descendants_au_niveau(dans_zone.id))
        else:
            garder = {ancetre_au_niveau(dans_zone.id)}
        cibles = {i: z for i, z in cibles.items() if i in garder}

    projets = Projet.objects.filter(id__in=projets_visibles).prefetch_related("zones")
    if projet is not None:
        projets = projets.filter(id=projet)
    projets = list(projets)
    presence = defaultdict(set)  # zone -> projets
    for p in projets:
        if p.tout_le_pays and pays in (p.pays or []):
            for zid in cibles:
                presence[zid].add(p.id)
            continue
        for z in p.zones.all():
            if z.id not in ordre_de:
                continue
            if ordre_de[z.id] >= ordre:
                cible = ancetre_au_niveau(z.id)
                if cible:
                    presence[cible].add(p.id)
            else:
                for cible in descendants_au_niveau(z.id):
                    presence[cible].add(p.id)

    # Bénéficiaires par zone et par projet (selon leur localité).
    benef_zone = defaultdict(set)
    benef_zone_projet = defaultdict(lambda: defaultdict(set))
    sexes = {}
    for b_id, sexe, zid, pid in ParticipationProjet.objects.filter(
        projet_id__in=[p.id for p in projets], beneficiaire__zone_id__isnull=False
    ).values_list("beneficiaire_id", "beneficiaire__sexe", "beneficiaire__zone_id", "projet_id"):
        cible = ancetre_au_niveau(zid)
        if cible in cibles:
            benef_zone[cible].add(b_id)
            benef_zone_projet[cible][pid].add(b_id)
            presence[cible].add(pid)
            sexes[b_id] = sexe

    par_id = {p.id: p for p in projets}
    taux = {}

    def taux_de(pid):
        if pid not in taux:
            p = par_id[pid]
            taux[pid] = (taux_execution_physique_global(p), taux_execution_financiere_global(p))
        return taux[pid]

    # Points d'étiquette : ceux des contours chargés (même nom), sinon le centre de la zone.
    etiquettes = {}
    limite = LimiteAdministrative.objects.filter(pays=pays, niveau=ordre).first()
    if limite:
        for f in limite.geojson.get("features", []):
            props = f.get("properties") or {}
            if props.get("lat") is not None:
                etiquettes[normaliser_nom(props.get("shapeName", ""))] = (props["lat"], props["lng"], props.get("shapeName"))

    resultat = []
    for zid, zone in sorted(cibles.items(), key=lambda x: x[1].nom):
        ids = sorted(presence.get(zid, ()), key=lambda i: par_id[i].code)
        lignes = []
        for pid in ids:
            p = par_id[pid]
            physique, financier = taux_de(pid)
            lignes.append({
                "id": p.id, "code": p.code, "nom": p.nom, "statut": p.statut, "budget": float(p.budget_total or 0),
                "taux_physique": physique, "taux_financier": financier,
                "beneficiaires": len(benef_zone_projet[zid].get(pid, ())),
            })
        physiques = [l["taux_physique"] for l in lignes if l["taux_physique"] is not None]
        financiers = [l["taux_financier"] for l in lignes if l["taux_financier"] is not None]
        beneficiaires = benef_zone.get(zid, set())
        lat, lng, nom_contour = etiquettes.get(normaliser_nom(zone.nom), (
            float(zone.latitude) if zone.latitude is not None else None,
            float(zone.longitude) if zone.longitude is not None else None, None))
        resultat.append({
            "zone": zid, "nom": zone.nom, "nom_contour": nom_contour, "lat": lat, "lng": lng,
            "projets": len(lignes),
            "beneficiaires": len(beneficiaires),
            "femmes": sum(1 for b in beneficiaires if sexes.get(b) == "F"),
            "hommes": sum(1 for b in beneficiaires if sexes.get(b) != "F"),
            "budget": float(sum((Decimal(str(l["budget"])) for l in lignes), Decimal("0"))),
            "taux_physique": round(sum(physiques) / len(physiques), 1) if physiques else None,
            "taux_financier": round(sum(financiers) / len(financiers), 1) if financiers else None,
            "liste_projets": lignes,
        })
    return {"niveau": {"ordre": ordre, "nom": niveau.nom_niveau}, "zones": resultat}
