from rest_framework.routers import DefaultRouter

from .views import AppreciationStrategiqueViewSet, CadreStrategiqueViewSet, ElementStrategiqueViewSet, TypeNiveauViewSet

router = DefaultRouter()
router.register("cadres-strategiques", CadreStrategiqueViewSet, basename="cadre-strategique")
router.register("types-niveaux", TypeNiveauViewSet, basename="type-niveau")
router.register("elements-strategiques", ElementStrategiqueViewSet, basename="element-strategique")
router.register("appreciations-strategiques", AppreciationStrategiqueViewSet, basename="appreciation-strategique")

urlpatterns = router.urls
