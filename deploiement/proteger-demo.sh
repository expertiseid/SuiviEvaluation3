#!/usr/bin/env bash
# Mot de passe d'entrée de la démonstration (serveur des démos 204.168.227.18) : le navigateur le demande avant
# d'ouvrir https://204-168-227-18.sslip.io, https://demo.204-168-227-18.sslip.io et
# https://formation.204-168-227-18.sslip.io (même installation). Nom d'utilisateur : « demo ».
#
# Le mot de passe est tapé ici, sans s'afficher ; seule son empreinte (bcrypt) est écrite sur le serveur, dans
# le Caddyfile de /opt/ariste. L'API (/api/…) n'est pas concernée : l'application y envoie déjà son propre jeton.
#
#   ./deploiement/proteger-demo.sh            # pose ou change le mot de passe
#   RETIRER=1 ./deploiement/proteger-demo.sh  # rouvre la démonstration à tous
set -euo pipefail

SERVEUR="${SERVEUR:-root@204.168.227.18}"

if [ "${RETIRER:-0}" = "1" ]; then
  EMPREINTE=""
else
  read -rsp "Mot de passe de la démonstration : " MDP; echo
  read -rsp "Encore une fois : " MDP2; echo
  [ -n "$MDP" ] || { echo "Mot de passe vide : rien n'est changé." >&2; exit 1; }
  [ "$MDP" = "$MDP2" ] || { echo "Les deux mots de passe diffèrent : rien n'est changé." >&2; exit 1; }
  EMPREINTE=$(printf '%s\n' "$MDP" | ssh "$SERVEUR" 'docker exec -i ariste-web-1 caddy hash-password')
  unset MDP MDP2
  [[ "$EMPREINTE" == \$2* ]] || { echo "Empreinte du mot de passe non obtenue : rien n'est changé." >&2; exit 1; }
fi

ssh "$SERVEUR" EMPREINTE="'$EMPREINTE'" bash -s <<'DISTANT'
set -euo pipefail
cd /opt/ariste
cp Caddyfile "Caddyfile.avant-protection-demo-$(date +%Y%m%d-%H%M%S)"
# Retire une protection déjà posée, puis la remet (si une empreinte est donnée) dans chaque bloc de la démo.
awk -v empreinte="$EMPREINTE" '
  /# debut-protection-demo/ { saute = 1; next }
  /# fin-protection-demo/ { saute = 0; next }
  saute { next }
  { print }
  empreinte != "" && /^(demo\.|formation\.)?204-168-227-18\.sslip\.io \{/ {
    print "\t# debut-protection-demo"
    print "\t@protege not path /api/*"
    print "\tbasic_auth @protege {"
    print "\t\tdemo " empreinte
    print "\t}"
    print "\t# fin-protection-demo"
  }
' Caddyfile > /tmp/Caddyfile.demo
# Réécrit le fichier en place : il est monté tel quel dans le conteneur de Caddy.
cat /tmp/Caddyfile.demo > Caddyfile && rm /tmp/Caddyfile.demo
docker exec ariste-web-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
docker exec ariste-web-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
echo "Blocs protégés : $(grep -c 'debut-protection-demo' Caddyfile)"
DISTANT
