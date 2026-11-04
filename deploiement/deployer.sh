#!/usr/bin/env bash
# Met à jour la plateforme sur le serveur, en une commande :
#   deploiement/deployer.sh root@204.168.227.18
#
# 1. assemble l'interface ici (vite build) ; 2. envoie le code (rsync : seuls les fichiers changés) ;
# 3. reconstruit et relance les conteneurs sur le serveur. Les données (bases, fichiers) sont dans
# des volumes Docker : une mise à jour n'y touche pas. Les migrations passent au démarrage
# (backend/demarrer_production.sh). Le .env.prod du serveur n'est jamais écrasé.
set -euo pipefail
cd "$(dirname "$0")/.."

CIBLE="${1:?Usage : deploiement/deployer.sh utilisateur@serveur [dossier]}"
DOSSIER="${2:-/opt/suivi-evaluation-plateforme}"

echo "1/3 Assemblage de l'interface…"
docker compose exec -T -e VITE_API_BASE_URL=/api/v1 frontend npx vite build >/dev/null

echo "2/3 Envoi du code vers $CIBLE:$DOSSIER…"
ssh "$CIBLE" "mkdir -p $DOSSIER/frontend"
rsync -az --delete \
  --exclude __pycache__ --exclude '.pytest_cache' --exclude media --exclude prive --exclude staticfiles \
  backend "$CIBLE:$DOSSIER/"
rsync -az --delete frontend/dist "$CIBLE:$DOSSIER/frontend/"
rsync -az --delete site-vitrine "$CIBLE:$DOSSIER/"
rsync -az --exclude .env.prod deploiement "$CIBLE:$DOSSIER/"

echo "3/3 Reconstruction et redémarrage…"
ssh "$CIBLE" "cd $DOSSIER/deploiement && test -f .env.prod && docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build --remove-orphans"
echo "Terminé."
