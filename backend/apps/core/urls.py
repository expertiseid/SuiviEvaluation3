from django.urls import path
from rest_framework.routers import DefaultRouter

from . import recherche, vues_transfert
from .views import JournalAuditViewSet, TraductionCorrigeeViewSet, activite, identite, logo_organisation, traductions

router = DefaultRouter()
router.register("traductions-corrigees", TraductionCorrigeeViewSet, basename="traduction-corrigee")
router.register("journal-audit", JournalAuditViewSet, basename="journal-audit")

urlpatterns = router.urls + [
    path("traductions/", traductions, name="traductions"),
    path("identite/", identite, name="identite"),
    path("recherche/", recherche.rechercher, name="recherche"),
    path("identite/logo/", logo_organisation, name="identite-logo"),
    path("session/activite/", activite, name="session-activite"),
    path("transfert/exporter/", vues_transfert.exporter, name="transfert-exporter"),
    path("transfert/morceau/", vues_transfert.recevoir_morceau, name="transfert-morceau"),
    path("transfert/reprendre/", vues_transfert.reprendre, name="transfert-reprendre"),
    path("transfert/reprise/", vues_transfert.suivre_reprise, name="transfert-reprise"),
    path("transfert/retirer/", vues_transfert.retirer, name="transfert-retirer"),
]
