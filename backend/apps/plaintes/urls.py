from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import public, views

router = DefaultRouter()
router.register("plaintes/types", views.TypeRetourViewSet, basename="plainte-type")
router.register("plaintes/priorites", views.PrioriteViewSet, basename="plainte-priorite")
router.register("plaintes/circuits", views.CircuitViewSet, basename="plainte-circuit")
router.register("plaintes/etapes", views.EtapeCircuitViewSet, basename="plainte-etape")
router.register("plaintes/categories", views.CategorieViewSet, basename="plainte-categorie")
router.register("plaintes/jours-feries", views.JourFerieViewSet, basename="plainte-jour-ferie")
router.register("plaintes/dossiers", views.DossierViewSet, basename="plainte-dossier")
# Hors de /plaintes/ : chacun enregistre ses propres vues, même en lecture seule sur le module.
router.register("plaintes-vues", views.VueDossiersViewSet, basename="plainte-vue")

urlpatterns = [
    path("plaintes/mecanisme/", views.mecanisme, name="plaintes-mecanisme"),
    path("plaintes/mecanisme/activer/", views.activer, name="plaintes-activer"),
    path("plaintes/mecanisme/desactiver/", views.desactiver, name="plaintes-desactiver"),
    path("plaintes/modeles/", views.modeles, name="plaintes-modeles"),
    path("plaintes/canevas/", views.canevas, name="plaintes-canevas"),
    path("plaintes/canevas/importer/", views.importer_canevas, name="plaintes-canevas-importer"),
    path("plaintes/qr/", views.qr_formulaire, name="plaintes-qr"),
    # Sans compte : formulaire public et suivi par code (hors de /plaintes/, que protègent les droits du module).
    path("public/plaintes/formulaire/", public.formulaire, name="plaintes-public-formulaire"),
    path("public/plaintes/deposer/", public.deposer, name="plaintes-public-deposer"),
    path("public/plaintes/suivi/", public.suivi, name="plaintes-public-suivi"),
    path("", include(router.urls)),
]
