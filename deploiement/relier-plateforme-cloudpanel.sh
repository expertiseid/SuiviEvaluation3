#!/bin/bash
# Relie expertise-id-monitora.com (CloudPanel de 128.140.126.17, qui garde le HTTPS public) à la
# plateforme de 128.140.123.104 : toutes les adresses passent par le relais chiffré (relais.conf.template),
# sauf les vérifications de Let's Encrypt. La plateforme sert aussi le site vitrine.
# Après avoir copié certificat.pem (deploiement/relais/ du serveur de la plateforme) dans le dossier d'alex :
#   ssh -t alex@128.140.126.17 sudo bash relier-plateforme-cloudpanel.sh
# Retour arrière : RETOUR=1 (remet le vhost d'avant).
set -euo pipefail
DOMAINE="${DOMAINE:-expertise-id-monitora.com}"
PLATEFORME="${PLATEFORME:-128.140.123.104:8443}"
SOURCE="$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)"
VHOST="/etc/nginx/sites-enabled/$DOMAINE.conf"
RELAIS="/etc/nginx/plateforme-$DOMAINE.inc"
CERTIFICAT="/etc/nginx/plateforme-$DOMAINE.pem"
COPIE="/root/$DOMAINE.conf.avant-plateforme"

if [ -n "${RETOUR:-}" ]; then
  cp "$COPIE" "$VHOST" && nginx -t && systemctl reload nginx && echo "Vhost d'avant remis."; exit 0
fi

cp "$SOURCE/certificat.pem" "$CERTIFICAT"
cat > "$RELAIS" <<EOF
# Plateforme Expertise-ID Monitora (relier-plateforme-cloudpanel.sh). « ^~ » passe avant les règles
# de CloudPanel sur les fichiers statiques ; chaque bloc a son add_header, pour ne pas reprendre
# la politique de contenu du site (la plateforme envoie la sienne).
location ^~ /.well-known/acme-challenge/ { try_files \$uri =404; }
location ^~ / {
    proxy_pass https://$PLATEFORME;
    proxy_ssl_trusted_certificate $CERTIFICAT;
    proxy_ssl_verify on;
    proxy_ssl_name relais-monitora;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 300;
    proxy_request_buffering off;
    client_max_body_size 100m;
    add_header Strict-Transport-Security "max-age=31536000" always;
}
EOF

if ! grep -q "$RELAIS" "$VHOST"; then
  cp "$VHOST" "$COPIE"
  # À la place des en-têtes du site statique (la plateforme envoie les siens), juste après « root ».
  sed -i "/securite-site-$DOMAINE.inc/d" "$VHOST"
  sed -i "0,/^\(\s*\)root\s.*$/s##&\n\1include $RELAIS;#" "$VHOST"
fi
if ! nginx -t; then
  cp "$COPIE" "$VHOST"; echo "Échec : vhost remis tel quel. Contenu, pour adapter le script :"; cat "$VHOST"; exit 1
fi
systemctl reload nginx
echo "Relié : https://$DOMAINE → plateforme ($PLATEFORME)"
