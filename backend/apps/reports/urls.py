from django.urls import path
from rest_framework.routers import DefaultRouter

from .partage import LienPartageViewSet, partage_public
from .views import cadre_logique, rapport_financier, rapport_suivi_strategique, registre_risques

router = DefaultRouter()
router.register("liens-partage", LienPartageViewSet, basename="lien-partage")

urlpatterns = router.urls + [
    path("rapports/financier/<int:projet_id>/", rapport_financier, name="rapport-financier"),
    path("rapports/cadre-logique/<int:projet_id>/", cadre_logique, name="cadre-logique"),
    path("rapports/risques/<int:projet_id>/", registre_risques, name="registre-risques"),
    path("rapports/suivi-strategique/<int:cadre_id>/", rapport_suivi_strategique, name="rapport-suivi-strategique"),
    path("public/partage/<str:jeton>/", partage_public, name="partage-public"),
    path("public/partage/<str:jeton>/<str:ressource>/", partage_public, name="partage-public-ressource"),
]
