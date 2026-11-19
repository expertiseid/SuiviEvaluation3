"""
Droits précis par objet (DroitObjet) : lecture seule ou lecture et écriture, et droit d'approuver, sur un
projet, un document stratégique (stratégie, programme, plan…) ou un élément stratégique (pilier, axe…).

Règles :
- L'Administrateur peut tout.
- Un droit précis sur l'objet l'emporte ; sinon celui de l'objet au-dessus : élément → élément parent →
  document de l'élément → élément ou document auquel ce document est rattaché, et ainsi de suite.
- Sans droit précis : les droits globaux (projets : niveau d'accès ou réglage du module, et rôle pour
  approuver ; stratégies : modifiables par l'Administrateur seul, approbation selon le rôle), ou lecture
  seule sans approbation si l'utilisateur est réglé ainsi (User.hors_droits_precis).
- Un module réglé explicitement en lecture (ou masqué) pour l'utilisateur le reste, même avec un droit
  précis d'écriture.
- Un droit précis sur un projet le rend visible à l'utilisateur.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from apps.accounts.constants import ROLE_ADMIN

PROJET, DOCUMENT, ELEMENT = "projet", "document", "element"


@dataclass(frozen=True)
class Droits:
    ecriture: bool
    approuver: bool


TOUT = Droits(True, True)
RIEN = Droits(False, False)

# Enregistrements faits pour le compte d'une approbation (l'approbateur peut n'avoir que la lecture).
_ecriture_accordee = ContextVar("ecriture_accordee", default=False)


@contextmanager
def ecriture_accordee():
    jeton = _ecriture_accordee.set(True)
    try:
        yield
    finally:
        _ecriture_accordee.reset(jeton)


def ecriture_deja_accordee() -> bool:
    return _ecriture_accordee.get()


def _est_admin(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and (user.role == ROLE_ADMIN or user.is_superuser))


def _entrees(user) -> dict:
    """Droits précis de l'utilisateur, lus une fois par requête : {(type, id): Droits}."""
    cache = getattr(user, "_droits_objets", None)
    if cache is None:
        from .models import DroitObjet

        cache = {}
        for projet, document, element, acces, approuver in DroitObjet.objects.filter(utilisateur_id=user.pk).values_list(
                "projet_id", "document_id", "element_id", "acces", "approuver"):
            cle = (PROJET, projet) if projet else (DOCUMENT, document) if document else (ELEMENT, element)
            cache[cle] = Droits(acces == DroitObjet.Acces.ECRITURE, approuver)
        user._droits_objets = cache
    return cache


def a_des_droits_precis(user, ecriture=None, approuver=None) -> bool:
    """L'utilisateur a-t-il au moins un droit précis (d'écriture, d'approbation) ?"""
    if not (user and getattr(user, "is_authenticated", False)):
        return False
    return any((ecriture is None or d.ecriture == ecriture) and (approuver is None or d.approuver == approuver)
               for d in _entrees(user).values())


def _module_bloque(user) -> bool:
    """Le module de la requête est réglé explicitement en lecture (ou masqué) pour cet utilisateur."""
    from apps.core.modules import ECRITURE, module_courant

    module = module_courant.get()
    niveau = (user.acces_modules or {}).get(module) if module else None
    return niveau is not None and niveau != ECRITURE


def _restreint(user) -> bool:
    from apps.accounts.models import User

    return user.hors_droits_precis == User.HorsDroitsPrecis.LECTURE


def _avec_module(user, droits: Droits) -> Droits:
    return Droits(droits.ecriture and not _module_bloque(user), droits.approuver)


def _global_projet(user) -> Droits:
    from apps.core.permissions import peut_approuver, peut_modifier

    if _restreint(user):
        return RIEN
    return Droits(peut_modifier(user), peut_approuver(user))


def _global_strategie(user, saisie=False) -> Droits:
    """Structure des stratégies : Administrateur seul ; saisies (appréciations) : niveau d'accès global."""
    from apps.core.permissions import peut_approuver, peut_modifier

    if _restreint(user):
        return RIEN
    return Droits(peut_modifier(user) if saisie else False, peut_approuver(user))


def droits_projet(user, projet_id) -> Droits:
    if _est_admin(user):
        return TOUT
    if not (user and getattr(user, "is_authenticated", False)):
        return RIEN
    precis = _entrees(user).get((PROJET, projet_id))
    return _avec_module(user, precis) if precis is not None else _global_projet(user)


def _remonter_element(user, element_id, vus=None):
    """Droit précis sur l'élément ou au-dessus de lui (éléments parents, puis document)."""
    from apps.strategy.models import ElementStrategique

    entrees = _entrees(user)
    vus = vus or set()
    while element_id and element_id not in vus:
        vus.add(element_id)
        if (ELEMENT, element_id) in entrees:
            return entrees[(ELEMENT, element_id)]
        parent, document = ElementStrategique.objects.filter(id=element_id).values_list(
            "element_parent_id", "type_niveau__cadre_strategique_id").first() or (None, None)
        if parent is None:
            return _remonter_document(user, document, vus)
        element_id = parent
    return None


