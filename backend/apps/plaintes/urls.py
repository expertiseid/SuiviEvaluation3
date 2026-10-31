from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("plaintes/types", views.TypeRetourViewSet, basename="plainte-type")
router.register("plaintes/priorites", views.PrioriteViewSet, basename="plainte-priorite")
router.register("plaintes/circuits", views.CircuitViewSet, basename="plainte-circuit")
router.register("plaintes/etapes", views.EtapeCircuitViewSet, basename="plainte-etape")
router.register("plaintes/categories", views.CategorieViewSet, basename="plainte-categorie")

urlpatterns = [
    path("plaintes/mecanisme/", views.mecanisme, name="plaintes-mecanisme"),
    path("plaintes/mecanisme/activer/", views.activer, name="plaintes-activer"),
    path("plaintes/mecanisme/desactiver/", views.desactiver, name="plaintes-desactiver"),
    path("plaintes/modeles/", views.modeles, name="plaintes-modeles"),
    path("plaintes/canevas/", views.canevas, name="plaintes-canevas"),
    path("plaintes/canevas/importer/", views.importer_canevas, name="plaintes-canevas-importer"),
    path("", include(router.urls)),
]
