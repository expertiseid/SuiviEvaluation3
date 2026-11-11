from django.urls import path
from rest_framework.routers import DefaultRouter

from . import console, newsletter, site

router = DefaultRouter()
# Site vitrine, géré dans la console Expertise-ID.
router.register("console/site/actualites", site.ActualiteConsoleViewSet, basename="console-site-actualite")
router.register("console/site/partenaires", site.PartenaireConsoleViewSet, basename="console-site-partenaire")
router.register("console/site/newsletter/abonnes", newsletter.AbonneConsoleViewSet, basename="console-newsletter-abonne")
router.register("console/site/newsletter/envois", newsletter.EnvoiConsoleViewSet, basename="console-newsletter-envoi")

urlpatterns = router.urls + [
    # Site vitrine : lecture publique (actualités publiées, partenaires visibles, leurs images).
    path("public/site/actualites/", site.actualites_publiques, name="site-actualites"),
    path("public/site/actualites/<int:pk>/", site.actualites_publiques, name="site-actualite"),
    path("public/site/partenaires/", site.partenaires_publics, name="site-partenaires"),
    # Newsletter (apps.organisations.newsletter) : inscription, confirmation, désinscription.
    path("public/site/newsletter/", newsletter.inscription, name="newsletter-inscription"),
    path("public/site/newsletter/confirmer/", newsletter.confirmer, name="newsletter-confirmer"),
    path("public/site/newsletter/desinscrire/", newsletter.desinscrire, name="newsletter-desinscrire"),
    path("public/site/images/<str:type_>/<int:pk>/", site.image_publique, name="site-image"),
    # Console Expertise-ID (adresse principale, opérateurs de la plateforme).
    path("console/organisations/", console.organisations, name="console-organisations"),
    path("console/organisations/<int:pk>/statut/", console.changer_statut, name="console-organisation-statut"),
    path("console/organisations/<int:pk>/stockage/", console.changer_stockage, name="console-organisation-stockage"),
    # Espace de stockage de l'organisation du compte connecté.
    path("abonnement/", console.abonnement_organisation, name="abonnement"),
    path("abonnement/devis/", console.abonnement_devis, name="abonnement-devis"),
    path("abonnement/payer/", console.abonnement_payer, name="abonnement-payer"),
    path("abonnement/paiement/<str:reference>/", console.abonnement_paiement, name="abonnement-paiement"),
    path("console/organisations/<int:pk>/abonnement/", console.changer_abonnement, name="console-organisation-abonnement"),
    path("stockage/", console.stockage, name="stockage"),
    path("stockage/achat/", console.acheter_stockage, name="stockage-achat"),
    path("stockage/paiement/<str:reference>/", console.paiement_stockage, name="stockage-paiement"),
    path("console/vue-ensemble/", console.vue_ensemble, name="console-vue-ensemble"),
    path("console/demandes/", console.demandes, name="console-demandes"),
    path("console/demandes/<int:pk>/activer/", console.activer, name="console-demande-activer"),
]
