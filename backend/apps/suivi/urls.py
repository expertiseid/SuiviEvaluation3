from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    PeriodePlanificationViewSet,
    PointSuiviViewSet,
    TranchePlanifieeViewSet,
    suivi_dashboard_projet,
    suivi_exporter_excel,
    suivi_exporter_pdf,
)

router = DefaultRouter()
router.register("points-suivi", PointSuiviViewSet, basename="point-suivi")
router.register("tranches-planifiees", TranchePlanifieeViewSet, basename="tranche-planifiee")
router.register("periodes-planification", PeriodePlanificationViewSet, basename="periode-planification")

urlpatterns = router.urls + [
    path("suivi/projets/<int:projet_id>/dashboard/", suivi_dashboard_projet, name="suivi-dashboard-projet"),
    path("suivi/projets/<int:projet_id>/exporter/excel/", suivi_exporter_excel, name="suivi-exporter-excel"),
    path("suivi/projets/<int:projet_id>/exporter/pdf/", suivi_exporter_pdf, name="suivi-exporter-pdf"),
]
