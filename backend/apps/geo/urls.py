from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    CoucheImporteeViewSet,
    NiveauAdministratifViewSet,
    ZoneViewSet,
    carte_synthese,
    couche_carte,
    limites_administratives,
    localites,
    pays_zones,
)

router = DefaultRouter()
router.register("zones", ZoneViewSet, basename="zone")
router.register("niveaux-administratifs", NiveauAdministratifViewSet, basename="niveau-administratif")
router.register("couches-importees", CoucheImporteeViewSet, basename="couche-importee")

urlpatterns = router.urls + [
    path("limites-administratives/", limites_administratives, name="limites-administratives"),
    path("couches-carte/", couche_carte, name="couches-carte"),
    path("localites/", localites, name="localites"),
    path("pays-zones/", pays_zones, name="pays-zones"),
    path("carte/synthese/", carte_synthese, name="carte-synthese"),
]
