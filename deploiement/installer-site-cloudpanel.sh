#!/bin/bash
# Site vitrine seul sur un serveur géré par CloudPanel (128.140.126.17, expertise-id-monitora.com).
# À lancer en administrateur sur le serveur, après avoir copié le site dans ~/site-vitrine :
#   rsync -a --delete --exclude .DS_Store site-vitrine/ alex@128.140.126.17:site-vitrine/
#   scp deploiement/installer-site-cloudpanel.sh deploiement/securite-site.inc alex@128.140.126.17:
#   ssh -t alex@128.140.126.17 sudo bash installer-site-cloudpanel.sh
# Première fois : crée le site statique dans CloudPanel, ajoute les en-têtes de sécurité et le certificat
# HTTPS (Let's Encrypt). Les fois suivantes : remplace seulement les fichiers du site.
set -euo pipefail
DOMAINE="${DOMAINE:-expertise-id-monitora.com}"
UTILISATEUR="${UTILISATEUR:-monitora}"
SOURCE="$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)"
RACINE="/home/$UTILISATEUR/htdocs/$DOMAINE"
VHOST="/etc/nginx/sites-enabled/$DOMAINE.conf"
ENTETES="/etc/nginx/securite-site-$DOMAINE.inc"

[ -f "$SOURCE/site-vitrine/index.html" ] || { echo "Site introuvable dans $SOURCE/site-vitrine"; exit 1; }

if [ ! -d "$RACINE" ]; then
  echo "Création du site $DOMAINE dans CloudPanel…"
  # Mot de passe du compte du site : aléatoire, jamais affiché (modifiable dans CloudPanel si besoin).
  clpctl site:add:static --domainName="$DOMAINE" --siteUser="$UTILISATEUR" --siteUserPassword="$(openssl rand -base64 24)"
fi

echo "Copie des fichiers…"
rsync -a --delete --exclude .DS_Store "$SOURCE/site-vitrine/" "$RACINE/"
chown -R "$UTILISATEUR:$UTILISATEUR" "$RACINE"
find "$RACINE" -type d -exec chmod 755 {} + ; find "$RACINE" -type f -exec chmod 644 {} +

# En-têtes de sécurité (deploiement/securite-site.inc), inclus une fois dans le vhost. CloudPanel envoie déjà
# X-Frame-Options, X-Content-Type-Options et Referrer-Policy : seule la politique de contenu est ajoutée.
grep "Content-Security-Policy" "$SOURCE/securite-site.inc" > "$ENTETES"
if ! grep -q "$ENTETES" "$VHOST"; then
  cp "$VHOST" "/root/$DOMAINE.conf.avant-entetes"
  sed -i "0,/^\(\s*\)root\s.*$/s##&\n\1include $ENTETES;#" "$VHOST"
  nginx -t || { cp "/root/$DOMAINE.conf.avant-entetes" "$VHOST"; echo "Vhost remis tel quel."; exit 1; }
fi

# CloudPanel pose d'abord un certificat provisoire : Let's Encrypt est demandé jusqu'à réussite (repère dans /root).
REPERE="/root/.letsencrypt-$DOMAINE"
if [ ! -f "$REPERE" ]; then
  echo "Certificat HTTPS…"
  if clpctl lets-encrypt:install:certificate --domainName="$DOMAINE" --subjectAlternativeName="www.$DOMAINE"; then touch "$REPERE"
  else echo "Certificat non obtenu : relancer ce script, ou le demander dans CloudPanel (SSL/TLS)."; fi
fi

nginx -t && systemctl reload nginx
echo "Site en ligne : https://$DOMAINE"
