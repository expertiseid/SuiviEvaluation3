"""
Django settings communs (dev + prod). Les fichiers dev.py / prod.py
surchargent ce qui doit différer entre les deux environnements.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", ".localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "simple_history",
    "drf_spectacular",
    "corsheaders",
    # Apps locales
    "apps.core",
    "apps.accounts",
    "apps.geo",
    "apps.strategy",
    "apps.partners",
    "apps.intervenants",
    "apps.projects",
    "apps.indicators",
    "apps.beneficiaries",
    "apps.reports",
    "apps.documents",
    "apps.dashboard",
    "apps.notifications",
    "apps.suivi",
    "apps.planification",
    "apps.plaintes",
    "apps.organisations",
    "apps.formation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    # Plateforme multi-organisations : la requête travaille dans la base de son organisation.
    "apps.organisations.middleware.OrganisationMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "apps.core.modules.ModulesMasquesMiddleware",
    # Installation de démonstration : le visiteur ne peut rien enregistrer (apps.accounts.demo).
    "apps.accounts.demo.ModeDemoMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://se_platform:changeme@localhost:5432/se_platform",
    )
}
# Base centrale (registre des organisations). Hors organisation, « default » est cette même base ; dans
# une organisation, « default » est la base de l'organisation (apps.organisations.contexte).
DATABASES["central"] = {**DATABASES["default"], "TEST": {"MIRROR": "default"}}
DATABASE_ROUTERS = ["apps.organisations.contexte.RouteurOrganisations"]

# --- Plateforme multi-organisations (apps/organisations) ---
# Faux : une organisation par installation (comportement historique). Vrai : chaque organisation a son
# sous-domaine (ong-a.DOMAINE_PLATEFORME) et sa propre base sur le même serveur.
MULTI_ORGANISATIONS = env.bool("MULTI_ORGANISATIONS", default=False)
DOMAINE_PLATEFORME = env("DOMAINE_PLATEFORME", default="localhost")

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", default="") or str(BASE_DIR / "media")
# Fichiers téléversés rangés par organisation (MEDIA_ROOT/organisations/<sous-domaine>/).
STORAGES = {
    "default": {"BACKEND": "apps.organisations.stockage.StockageOrganisation"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Clés du cache (compteurs anti-abus…) séparées par organisation.
# Production (plusieurs processus, voire plusieurs serveurs) : REDIS_URL, cache partagé. Sinon, en mémoire.
REDIS_URL = env("REDIS_URL", default="")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache" if REDIS_URL else "django.core.cache.backends.locmem.LocMemCache",
        "KEY_FUNCTION": "apps.organisations.contexte.cle_cache",
        **({"LOCATION": REDIS_URL} if REDIS_URL else {}),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Jeton JWT, refusé pour un compte soumis au second facteur s'il a été obtenu sans lui.
        "apps.accounts.double_auth.JWTAvecDoubleFacteur",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Expertise-ID Monitora — API",
    "DESCRIPTION": "API de la plateforme Expertise-ID Monitora (suivi-évaluation multi-projets).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- JWT ---
# Démonstration : MODE_DEMO=True sur l'installation de démonstration uniquement (données fictives) ;
# « Essayer la démo » y connecte un visiteur qui peut tout voir mais rien enregistrer (apps.accounts.demo).
# Sur une installation d'organisation : URL_DEMO = adresse de l'installation de démonstration.
MODE_DEMO = env.bool("MODE_DEMO", default=False)
URL_DEMO = env("URL_DEMO", default="")
# Page d'accueil : une organisation peut demander à créer son profil (puis s'abonner).
INSCRIPTIONS_OUVERTES = env.bool("INSCRIPTIONS_OUVERTES", default=True)
# Adresse d'Expertise-ID qui reçoit les profils créés et les offres d'abonnement choisies.
COURRIEL_ABONNEMENTS = env("COURRIEL_ABONNEMENTS", default="")

# Code de connexion envoyé par courriel à chaque connexion, pour tous les comptes
# (apps/accounts/double_auth.py). À ne désactiver que sur un poste de développement.
DOUBLE_AUTH_OBLIGATOIRE = env.bool("DOUBLE_AUTH_OBLIGATOIRE", default=True)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_LIFETIME_MIN", default=45)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS ---
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"]
)
# Nom des fichiers téléchargés (cartes, rapports) lisible par le navigateur.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]
# Espaces des organisations : https://<sous-domaine>.DOMAINE_PLATEFORME (et *.localhost en développement).
CORS_ALLOWED_ORIGIN_REGEXES = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[r"^http://([a-z0-9-]+\.)?localhost(:\d+)?$"])
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = (*default_headers, "x-organisation")

# --- Email (notifications) ---
# Backend "console" par défaut : les emails sont écrits dans les logs du
# conteneur backend plutôt qu'envoyés réellement — pratique en dev, à
# remplacer par un backend SMTP réel en prod via EMAIL_BACKEND/EMAIL_HOST*.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)  # port 465 (exclusif avec EMAIL_USE_TLS)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)  # un serveur lent ne doit jamais bloquer une page
# Liste blanche de destinataires (postes de test) : voir apps/core/courriel.py. Vide en production.
EMAIL_DESTINATAIRES_AUTORISES = env("EMAIL_DESTINATAIRES_AUTORISES", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="notifications@suivi-evaluation.local")

# --- Plaintes : clé de chiffrement des données protégées (récits, coordonnées, notes) ---
# Clé Fernet propre à l'organisation, hors du code et de la base ; plusieurs clés séparées par des
# virgules pour une rotation (la première chiffre). Voir apps/plaintes/chiffrement.py.
PLAINTES_CLE_CHIFFREMENT = env("PLAINTES_CLE_CHIFFREMENT", default="")

# --- Plaintes : messages au plaignant ---
# Adresse publique de la plateforme (lien de suivi dans les messages).
PLAINTES_URL_PUBLIQUE = env("PLAINTES_URL_PUBLIQUE", default="http://localhost:5192")
# Passerelle SMS (HTTP POST JSON {to, message, from}, jeton en « Authorization: Bearer »). Vide : envoi simulé.
PLAINTES_SMS_URL = env("PLAINTES_SMS_URL", default="")
PLAINTES_SMS_JETON = env("PLAINTES_SMS_JETON", default="")
PLAINTES_SMS_EXPEDITEUR = env("PLAINTES_SMS_EXPEDITEUR", default="")

# --- Plaintes : pièces jointes (lot 8) ---
# Répertoire privé, hors de MEDIA_ROOT et de toute racine web : les fichiers y sont toujours chiffrés et
# ne sont servis que par l'application, après contrôle d'accès. Voir apps/plaintes/pieces.py.
PLAINTES_STOCKAGE_PRIVE = env("PLAINTES_STOCKAGE_PRIVE", default="") or str(BASE_DIR / "prive" / "plaintes")
# Plafond de la plateforme par fichier (Mo) ; chaque mécanisme règle sa limite en dessous.
PLAINTES_PLAFOND_PIECE_MO = env.int("PLAINTES_PLAFOND_PIECE_MO", default=10)
# Durée de validité des liens de téléchargement, en minutes (1 à 15).
PLAINTES_DUREE_LIEN_PIECE_MIN = env.int("PLAINTES_DUREE_LIEN_PIECE_MIN", default=5)
