"""
Performance des indicateurs au tableau de bord : référence, valeur actuelle, cible, écart à la cible, taux
d'atteinte et tendance de chaque indicateur ; indicateurs ayant atteint leur cible, en progrès ou en recul ;
éléments de la planification (produits, effets…) dont tous les indicateurs ont atteint leur cible ; documents
de la chaîne stratégique (programmes, plans d'action…) dont relèvent les projets.

Mêmes règles que la fiche indicateur (apps.indicators.services) : saisies approuvées seulement, taux None
quand il n'est pas calculable, sens « plus bas = mieux » respecté.
"""
from collections import defaultdict

from apps.core.vocabulaire import v


LISTE_MAX = 200  # les moins avancés d'abord : le tableau de bord reste léger


def _niveau(indicateur, valeur):
    """Niveau atteint, comparable à la cible : référence + saisies pour une progression cumulable."""
    from apps.indicators.models import Indicateur

    if valeur is None:
        return None
    if (indicateur.calcul_taux == Indicateur.CalculTaux.PROGRESSION and indicateur.valeur_reference is not None
            and indicateur.agregation == Indicateur.Agregation.SOMME and not indicateur.formule):
        return indicateur.valeur_reference + valeur
    return valeur


def ecart_a_la_cible(indicateur, valeur):
    """Ce qu'il reste à faire pour atteindre la cible (négatif : dépassée), dans le sens de l'indicateur."""
    from apps.indicators.models import Indicateur

    niveau = _niveau(indicateur, valeur)
    if niveau is None:
        return None
    return indicateur.valeur_cible - niveau if indicateur.sens == Indicateur.Sens.HAUSSE else niveau - indicateur.valeur_cible


def _tendances(indicateurs) -> dict:
    """
    Tendance entre les deux dernières périodes saisies : {numéro : (écart, progrès ?)} — progrès None si stable.
    Seulement pour les niveaux mesurés (dernière valeur) : pour un indicateur cumulable, une période plus faible
    que la précédente reste un progrès du total.
    """
    from apps.indicators.models import Indicateur, ValeurIndicateur

    dernieres = defaultdict(list)
    for numero, valeur in (ValeurIndicateur.objects.filter(indicateur__in=[
            i.pk for i in indicateurs if not i.formule and i.agregation == Indicateur.Agregation.DERNIERE])
                           .order_by("indicateur_id", "-periode_fin", "-id").values_list("indicateur_id", "valeur_realisee")):
        if len(dernieres[numero]) < 2:
            dernieres[numero].append(valeur)
    resultat = {}
    for i in indicateurs:
        deux = dernieres.get(i.pk, [])
        if len(deux) == 2:
            ecart = deux[0] - deux[1]
            resultat[i.pk] = (ecart, None if ecart == 0 else (ecart > 0) == (i.sens == Indicateur.Sens.HAUSSE))
    return resultat


def _profondeurs(activite_ids) -> dict:
    """Profondeur de chaque élément de planification (0 = premier niveau sous le projet)."""
    from apps.projects.models import Activite

    parents = dict(Activite.objects.filter(projet__activites__id__in=activite_ids).distinct()
                   .values_list("id", "activite_parent_id"))
    memo = {}

    def profondeur(a):
        if a not in memo:
            parent = parents.get(a)
            memo[a] = 0 if parent is None else profondeur(parent) + 1
        return memo[a]

    return {a: profondeur(a) for a in activite_ids if a in parents}


