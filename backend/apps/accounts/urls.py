from django.urls import path
from rest_framework.routers import DefaultRouter

from .demo import connexion_demo

from .views import (
    DemandeInscriptionViewSet, RoleViewSet, UserViewSet, connexion_code, connexion_renvoyer, inscription, inscription_offre,
)

router = DefaultRouter()
router.register("utilisateurs", UserViewSet, basename="utilisateur")
router.register("roles", RoleViewSet, basename="role")
router.register("demandes-inscription", DemandeInscriptionViewSet, basename="demande-inscription")

urlpatterns = router.urls + [
    # Code de connexion envoyé par courriel (apps.accounts.double_auth).
    path("auth/double-authentification/code/", connexion_code, name="connexion-code"),
    path("auth/double-authentification/renvoyer/", connexion_renvoyer, name="connexion-renvoyer"),
    # Page d'accueil : profil d'une organisation, puis abonnement (apps.accounts.inscriptions).
    path("public/inscription/", inscription, name="inscription"),
    path("public/inscription/offre/", inscription_offre, name="inscription-offre"),
    path("public/demo/", connexion_demo, name="connexion-demo"),
]
