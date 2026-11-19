"""
Exports désactivés pour certains utilisateurs (User.peut_exporter, réglé par l'Administrateur dans la fiche).

Tout fichier que la plateforme fait télécharger (réponse « attachment » : Excel, PDF, Word, images, zip…, de
tous les modules, y compris les exports « comme à l'écran ») est refusé à ces utilisateurs. Restent permis :
les modèles d'import vierges, l'attestation de formation, l'ouverture des documents dans le navigateur
(« inline ») et la sauvegarde de l'espace, qui a sa propre autorisation (User.export_global). Les liens signés
de téléchargement des documents (apps.documents.liens) appliquent la même règle.
"""
import re

from django.http import JsonResponse

PERMIS = re.compile(r"^/api/v1/(transfert/|formation/)|modele")
MESSAGE = "L'export est désactivé pour votre compte : demandez l'autorisation à l'administrateur."


def export_autorise(utilisateur) -> bool:
    from apps.accounts.constants import ROLE_ADMIN

    return utilisateur.role == ROLE_ADMIN or utilisateur.peut_exporter


class ExportsDesactivesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)
        if (not request.path.startswith("/api/v1/") or PERMIS.search(request.path)
                or not str(reponse.get("Content-Disposition", "")).lower().startswith("attachment")):
            return reponse
        from .approbation_generale import _utilisateur

        utilisateur = _utilisateur(request)
        if utilisateur is None or export_autorise(utilisateur):
            return reponse
        fichier = getattr(reponse, "file_to_stream", None)  # pas reponse.close() : elle fermerait la connexion à la base
        if fichier is not None:
            fichier.close()
        return JsonResponse({"detail": MESSAGE, "code": "export_desactive"}, status=403)
