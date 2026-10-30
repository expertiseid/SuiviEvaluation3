"""
Suivi propre à un document stratégique : pour chaque élément, l'avancement calculé à partir des
projets qui y contribuent (activités rattachées à l'élément ou à un élément en dessous, ou
projets rattachés sans précision d'élément), à côté de ce qui est renseigné directement —
valeurs des indicateurs stratégiques, appréciations par période, pièces justificatives.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum


def sous_arbre(element) -> set:
    """Id de l'élément et de tous ceux en dessous (lien principal)."""
    from .models import ElementStrategique

    ids, a_voir = {element.id}, [element.id]
    while a_voir:
        enfants = list(ElementStrategique.objects.filter(element_parent_id__in=a_voir).values_list("id", flat=True))
        a_voir = [i for i in enfants if i not in ids]
        ids.update(a_voir)
    return ids


def contribution_projets(element, projets_visibles, arbres=None, rattachees_document=None) -> dict:
    """
    Avancement calculé : activités et projets qui contribuent à l'élément (et à ceux en dessous),
    y compris par les documents rattachés en dessous (chaîne des documents, voir chaine.py).
    `arbres` : cache {projet_id: ArbreTaux} partagé entre plusieurs éléments d'un même cadre ;
    `rattachees_document` : activites_rattachees() du document, à calculer une fois pour tous ses éléments.
    """
    from apps.projects.budgets import activites_comptees
    from apps.projects.models import Activite
    from apps.projects.taux import ArbreTaux

    from .chaine import activites_rattachees

    ids = sous_arbre(element)
    if rattachees_document is None:
        rattachees_document = activites_rattachees(element.type_niveau.cadre_strategique, projets_visibles)
    rattachees = [a for a, atteint in rattachees_document if atteint in ids]
    if not rattachees:
        return {"projets": [], "nombre_activites": 0, "taux_physique": None, "budget_alloue": 0, "budget_realise": 0, "taux_financier": None}

    projets = {a.projet_id: a.projet for a in rattachees}
    toutes = list(Activite.objects.filter(projet_id__in=projets).only("id", "activite_parent_id", "projet_id", "budget_alloue", "budget_realise"))
    parent = {a.id: a.activite_parent_id for a in toutes}
    enfants = defaultdict(list)
    for a in toutes:
        enfants[a.activite_parent_id].append(a.id)
    ids_rattaches = {a.id for a in rattachees}

    def a_un_ancetre_rattache(activite_id):
        courant = parent.get(activite_id)
        while courant is not None:
            if courant in ids_rattaches:
                return True
            courant = parent.get(courant)
        return False

    # Sommets : une activité dont un ancêtre est aussi rattaché est déjà comptée à travers lui.
    sommets = [a for a in rattachees if not a_un_ancetre_rattache(a.id)]
    couverts = set()
    for a in sommets:
        pile = [a.id]
        while pile:
            courant = pile.pop()
            couverts.add(courant)
            pile.extend(enfants.get(courant, []))
    alloue_compte = activites_comptees(toutes, "budget_alloue")
    realise_compte = activites_comptees(toutes, "budget_realise")
    budget_alloue = sum((a.budget_alloue for a in toutes if a.id in couverts and a.id in alloue_compte), Decimal("0"))
    budget_realise = sum((a.budget_realise for a in toutes if a.id in couverts and a.id in realise_compte), Decimal("0"))

    arbres = {} if arbres is None else arbres
    for pid, p in projets.items():
        if pid not in arbres:
            arbres[pid] = ArbreTaux(p)
    taux = [t for t in (arbres[a.projet_id].resultat(a.id).taux for a in sommets) if t is not None]
    par_projet = defaultdict(list)
    for a in sommets:
        par_projet[a.projet_id].append(a)
    return {
        "projets": [
            {
                "id": p.id, "code": p.code, "nom": p.nom, "nombre_activites": len(par_projet[pid]),
                "taux_physique": arbres[pid].taux_projet().taux,
            }
            for pid, p in sorted(projets.items(), key=lambda x: x[1].code)
        ],
        "nombre_activites": len(sommets),
        "taux_physique": round(sum(taux) / len(taux), 1) if taux else None,
        "budget_alloue": budget_alloue,
        "budget_realise": budget_realise,
        "taux_financier": round(float(budget_realise) / float(budget_alloue) * 100, 1) if budget_alloue else None,
    }


def piece_jointe(piece, request):
    """Pièce justificative telle qu'affichée : nom et lien de téléchargement."""
    return {
        "id": piece.id, "nom": piece.nom, "telechargement": f"/pieces-justificatives/{piece.id}/telecharger/",
        "ajoute_par": str(piece.uploaded_by) if piece.uploaded_by_id else "",
    }


def indicateurs_element(element, request=None) -> list:
    """Indicateurs rattachés à l'élément : réalisé (saisies approuvées) et, pour ceux saisis directement, leurs valeurs."""
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.indicators.services import taux_realisation

    indicateurs = list(Indicateur.objects.filter(elements_strategiques=element).select_related("projet", "activite__projet").order_by("id"))
    realises = dict(
        ValeurIndicateur.objects.filter(indicateur__in=indicateurs)
        .values("indicateur").annotate(t=Sum("valeur_realisee")).values_list("indicateur", "t")
    )
    resultat = []
    for i in indicateurs:
        projet = i.projet or (i.activite.projet if i.activite_id else None)
        realise = realises.get(i.id, Decimal("0"))
        direct = projet is None
        valeurs = []
        if direct:
            for valeur in ValeurIndicateur.tous.filter(indicateur=i).prefetch_related("pieces_justificatives__uploaded_by").order_by("-periode_fin")[:20]:
                valeurs.append({
                    "id": valeur.id, "periode_debut": valeur.periode_debut, "periode_fin": valeur.periode_fin,
                    "valeur_realisee": valeur.valeur_realisee, "commentaire": valeur.commentaire,
                    "etat_approbation": valeur.etat_approbation,
                    "pieces": [piece_jointe(p, request) for p in valeur.pieces_justificatives.all()],
                })
        resultat.append({
            "id": i.id, "libelle": i.libelle, "unite": i.unite, "valeur_reference": i.valeur_reference,
            "valeur_cible": i.valeur_cible, "frequence_collecte": i.frequence_collecte, "realise": realise,
            "taux": taux_realisation(realise, i.valeur_cible) if i.valeur_cible else None,
            "origine": "Saisie directe" if direct else f"Projet {projet.code}",
            "saisie_directe": direct,
            "valeurs": valeurs,
        })
    return resultat


def suivi_element(element, projets_visibles, request=None) -> dict:
    from .serializers import AppreciationStrategiqueSerializer

    appreciations = element.appreciations.select_related("saisi_par").prefetch_related("pieces_justificatives__uploaded_by")
    return {
        "element": {"id": element.id, "code": element.code, "nom": element.nom, "niveau": element.type_niveau.nom_niveau},
        "calcule": contribution_projets(element, projets_visibles),
        "indicateurs": indicateurs_element(element, request),
        "appreciations": AppreciationStrategiqueSerializer(appreciations, many=True, context={"request": request}).data,
    }
