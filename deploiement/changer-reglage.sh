#!/bin/bash
# Change un réglage secret de .env.prod (mot de passe CinetPay, SMTP…) sans qu'il s'affiche ni passe par
# une commande, puis relance la plateforme. Sur le serveur de la plateforme :
#   ssh -t alex@128.140.123.104 bash /opt/suivi-evaluation-plateforme/deploiement/changer-reglage.sh CINETPAY_API_PASSWORD
set -euo pipefail
NOM="${1:?Nom du réglage manquant (ex. CINETPAY_API_PASSWORD)}"
cd "$(dirname "$0")"
grep -q "^$NOM=" .env.prod || { echo "Réglage $NOM absent de .env.prod : rien n'a été changé."; exit 1; }

read -r -s -p "Nouvelle valeur de $NOM (rien ne s'affiche, c'est normal) : " VALEUR; echo
read -r -s -p "Encore une fois : " ENCORE; echo
[ -n "$VALEUR" ] || { echo "Valeur vide : rien n'a été changé."; exit 1; }
[ "$VALEUR" = "$ENCORE" ] || { echo "Les deux saisies sont différentes : rien n'a été changé."; exit 1; }

cp -p .env.prod .env.prod.avant-changement
NOM="$NOM" VALEUR="$VALEUR" awk 'index($0, ENVIRON["NOM"] "=") == 1 { print ENVIRON["NOM"] "=" ENVIRON["VALEUR"]; next } { print }' \
  .env.prod.avant-changement > .env.prod.nouveau
chmod --reference=.env.prod .env.prod.nouveau && mv .env.prod.nouveau .env.prod
unset VALEUR ENCORE

echo "Relance de la plateforme…"
FICHIERS="-f docker-compose.prod.yml"
! grep -q '^RELAIS_IP=.' .env.prod || FICHIERS="$FICHIERS -f docker-compose.relais.yml"
! grep -q '^SERVEUR_DONNEES=.' .env.prod || FICHIERS="$FICHIERS -f docker-compose.donnees.yml"
# shellcheck disable=SC2086
docker compose --env-file .env.prod $FICHIERS up -d backend scheduler >/dev/null 2>&1
# shellcheck disable=SC2086
docker compose --env-file .env.prod $FICHIERS exec -T web nginx -s reload >/dev/null 2>&1
rm -f .env.prod.avant-changement
echo "$NOM changé, plateforme relancée."
