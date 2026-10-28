from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import NiveauAdministratifViewSet, ZoneViewSet, couche_carte, limites_administratives, localites

router = DefaultRouter()
router.register("zones", ZoneViewSet, basename="zone")
router.register("niveaux-administratifs", NiveauAdministratifViewSet, basename="niveau-administratif")

urlpatterns = router.urls + [
    path("limites-administratives/", limites_administratives, name="limites-administratives"),
    path("couches-carte/", couche_carte, name="couches-carte"),
    path("localites/", localites, name="localites"),
]
