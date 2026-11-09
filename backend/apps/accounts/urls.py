from django.urls import path
from rest_framework.routers import DefaultRouter

from .demo import connexion_demo

from .views import (
    DemandeInscriptionViewSet, RoleViewSet, UserViewSet, connexion_code, connexion_renvoyer, inscription, inscription_offre,
    inscription_paiement, inscription_paiement_etat, inscription_paiement_notification, inscription_tarifs,
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
    path("public/inscription/tarifs/", inscription_tarifs, name="inscription-tarifs"),
    path("public/inscription/paiement/", inscription_paiement, name="inscription-paiement"),
    path("public/inscription/paiement/notification/", inscription_paiement_notification, name="inscription-paiement-notification"),
    path("public/inscription/paiement/<str:reference>/", inscription_paiement_etat, name="inscription-paiement-etat"),
    path("public/demo/", connexion_demo, name="connexion-demo"),
]
