"""
Permissions DRF basées sur le champ `role` de l'utilisateur plutôt que sur
les Groups/Permissions Django natifs : les 5 rôles métier correspondent à
des niveaux d'accès fonctionnels transversaux (lecture seule / saisie /
validation / administration) qui ne collent pas à la sémantique CRUD
standard add/change/delete/view.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN


def peut_modifier(user) -> bool:
    """
    Droit d'écriture (créer/modifier/supprimer) : toujours vrai pour un
    Administrateur, sinon dépend du niveau d'accès choisi par l'admin pour
    cet utilisateur — indépendamment de son rôle, qui ne détermine que la
    visibilité (tous les projets ou seulement ceux affectés). Si la requête
    relève d'un module réglé pour cet utilisateur, c'est ce réglage qui compte
    (voir apps.core.modules).
    """
    from .modules import ECRITURE, acces_module, module_courant

    module = module_courant.get()
    if module is not None:
        return acces_module(user, module) == ECRITURE
    return user.role == ROLE_ADMIN or user.niveau_acces == NIVEAU_ACCES_LECTURE_ECRITURE


def peut_personnaliser_tableau_de_bord(user) -> bool:
    """Droit de configurer le tableau de bord pour tous : Administrateur, ou rôle ayant ce droit."""
    from apps.accounts.models import Role

    if not (user and user.is_authenticated):
        return False
    if user.role == ROLE_ADMIN:
        return True
    return Role.objects.filter(code=user.role, peut_personnaliser_tableau_de_bord=True).exists()


def peut_approuver(user) -> bool:
    """Droit d'approuver saisies et demandes de modification : Administrateur, ou rôle ayant ce droit."""
    from apps.accounts.models import Role

    if not (user and user.is_authenticated):
        return False
    if user.role == ROLE_ADMIN:
        return True
    return Role.objects.filter(code=user.role, peut_approuver=True).exists()


class IsAdmin(BasePermission):
    """Réservé au rôle Administrateur."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ROLE_ADMIN)


class IsAdminOrReadOnly(BasePermission):
    """Lecture pour tout utilisateur authentifié, écriture réservée à l'Administrateur."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == ROLE_ADMIN


class IsAdminOrCreateForAuthenticated(BasePermission):
    """
    Lecture ouverte à tout utilisateur authentifié ; création (POST) ouverte
    à tout utilisateur ayant le droit d'écriture (niveau d'accès) — pour les
    référentiels légers créables « à la volée » depuis un autre formulaire
    (ex : nouvelle commune, nouveau bailleur saisi en tapant son nom) —
    modification et suppression réservées à l'Administrateur.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return peut_modifier(request.user)
        return request.user.role == ROLE_ADMIN


class HasGlobalVisibilityOrAssigned(BasePermission):
    """
    Lecture ouverte à tout utilisateur authentifié ; écriture (create/
    update/delete) réservée à ceux ayant le droit d'écriture (niveau
    d'accès, cf. peut_modifier). Le filtrage fin par affectation
    (zones/projets) se fait séparément dans get_queryset() de chaque
    viewset via has_global_visibility(request.user).
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return peut_modifier(request.user)


def has_global_visibility(user) -> bool:
    """Visibilité définie par le rôle (référentiel Role, modifiable par l'Administrateur)."""
    from apps.accounts.models import Role

    if user.role == ROLE_ADMIN:
        return True
    return Role.objects.filter(code=user.role, visibilite_globale=True).exists()


class SuppressionAtomiqueMixin:
    """
    Suppression dans son propre bloc transactionnel : si un contrôle la refuse en cours de route
    (projet clôturé, saisie fermée, saisie approuvée…), elle est annulée proprement sans laisser
    la connexion inutilisable pour la suite de la requête.
    """

    def perform_destroy(self, instance):
        from django.db import transaction

        with transaction.atomic():
            super().perform_destroy(instance)


class AvertissementsSaisieMixin:
    """
    Après l'enregistrement d'une saisie (point de suivi, valeur d'indicateur), ajoute à la réponse
    les incohérences repérées (apps.projects.coherence), affichées tout de suite à l'utilisateur.
    """

    def _avec_avertissements(self, response):
        from apps.projects.coherence import avertissements_saisie

        if response.status_code in (200, 201) and isinstance(response.data, dict) and "id" in response.data:
            saisie = self.get_queryset().model.tous.get(pk=response.data["id"])
            response.data["avertissements"] = avertissements_saisie(saisie)
        return response

    def create(self, request, *args, **kwargs):
        return self._avec_avertissements(super().create(request, *args, **kwargs))

    def update(self, request, *args, **kwargs):
        return self._avec_avertissements(super().update(request, *args, **kwargs))

