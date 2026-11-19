"""
Approbation de n'importe quelle modification de la plateforme, avant qu'elle ne s'applique.

Quand :
- l'onglet (module, voir apps.core.modules) est dans IdentiteOrganisation.modules_a_approuver : pour tout le
  monde, sauf l'Administrateur ;
- ou l'utilisateur est réglé « tout ce qu'il renseigne doit être approuvé » (User.saisies_a_approuver), pour tous
  les onglets ou seulement ceux de User.modules_a_approuver.

Comment : la requête (création, modification, suppression) est exécutée « à blanc » dans une transaction
annulée. Si elle est valable et qu'elle a écrit en base, elle devient une demande (DemandeModification, cible
« generique ») au lieu de s'appliquer ; une requête invalide reçoit sa réponse habituelle (400…), une simple
lecture (export, aperçu…) passe normalement. À l'approbation, la requête est rejouée telle quelle, au nom de son
auteur et avec ses droits (rejouer).

Les saisies de réalisations (suivis, valeurs d'indicateurs, taux) gardent leur propre circuit : elles sont
enregistrées « en attente » (apps.projects.approbation). Les vues qui créent elles-mêmes une demande (planification,
stratégies : réponse 202) ne sont pas interceptées une seconde fois.
"""
import base64
import json
import re
from contextvars import ContextVar

from django.db import connections, transaction
from django.http import JsonResponse

# Jamais interceptées : connexion, approbations elles-mêmes, préférences, formation, notifications, traductions,
# et saisies de réalisations (circuit « en attente » propre).
EXCLUS = re.compile(
    r"^/api/v1/(auth/|approbations/|notifications|formation/|traductions|utilisateurs/moi|preferences|"
    r"points-suivi|valeurs-indicateurs|taux-manuels|journal|partage/|transfert/)"
)
# Écritures techniques qui ne sont pas des modifications (journal d'audit, jetons, sessions, cache).
TABLES_TECHNIQUES = re.compile(r'"?(core_evenementaudit|token_blacklist_\w+|django_session|django_cache\w*)"?', re.I)
ECRITURE_SQL = re.compile(r"^\s*(INSERT|UPDATE|DELETE)\b", re.I)
TAILLE_MAX = 15 * 1024 * 1024

_rejeu = ContextVar("rejeu_approuve", default=False)

LIBELLES_MODULES = {
    "/indicateurs": "Indicateurs", "/beneficiaires": "Bénéficiaires", "/documents": "Documents", "/projets": "Projets",
    "/strategie": "Stratégies", "/suivi": "Suivi", "/carte": "Cartographie", "/plaintes": "Plaintes et retours",
    "/zones-administratives": "Zones administratives", "/planification": "Planification",
    "projet:equipe": "Équipe de projet", "projet:risques": "Risques", "projet:pilotage": "Pilotage",
    "projet:financement": "Financement",
}


def approbation_requise(utilisateur, module=None) -> bool:
    """Ce que fait l'utilisateur dans ce module (celui de la requête par défaut) doit-il être approuvé ?"""
    from apps.accounts.constants import ROLE_ADMIN

    from .models import IdentiteOrganisation
    from .modules import module_courant

    if _rejeu.get() or not utilisateur or not getattr(utilisateur, "is_authenticated", False) or utilisateur.role == ROLE_ADMIN:
        return False
    module = module or module_courant.get()
    if getattr(utilisateur, "saisies_a_approuver", False) and (
            not utilisateur.modules_a_approuver or module in utilisateur.modules_a_approuver):
        return True
    return bool(module and module in (IdentiteOrganisation.courante().modules_a_approuver or []))


def _utilisateur(request):
    from rest_framework_simplejwt.authentication import JWTAuthentication

    try:
        authentification = JWTAuthentication().authenticate(request)
    except Exception:
        return None
    return authentification[0] if authentification else None


def _libelle(chemin, module, methode):
    from apps.projects.models import DemandeModification

    morceaux = [m for m in chemin.split("/") if m][2:]  # sans « api/v1 »
    sujet = LIBELLES_MODULES.get(module) or (morceaux[0].replace("-", " ").capitalize() if morceaux else chemin)
    numero = next((m for m in morceaux if m.isdigit()), None)
    action = {"POST": DemandeModification.Action.CREATION, "DELETE": DemandeModification.Action.SUPPRESSION}.get(
        methode, DemandeModification.Action.MODIFICATION)
    return f"{sujet}{f' (n° {numero})' if numero else ''} — {' / '.join(m for m in morceaux if not m.isdigit())}", action


