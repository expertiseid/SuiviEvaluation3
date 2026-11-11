"""
Journal d'audit automatique des exports et des suppressions, dans tous les modules (RGPD : traçabilité
des sorties et des effacements de données), sans rien à ajouter dans chaque écran.

- Export : toute réponse réussie (2xx) d'une adresse de l'API qui contient « export » (export,
  exporter, exporter-suivi, carte/export…), pour un compte connecté ; les paramètres de la requête
  (projet, période…) sont gardés, jamais le contenu exporté.
- Suppression : toute requête DELETE réussie, et les suppressions groupées (supprimer-selection,
  corbeille/vider). L'élément est désigné par son adresse (son nom n'existe plus).
- Le mécanisme de plaintes et le journal lui-même ont leur propre journalisation, plus détaillée
  (apps.plaintes.audit_plaintes, apps.core.views) : exclus ici, pour ne pas compter deux fois.
- Une erreur d'écriture dans le journal ne fait jamais échouer la requête : elle est signalée dans
  les journaux du serveur.
"""
import logging
import re

from .audit import A, auditer

logger = logging.getLogger(__name__)

EXCLUS = re.compile(r"^/api/v1/(plaintes|journal-audit|public|auth|session)/")
SUPPRESSION_GROUPEE = re.compile(r"/(supprimer-selection|corbeille/vider)/$")
PARAMETRES_SECRETS = {"jeton", "token", "code"}


def evenement(request, statut):
    """(action, module) à journaliser pour cette requête, ou None."""
    chemin = request.path
    if not 200 <= statut < 300 or not chemin.startswith("/api/v1/") or EXCLUS.match(chemin):
        return None
    module = chemin.split("/")[3]
    if request.method == "DELETE" or (request.method == "POST" and SUPPRESSION_GROUPEE.search(chemin)):
        return A.SUPPRESSION, module
    if request.method in ("GET", "POST") and "export" in chemin:
        return A.EXPORT, module
    return None


class JournalAutomatiqueMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)
        try:
            self._journaliser(request, reponse)
        except Exception:  # le journal ne doit jamais empêcher un export ou une suppression
            logger.exception("Journal d'audit automatique : écriture impossible pour %s %s", request.method, request.path)
        return reponse

    def _journaliser(self, request, reponse):
        utilisateur = getattr(request, "user", None)
        if not utilisateur or not utilisateur.is_authenticated:
            return
        trouve = evenement(request, reponse.status_code)
        if trouve is None:
            return
        action, module = trouve
        parametres = {cle: valeur for cle, valeur in request.GET.items() if cle not in PARAMETRES_SECRETS}
        auditer(utilisateur, action, request.path, module=module, **({"parametres": parametres} if parametres else {}))
