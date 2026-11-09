from django.urls import path
from rest_framework.routers import DefaultRouter

from . import console, site

router = DefaultRouter()
# Site vitrine, géré dans la console Expertise-ID.
router.register("console/site/actualites", site.ActualiteConsoleViewSet, basename="console-site-actualite")
router.register("console/site/partenaires", site.PartenaireConsoleViewSet, basename="console-site-partenaire")

urlpatterns = router.urls + [
    # Site vitrine : lecture publique (actualités publiées, partenaires visibles, leurs images).
    path("public/site/actualites/", site.actualites_publiques, name="site-actualites"),
    path("public/site/actualites/<int:pk>/", site.actualites_publiques, name="site-actualite"),
    path("public/site/partenaires/", site.partenaires_publics, name="site-partenaires"),
    path("public/site/images/<str:type_>/<int:pk>/", site.image_publique, name="site-image"),
    # Console Expertise-ID (adresse principale, opérateurs de la plateforme).
    path("console/organisations/", console.organisations, name="console-organisations"),
    path("console/organisations/<int:pk>/statut/", console.changer_statut, name="console-organisation-statut"),
    path("console/organisations/<int:pk>/stockage/", console.changer_stockage, name="console-organisation-stockage"),
    # Espace de stockage de l'organisation du compte connecté.
    path("stockage/", console.stockage, name="stockage"),
    path("stockage/achat/", console.acheter_stockage, name="stockage-achat"),
    path("stockage/paiement/<str:reference>/", console.paiement_stockage, name="stockage-paiement"),
    path("console/demandes/", console.demandes, name="console-demandes"),
    path("console/demandes/<int:pk>/activer/", console.activer, name="console-demande-activer"),
]