def _projet(champs, reponse):
    """Projet concerné, s'il se lit dans les données envoyées ou dans la réponse de l'essai."""
    from apps.projects.models import Projet

    for source in (champs, getattr(reponse, "data", None)):
        valeur = source.get("projet") if isinstance(source, dict) else None
        if isinstance(valeur, int) or (isinstance(valeur, str) and valeur.isdigit()):
            return Projet.objects.filter(pk=int(valeur)).first()
    return None


class ApprobationGeneraleMiddleware:
    """Intercepte les modifications soumises à approbation (voir le module)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("GET", "HEAD", "OPTIONS") or not request.path.startswith("/api/v1/") or EXCLUS.match(request.path):
            return self.get_response(request)
        from .modules import module_de

        utilisateur = _utilisateur(request)
        if utilisateur is None or not approbation_requise(utilisateur, module_de(request.path)):
            return self.get_response(request)
        corps = request.body  # lu avant la vue : il sera rejoué à l'approbation
        if len(corps) > TAILLE_MAX:
            return JsonResponse({"detail": "Envoi trop lourd pour une demande d'approbation (15 Mo au plus)."}, status=400)

        ecritures = []

        def espion(execute, sql, params, many, contexte):
            if ECRITURE_SQL.match(sql) and not TABLES_TECHNIQUES.search(sql.split("(")[0][:200]):
                ecritures.append(sql[:80])
            return execute(sql, params, many, contexte)

        connexion = connections["default"]
        with transaction.atomic(using="default"):
            with connexion.execute_wrapper(espion):
                reponse = self.get_response(request)
            interceptee = 200 <= reponse.status_code < 300 and reponse.status_code != 202 and bool(ecritures)
            if interceptee:
                transaction.set_rollback(True, using="default")
        if not interceptee:
            return reponse
        return self._demande(request, utilisateur, corps, reponse)

    def _demande(self, request, utilisateur, corps, reponse):
        from apps.projects.models import DemandeModification

        from .modules import module_de

        type_contenu = request.META.get("CONTENT_TYPE", "")
        champs = {}
        if type_contenu.startswith("application/json") and corps:
            try:
                champs = json.loads(corps)
            except ValueError:
                champs = {}
        elif request.POST:
            champs = {cle: request.POST.get(cle) for cle in request.POST}
        libelle, action = _libelle(request.path, module_de(request.path), request.method)
        demande = DemandeModification.objects.create(
            projet=_projet(champs if isinstance(champs, dict) else {}, reponse),
            cible=DemandeModification.Cible.GENERIQUE, action=action, libelle=libelle[:300],
            donnees={
                "requete": {"methode": request.method, "chemin": request.path, "parametres": request.META.get("QUERY_STRING", ""),
                            "type": type_contenu, "corps": base64.b64encode(corps).decode()},
                "champs": champs if isinstance(champs, dict) else {},
                "fichiers": [f.name for f in request.FILES.values()] if request.FILES else [],
            },
            demandeur=utilisateur,
        )
        return JsonResponse({
            "demande_approbation": demande.id,
            "message": f"{demande.get_action_display()} envoyée pour approbation : elle sera appliquée une fois approuvée.",
        }, status=202)


def rejouer(demande):
    """Applique une demande générique approuvée : la requête est rejouée telle quelle, au nom de son auteur."""
    from django.urls import resolve
    from rest_framework.exceptions import ValidationError
    from rest_framework.test import APIRequestFactory, force_authenticate
    from simple_history.models import HistoricalRecords

    from .modules import module_courant, module_de

    requete = demande.donnees["requete"]
    chemin = requete["chemin"] + (f"?{requete['parametres']}" if requete["parametres"] else "")
    rejouee = APIRequestFactory().generic(requete["methode"], chemin, data=base64.b64decode(requete["corps"]),
                                          content_type=requete["type"] or "application/json")
    rejouee.user = demande.demandeur
    force_authenticate(rejouee, user=demande.demandeur)
    correspondance = resolve(requete["chemin"])
    precedente = getattr(HistoricalRecords.context, "request", None)
    HistoricalRecords.context.request = rejouee  # historique et contrôles au nom de l'auteur
    jeton_rejeu, jeton_module = _rejeu.set(True), module_courant.set(module_de(requete["chemin"]))
    try:
        reponse = correspondance.func(rejouee, *correspondance.args, **correspondance.kwargs)
        if hasattr(reponse, "render"):
            reponse.render()
    finally:
        module_courant.reset(jeton_module)
        _rejeu.reset(jeton_rejeu)
        HistoricalRecords.context.request = precedente
    if not 200 <= reponse.status_code < 300:
        detail = getattr(reponse, "data", None) or reponse.content[:300].decode(errors="ignore")
        raise ValidationError({"detail": f"La modification ne peut plus être appliquée : {detail}"})