def performance(indicateurs, projet_ids) -> dict:
    from apps.indicators.models import Indicateur
    from apps.indicators.services import taux_indicateur, valeurs_actuelles
    from apps.projects.models import Activite, NiveauActivite, Projet

    elements = list(indicateurs.select_related("projet", "activite__projet"))
    valeurs = valeurs_actuelles(elements)
    tendances = _tendances(elements)
    liste = []
    for i in elements:
        valeur = valeurs.get(i.pk)
        niveau = _niveau(i, valeur)
        taux = taux_indicateur(i, valeur) if valeur is not None else None
        tendance = tendances.get(i.pk)
        projet = i.projet or (i.activite.projet if i.activite_id else None)
        liste.append({
            "id": i.pk, "libelle": i.libelle[:160], "unite": i.unite, "projet": projet.code if projet else "",
            "reference": i.valeur_reference, "actuelle": niveau, "cible": i.valeur_cible,
            "ecart": ecart_a_la_cible(i, valeur),
            "taux": taux, "calcule": bool(i.formule), "sens": i.sens,
            "tendance": None if tendance is None else ("stable" if tendance[1] is None else "progres" if tendance[1] else "recul"),
            "variation": tendance[0] if tendance else None,
            "activite_id": i.activite_id, "poids": i.poids,
        })

    renseignes = [x for x in liste if x["actuelle"] is not None]
    avec_taux = [x for x in liste if x["taux"] is not None]
    atteints = [x for x in avec_taux if x["taux"] >= 100]
    compter = lambda t: sum(1 for x in liste if x["tendance"] == t)
    avec_tendance = sum(1 for x in liste if x["tendance"])

    def part(n, total):
        return round(n / total * 100, 1) if total else None

    # Éléments de la planification (produit, effet, résultat…) : atteint quand tous ses indicateurs le sont.
    par_element = defaultdict(list)
    for x in liste:
        if x["activite_id"]:
            par_element[x["activite_id"]].append(x)
    profondeurs = _profondeurs(list(par_element))
    projets_elements = dict(Activite.objects.filter(id__in=par_element).values_list("id", "projet_id"))
    noms = {(n.projet_id, n.profondeur): n.nom_niveau for n in NiveauActivite.objects.filter(projet_id__in=set(projets_elements.values()))}
    niveaux = defaultdict(lambda: {"elements": 0, "atteints": 0, "mesures": 0})
    for element, xs in par_element.items():
        nom = noms.get((projets_elements.get(element), profondeurs.get(element)), v("Activité"))
        ligne = niveaux[nom]
        ligne["elements"] += 1
        if any(x["taux"] is not None for x in xs):
            ligne["mesures"] += 1
            if all(x["taux"] is not None and x["taux"] >= 100 for x in xs):
                ligne["atteints"] += 1
    par_niveau = sorted(({"niveau": nom, **l, "part": part(l["atteints"], l["mesures"])} for nom, l in niveaux.items()),
                        key=lambda l: -l["elements"])

    # Documents de la chaîne stratégique dont relèvent les projets (et leurs documents parents).
    documents = {}
    a_voir = set(Projet.objects.filter(id__in=projet_ids, cadre_strategique__isnull=False).values_list("cadre_strategique_id", flat=True))
    from apps.strategy.models import CadreStrategique

    while a_voir:
        lus = list(CadreStrategique.objects.filter(id__in=a_voir).values("id", "document_parent_id", "type_document__nom_pluriel"))
        documents.update({d["id"]: d["type_document__nom_pluriel"] or v("Stratégies") for d in lus})
        a_voir = {d["document_parent_id"] for d in lus if d["document_parent_id"] and d["document_parent_id"] not in documents}
    par_type = defaultdict(int)
    for nom in documents.values():
        par_type[nom] += 1

    # Score de performance : moyenne des taux d'atteinte (plafonnés à 100 %) pondérée par le poids de chaque
    # indicateur (vide : 1), sur les indicateurs dont le taux est calculable.
    def score(lignes):
        ponderes = [(min(x["taux"], 100), float(x["poids"] if x["poids"] is not None else 1)) for x in lignes if x["taux"] is not None]
        total = sum(p for _, p in ponderes)
        return round(sum(t * p for t, p in ponderes) / total, 1) if total else None

    par_projet = defaultdict(list)
    for x in liste:
        par_projet[x["projet"]].append(x)
    scores = sorted(({"projet": code, "score": score(lignes), "indicateurs": len(lignes)} for code, lignes in par_projet.items()),
                    key=lambda l: (l["score"] is None, l["score"] if l["score"] is not None else 0))
    score_global, avec_poids = score(liste), sum(1 for x in liste if x["poids"] is not None)

    taux_projets = defaultdict(list)
    for x in liste:
        del x["activite_id"], x["poids"]
        if x["taux"] is not None:
            taux_projets[x["projet"]].append(x["taux"])
    liste.sort(key=lambda x: (x["taux"] is None, x["taux"] if x["taux"] is not None else 0))
    return {
        "total": len(liste), "renseignes": len(renseignes), "part_renseignes": part(len(renseignes), len(liste)),
        "avec_taux": len(avec_taux), "atteints": len(atteints), "part_atteints": part(len(atteints), len(avec_taux)),
        "en_progres": compter("progres"), "en_recul": compter("recul"), "stables": compter("stable"),
        "part_en_progres": part(compter("progres"), avec_tendance), "part_en_recul": part(compter("recul"), avec_tendance),
        "score": score_global, "indicateurs_ponderes": avec_poids, "scores_projets": scores,
        "par_niveau": par_niveau,
        "documents": [{"type": t, "nombre": n} for t, n in sorted(par_type.items())],
        "liste": liste[:LISTE_MAX],
        # Taux moyen des indicateurs de chaque projet (pour la performance par territoire).
        "taux_par_projet": {code: round(sum(t) / len(t), 1) for code, t in taux_projets.items()},
    }
