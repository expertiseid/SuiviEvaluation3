from rest_framework.routers import DefaultRouter

from .views import RoleViewSet, UserViewSet

router = DefaultRouter()
router.register("utilisateurs", UserViewSet, basename="utilisateur")
router.register("roles", RoleViewSet, basename="role")

urlpatterns = router.urls
