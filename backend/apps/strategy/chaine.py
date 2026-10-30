"""
Chaîne des documents stratégiques (TypeDocument) : contrôles des rattachements et remontée des
projets d'un maillon à l'autre.

Un document se rattache à un document d'un maillon au-dessus (au document lui-même ou à l'un de
ses éléments) ; chacun de ses éléments peut préciser l'élément d'un document au-dessus auquel il
contribue (ElementStrategique.contribue_a), ce qui l'emporte sur le rattachement du document.
Sauter des maillons est permis, avec un avertissement.

Remontée : partant de l'élément d'une activité (ou du rattachement de son projet), on monte de
document en document — par la contribution de l'élément ou de l'un de ses ancêtres dans son
document, sinon par le rattachement du document — et l'on note, pour chaque document atteint,
l'élément atteint (None : le document lui-même). Une activité compte ainsi pour tous les
documents au-dessus d'elle, sur l'élément où elle arrive.
"""
from functools import lru_cache

from apps.core.vocabulaire import v


def types_ordonnes():
    """Maillons de la chaîne, du plus haut au plus bas."""
    from .models import TypeDocument

    return list(TypeDocument.objects.order_by("ordre", "id"))


def ordre_du_type(type_document, types=None) -> int:
    """Rang du maillon (1 = le plus haut) ; un document sans type est du premier maillon."""
    types = types if types is not None else types_ordonnes()
    if type_document is None:
        return 1
    return next((i for i, t in enumerate(types, start=1) if t.id == type_document.id), 1)


def maillons_sautes(ordre_haut, ordre_bas, types=None) -> list:
    """Noms des maillons entre deux rangs (exclus)."""
    types = types if types is not None else types_ordonnes()
    return [t.nom for t in types[ordre_haut:ordre_bas - 1]]


def avertissement_saut(cible, sautes) -> str:
    """Message d'un rattachement qui saute des maillons (texte fixe : relevé pour la traduction)."""
    noms = ", ".join(sautes)
    return v(f"Rattaché directement à « {cible} » : maillon(s) sauté(s) : {noms}.")


def controler_rattachement(document_id, type_document, document_parent, element_parent) -> tuple[list, list]:
    """(erreurs, avertissements) du rattachement d'un document à un document au-dessus."""
    types = types_ordonnes()
    erreurs, avertissements = [], []
    rang = ordre_du_type(type_document, types)
    if element_parent is not None and document_parent is None:
        erreurs.append("Choisir le document auquel appartient l'élément de rattachement.")
    if document_parent is None:
        if rang > 1:
            avertissements.append("Pas encore rattaché à un document d'un maillon au-dessus.")
        return erreurs, avertissements
    if document_id is not None and document_parent.id == document_id:
        erreurs.append("Un document ne peut pas être rattaché à lui-même.")
        return erreurs, avertissements
    rang_parent = ordre_du_type(document_parent.type_document, types)
    if rang_parent >= rang:
        nom = type_document.nom if type_document else (types[0].nom if types else "")
        erreurs.append(f"« {document_parent} » n'est pas d'un maillon au-dessus de « {nom} ».")
        return erreurs, avertissements
    if element_parent is not None and element_parent.type_niveau.cadre_strategique_id != document_parent.id:
        erreurs.append(f"L'élément « {element_parent} » n'appartient pas à « {document_parent} ».")
    sautes = maillons_sautes(rang_parent, rang, types)
    if sautes:
        avertissements.append(avertissement_saut(document_parent, sautes))
    return erreurs, avertissements


def documents_au_dessus(document) -> list:
    """Documents de la chaîne de rattachement au-dessus de `document`, du plus proche au plus haut."""
    resultat, courant, vus = [], document.document_parent, {document.id}
    while courant is not None and courant.id not in vus:
        resultat.append(courant)
        vus.add(courant.id)
        courant = courant.document_parent
    return resultat


def controler_contribution(element, cible) -> tuple[list, list]:
    """(erreurs, avertissements) du lien « contribue à » d'un élément vers l'élément d'un autre document."""
    if cible is None:
        return [], []
    document = element.type_niveau.cadre_strategique
    document_cible = cible.type_niveau.cadre_strategique
    if document_cible.id == document.id:
        return [v("Dans un même document, le rattachement passe par l'élément parent.")], []
    types = types_ordonnes()
    rang, rang_cible = ordre_du_type(document.type_document, types), ordre_du_type(document_cible.type_document, types)
    if rang_cible >= rang:
        return [f"« {document_cible} » n'est pas d'un maillon au-dessus de « {document} »."], []
    avertissements = []
    sautes = maillons_sautes(rang_cible, rang, types)
    if sautes:
        avertissements.append(avertissement_saut(document_cible, sautes))
    if document_cible.id not in {d.id for d in documents_au_dessus(document)}:
        avertissements.append(f"« {document_cible} » n'est pas dans la chaîne de rattachement de « {document} ».")
    return [], avertissements


