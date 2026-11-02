from django.db.models import ProtectedError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.audit import A, auditer
from apps.core.permissions import IsAdmin, IsAdminOrReadOnly
from apps.core.vocabulaire import v

from .models import Role, User
from .serializers import RoleSerializer, UserSerializer, UserWriteSerializer


class UserViewSet(viewsets.ModelViewSet):
    """CRUD des utilisateurs — réservé à l'Administrateur, sauf /me/."""

    queryset = User.objects.all().order_by("username")
    filterset_fields = ("role", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ("me", "list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdmin()]

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Son propre compte ; PATCH : seulement ses préférences (langue de l'interface)."""
        if request.method == "PATCH":
            from apps.core.models import CODES_LANGUES

            langue = request.data.get("langue", "")
            if langue not in ("", *CODES_LANGUES):
                raise ValidationError({"langue": "Langue inconnue."})
            request.user.langue = langue
            request.user.save(update_fields=["langue"])
        return Response(UserSerializer(request.user).data)

    # Droits d'un compte : inscrits au journal d'audit (champs changés seulement, jamais le mot de passe).
    CHAMPS_DROITS = ("role", "niveau_acces", "acces_modules", "is_active")

    def perform_create(self, serializer):
        compte = serializer.save()
        auditer(self.request.user, A.PERMISSION, compte.username, module="comptes", operation="creation",
                **{c: getattr(compte, c) for c in self.CHAMPS_DROITS})

    def perform_update(self, serializer):
        avant = {c: getattr(serializer.instance, c) for c in self.CHAMPS_DROITS}
        compte = serializer.save()
        changes = {c: [avant[c], getattr(compte, c)] for c in self.CHAMPS_DROITS if avant[c] != getattr(compte, c)}
        if changes:
            auditer(self.request.user, A.PERMISSION, compte.username, module="comptes", operation="modification", **changes)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError({"detail": "Impossible de supprimer ton propre compte."})
        try:
            nom = instance.username
            instance.delete()
            auditer(self.request.user, A.PERMISSION, nom, module="comptes", operation="suppression")
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": v('Impossible de supprimer cet utilisateur : il a déjà des données rattachées (valeurs saisies, documents, points de suivi...). Désactive-le plutôt (Actif = Non).')
                }
            )


class RoleViewSet(viewsets.ModelViewSet):
    """Référentiel des rôles — lecture pour tous, gestion réservée à l'Administrateur."""

    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = (IsAdminOrReadOnly,)
    pagination_class = None

    def perform_destroy(self, instance):
        if instance.systeme:
            raise ValidationError({"detail": "Rôle système : il peut être renommé, mais pas supprimé."})
        if User.objects.filter(role=instance.code).exists():
            raise ValidationError(
                {"detail": v("Impossible de supprimer ce rôle : des utilisateurs l'ont encore. Change d'abord leur rôle.")}
            )
        instance.delete()
