from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import JournalAuditViewSet, TraductionCorrigeeViewSet, identite, logo_organisation, traductions

router = DefaultRouter()
router.register("traductions-corrigees", TraductionCorrigeeViewSet, basename="traduction-corrigee")
router.register("journal-audit", JournalAuditViewSet, basename="journal-audit")

urlpatterns = router.urls + [
    path("traductions/", traductions, name="traductions"),
    path("identite/", identite, name="identite"),
    path("identite/logo/", logo_organisation, name="identite-logo"),
]
