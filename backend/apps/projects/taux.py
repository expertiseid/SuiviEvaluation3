"""
Calcul du taux d'exécution physique des éléments de la planification et du projet.

Rien n'est stocké : tout est recalculé à la volée, pour qu'un changement de méthode, de
poids ou de saisie se répercute immédiatement.

Méthode d'un élément (héritage)
-------------------------------
Méthode de calcul : celle de l'élément, sinon celle du premier élément parent qui en fixe
une (hors « Saisie manuelle », propre à l'élément qui la porte), sinon celle du projet,
sinon celle de l'organisation (ParametresCalcul, par défaut « Par quantité »). Même chaîne
pour la méthode d'agrégation.

- Un élément qui a des éléments en dessous prend le taux agrégé de ceux-ci — sauf s'il est
  lui-même réglé explicitement en « Saisie manuelle ».
- Un élément du dernier niveau applique sa méthode de calcul.

Formules (élément du dernier niveau)
------------------------------------
- QUANTITE  : quantité réalisée ÷ quantité prévue × 100. Quantité prévue vide ou nulle :
  non calculable. Dépassement de cible : le taux réel est gardé (ex : 130 %).
- TACHES    : Σ (poids × avancement) ÷ Σ poids, sur les sous-activités. Avancement d'une
  sous-activité : son avancement saisi, sinon quantité réalisée ÷ prévue (plafonnée à
  100 %), sinon 100 % si « Terminée » et 0 % sinon.
- JALONS    : Σ (poids × achèvement) ÷ Σ poids, sur les jalons.
- LIVRABLES : Σ poids des livrables validés ÷ Σ poids × 100.
- BINAIRE   : 100 % si l'élément est « Réalisée », 0 % sinon.
- MANUELLE  : dernier taux saisi (0 à 100 %), jamais recalculé ; aucun : non calculable.

Poids (TACHES, JALONS, LIVRABLES, agrégation par poids) : aucun poids saisi → poids égaux ;
un poids manquant compte pour 0 ; si les poids ne totalisent pas 100, le calcul est fait
proportionnellement et un avertissement est signalé.

Agrégation (élément avec des éléments en dessous, et projet)
------------------------------------------------------------
- MOYENNE          : moyenne simple des taux des éléments du dernier niveau situés en
  dessous (même calcul qu'avant l'introduction des méthodes).
- PONDEREE_BUDGET  : moyenne de ces mêmes taux pondérée par leur budget alloué (aucun
  budget → moyenne simple).
- PONDEREE_POIDS   : moyenne des taux des éléments directement en dessous, pondérée par
  leur poids.

Les éléments non calculables sont ignorés. Avec « plafonner » (réglage de l'organisation,
activé par défaut), un taux supérieur à 100 % compte pour 100 % dans une agrégation.
"""
from dataclasses import dataclass, field

from .models import JalonLivrable, MethodeAgregation, MethodeCalcul, ParametresCalcul, SousActivite


@dataclass
class ResultatTaux:
    taux: float | None  # taux affiché (réel, peut dépasser 100), arrondi à 0,1
    methode: str  # méthode appliquée, ou "AGREGATION"
    avertissements: list[str] = field(default_factory=list)


def _arrondi(valeur):
    return None if valeur is None else round(valeur, 1)


def _moyenne_ponderee(valeurs_poids):
    """[(valeur, poids)] → moyenne pondérée ; poids tous vides → moyenne simple ; None si aucune valeur."""
    valeurs_poids = [(v, p) for v, p in valeurs_poids if v is not None]
    if not valeurs_poids:
        return None, None
    if all(p is None for _, p in valeurs_poids):
        return sum(v for v, _ in valeurs_poids) / len(valeurs_poids), None
    poids = [(v, float(p or 0)) for v, p in valeurs_poids]
    total = sum(p for _, p in poids)
    if total <= 0:
        return sum(v for v, _ in poids) / len(poids), None
    return sum(v * p for v, p in poids) / total, total


def _avertissement_poids(total, quoi):
    if total is not None and abs(total - 100) > 0.01:
        return [f"Les poids des {quoi} totalisent {round(total, 2):g} % au lieu de 100 % : calcul proportionnel."]
    return []


def avancement_sous_activite(sa) -> float:
    if sa.avancement is not None:
        return float(sa.avancement)
    if sa.quantite_prevue:
        return min(100.0, float(sa.quantite_realisee or 0) / float(sa.quantite_prevue) * 100)
    return 100.0 if sa.statut == SousActivite.Statut.TERMINEE else 0.0


