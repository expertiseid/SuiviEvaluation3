from rest_framework.routers import DefaultRouter

from .views import (
    BailleurViewSet,
    CategoriePartiePrenanteViewSet,
    FinancementViewSet,
    PartenaireViewSet,
    PartiePrenanteViewSet,
    RallongeFinancementViewSet,
    StructureOrganisationViewSet,
)

router = DefaultRouter()
router.register("partenaires", PartenaireViewSet, basename="partenaire")
router.register("bailleurs", BailleurViewSet, basename="bailleur")
router.register("financements", FinancementViewSet, basename="financement")
router.register("rallonges-financement", RallongeFinancementViewSet, basename="rallonge-financement")

router.register("structures-organisation", StructureOrganisationViewSet, basename="structure-organisation")
router.register("categories-parties-prenantes", CategoriePartiePrenanteViewSet, basename="categorie-partie-prenante")
router.register("parties-prenantes", PartiePrenanteViewSet, basename="partie-prenante")

urlpatterns = router.urls
