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

# Indicateurs par zone, regroupés comme les blocs du tableau de bord consolidé :
# (code, libellé, libellé court, famille de couleurs, type de valeur, groupe).
# Famille : projets (bleus), beneficiaires (verts), budget (ocres), taux (rouge → vert).
# Type : entier, montant (FCFA) ou pourcentage. Même catalogue à l'écran (utils/carteParZone.ts).
CATALOGUE = [
    ("projets", "Nombre de projets", "Projets", "projets", "entier", "Vue d'ensemble"),
    ("beneficiaires", "Bénéficiaires inscrits", "Bénéficiaires", "beneficiaires", "entier", "Vue d'ensemble"),
    ("budget", "Budget des projets présents (FCFA)", "Budget", "budget", "montant", "Vue d'ensemble"),
    ("fonds_propres", "Fonds propres (FCFA)", "Fonds propres", "budget", "montant", "Budget et financements"),
    ("financements", "Financements des bailleurs (FCFA)", "Financements", "budget", "montant", "Budget et financements"),
    ("depenses", "Dépenses réalisées (FCFA)", "Dépenses", "budget", "montant", "Budget et financements"),
    ("bailleurs", "Nombre de bailleurs", "Bailleurs", "projets", "entier", "Budget et financements"),
    ("partenaires_consortium", "Nombre de partenaires de consortium", "Consortium", "projets", "entier", "Budget et financements"),
    ("partenaires_mise_en_oeuvre", "Nombre de partenaires de mise en œuvre", "Mise en œuvre", "projets", "entier", "Budget et financements"),
    ("projets_en_cours", "Projets en cours", "En cours", "projets", "entier", "Projets"),
    ("projets_en_preparation", "Projets en préparation", "En préparation", "projets", "entier", "Projets"),
    ("projets_clotures", "Projets clôturés", "Clôturés", "projets", "entier", "Projets"),
    ("activites", "Nombre d'activités", "Activités", "projets", "entier", "Projets"),
    ("activites_realisees", "Activités réalisées", "Réalisées", "projets", "entier", "Projets"),
    ("activites_en_cours", "Activités en cours", "Act. en cours", "projets", "entier", "Projets"),
    ("activites_non_realisees", "Activités non réalisées", "Non réalisées", "projets", "entier", "Projets"),
    ("indicateurs", "Nombre d'indicateurs", "Indicateurs", "projets", "entier", "Projets"),
    ("taux_physique", "Exécution physique moyenne (%)", "Exécution physique", "taux", "pourcentage", "Projets"),
    ("taux_financier", "Exécution financière moyenne (%)", "Exécution financière", "taux", "pourcentage", "Projets"),
    ("cible_totale", "Cible totale des projets", "Cible", "beneficiaires", "entier", "Bénéficiaires"),
    ("cible_femmes", "Cible femmes", "Cible femmes", "beneficiaires", "entier", "Bénéficiaires"),
    ("cible_hommes", "Cible hommes", "Cible hommes", "beneficiaires", "entier", "Bénéficiaires"),
    ("cible_jeunes", "Cible jeunes", "Cible jeunes", "beneficiaires", "entier", "Bénéficiaires"),
    ("cible_pdi", "Cible personnes déplacées (PDI)", "Cible PDI", "beneficiaires", "entier", "Bénéficiaires"),
    ("femmes", "Bénéficiaires inscrites (femmes)", "Femmes", "beneficiaires", "entier", "Bénéficiaires"),
    ("hommes", "Bénéficiaires inscrits (hommes)", "Hommes", "beneficiaires", "entier", "Bénéficiaires"),
    ("nouveaux_beneficiaires", "Nouveaux bénéficiaires inscrits (12 derniers mois)", "Nouveaux bénéf.", "beneficiaires", "entier", "Évolution dans le temps"),
    ("depenses_12_mois", "Dépenses des 12 derniers mois (FCFA)", "Dépenses 12 mois", "budget", "montant", "Évolution dans le temps"),
]
INDICATEURS = {code: libelle for code, libelle, *_ in CATALOGUE}
COURTS = {code: court for code, _, court, *_ in CATALOGUE}
FAMILLES = {code: famille for code, _, _, famille, *_ in CATALOGUE}
TYPES = {code: type_valeur for code, _, _, _, type_valeur, _ in CATALOGUE}

