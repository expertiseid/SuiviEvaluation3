"""
Pages publiques du mécanisme, sans compte : formulaire de dépôt et suivi par code.

Protection contre les envois automatisés : champ piège invisible (« site_web ») et nombre d'envois
limité par connexion et par heure. L'adresse IP ne sert qu'à ce contrôle : elle n'est jamais
enregistrée, et le compteur n'en garde qu'une empreinte, effacée à la fin de la période.
"""
import hashlib

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Canal, Categorie, Dossier, Mecanisme, TypeRetour
from .reception import empreinte_code, lire_envoi, recevoir


class _Limite(SimpleRateThrottle):
    """Limite d'envois par connexion, sur l'empreinte de l'adresse (jamais l'adresse elle-même)."""

    def get_cache_key(self, request, view):
        empreinte = hashlib.sha256((self.get_ident(request) + settings.SECRET_KEY).encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": empreinte}


class LimiteDepot(_Limite):
    scope = "plaintes_depot"
    rate = getattr(settings, "PLAINTES_LIMITE_DEPOTS", "10/hour")


class LimiteSuivi(_Limite):
    scope = "plaintes_suivi"
    rate = getattr(settings, "PLAINTES_LIMITE_SUIVIS", "30/hour")


TROP = Response(
    {"detail": "Trop d'envois depuis cette connexion. Réessayez un peu plus tard."},
    status=status.HTTP_429_TOO_MANY_REQUESTS,
)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def formulaire(request):
    """Ce qu'affiche le formulaire public : textes, types, catégories, projets couverts."""
    mecanisme = Mecanisme.courant()
    if not mecanisme.actif:
        return Response({"disponible": False, "nom": mecanisme.nom})
    from apps.projects.models import Projet

    projets = mecanisme.projets.all() if mecanisme.projets.exists() else Projet.objects.all()
    fixe = request.query_params.get("projet", "")
    if fixe.isdigit():
        projets = projets.filter(pk=fixe)
    categories = Categorie.objects.filter(actif=True).filter(Q(parent__isnull=True) | Q(parent__actif=True))
    return Response({
        "disponible": True,
        "nom": mecanisme.nom,
        "texte_information": mecanisme.texte_information,
        "anonymat_autorise": mecanisme.anonymat_autorise,
        "pieces": _pieces_acceptees(mecanisme),
        "langues": mecanisme.langues,
        "projet_fixe": fixe.isdigit() and projets.exists(),
        "types": [{"id": t.id, "nom": t.nom, "description": t.description}
                  for t in TypeRetour.objects.filter(actif=True)],
        "categories": [{"id": c.id, "nom": c.nom, "parent": c.parent_id} for c in categories.order_by("ordre", "nom")],
        "projets": [{"id": p.id, "code": p.code, "nom": p.nom} for p in projets.order_by("nom")],
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def deposer(request):
    """Dépôt d'un retour : renvoie le numéro de dossier et le code de suivi (affiché une seule fois)."""
    if not LimiteDepot().allow_request(request, None):
        return TROP
    if request.data.get("site_web"):  # champ piège, invisible pour une personne
        return Response({"detail": "Envoi refusé."}, status=status.HTTP_400_BAD_REQUEST)
    donnees, fichiers = lire_envoi(request)
    if donnees.get("site_web"):
        return Response({"detail": "Envoi refusé."}, status=status.HTTP_400_BAD_REQUEST)
    dossier, code = recevoir(donnees, Canal.FORMULAIRE, public=True, fichiers=fichiers)
    return Response({"numero": dossier.numero, "code_suivi": code}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def suivi(request):
    """État général d'un dossier à partir de son code de suivi — aucun détail sur son contenu."""
    if not LimiteSuivi().allow_request(request, None):
        return TROP
    dossier = Dossier.objects.filter(empreinte_code_suivi=empreinte_code(request.data.get("code", ""))).first()
    if dossier is None:
        return Response({"detail": "Code de suivi inconnu. Vérifiez qu'il est recopié sans erreur."},
                        status=status.HTTP_404_NOT_FOUND)
    mecanisme = Mecanisme.courant()
    return Response({
        "numero": dossier.numero,
        "date_reception": dossier.date_reception,
        "statut": dossier.statut,
        # Peut-il encore compléter son dossier (précision, fichiers) ? Rien sur le contenu.
        "complement_possible": not dossier.anonymise and dossier.statut != "CLOTURE",
        "pieces": _pieces_acceptees(mecanisme),
    })


def _pieces_acceptees(mecanisme):
    from .pieces import FORMATS_ACCEPTES, PIECES_PAR_ENVOI, taille_max_mo

    if not mecanisme.pieces_formulaire_public:
        return None
    return {"formats": FORMATS_ACCEPTES, "taille_max_mo": taille_max_mo(mecanisme), "nombre_max": PIECES_PAR_ENVOI}


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def complement(request):
    """Le plaignant complète son dossier avec son code de suivi : précision écrite et/ou fichiers."""
    from .pieces import completer

    if not LimiteDepot().allow_request(request, None):
        return TROP
    donnees, fichiers = lire_envoi(request)
    dossier = Dossier.objects.filter(empreinte_code_suivi=empreinte_code(donnees.get("code", ""))).first()
    if dossier is None:
        return Response({"detail": "Code de suivi inconnu. Vérifiez qu'il est recopié sans erreur."},
                        status=status.HTTP_404_NOT_FOUND)
    completer(dossier, donnees, fichiers)
    return Response({"numero": dossier.numero}, status=status.HTTP_201_CREATED)