def avertissements_projet(projet) -> list:
    """Projet rattaché à un document qui n'est pas du dernier maillon : maillons sautés."""
    cadre = projet.cadre_strategique
    if cadre is None:
        return []
    types = types_ordonnes()
    sautes = [t.nom for t in types[ordre_du_type(cadre.type_document, types):]]
    return [avertissement_saut(cadre, sautes)] if sautes else []


class Chaine:
    """Documents et éléments chargés une fois, pour remonter de nombreuses activités."""

    def __init__(self):
        from .models import CadreStrategique, ElementStrategique

        self.parent_document = {}
        self.element_rattachement = {}
        for d in CadreStrategique.objects.values("id", "document_parent_id", "element_parent_id"):
            self.parent_document[d["id"]] = d["document_parent_id"]
            self.element_rattachement[d["id"]] = d["element_parent_id"]
        self.document_de = {}
        self.parent_element = {}
        self.contribution = {}
        for e in ElementStrategique.objects.values("id", "type_niveau__cadre_strategique_id", "element_parent_id", "contribue_a_id"):
            self.document_de[e["id"]] = e["type_niveau__cadre_strategique_id"]
            self.parent_element[e["id"]] = e["element_parent_id"]
            self.contribution[e["id"]] = e["contribue_a_id"]
        self.projeter = lru_cache(maxsize=None)(self._projeter)

    def _contribution_proche(self, element_id):
        """Contribution de l'élément ou, à défaut, de son plus proche ancêtre dans son document."""
        courant, vus = element_id, set()
        while courant is not None and courant not in vus:
            vus.add(courant)
            if self.contribution.get(courant):
                return self.contribution[courant]
            courant = self.parent_element.get(courant)
        return None

    def _projeter(self, document_id, element_id):
        """{document atteint: élément atteint (None = le document lui-même)} en remontant la chaîne."""
        atteints = {}
        while document_id is not None and document_id not in atteints:
            atteints[document_id] = element_id
            cible = self._contribution_proche(element_id) if element_id else None
            if cible is not None and cible in self.document_de:
                document_id, element_id = self.document_de[cible], cible
            else:
                document_id, element_id = self.parent_document.get(document_id), self.element_rattachement.get(document_id)
        return atteints

    def depart_activite(self, activite):
        """(document, élément) de départ d'une activité : son élément, sinon le rattachement de son projet."""
        if activite.axe_strategique_id and activite.axe_strategique_id in self.document_de:
            return self.document_de[activite.axe_strategique_id], activite.axe_strategique_id
        return self.depart_projet(activite.projet)

    def depart_projet(self, projet):
        """(document, élément) de départ d'un projet : son document et son élément s'il en fait partie."""
        document = projet.cadre_strategique_id
        element = projet.element_strategique_id
        if element is not None and self.document_de.get(element) != document:
            element = None
        return document, element

    def atteint(self, depart, document_id):
        """(compte pour ce document ?, élément atteint)."""
        atteints = self.projeter(*depart) if depart[0] is not None else {}
        return (document_id in atteints), atteints.get(document_id)


def activites_rattachees(document, projets_visibles, chaine=None) -> list:
    """
    [(activité, élément atteint dans `document` ou None)] : activités des projets visibles qui
    comptent pour ce document, directement ou par les documents rattachés en dessous.
    """
    from apps.projects.models import Activite

    chaine = chaine or Chaine()
    resultat = []
    activites = (
        Activite.objects.filter(projet__id__in=projets_visibles)
        .filter(_q_activites_candidates())
        .select_related("projet")
        .order_by("projet__code", "code_activite", "libelle")
    )
    for a in activites:
        compte, element = chaine.atteint(chaine.depart_activite(a), document.id)
        if compte:
            resultat.append((a, element))
    return resultat


def _q_activites_candidates():
    """Activités qui peuvent remonter quelque part : rattachées à un élément ou dont le projet a un document."""
    from django.db.models import Q

    return Q(axe_strategique__isnull=False) | Q(projet__cadre_strategique__isnull=False)


def documents_des_projets(projets, chaine=None) -> set:
    """Documents auxquels comptent ces projets (leur document et tous ceux au-dessus)."""
    chaine = chaine or Chaine()
    ids = set()
    for p in projets:
        depart = chaine.depart_projet(p)
        if depart[0] is not None:
            ids.update(chaine.projeter(*depart))
    return ids