# Valeurs additionnées projet par projet (un projet compte dans chaque zone où il est présent).
_SOMMES = ("budget", "fonds_propres", "financements", "depenses", "depenses_12_mois", "activites", "activites_realisees",
           "activites_en_cours", "activites_non_realisees", "indicateurs", "cible_totale", "cible_femmes", "cible_hommes",
           "cible_jeunes", "cible_pdi")
# Valeurs comptées sans doublon (un même bailleur sur deux projets de la zone compte une fois).
_ENSEMBLES = ("bailleurs", "partenaires_consortium", "partenaires_mise_en_oeuvre")


def ids_parametre(params, nom) -> list[int]:
    """Identifiants d'un paramètre de requête : ?zone=1,2 ou ?zone=1&zone=2 (un seul aussi)."""
    return [int(x) for valeur in params.getlist(nom) for x in str(valeur).split(",") if x.strip().isdigit()]


def _chiffres_projets(projets) -> dict:
    """Chiffres de chaque projet nécessaires aux indicateurs par zone, en quelques requêtes."""
    from datetime import timedelta

    from django.db.models import Count, Q, Sum
    from django.utils import timezone

    from apps.indicators.models import Indicateur
    from apps.partners.models import Financement, RallongeFinancement
    from apps.projects.budgets import total_budget
    from apps.projects.models import Activite, PartenaireProjet
    from apps.suivi.models import PointSuivi

    ids = [p.id for p in projets]
    il_y_a_un_an = timezone.localdate() - timedelta(days=365)
    chiffres = {p.id: {
        "budget": Decimal(p.budget_total or 0), "fonds_propres": Decimal(p.fonds_propres or 0), "financements": Decimal("0"),
        "depenses": Decimal("0"), "depenses_12_mois": Decimal("0"), "activites": 0, "activites_realisees": 0,
        "activites_en_cours": 0, "activites_non_realisees": 0, "indicateurs": 0,
        "cible_totale": p.cible_totale or 0, "cible_femmes": p.cible_femmes or 0, "cible_hommes": p.cible_hommes or 0,
        "cible_jeunes": p.cible_jeunes or 0, "cible_pdi": p.cible_pdi or 0,
        "bailleurs": set(), "partenaires_consortium": {c.id for c in p.partenaires_consortium.all()},
        "partenaires_mise_en_oeuvre": {p.partenaire_mise_en_oeuvre_id} if p.partenaire_mise_en_oeuvre_id else set(),
    } for p in projets}
    for pid, bailleur, montant in Financement.objects.filter(projet_id__in=ids).values_list("projet_id", "bailleur_id", "montant_finance"):
        chiffres[pid]["bailleurs"].add(bailleur)
        chiffres[pid]["financements"] += montant
    for r in RallongeFinancement.objects.filter(financement__projet_id__in=ids).values("financement__projet_id").annotate(t=Sum("montant")):
        chiffres[r["financement__projet_id"]]["financements"] += r["t"]
    for pid, partenaire, nature in PartenaireProjet.objects.filter(projet_id__in=ids).values_list("projet_id", "partenaire_id", "nature"):
        cle = "partenaires_consortium" if nature == PartenaireProjet.Nature.CONSORTIUM else "partenaires_mise_en_oeuvre"
        chiffres[pid][cle].add(partenaire)
    activites_par_projet = {}
    for a in Activite.objects.filter(projet_id__in=ids).only("id", "projet_id", "activite_parent_id", "statut", "budget_realise"):
        activites_par_projet.setdefault(a.projet_id, []).append(a)
        chiffres[a.projet_id]["activites"] += 1
        chiffres[a.projet_id][{"REALISEE": "activites_realisees", "EN_COURS": "activites_en_cours"}.get(a.statut, "activites_non_realisees")] += 1
    for pid, activites in activites_par_projet.items():
        chiffres[pid]["depenses"] = total_budget([a for a in activites if a.budget_realise is not None], "budget_realise")
    for r in PointSuivi.objects.filter(activite__projet_id__in=ids, periode_fin__gte=il_y_a_un_an, budget_realise__isnull=False).values(
        "activite__projet_id"
    ).annotate(t=Sum("budget_realise")):
        chiffres[r["activite__projet_id"]]["depenses_12_mois"] = r["t"]
    for r in (
        Indicateur.objects.filter(Q(projet_id__in=ids) | Q(activite__projet_id__in=ids))
        .values("projet_id", "activite__projet_id").annotate(n=Count("id"))
    ):
        chiffres[r["projet_id"] or r["activite__projet_id"]]["indicateurs"] += r["n"]
    return chiffres


