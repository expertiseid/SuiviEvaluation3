"""En-têtes de sécurité des réponses de l'API.

L'API ne renvoie que des données (JSON, fichiers) : le navigateur n'a rien à y exécuter. La politique
de contenu (Content-Security-Policy) le lui interdit, ce qui neutralise une éventuelle injection de
code dans une réponse. Les fichiers montrés en aperçu dans la plateforme (xframe_options_exempt,
ex. document partagé par lien) restent affichables dans une page de la même adresse.
"""

from django.middleware.common import CommonMiddleware

# Pages de l'API qui ont leur propre interface (documentation, administration Django) : non concernées.
CHEMINS_EXCLUS = ("/api/docs/", "/api/redoc/", "/admin/")

POLITIQUE_DONNEES = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
POLITIQUE_APERCU = "frame-ancestors 'self'"


class CommunMiddleware(CommonMiddleware):
    """CommonMiddleware de Django, sans l'ajout de la barre finale pour les envois (POST, PUT, PATCH, DELETE).

    Une redirection ferait perdre le contenu envoyé, et en mode développement Django lève une erreur
    (réponse 500) : une adresse d'envoi sans « / » final répond simplement « introuvable » (404).
    """

    def should_redirect_with_slash(self, request):
        return request.method in ("GET", "HEAD", "OPTIONS") and super().should_redirect_with_slash(request)


class EntetesSecuriteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)
        if request.path.startswith(CHEMINS_EXCLUS) or "Content-Security-Policy" in reponse:
            return reponse
        apercu = getattr(reponse, "xframe_options_exempt", False)
        reponse["Content-Security-Policy"] = POLITIQUE_APERCU if apercu else POLITIQUE_DONNEES
        return reponse
