#!/usr/bin/env bash
# Étape 4 du passage multi-organisations : l'ancienne installation devient l'espace d'une organisation.
#
#   scripts/reprendre_installation.sh expertise-id "Expertise-ID" [contact@…]
#
# 1. sauvegarde de la base et des fichiers dans sauvegardes/ ;
# 2. copie de la base dans org_<sous-domaine> (la base d'origine n'est pas modifiée) ;
# 3. manage.py reprendre_installation : registre, rechiffrement, fichiers (apps/organisations/reprise.py).
set -euo pipefail
cd "$(dirname "$0")/.."

SOUS_DOMAINE="${1:?sous-domaine requis}"
NOM="${2:?nom requis}"
COURRIEL="${3:-}"
BASE="org_${SOUS_DOMAINE//-/_}"
UTILISATEUR="$(docker compose exec -T db sh -c 'echo $POSTGRES_USER')"
SOURCE="$(docker compose exec -T db sh -c 'echo $POSTGRES_DB')"
HORODATAGE="$(date +%Y%m%d_%H%M%S)"

mkdir -p sauvegardes
echo "1/3 Sauvegarde…"
docker compose exec -T db pg_dump -U "$UTILISATEUR" -Fc "$SOURCE" > "sauvegardes/${SOURCE}_${HORODATAGE}.dump"
tar czf "sauvegardes/fichiers_${HORODATAGE}.tgz" -C backend media prive 2>/dev/null || true

echo "2/3 Copie de la base dans ${BASE}…"
if docker compose exec -T db psql -U "$UTILISATEUR" -d "$SOURCE" -tAc "SELECT 1 FROM pg_database WHERE datname='${BASE}'" | grep -q 1; then
  echo "La base ${BASE} existe déjà : arrêt." >&2
  exit 1
fi
docker compose exec -T db createdb -U "$UTILISATEUR" "$BASE"
docker compose exec -T db pg_restore -U "$UTILISATEUR" -d "$BASE" --no-owner < "sauvegardes/${SOURCE}_${HORODATAGE}.dump"

echo "3/3 Rattachement de l'espace…"
docker compose exec -T backend python manage.py reprendre_installation "$SOUS_DOMAINE" "$NOM" ${COURRIEL:+--courriel "$COURRIEL"}