class ArbreTaux:
    """
    Calcule les taux de tous les éléments d'un projet en une passe (quelques requêtes,
    puis tout en mémoire). Usage : arbre = ArbreTaux(projet) ; arbre.resultat(activite_id) ;
    arbre.taux_projet().
    """

    def __init__(self, projet, parametres=None):
        from .models import Activite

        self.projet = projet
        self.parametres = parametres or ParametresCalcul.courants()
        elements = list(
            Activite.objects.filter(projet=projet).prefetch_related("sous_activites", "jalons_livrables", "taux_manuels")
        )
        self.elements = {e.id: e for e in elements}
        self.enfants = {e.id: [] for e in elements}
        self.racines = []
        for e in elements:
            (self.enfants[e.activite_parent_id] if e.activite_parent_id in self.enfants else self.racines).append(e)
        self._resultats = {}

    # -- héritage --------------------------------------------------------------------
    def _herite(self, element, champ):
        courant = element
        while courant is not None:
            if getattr(courant, champ):
                return getattr(courant, champ)
            courant = self.elements.get(courant.activite_parent_id)
        return getattr(self.projet, champ) or getattr(self.parametres, champ)

    def methode_calcul(self, element):
        # « Saisie manuelle » réglée sur un élément parent ne vaut que pour lui : ses
        # éléments en dessous héritent de la méthode fixée plus haut.
        if element.methode_calcul:
            return element.methode_calcul
        courant = self.elements.get(element.activite_parent_id)
        while courant is not None:
            if courant.methode_calcul and courant.methode_calcul != MethodeCalcul.MANUELLE:
                return courant.methode_calcul
            courant = self.elements.get(courant.activite_parent_id)
        return self.projet.methode_calcul or self.parametres.methode_calcul

    def methode_agregation(self, element=None):
        if element is None:
            return self.projet.methode_agregation or self.parametres.methode_agregation
        return self._herite(element, "methode_agregation")

    # -- calcul ----------------------------------------------------------------------
    def resultat(self, element_id) -> ResultatTaux:
        if element_id not in self._resultats:
            self._resultats[element_id] = self._calculer(self.elements[element_id])
        return self._resultats[element_id]

    def _plafonne(self, taux):
        if taux is None:
            return None
        return min(taux, 100.0) if self.parametres.plafonner_agregation else taux

    def _feuilles(self, element):
        enfants = self.enfants[element.id] if element is not None else self.racines
        if element is not None and not enfants:
            return [element]
        return [f for e in enfants for f in self._feuilles(e)]

    def _agreger(self, element):
        """Taux agrégé de l'élément (None = le projet) à partir des éléments en dessous."""
        methode = self.methode_agregation(element)
        avertissements = []
        if methode == MethodeAgregation.PONDEREE_POIDS:
            enfants = self.enfants[element.id] if element is not None else self.racines
            valeur, total = _moyenne_ponderee(
                [(self._plafonne(self.resultat(e.id).taux), e.poids) for e in enfants]
            )
            avertissements = _avertissement_poids(total, "éléments en dessous")
        else:
            feuilles = self._feuilles(element)
            budget = methode == MethodeAgregation.PONDEREE_BUDGET
            valeur, _ = _moyenne_ponderee(
                [(self._plafonne(self.resultat(f.id).taux), (f.budget_alloue if budget else None)) for f in feuilles]
            )
        return ResultatTaux(_arrondi(valeur), "AGREGATION", avertissements)

    def _calculer(self, element) -> ResultatTaux:
        a_des_enfants = bool(self.enfants[element.id])
        if a_des_enfants and element.methode_calcul != MethodeCalcul.MANUELLE:
            return self._agreger(element)
        methode = element.methode_calcul if a_des_enfants else self.methode_calcul(element)

        if methode == MethodeCalcul.MANUELLE:
            saisies = sorted(element.taux_manuels.all(), key=lambda t: (t.date, t.id), reverse=True)
            return ResultatTaux(_arrondi(float(saisies[0].taux)) if saisies else None, methode)

        if methode == MethodeCalcul.BINAIRE:
            return ResultatTaux(100.0 if element.statut == element.Statut.REALISEE else 0.0, methode)

        if methode == MethodeCalcul.TACHES:
            taches = list(element.sous_activites.all())
            valeur, total = _moyenne_ponderee([(avancement_sous_activite(t), t.poids) for t in taches])
            return ResultatTaux(_arrondi(valeur), methode, _avertissement_poids(total, "tâches"))

        if methode == MethodeCalcul.JALONS:
            jalons = [j for j in element.jalons_livrables.all() if j.type == JalonLivrable.Type.JALON]
            valeur, total = _moyenne_ponderee([(float(j.achevement), j.poids) for j in jalons])
            return ResultatTaux(_arrondi(valeur), methode, _avertissement_poids(total, "jalons"))

        if methode == MethodeCalcul.LIVRABLES:
            livrables = [j for j in element.jalons_livrables.all() if j.type == JalonLivrable.Type.LIVRABLE]
            valeur, total = _moyenne_ponderee([(100.0 if j.valide else 0.0, j.poids) for j in livrables])
            return ResultatTaux(_arrondi(valeur), methode, _avertissement_poids(total, "livrables"))

        # QUANTITE (défaut)
        if not element.quantite_prevue:
            return ResultatTaux(None, MethodeCalcul.QUANTITE)
        return ResultatTaux(
            _arrondi(float(element.quantite_realisee or 0) / float(element.quantite_prevue) * 100), MethodeCalcul.QUANTITE
        )

    def taux_projet(self) -> ResultatTaux:
        return self._agreger(None)


def taux_element(activite) -> ResultatTaux:
    """Taux d'un seul élément (charge l'arbre de son projet)."""
    return ArbreTaux(activite.projet).resultat(activite.id)
