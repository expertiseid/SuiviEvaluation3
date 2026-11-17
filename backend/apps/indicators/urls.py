from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EnqueteViewSet, IndicateurViewSet, ParametresAlerteView, ValeurIndicateurViewSet, paliers_alerte

router = DefaultRouter()
router.register("indicateurs", IndicateurViewSet, basename="indicateur")
router.register("valeurs-indicateurs", ValeurIndicateurViewSet, basename="valeur-indicateur")
router.register("enquetes", EnqueteViewSet, basename="enquete")

urlpatterns = router.urls + [
    path("parametres-alerte/", ParametresAlerteView.as_view(), name="parametres-alerte"),
    path("paliers-alerte/", paliers_alerte, name="paliers-alerte"),
]
