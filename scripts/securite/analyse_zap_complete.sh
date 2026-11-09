#!/bin/bash
# Analyse ZAP complète : connectée avec un compte d'un espace d'essai, attaques actives sur l'API.
# Usage : scripts/securite/analyse_zap_complete.sh <espace d'essai> <identifiant du compte>
#   ex. : scripts/securite/analyse_zap_complete.sh zap-essai admin_zap
# Pendant l'analyse, les courriels sont seulement écrits dans le journal du serveur (rien n'est envoyé) ;
# le réglage d'origine est remis à la fin, même en cas d'échec.
set -e
ESPACE="${1:?Nom de l espace d essai manquant}" ; COMPTE="${2:?Identifiant du compte manquant}"
RACINE="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RACINE"
SORTIE="$RACINE/rapports/securite/complete_$(date +%Y-%m-%d_%H%M)"; mkdir -p "$SORTIE"

cp .env "$SORTIE/.env.sauvegarde"
retablir() { cp "$SORTIE/.env.sauvegarde" .env; rm -f "$SORTIE/.env.sauvegarde"; docker compose up -d backend scheduler >/dev/null 2>&1; echo "Courriels rétablis."; }
trap retablir EXIT
sed -i '' 's#^EMAIL_BACKEND=.*#EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend#' .env
docker compose up -d backend scheduler >/dev/null 2>&1; sleep 8
echo "Courriels coupés pendant l'analyse."

# Jeton de connexion de 8 heures, marqué « double authentification faite », pour l'espace d'essai.
JETON=$(docker compose exec -T backend python manage.py shell -c "
from datetime import timedelta
from apps.organisations import contexte; from apps.organisations.models import Organisation
from apps.accounts.models import User; from apps.accounts.double_auth import jetons
from rest_framework_simplejwt.tokens import AccessToken
org = Organisation.objects.get(sous_domaine='$ESPACE')
assert not org.mode_demo, 'espace de démonstration : refusé'
with contexte.dans_organisation(org):
    acces = AccessToken(jetons(User.objects.get(username='$COMPTE'))['access'])
    acces.set_exp(lifetime=timedelta(hours=8))
    print(str(acces))
" 2>/dev/null | tail -1)
[ -n "$JETON" ] || { echo "Jeton introuvable"; exit 1; }
sed "s#JETON_ESSAI#$JETON#" scripts/securite/plan-zap-complet.yaml > "$SORTIE/plan.yaml"

HOTE=$(docker run --rm --entrypoint getent zaproxy/zap-stable hosts host.docker.internal | awk '{print $1}')
docker run --rm --memory 6g --add-host "zap.localhost:$HOTE" -v "$SORTIE:/zap/wrk:rw" -u zap zaproxy/zap-stable \
  zap.sh -cmd -autorun /zap/wrk/plan.yaml -config start.checkForUpdates=false
rm -f "$SORTIE/plan.yaml"   # il contient le jeton
echo "Rapport : $SORTIE/rapport-zap-complet.pdf"
