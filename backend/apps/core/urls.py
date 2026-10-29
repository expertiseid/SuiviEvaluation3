from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import TraductionCorrigeeViewSet, traductions

router = DefaultRouter()
router.register("traductions-corrigees", TraductionCorrigeeViewSet, basename="traduction-corrigee")

urlpatterns = router.urls + [path("traductions/", traductions, name="traductions")]
