"""Serveur du site vitrine sur le poste de développement (service « vitrine » de docker-compose.yml).

Sert les fichiers de site-vitrine/ comme `python -m http.server`, avec les mêmes en-têtes de sécurité
qu'en production (deploiement/securite.inc), sans annoncer la version du serveur. Sur le poste,
l'API (port 8093) et les vidéos (port 5192) sont à une autre adresse que le site : la politique de
contenu les autorise.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Gestionnaire(SimpleHTTPRequestHandler):
    server_version = "Serveur"
    sys_version = ""

    def end_headers(self):
        hote = (self.headers.get("Host") or "localhost").split(":")[0]
        api, plateforme = f"http://{hote}:8093", f"http://{hote}:5192"
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
            f"img-src 'self' data: {api} {plateforme}; media-src 'self' {plateforme}; connect-src 'self' {api} {plateforme}; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
        )
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()


if __name__ == "__main__":
    dossier = sys.argv[1] if len(sys.argv) > 1 else "/site"
    ThreadingHTTPServer(("0.0.0.0", 80), partial(Gestionnaire, directory=dossier)).serve_forever()
