"""
Budgets sans double compte (règle A).

Un budget peut être saisi à n'importe quel niveau de la planification. Si un niveau (ex. un
pilier) et les éléments placés en dessous ont tous un budget, ceux d'en dessous en sont le
détail : les additionner tous compterait la même somme deux fois.

Règle : dans chaque branche, seul compte le budget du niveau le plus bas où il est saisi.
Un niveau dont des éléments en dessous ont un budget ne sert que de contrôle :
- avertissement si la somme d'en dessous dépasse son propre budget ;
- avertissement si une partie de son budget n'est répartie sur aucun élément en dessous
  (cette partie n'est pas comptée).

La règle s'applique séparément au budget alloué et au budget dépensé (un budget alloué au
pilier et des dépenses saisies sur ses activités restent tous deux comptés).
"""
from decimal import Decimal


def _a_valeur(valeur) -> bool:
    return valeur is not None and valeur != 0


def ids_comptes(noeuds) -> set:
    """
    noeuds : [(id, parent_id, valeur)]. Renvoie les id dont la valeur est comptée : valeur
    renseignée et aucun élément en dessous (à n'importe quelle profondeur) n'en a une.
    """
    noeuds = list(noeuds)
    parents = {i: p for i, p, _ in noeuds}
    masques = set()
    for i, _, valeur in noeuds:
        if not _a_valeur(valeur):
            continue
        courant = parents.get(i)
        while courant is not None and courant not in masques:
            masques.add(courant)
            courant = parents.get(courant)
    # Un ancêtre déjà masqué a forcément ses propres ancêtres masqués : la boucle peut s'arrêter.
    return {i for i, _, valeur in noeuds if _a_valeur(valeur) and i not in masques}


def _noeuds(activites, champ):
    return [(a.id, a.activite_parent_id, getattr(a, champ)) for a in activites]


def activites_comptees(activites, champ) -> set:
    """Id des activités dont le budget `champ` (budget_alloue / budget_realise) est compté."""
    return ids_comptes(_noeuds(activites, champ))


def total_budget(activites, champ) -> Decimal:
    """Somme du budget `champ` sans double compte. `activites` : toutes celles d'un ou plusieurs projets."""
    activites = list(activites)
    comptees = activites_comptees(activites, champ)
    return sum((getattr(a, champ) for a in activites if a.id in comptees), Decimal("0"))


def _fcfa(valeur) -> str:
    return f"{valeur:,.0f}".replace(",", " ") + " FCFA"


def avertissements_budget(activites) -> dict:
    """
    {id d'activité: [messages]} pour les niveaux dont le budget alloué est un plafond de
    contrôle (éléments en dessous avec budget) et ne concorde pas avec ceux-ci.
    """
    activites = list(activites)
    enfants = {}
    for a in activites:
        enfants.setdefault(a.activite_parent_id, []).append(a)
    comptees = activites_comptees(activites, "budget_alloue")

    def somme_dessous(element_id):
        total = Decimal("0")
        for e in enfants.get(element_id, []):
            total += (e.budget_alloue if e.id in comptees else Decimal("0")) + somme_dessous(e.id)
        return total

    resultat = {}
    for a in activites:
        if not _a_valeur(a.budget_alloue) or a.id in comptees:
            continue
        dessous = somme_dessous(a.id)
        if dessous > a.budget_alloue:
            message = (
                f"Les budgets saisis en dessous ({_fcfa(dessous)}) dépassent le budget de ce niveau "
                f"({_fcfa(a.budget_alloue)})."
            )
        elif dessous < a.budget_alloue:
            message = (
                f"{_fcfa(a.budget_alloue - dessous)} du budget de ce niveau ne sont répartis sur aucun élément "
                "en dessous : seuls les budgets d'en dessous sont comptés dans les totaux."
            )
        else:
            continue
        resultat.setdefault(a.id, []).append(message)
    return resultat
