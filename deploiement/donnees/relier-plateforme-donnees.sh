#!/bin/bash
# Relie le serveur de la plateforme (128.140.123.104) au serveur de données (37.27.193.28), en administrateur :
#   ssh -t alex@128.140.123.104 sudo bash relier-plateforme-donnees.sh
# Avant : Claude a déposé dans le dossier d'alex wg-plateforme.cle (clé privée du tunnel) et
# wg-donnees.pub (clé publique du serveur de données).
#
# Tunnel privé WireGuard « wg-monitora » (ce serveur 10.77.0.1) ; les fichiers du serveur de données
# sont montés dans /mnt/monitora-fichiers (NFS v4 dans le tunnel). Ne touche à rien d'autre sur ce
# serveur (autres applications, Docker, pare-feu).
set -euo pipefail
SOURCE="$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)"
DONNEES_IP="${DONNEES_IP:-37.27.193.28}"
MONTAGE=/mnt/monitora-fichiers

echo "1/3 Logiciels…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q wireguard-tools nfs-common >/dev/null

echo "2/3 Tunnel privé…"
install -d -m 700 /etc/wireguard
if [ ! -f /etc/wireguard/wg-monitora.conf ]; then
  cat > /etc/wireguard/wg-monitora.conf <<EOF
[Interface]
Address = 10.77.0.1/24
PrivateKey = $(cat "$SOURCE/wg-plateforme.cle")

[Peer]
# Serveur de données
PublicKey = $(cat "$SOURCE/wg-donnees.pub")
Endpoint = $DONNEES_IP:51820
AllowedIPs = 10.77.0.2/32
PersistentKeepalive = 25
EOF
  chmod 600 /etc/wireguard/wg-monitora.conf
fi
rm -f "$SOURCE/wg-plateforme.cle"
systemctl enable --now wg-quick@wg-monitora >/dev/null
ping -c 2 -W 3 10.77.0.2 >/dev/null && echo "Tunnel ouvert." || { echo "Le serveur de données ne répond pas dans le tunnel."; exit 1; }

echo "3/3 Fichiers…"
install -d "$MONTAGE"
LIGNE="10.77.0.2:/ $MONTAGE nfs4 _netdev,hard,timeo=600,x-systemd.requires=wg-quick@wg-monitora.service 0 0"
grep -q " $MONTAGE " /etc/fstab || echo "$LIGNE" >> /etc/fstab
systemctl daemon-reload
mountpoint -q "$MONTAGE" || mount "$MONTAGE"
ls "$MONTAGE"
echo "Plateforme reliée au serveur de données."
