from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Derrière le serveur web (Caddy, puis Nginx) : le HTTPS est terminé en amont, qui le signale par
# X-Forwarded-Proto. Sans ce réglage, la redirection HTTPS tournerait en boucle.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Appelé en HTTP par le serveur web (certificats « à la demande ») : pas de redirection.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/tls/"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Administration Django en HTTPS : origines autorisées (ex. https://plateforme.exemple.com,https://*.plateforme.exemple.com).
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
