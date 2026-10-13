from django.db.models import ProtectedError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdmin, IsAdminOrReadOnly

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

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError({"detail": "Impossible de supprimer ton propre compte."})
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": "Impossible de supprimer cet utilisateur : il a déjà des données rattachées "
                    "(valeurs saisies, documents, points de suivi...). Désactive-le plutôt (Actif = Non)."
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
                {"detail": "Impossible de supprimer ce rôle : des utilisateurs l'ont encore. Change d'abord leur rôle."}
            )
        instance.delete()
