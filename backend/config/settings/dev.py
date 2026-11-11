from .base import *  # noqa: F401,F403

DEBUG = True

# Le serveur de développement n'annonce pas sa version dans ses réponses (signalé par l'analyse ZAP).
# En production, gunicorn est derrière Nginx, qui la masque (deploiement/commun.inc).
from django.core.servers import basehttp  # noqa: E402

basehttp.ServerHandler.server_software = "Serveur"

# Sans Redis, cache partagé sur disque plutôt qu'en mémoire : la dernière activité des sessions
# (apps/core/inactivite.py) survit aux rechargements du serveur de développement et reste commune à
# ses processus (manage.py shell). Les tests gardent le cache en mémoire.
import sys  # noqa: E402

if not REDIS_URL and "pytest" not in sys.modules:  # noqa: F405
    CACHES = {"default": {**CACHES["default"],  # noqa: F405
                          "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                          "LOCATION": "/tmp/suivi-evaluation-cache"}}
