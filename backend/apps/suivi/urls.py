from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    PeriodePlanificationViewSet,
    canevas_suivi,
    canevas_suivi_apercu,
    canevas_suivi_importer,
    canevas_suivi_rapport_erreurs,
    PointSuiviViewSet,
    TranchePlanifieeViewSet,
    suivi_dashboard_projet,
    suivi_exporter_excel,
    suivi_exporter_pdf,
    suivi_exporter_word,
)

router = DefaultRouter()
router.register("points-suivi", PointSuiviViewSet, basename="point-suivi")
router.register("tranches-planifiees", TranchePlanifieeViewSet, basename="tranche-planifiee")
router.register("periodes-planification", PeriodePlanificationViewSet, basename="periode-planification")

urlpatterns = router.urls + [
    path("suivi/projets/<int:projet_id>/dashboard/", suivi_dashboard_projet, name="suivi-dashboard-projet"),
    path("suivi/projets/<int:projet_id>/exporter/excel/", suivi_exporter_excel, name="suivi-exporter-excel"),
    path("suivi/projets/<int:projet_id>/exporter/pdf/", suivi_exporter_pdf, name="suivi-exporter-pdf"),
    path("suivi/projets/<int:projet_id>/exporter/word/", suivi_exporter_word, name="suivi-exporter-word"),
    path("suivi/projets/<int:projet_id>/canevas/", canevas_suivi, name="suivi-canevas"),
    path("suivi/projets/<int:projet_id>/canevas/apercu/", canevas_suivi_apercu, name="suivi-canevas-apercu"),
    path("suivi/projets/<int:projet_id>/canevas/importer/", canevas_suivi_importer, name="suivi-canevas-importer"),
    path(
        "suivi/projets/<int:projet_id>/canevas/rapport-erreurs/",
        canevas_suivi_rapport_erreurs,
        name="suivi-canevas-rapport-erreurs",
    ),
]
