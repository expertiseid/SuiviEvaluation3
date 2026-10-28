from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ActiviteViewSet,
    EquipeViewSet,
    FenetreRapportageViewSet,
    JalonLivrableViewSet,
    NiveauActiviteViewSet,
    ProjetViewSet,
    SousActiviteViewSet,
    TauxManuelViewSet,
    approbations,
    parametres_calcul,
    parametres_rapportage,
    traiter_demande_vue,
    traiter_saisie_vue,
)

router = DefaultRouter()
router.register("projets", ProjetViewSet, basename="projet")
router.register("activites", ActiviteViewSet, basename="activite")
router.register("sous-activites", SousActiviteViewSet, basename="sous-activite")
router.register("niveaux-activite", NiveauActiviteViewSet, basename="niveau-activite")
router.register("equipes", EquipeViewSet, basename="equipe")
router.register("jalons-livrables", JalonLivrableViewSet, basename="jalon-livrable")
router.register("taux-manuels", TauxManuelViewSet, basename="taux-manuel")
router.register("periodes-rapportage", FenetreRapportageViewSet, basename="periode-rapportage")

urlpatterns = [
    path("parametres-calcul/", parametres_calcul, name="parametres-calcul"),
    path("parametres-rapportage/", parametres_rapportage, name="parametres-rapportage"),
    path("approbations/", approbations, name="approbations"),
    path("approbations/saisies/<str:type_saisie>/<int:pk>/", traiter_saisie_vue, name="approbation-saisie"),
    path("approbations/demandes/<int:pk>/", traiter_demande_vue, name="approbation-demande"),
    *router.urls,
]
