#!/bin/bash
# Analyse de sécurité ZAP de la plateforme locale (Docker, image zaproxy/zap-stable).
# Rapports : rapports/securite/<date>/rapport-zap.pdf (et .html, .json). Usage : scripts/securite/analyse_zap.sh
# Autre plan : PLAN=plan-zap-site.yaml (site vitrine seul) ; mémoire de ZAP : MEMOIRE=2g (6g par défaut).
set -e
RACINE="$(cd "$(dirname "$0")/../.." && pwd)"
SORTIE="$RACINE/rapports/securite/$(date +%Y-%m-%d_%H%M)"
mkdir -p "$SORTIE"
PLAN="${PLAN:-plan-zap.yaml}"
cp "$RACINE/scripts/securite/$PLAN" "$SORTIE/"
# Adresse du Mac vue depuis un conteneur (Docker Desktop).
HOTE=$(docker run --rm --entrypoint getent zaproxy/zap-stable hosts host.docker.internal | awk '{print $1}')
docker run --rm --memory "${MEMOIRE:-6g}" --add-host "zap.localhost:$HOTE" -v "$SORTIE:/zap/wrk:rw" -u zap zaproxy/zap-stable \
  zap.sh -cmd -autorun "/zap/wrk/$PLAN" -config start.checkForUpdates=false
RAPPORT=$(ls "$SORTIE"/*.pdf | head -1)
echo "Rapport : $RAPPORT"
[ -z "$SANS_OUVRIR" ] && open "$RAPPORT" 2>/dev/null || true
