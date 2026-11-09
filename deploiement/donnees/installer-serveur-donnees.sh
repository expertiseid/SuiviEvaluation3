#!/bin/bash
# Installe le serveur de données (37.27.193.28), à lancer en administrateur :
#   ssh -t alex@37.27.193.28 sudo bash installer-serveur-donnees.sh
# Avant : Claude a déposé dans le dossier d'alex docker-compose.yml, donnees.env (mot de passe de la base),
# wg-donnees.cle (clé privée du tunnel) et wg-plateforme.pub (clé publique de la plateforme).
#
# - Tunnel privé WireGuard « wg-monitora » : ce serveur 10.77.0.2, la plateforme (128.140.123.104) 10.77.0.1.
# - PostgreSQL 16 (Docker) et fichiers (NFS v4) n'écoutent que dans le tunnel.
# - Pare-feu : seuls SSH et le tunnel sont ouverts sur Internet.
# - Sauvegarde chaque nuit à 2 h : bases et fichiers, 7 jours gardés (/srv/monitora/sauvegardes).
set -euo pipefail
SOURCE="$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)"
PLATEFORME_IP="${PLATEFORME_IP:-128.140.123.104}"

echo "1/6 Logiciels…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q wireguard-tools nfs-kernel-server docker.io docker-compose-v2 ufw >/dev/null
usermod -aG docker "${SUDO_USER:-root}" || true

echo "2/6 Tunnel privé…"
install -d -m 700 /etc/wireguard
if [ ! -f /etc/wireguard/wg-monitora.conf ]; then
  cat > /etc/wireguard/wg-monitora.conf <<EOF
[Interface]
Address = 10.77.0.2/24
ListenPort = 51820
PrivateKey = $(cat "$SOURCE/wg-donnees.cle")

[Peer]
# Plateforme
PublicKey = $(cat "$SOURCE/wg-plateforme.pub")
AllowedIPs = 10.77.0.1/32
EOF
  chmod 600 /etc/wireguard/wg-monitora.conf
fi
rm -f "$SOURCE/wg-donnees.cle"
systemctl enable --now wg-quick@wg-monitora >/dev/null

echo "3/6 Pare-feu…"
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 22/tcp >/dev/null
ufw allow 51820/udp >/dev/null
ufw allow in on wg-monitora >/dev/null
ufw --force enable >/dev/null

echo "4/6 Fichiers (NFS v4, dans le tunnel seulement)…"
install -d -m 755 /srv/monitora/fichiers/media /srv/monitora/fichiers/prive /srv/monitora/sauvegardes
install -d -m 700 /srv/monitora/postgres
install -d /etc/exports.d
echo "/srv/monitora/fichiers 10.77.0.1/32(rw,sync,no_subtree_check,no_root_squash,fsid=0)" > /etc/exports.d/monitora.exports
mkdir -p /etc/nfs.conf.d
printf "[nfsd]\nhost=10.77.0.2\nvers3=n\n" > /etc/nfs.conf.d/monitora.conf
# NFS v4 n'a pas besoin de rpcbind (port 111) : coupé.
systemctl mask --now rpcbind.service rpcbind.socket >/dev/null 2>&1 || true
mkdir -p /etc/systemd/system/nfs-server.service.d
printf "[Unit]\nAfter=wg-quick@wg-monitora.service\nRequires=wg-quick@wg-monitora.service\n" > /etc/systemd/system/nfs-server.service.d/tunnel.conf
systemctl daemon-reload
systemctl enable nfs-server >/dev/null
systemctl restart nfs-server
exportfs -ra

echo "5/6 Base de données…"
# Docker démarre après le tunnel : la base écoute sur l'adresse du tunnel (10.77.0.2).
mkdir -p /etc/systemd/system/docker.service.d
printf "[Unit]\nAfter=wg-quick@wg-monitora.service\nWants=wg-quick@wg-monitora.service\n" > /etc/systemd/system/docker.service.d/tunnel.conf
systemctl daemon-reload
install -m 644 "$SOURCE/docker-compose.yml" /srv/monitora/docker-compose.yml
install -m 600 "$SOURCE/donnees.env" /srv/monitora/donnees.env
rm -f "$SOURCE/donnees.env"
cd /srv/monitora && docker compose up -d

echo "6/6 Sauvegarde de chaque nuit…"
cat > /usr/local/bin/sauvegarder-monitora <<'EOF'
#!/bin/bash
# Sauvegarde de la nuit : toutes les bases (pg_dumpall) et les fichiers ; 7 jours gardés.
set -euo pipefail
JOUR=$(date +%F); DOSSIER=/srv/monitora/sauvegardes
cd /srv/monitora
docker compose exec -T db sh -c 'pg_dumpall -U "$POSTGRES_USER"' | gzip > "$DOSSIER/bases-$JOUR.sql.gz"
tar -C /srv/monitora -czf "$DOSSIER/fichiers-$JOUR.tar.gz" fichiers
find "$DOSSIER" -name '*.gz' -mtime +6 -delete
EOF
chmod 755 /usr/local/bin/sauvegarder-monitora
echo "0 2 * * * root /usr/local/bin/sauvegarder-monitora" > /etc/cron.d/sauvegarder-monitora

echo "Serveur de données prêt. Clé publique du tunnel :"
wg show wg-monitora public-key