def _remonter_document(user, document_id, vus=None):
    """Droit précis sur le document ou au-dessus de lui (élément ou document auquel il est rattaché)."""
    from apps.strategy.models import CadreStrategique

    entrees = _entrees(user)
    vus = vus if vus is not None else set()
    while document_id and ("D", document_id) not in vus:
        vus.add(("D", document_id))
        if (DOCUMENT, document_id) in entrees:
            return entrees[(DOCUMENT, document_id)]
        element_parent, document_parent = CadreStrategique.objects.filter(id=document_id).values_list(
            "element_parent_id", "document_parent_id").first() or (None, None)
        if element_parent:
            return _remonter_element(user, element_parent, vus)
        document_id = document_parent
    return None


def droits_document(user, document_id, saisie=False) -> Droits:
    if _est_admin(user):
        return TOUT
    if not (user and getattr(user, "is_authenticated", False)):
        return RIEN
    precis = _remonter_document(user, document_id) if _entrees(user) else None
    return _avec_module(user, precis) if precis is not None else _global_strategie(user, saisie)


def droits_element(user, element_id, saisie=False) -> Droits:
    if _est_admin(user):
        return TOUT
    if not (user and getattr(user, "is_authenticated", False)):
        return RIEN
    precis = _remonter_element(user, element_id) if _entrees(user) else None
    return _avec_module(user, precis) if precis is not None else _global_strategie(user, saisie)


# --- Objet → projet, document ou élément ------------------------------------------------------------

def cible_objet(instance):
    """(type, id) du projet, document ou élément dont relève l'objet ; None s'il n'en relève d'aucun."""
    from apps.strategy.models import AppreciationStrategique, CadreStrategique, ElementStrategique, FinancementDocument, TypeNiveau

    from .models import Projet
    from .verrou import _projet_id

    if isinstance(instance, Projet):
        return (PROJET, instance.pk) if instance.pk else None
    if isinstance(instance, CadreStrategique):
        if instance.pk:
            return (DOCUMENT, instance.pk)
        # Nouveau document : celui (ou l'élément) auquel il est rattaché.
        if instance.element_parent_id:
            return (ELEMENT, instance.element_parent_id)
        return (DOCUMENT, instance.document_parent_id) if instance.document_parent_id else None
    if isinstance(instance, ElementStrategique):
        if instance.pk:
            return (ELEMENT, instance.pk)
        if instance.element_parent_id:
            return (ELEMENT, instance.element_parent_id)
        document = TypeNiveau.objects.filter(id=instance.type_niveau_id).values_list("cadre_strategique_id", flat=True).first()
        return (DOCUMENT, document) if document else None
    if isinstance(instance, TypeNiveau):
        return (DOCUMENT, instance.cadre_strategique_id) if instance.cadre_strategique_id else None
    if isinstance(instance, AppreciationStrategique):
        return (ELEMENT, instance.element_id) if instance.element_id else None
    if isinstance(instance, FinancementDocument):
        return (DOCUMENT, instance.document_id) if instance.document_id else None
    projet_id = _projet_id(instance)
    return (PROJET, projet_id) if projet_id else None


def droits_cible(user, cible, saisie=False) -> Droits:
    """`saisie` : contenu saisi (appréciations…) plutôt que structure d'une stratégie (voir _global_strategie)."""
    genre, identifiant = cible
    if genre == PROJET:
        return droits_projet(user, identifiant)
    return (droits_document if genre == DOCUMENT else droits_element)(user, identifiant, saisie)


# Clés d'une requête qui désignent l'objet concerné (création, import…), dans l'ordre de priorité.
_CLES_REQUETE = (
    ("element", ELEMENT), ("element_strategique", ELEMENT), ("element_parent", ELEMENT),
    ("cadre_strategique", DOCUMENT), ("document_parent", DOCUMENT),
    ("projet", PROJET), ("projet_id", PROJET),
)


def cible_requete(request, view=None):
    """Projet, document ou élément désigné par une requête sans objet (création, action sur une liste)."""
    donnees = request.data if hasattr(request.data, "get") else {}
    parametres = getattr(request, "query_params", {})
    for cle, genre in _CLES_REQUETE:
        valeur = donnees.get(cle) or parametres.get(cle)
        if valeur not in (None, "") and str(valeur).isdigit():
            return (genre, int(valeur))
    # Objet parent désigné par sa clé (activité, sous-activité, risque, indicateur, niveau…) : on remonte de lui.
    try:
        modele = view.get_serializer_class().Meta.model
    except Exception:
        return None
    for champ in modele._meta.get_fields():
        if not getattr(champ, "many_to_one", False) or champ.related_model is None:
            continue
        valeur = donnees.get(champ.name)
        if valeur not in (None, "") and str(valeur).isdigit():
            parent = champ.related_model.objects.filter(pk=valeur).first()
            cible = cible_objet(parent) if parent is not None else None
            if cible:
                return cible
    return None
