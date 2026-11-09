"""
Organisation de la requête, sur une plateforme à adresse unique (voir contexte.py) :

1. jeton de connexion (Authorization: Bearer …) : sa marque « org », posée à la connexion ;
2. renouvellement du jeton (/auth/token/refresh/) : la marque « org » du jeton de rafraîchissement ;
3. pages publiques d'une organisation (formulaire et suivi des plaintes, lien de partage, liens de
   fichiers, logo) : en-tête X-Organisation ou paramètre ?org= (ses liens le portent).

Les jetons sont vérifiés (signature, expiration) avant d'en lire la marque : on ne peut pas se faire
passer pour une autre organisation. Abonnement terminé depuis plus de 7 jours (abonnement.py) : accès
bloqué, sauf la page Abonnement pour payer. Sans organisation : base centrale, et seules les routes publiques
de la plateforme répondent (connexion, inscription, démonstration, console Expertise-ID).
"""
import json

from django.http import JsonResponse

from . import abonnement, contexte

PUBLIQUES_PRINCIPALES = ("/api/v1/identite/", "/api/v1/traductions/", "/api/v1/public/inscription/",
                         "/api/v1/public/inscription/offre/", "/api/v1/public/demo/", "/admin/", "/api/schema/", "/api/docs/",
                         # Connexion (courriel et mot de passe, puis code), opérateurs Expertise-ID et console.
                         "/api/v1/auth/", "/api/v1/console/", "/api/v1/utilisateurs/me/",
                         # Site vitrine : actualités et partenaires (base centrale).
                         "/api/v1/public/site/")
RENOUVELLEMENT = "/api/v1/auth/token/refresh/"
# Abonnement terminé depuis plus de 7 jours : seules la page Abonnement (payer) et la session répondent.
AUTORISEES_SI_BLOQUE = ("/api/v1/abonnement/", "/api/v1/identite/", "/api/v1/utilisateurs/me/", "/api/v1/auth/",
                        "/api/v1/traductions/")
INVALIDE = object()


def _marque_org(jeton, classe):
    """Marque « org » d'un jeton valide ; INVALIDE si le jeton est faux ou expiré."""
    try:
        return classe(jeton).get("org", "")
    except Exception:
        return INVALIDE


def organisation_demandee(request):
    """Sous-domaine (identifiant interne) de l'organisation visée, « » pour la plateforme, INVALIDE si jeton refusé."""
    from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

    entete = request.headers.get("Authorization", "")
    if entete.startswith("Bearer "):
        return _marque_org(entete[7:].strip(), AccessToken)
    if request.path == RENOUVELLEMENT and request.method == "POST":
        try:
            corps = json.loads(request.body or b"{}")
        except ValueError:
            corps = {}
        marque = _marque_org(corps.get("refresh") or "", RefreshToken)
        if marque is not INVALIDE:
            return marque
    return (request.headers.get("X-Organisation") or request.GET.get("org") or "").strip().lower()


class OrganisationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not contexte.actif():
            return self.get_response(request)
        from .models import Organisation

        publique = not request.path.startswith("/api/") or request.path.startswith(PUBLIQUES_PRINCIPALES)
        sous_domaine = organisation_demandee(request)
        if sous_domaine is INVALIDE:
            # Jeton expiré ou faux : l'interface le renouvelle (401), ou renvoie à la connexion.
            if publique:
                return self.get_response(request)
            return JsonResponse({"detail": "Session expirée : reconnectez-vous.", "code": "token_not_valid"}, status=401)
        if not sous_domaine:
            if not publique:
                connecte = request.headers.get("Authorization", "").startswith("Bearer ")
                return JsonResponse({"detail": "Connectez-vous avec le compte de votre organisation.", "code": "connexion_requise"},
                                    status=403 if connecte else 401)
            return self.get_response(request)
        org = Organisation.objects.filter(sous_domaine=sous_domaine).first()
        if org is None or org.statut == Organisation.Statut.EN_ATTENTE:
            return JsonResponse({"detail": "Cette organisation n'existe pas.", "code": "espace_inconnu"}, status=404)
        if org.statut == Organisation.Statut.SUSPENDUE:
            return JsonResponse({"detail": "L'abonnement de cette organisation est suspendu. Contactez Expertise-ID.",
                                 "code": "organisation_suspendue"}, status=403)
        if abonnement.bloque(org) and not request.path.startswith(AUTORISEES_SI_BLOQUE):
            return JsonResponse({"detail": "L'abonnement de votre organisation est terminé : l'accès est bloqué jusqu'au "
                                           "renouvellement, depuis la page Abonnement.", "code": "abonnement_expire"}, status=403)
        request.organisation = org
        with contexte.dans_organisation(org):
            return self.get_response(request)
