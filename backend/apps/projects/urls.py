from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ActiviteViewSet,
    EquipeViewSet,
    JalonLivrableViewSet,
    NiveauActiviteViewSet,
    ProjetViewSet,
    SousActiviteViewSet,
    TauxManuelViewSet,
    parametres_calcul,
)

router = DefaultRouter()
router.register("projets", ProjetViewSet, basename="projet")
router.register("activites", ActiviteViewSet, basename="activite")
router.register("sous-activites", SousActiviteViewSet, basename="sous-activite")
router.register("niveaux-activite", NiveauActiviteViewSet, basename="niveau-activite")
router.register("equipes", EquipeViewSet, basename="equipe")
router.register("jalons-livrables", JalonLivrableViewSet, basename="jalon-livrable")
router.register("taux-manuels", TauxManuelViewSet, basename="taux-manuel")

urlpatterns = [path("parametres-calcul/", parametres_calcul, name="parametres-calcul"), *router.urls]
