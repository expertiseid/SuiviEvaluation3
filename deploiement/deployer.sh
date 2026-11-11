#!/usr/bin/env bash
# Met à jour la plateforme sur le serveur, en une commande :
#   deploiement/deployer.sh root@204.168.227.18
#   deploiement/deployer.sh alex@128.140.123.104   (plateforme derrière le CloudPanel du site, voir relais.conf.template)
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

echo "2/3 Envoi du code vers ${CIBLE}:${DOSSIER}…"
ssh "$CIBLE" "mkdir -p $DOSSIER/frontend"
rsync -az --delete \
  --exclude __pycache__ --exclude '.pytest_cache' --exclude media --exclude prive --exclude staticfiles \
  backend "$CIBLE:$DOSSIER/"
rsync -az --delete frontend/dist "$CIBLE:$DOSSIER/frontend/"
rsync -az --delete site-vitrine "$CIBLE:$DOSSIER/"
rsync -az --exclude .env.prod deploiement "$CIBLE:$DOSSIER/"

echo "3/3 Reconstruction et redémarrage…"
# Relais chiffré (docker-compose.relais.yml) si le HTTPS public est géré par un autre serveur (RELAIS_IP rempli) ;
# base et fichiers sur le serveur de données (docker-compose.donnees.yml) si SERVEUR_DONNEES est rempli.
ssh "$CIBLE" "cd $DOSSIER/deploiement && test -f .env.prod && FICHIERS='-f docker-compose.prod.yml' && \
  { ! grep -q '^RELAIS_IP=.' .env.prod || FICHIERS=\"\$FICHIERS -f docker-compose.relais.yml\"; } && \
  { ! grep -q '^SERVEUR_DONNEES=.' .env.prod || FICHIERS=\"\$FICHIERS -f docker-compose.donnees.yml\"; } && \
  docker compose --env-file .env.prod \$FICHIERS up -d --build --remove-orphans && \
  docker compose --env-file .env.prod \$FICHIERS up -d --force-recreate --no-deps web"
# Nginx recréé (quelques secondes) : il garderait sinon l'adresse de l'ancien conteneur backend (502), et les
# fichiers de configuration montés un par un (*.inc), remplacés par rsync, resteraient dans leur ancienne version.
echo "Terminé."
