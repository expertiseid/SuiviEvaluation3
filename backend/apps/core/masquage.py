"""
Éléments masqués à un utilisateur (fiche de l'utilisateur, onglet « Visibilité ») : activités de la
planification (Activite.masquee_pour) et éléments des documents stratégiques (ElementStrategique.masque_pour).

- Masquer un élément masque tout ce qui est en dessous (enfants, sous-activités, suivis, indicateurs et
  documents qui y sont rattachés).
- Les listes et les fiches de l'utilisateur les excluent ; les totaux (budget du projet, taux, tableaux de
  bord) restent ceux de tout le projet : tous les utilisateurs voient les mêmes chiffres.
- L'Administrateur voit toujours tout.
"""
from apps.accounts.constants import ROLE_ADMIN


def _sans_masquage(user) -> bool:
    return not user or not getattr(user, "is_authenticated", False) or user.role == ROLE_ADMIN or user.is_superuser


def _avec_descendants(modele, champ_parent, racines) -> frozenset:
    tout, frontiere = set(racines), set(racines)
    while frontiere:
        enfants = set(modele.objects.filter(**{f"{champ_parent}__in": frontiere}).values_list("id", flat=True)) - tout
        tout |= enfants
        frontiere = enfants
    return frozenset(tout)


def activites_masquees(user) -> frozenset:
    """Identifiants des activités (tous niveaux) que l'utilisateur ne voit pas."""
    from apps.projects.models import Activite

    if _sans_masquage(user):
        return frozenset()
    cache = getattr(user, "_activites_masquees", None)
    if cache is None:
        racines = Activite.masquee_pour.through.objects.filter(user_id=user.pk).values_list("activite_id", flat=True)
        cache = _avec_descendants(Activite, "activite_parent", racines) if racines else frozenset()
        user._activites_masquees = cache
    return cache


def elements_masques(user) -> frozenset:
    """Identifiants des éléments stratégiques que l'utilisateur ne voit pas."""
    from apps.strategy.models import ElementStrategique

    if _sans_masquage(user):
        return frozenset()
    cache = getattr(user, "_elements_masques", None)
    if cache is None:
        racines = ElementStrategique.masque_pour.through.objects.filter(user_id=user.pk).values_list(
            "elementstrategique_id", flat=True)
        cache = _avec_descendants(ElementStrategique, "element_parent", racines) if racines else frozenset()
        user._elements_masques = cache
    return cache
