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

Taux à une date (ArbreTaux(projet, a_la_date=...))
--------------------------------------------------
Sert au suivi par période : où en était chaque élément à la fin de la période. Méthodes,
poids et quantités prévues sont ceux d'aujourd'hui ; seules les réalisations sont datées :
- quantités réalisées et statut : saisies de suivi dont la période se termine au plus tard
  à cette date (statut de la dernière saisie qui en indique un, sinon celui enregistré à
  cette date dans l'historique) ;
- avancement des tâches, achèvement des jalons : valeur enregistrée à cette date
  (historique des modifications) ; une tâche ou un jalon enregistré après cette date compte
  avec un avancement nul (les poids restent ceux d'aujourd'hui) ;
- livrables : validés à cette date (date de validation) ;
- saisie manuelle : dernier taux daté au plus tard de ce jour.
"""
import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .models import JalonLivrable, MethodeAgregation, MethodeCalcul, ParametresCalcul, SousActivite


@dataclass
class ResultatTaux:
    taux: float | None  # taux affiché (réel, peut dépasser 100), arrondi à 0,1
    methode: str  # méthode appliquée, ou "AGREGATION"
    avertissements: list[str] = field(default_factory=list)


def libelle_methode(methode) -> str:
    """Libellé d'une méthode appliquée (ResultatTaux.methode), pour les exports."""
    from apps.core.vocabulaire import v

    if methode == "AGREGATION":
        return v("Agrégé des éléments en dessous")
    return v(MethodeCalcul(methode).label)


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


def avancement_sous_activite(sa, quantite_realisee=None, statut=None) -> float:
    quantite_realisee = sa.quantite_realisee if quantite_realisee is None else quantite_realisee
    statut = sa.statut if statut is None else statut
    if sa.avancement is not None:
        return float(sa.avancement)
    if sa.quantite_prevue:
        return min(100.0, float(quantite_realisee or 0) / float(sa.quantite_prevue) * 100)
    return 100.0 if statut == SousActivite.Statut.TERMINEE else 0.0


def _etat_historique(modele, ids, instant):
    """
    {id: enregistrement historique à cet instant} pour les objets qui existaient alors.
    Les objets sans aucun historique (créés hors de l'application) gardent leur état actuel :
    ils sont absents du résultat et de `ids_avec_historique`.
    """
    etats, avec_historique = {}, set()
    for h in modele.history.filter(id__in=ids).order_by("id", "-history_date", "-history_id"):
        avec_historique.add(h.id)
        if h.id not in etats and h.history_date <= instant:
            etats[h.id] = h
    return {i: h for i, h in etats.items() if h.history_type != "-"}, avec_historique


class _EtatALaDate:
    """Réalisations des éléments d'un projet telles qu'elles étaient à une date (voir en tête)."""

    def __init__(self, projet, elements, date):
        from django.db.models import Q
        from django.utils import timezone

        from apps.suivi.models import PointSuivi

        from .models import Activite

        self.date = date
        instant = timezone.make_aware(datetime.datetime.combine(date, datetime.time.max))
        self.quantites = defaultdict(lambda: Decimal("0"))
        self.statuts = {}
        points = PointSuivi.objects.filter(
            Q(activite__projet=projet) | Q(sous_activite__activite__projet=projet), periode_fin__lte=date
        ).order_by("periode_fin", "id")
        for p in points:
            cle = ("A", p.activite_id) if p.activite_id else ("S", p.sous_activite_id)
            self.quantites[cle] += p.quantite_realisee or Decimal("0")
            if p.statut:
                self.statuts[cle] = p.statut

        taches = [t for e in elements for t in e.sous_activites.all()]
        jalons = [j for e in elements for j in e.jalons_livrables.all()]
        self.activites_hist, self.activites_suivies = _etat_historique(Activite, [e.id for e in elements], instant)
        self.taches_hist, self.taches_suivies = _etat_historique(SousActivite, [t.id for t in taches], instant)
        self.jalons_hist, self.jalons_suivis = _etat_historique(JalonLivrable, [j.id for j in jalons], instant)

    def _statut(self, cle, objet, historique, suivis):
        if cle in self.statuts:
            return self.statuts[cle]
        if objet.id in historique:
            return historique[objet.id].statut
        return objet.statut if objet.id not in suivis else None

    def statut_element(self, e):
        return self._statut(("A", e.id), e, self.activites_hist, self.activites_suivies)

    def quantite_element(self, e):
        return self.quantites[("A", e.id)]

    def taches(self, e):
        """[(tâche, avancement à la date)]."""
        resultat = []
        for t in e.sous_activites.all():
            quantite = self.quantites[("S", t.id)]
            if t.id in self.taches_suivies and t.id not in self.taches_hist:
                # Enregistrée après la date : seules ses saisies datées comptent.
                avancement = min(100.0, float(quantite) / float(t.quantite_prevue) * 100) if t.quantite_prevue else 0.0
                resultat.append((t, avancement))
                continue
            etat = self.taches_hist.get(t.id, t)
            statut = self._statut(("S", t.id), t, self.taches_hist, self.taches_suivies)
            resultat.append((t, avancement_sous_activite(etat, quantite, statut)))
        return resultat

    def jalons(self, e):
        """[(jalon ou livrable, achèvement à la date, validé à la date)]."""
        resultat = []
        for j in e.jalons_livrables.all():
            if j.id in self.jalons_suivis and j.id not in self.jalons_hist:
                achevement = 0.0  # enregistré après la date
            else:
                achevement = float(self.jalons_hist.get(j.id, j).achevement)
            valide = bool(j.valide and j.date_validation and j.date_validation <= self.date)
            resultat.append((j, achevement, valide))
        return resultat

    def taux_manuels(self, e):
        return [t for t in e.taux_manuels.all() if t.date <= self.date]


class ArbreTaux:
    """
    Calcule les taux de tous les éléments d'un projet en une passe (quelques requêtes,
    puis tout en mémoire). Usage : arbre = ArbreTaux(projet) ; arbre.resultat(activite_id) ;
    arbre.taux_projet().
    """

    def __init__(self, projet, parametres=None, a_la_date=None):
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
        self._etat = _EtatALaDate(projet, elements, a_la_date) if a_la_date else None

    # -- réalisations (actuelles, ou à la date demandée) ---------------------------------
    def _statut(self, element):
        return self._etat.statut_element(element) if self._etat else element.statut

    def _quantite_realisee(self, element):
        return self._etat.quantite_element(element) if self._etat else element.quantite_realisee

    def _taches(self, element):
        if self._etat:
            return self._etat.taches(element)
        return [(t, avancement_sous_activite(t)) for t in element.sous_activites.all()]

    def _jalons(self, element):
        if self._etat:
            return self._etat.jalons(element)
        return [(j, float(j.achevement), j.valide) for j in element.jalons_livrables.all()]

    def _taux_manuels(self, element):
        return self._etat.taux_manuels(element) if self._etat else list(element.taux_manuels.all())

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
            saisies = sorted(self._taux_manuels(element), key=lambda t: (t.date, t.id), reverse=True)
            return ResultatTaux(_arrondi(float(saisies[0].taux)) if saisies else None, methode)

        if methode == MethodeCalcul.BINAIRE:
            return ResultatTaux(100.0 if self._statut(element) == element.Statut.REALISEE else 0.0, methode)

        if methode == MethodeCalcul.TACHES:
            valeur, total = _moyenne_ponderee([(avancement, t.poids) for t, avancement in self._taches(element)])
            return ResultatTaux(_arrondi(valeur), methode, _avertissement_poids(total, "tâches"))

        if methode == MethodeCalcul.JALONS:
            jalons = [(j, achevement) for j, achevement, _ in self._jalons(element) if j.type == JalonLivrable.Type.JALON]
            valeur, total = _moyenne_ponderee([(achevement, j.poids) for j, achevement in jalons])
            return ResultatTaux(_arrondi(valeur), methode, _avertissement_poids(total, "jalons"))

        if methode == MethodeCalcul.LIVRABLES:
            livrables = [(j, valide) for j, _, valide in self._jalons(element) if j.type == JalonLivrable.Type.LIVRABLE]
            valeur, total = _moyenne_ponderee([(100.0 if valide else 0.0, j.poids) for j, valide in livrables])
            return ResultatTaux(_arrondi(valeur), methode, _avertissement_poids(total, "livrables"))

        # QUANTITE (défaut)
        if not element.quantite_prevue:
            return ResultatTaux(None, MethodeCalcul.QUANTITE)
        return ResultatTaux(
            _arrondi(float(self._quantite_realisee(element) or 0) / float(element.quantite_prevue) * 100),
            MethodeCalcul.QUANTITE,
        )

    def taux_projet(self) -> ResultatTaux:
        return self._agreger(None)


def taux_element(activite) -> ResultatTaux:
    """Taux d'un seul élément (charge l'arbre de son projet)."""
    return ArbreTaux(activite.projet).resultat(activite.id)