def synthese_par_zone(pays, ordre, projets_visibles, projets=None, dans_zones=None) -> dict:
    """
    `ordre` : niveau des zones (1 = régions…) ; `projets` : limiter à ces projets (liste d'id) ;
    `dans_zones` : limiter aux zones situées dans l'une de ces zones (ou elles-mêmes).
    """
    from datetime import timedelta

    from django.utils import timezone

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
    if dans_zones:
        garder = set()
        for dans_zone in dans_zones:
            if dans_zone.niveau_administratif.ordre <= ordre:
                garder.update(descendants_au_niveau(dans_zone.id))
            else:
                garder.add(ancetre_au_niveau(dans_zone.id))
        cibles = {i: z for i, z in cibles.items() if i in garder}

    filtre_projets = projets
    projets = Projet.objects.filter(id__in=projets_visibles).prefetch_related("zones", "partenaires_consortium")
    if filtre_projets:
        projets = projets.filter(id__in=filtre_projets)
    projets = list(projets)
    chiffres = _chiffres_projets(projets)
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
    nouveaux_zone = defaultdict(set)
    il_y_a_un_an = timezone.localdate() - timedelta(days=365)
    sexes = {}
    for b_id, sexe, zid, pid, inscription in ParticipationProjet.objects.filter(
        projet_id__in=[p.id for p in projets], beneficiaire__zone_id__isnull=False
    ).values_list("beneficiaire_id", "beneficiaire__sexe", "beneficiaire__zone_id", "projet_id", "date_inscription"):
        cible = ancetre_au_niveau(zid)
        if cible in cibles:
            benef_zone[cible].add(b_id)
            benef_zone_projet[cible][pid].add(b_id)
            presence[cible].add(pid)
            sexes[b_id] = sexe
            if inscription and inscription >= il_y_a_un_an:
                nouveaux_zone[cible].add(b_id)

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
        valeurs = {
            "projets": len(lignes),
            "beneficiaires": len(beneficiaires),
            "femmes": sum(1 for b in beneficiaires if sexes.get(b) == "F"),
            "hommes": sum(1 for b in beneficiaires if sexes.get(b) != "F"),
            "nouveaux_beneficiaires": len(nouveaux_zone.get(zid, ())),
            "taux_physique": round(sum(physiques) / len(physiques), 1) if physiques else None,
            "taux_financier": round(sum(financiers) / len(financiers), 1) if financiers else None,
            "projets_en_cours": sum(1 for l in lignes if l["statut"] == "EN_COURS"),
            "projets_en_preparation": sum(1 for l in lignes if l["statut"] == "EN_PREPARATION"),
            "projets_clotures": sum(1 for l in lignes if l["statut"] == "CLOTURE"),
        }
        for cle in _SOMMES:
            valeurs[cle] = float(sum((Decimal(chiffres[pid][cle]) for pid in ids), Decimal("0")))
        for cle in _ENSEMBLES:
            valeurs[cle] = len(set().union(*(chiffres[pid][cle] for pid in ids)))
        resultat.append({
            "zone": zid, "nom": zone.nom, "nom_contour": nom_contour, "lat": lat, "lng": lng,
            **{cle: valeurs[cle] for cle in ("projets", "beneficiaires", "femmes", "hommes", "budget", "taux_physique", "taux_financier")},
            "valeurs": valeurs,
            "liste_projets": lignes,
        })
    return {"niveau": {"ordre": ordre, "nom": niveau.nom_niveau}, "zones": resultat}
