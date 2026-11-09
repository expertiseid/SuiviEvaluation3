from .base import *  # noqa: F401,F403

DEBUG = True

# Le serveur de développement n'annonce pas sa version dans ses réponses (signalé par l'analyse ZAP).
# En production, gunicorn est derrière Nginx, qui la masque (deploiement/commun.inc).
from django.core.servers import basehttp  # noqa: E402

basehttp.ServerHandler.server_software = "Serveur"
