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
router.register("plaintes/prestataires", views.PrestataireViewSet, basename="plainte-prestataire")
router.register("plaintes/modeles-messages", views.ModeleMessageViewSet, basename="plainte-modele-message")
router.register("plaintes/actions-correctives", views.ActionCorrectiveViewSet, basename="plainte-action-corrective")
router.register("plaintes/dossiers", views.DossierViewSet, basename="plainte-dossier")
router.register("plaintes/habilitations", views.HabilitationViewSet, basename="plainte-habilitation")
router.register("plaintes/demandes-droits", views.DemandeDroitsViewSet, basename="plainte-demande-droits")
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
    path("plaintes/tableau-de-bord/", views.tableau_de_bord, name="plaintes-tableau"),
    path("plaintes/tableau-de-bord/catalogue/", views.catalogue_tableau, name="plaintes-tableau-catalogue"),
    path("plaintes/tableau-de-bord/export/<str:format_>/", views.export_tableau, name="plaintes-tableau-export"),
    path("plaintes/projets/<int:projet_id>/retours/", views.retours_projet, name="plaintes-retours-projet"),
    # Hors de /plaintes/ : chacun règle sa propre copie d'une vue, même en lecture seule sur le module.
    path("plaintes-tableau/configuration/", views.configuration_tableau, name="plaintes-tableau-configuration"),
    # Hors de /plaintes/ : tout utilisateur qui voit un dossier peut le signaler comme sensible.
    path("plaintes-signaler/<int:pk>/", views.signaler_sensible, name="plaintes-signaler"),
    # Sans compte : formulaire public et suivi par code (hors de /plaintes/, que protègent les droits du module).
    path("public/plaintes/formulaire/", public.formulaire, name="plaintes-public-formulaire"),
    path("public/plaintes/deposer/", public.deposer, name="plaintes-public-deposer"),
    path("public/plaintes/suivi/", public.suivi, name="plaintes-public-suivi"),
    path("public/plaintes/complement/", public.complement, name="plaintes-public-complement"),
    # Lien temporaire signé (pieces.py) : ouvert dans un nouvel onglet, donc sans jeton de connexion.
    path("plaintes-piece/<str:jeton>/", views.telecharger_piece, name="plaintes-piece"),
    path("", include(router.urls)),
]
