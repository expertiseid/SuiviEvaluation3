"""
Mode démonstration (MODE_DEMO=True, sur l'installation de démonstration seulement : données fictives).

- « Essayer la démo » (page d'accueil) connecte directement le compte « visiteur_demo », sans mot de
  passe ni code : il voit toutes les rubriques et tous les écrans, comme un Administrateur.
- Il peut ouvrir chaque formulaire, le remplir et cliquer sur « Enregistrer » : rien n'est conservé.
  Toute écriture (POST, PUT, PATCH, DELETE) est refusée avec le code « mode_demo » ; l'interface
  l'annonce comme un enregistrement simulé. Seuls les exports et aperçus (lecture) restent permis.
- Hors MODE_DEMO, la connexion de démonstration est refusée et ce filtre ne fait rien.
"""
import re

from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

IDENTIFIANT = "visiteur_demo"
MARQUE = "demo"
# Écritures de pure lecture (exports, aperçus, renouvellement du jeton) : permises au visiteur.
LECTURES = re.compile(r"/(auth/token/refresh|export[a-z-]*|exporter[a-z-]*|apercu[a-z-]*|telecharger[a-z-]*|lien)/?($|\?)")


def actif() -> bool:
    """Installation de démonstration, ou (multi-organisations) espace de démonstration."""
    from apps.organisations.contexte import courante

    org = courante()
    return getattr(settings, "MODE_DEMO", False) or bool(org and org.mode_demo)


def visiteur():
    from .constants import ROLE_ADMIN
    from .models import User

    utilisateur, cree = User.objects.get_or_create(
        username=IDENTIFIANT,
        defaults={"first_name": "Visiteur", "last_name": "démo", "role": ROLE_ADMIN, "email": "visiteur.demo@example.org"},
    )
    if cree:
        utilisateur.set_unusable_password()
        utilisateur.save()
    return utilisateur


class LimiteDemo(AnonRateThrottle):
    rate = "60/hour"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LimiteDemo])
def connexion_demo(request):
    """Jetons du visiteur de démonstration (installation de démonstration seulement)."""
    from .double_auth import jetons

    from apps.organisations import contexte

    if contexte.actif() and contexte.courante() is None:
        # Adresse unique : la démonstration est l'espace marqué « démonstration » du registre.
        org = espace_demo()
        if org is None:
            raise PermissionDenied("La démonstration n'est pas disponible.")
        with contexte.dans_organisation(org):
            return Response(jetons(visiteur(), **{MARQUE: True}))
    if not actif():
        raise PermissionDenied("La démonstration n'est pas disponible sur cette installation.")
    return Response(jetons(visiteur(), **{MARQUE: True}))


def espace_demo():
    """Espace de démonstration actif de la plateforme multi-organisations, sinon None."""
    from apps.organisations.models import Organisation

    return Organisation.objects.using("central").filter(mode_demo=True, statut=Organisation.Statut.ACTIVE).first()


class ModeDemoMiddleware:
    """Refuse toute écriture du visiteur de démonstration : l'enregistrement est seulement simulé."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if actif() and request.method not in ("GET", "HEAD", "OPTIONS") and not LECTURES.search(request.path):
            from rest_framework_simplejwt.authentication import JWTAuthentication

            try:
                authentification = JWTAuthentication().authenticate(request)
            except Exception:
                authentification = None
            if authentification and (authentification[1].get(MARQUE) or authentification[0].username == IDENTIFIANT):
                return JsonResponse({"detail": "Mode démonstration : enregistrement simulé, rien n'est conservé.",
                                     "code": "mode_demo"}, status=403)
        return self.get_response(request)
