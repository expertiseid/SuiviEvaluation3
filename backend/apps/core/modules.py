"""
Droits par module, réglés utilisateur par utilisateur (User.acces_modules, écran Utilisateurs).

Pour chaque module : MASQUE (caché), LECTURE (consultation) ou ECRITURE (création et
modification). Un module non réglé suit le niveau d'accès de l'utilisateur (par défaut : tout).
L'Administrateur a toujours tout. Les onglets (« projet:… », « suivi:… ») ne peuvent qu'être
cachés ; leurs données relèvent du module dont ils font partie.

Côté serveur (ModulesMasquesMiddleware) :
- création, modification et suppression refusées dans un module qui n'est pas en ECRITURE ;
- dans un module en ECRITURE, l'utilisateur peut écrire même si son niveau d'accès général est
  « lecture seule » (core.permissions.peut_modifier consulte le module de la requête) ;
- un module caché dont les données ne servent pas ailleurs est refusé même en lecture
  (bénéficiaires, documents, financement) ; les autres (projets, zones…) alimentent aussi les
  formulaires communs : ils sont seulement cachés à l'écran.
"""
from contextvars import ContextVar

from django.http import JsonResponse

MASQUE, LECTURE, ECRITURE = "MASQUE", "LECTURE", "ECRITURE"
NIVEAUX = (MASQUE, LECTURE, ECRITURE)

# Module (route du menu ou onglet) → préfixes d'API dont il protège l'écriture.
API_PAR_MODULE = {
    "/planification": ["/api/v1/planification/"],
    "/strategie": [
        "/api/v1/cadres-strategiques", "/api/v1/types-niveaux", "/api/v1/elements-strategiques",
        "/api/v1/appreciations-strategiques", "/api/v1/rapports/suivi-strategique",
    ],
    "/projets": [
        "/api/v1/projets", "/api/v1/activites", "/api/v1/sous-activites", "/api/v1/niveaux-activite",
        "/api/v1/jalons-livrables", "/api/v1/tranches-planifiees", "/api/v1/periodes-planification",
        "/api/v1/partenaires-projet", "/api/v1/rapports/cadre-logique",
    ],
    "/indicateurs": ["/api/v1/indicateurs", "/api/v1/valeurs-indicateurs"],
    "/suivi": ["/api/v1/points-suivi", "/api/v1/taux-manuels", "/api/v1/suivi/"],
    # Avant « /beneficiaires » : la carte des bénéficiaires relève de la rubrique Carte.
    "/carte": ["/api/v1/couches-importees", "/api/v1/beneficiaires/carte", "/api/v1/carte/"],
    "/beneficiaires": [
        "/api/v1/beneficiaires", "/api/v1/participations-projet", "/api/v1/signalements-doublons",
        "/api/v1/variables-beneficiaires",
    ],
    "/documents": ["/api/v1/documents", "/api/v1/dossiers", "/api/v1/pieces-justificatives"],
    "/zones-administratives": ["/api/v1/zones", "/api/v1/niveaux-administratifs"],
    "/plaintes": ["/api/v1/plaintes/"],
    "projet:equipe": ["/api/v1/equipes"],
    "projet:risques": ["/api/v1/risques", "/api/v1/evaluations-risques", "/api/v1/rapports/risques"],
    "projet:financement": ["/api/v1/financements", "/api/v1/rallonges-financement", "/api/v1/rapports/financier"],
}
# Modules refusés même en lecture quand ils sont cachés.
LECTURE_BLOQUEE_SI_MASQUE = {"/beneficiaires", "/documents", "projet:financement"}

# Module de la requête en cours (voir core.permissions.peut_modifier).
module_courant: ContextVar[str | None] = ContextVar("module_courant", default=None)


def module_de(chemin: str):
    return next((m for m, prefixes in API_PAR_MODULE.items() if any(chemin.startswith(p) for p in prefixes)), None)


def acces_module(user, cle: str) -> str:
    """Droit effectif de l'utilisateur sur un module : son réglage, sinon son niveau d'accès."""
    from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN

    if user.role == ROLE_ADMIN:
        return ECRITURE
    niveau = (user.acces_modules or {}).get(cle)
    if niveau in NIVEAUX:
        return niveau
    return ECRITURE if user.niveau_acces == NIVEAU_ACCES_LECTURE_ECRITURE else LECTURE


class ModulesMasquesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        module = module_de(request.path)
        if module is None:
            return self.get_response(request)
        from rest_framework_simplejwt.authentication import JWTAuthentication

        try:
            authentification = JWTAuthentication().authenticate(request)
        except Exception:  # jeton invalide : la vue répondra 401 elle-même
            authentification = None
        if authentification:
            niveau = acces_module(authentification[0], module)
            if niveau == MASQUE and module in LECTURE_BLOQUEE_SI_MASQUE:
                return JsonResponse({"detail": "Ce module n'est pas accessible avec votre compte."}, status=403)
            if niveau != ECRITURE and request.method not in ("GET", "HEAD", "OPTIONS"):
                return JsonResponse(
                    {"detail": "Votre compte permet de consulter ce module, pas d'y créer ou modifier."}, status=403
                )
        jeton = module_courant.set(module)
        try:
            return self.get_response(request)
        finally:
            module_courant.reset(jeton)
