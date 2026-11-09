#!/bin/bash
# Déplace les données (base PostgreSQL et fichiers, /srv/monitora) du disque du serveur vers le Volume
# Hetzner, qui peut grandir sans arrêt (agrandissement automatique). En administrateur, une seule fois :
#   ssh -t alex@37.27.193.28 sudo bash deplacer-sur-volume.sh
# Coupure d'une à deux minutes. L'ancienne copie reste dans /srv/monitora.avant-volume (retour arrière).
# Ensuite : le Volume est monté sur /srv/monitora ; Docker et NFS ne démarrent que s'il est monté
# (jamais une base vide à sa place).
set -euo pipefail
DONNEES=/srv/monitora
LIEN=$(ls /dev/disk/by-id/scsi-0HC_Volume_* 2>/dev/null | head -1)
[ -n "$LIEN" ] || { echo "Aucun Volume Hetzner branché."; exit 1; }
if mountpoint -q "$DONNEES"; then
  echo "Les données sont déjà sur le Volume."; exit 0
fi

echo "1/5 Arrêt de la base et du partage de fichiers…"
cd "$DONNEES" && docker compose stop >/dev/null
systemctl stop nfs-server

echo "2/5 Préparation du Volume…"
# Montage automatique proposé par Hetzner (/mnt/HC_Volume_…) retiré : le Volume ira sur /srv/monitora.
for ancien in $(findmnt -n -o TARGET -S "$(readlink -f "$LIEN")" || true); do umount "$ancien"; done
sed -i "\#HC_Volume_#d" /etc/fstab
TEMPORAIRE=$(mktemp -d)
mount "$LIEN" "$TEMPORAIRE"
if [ -n "$(ls -A "$TEMPORAIRE" | grep -v '^lost+found$' || true)" ]; then
  umount "$TEMPORAIRE"; echo "Le Volume n'est pas vide : arrêt, rien n'a été déplacé."
  systemctl start nfs-server; cd "$DONNEES" && docker compose start >/dev/null; exit 1
fi

echo "3/5 Copie des données…"
rsync -aHAX "$DONNEES/" "$TEMPORAIRE/"
umount "$TEMPORAIRE"; rmdir "$TEMPORAIRE"

echo "4/5 Volume monté sur $DONNEES…"
mv "$DONNEES" "$DONNEES.avant-volume"
install -d "$DONNEES"
echo "$LIEN $DONNEES ext4 discard,nofail,defaults 0 2" >> /etc/fstab
systemctl daemon-reload
mount "$DONNEES"
for service in docker nfs-server; do
  mkdir -p "/etc/systemd/system/$service.service.d"
  printf "[Unit]\nRequiresMountsFor=%s\n" "$DONNEES" > "/etc/systemd/system/$service.service.d/volume.conf"
done
systemctl daemon-reload

echo "5/5 Redémarrage…"
systemctl start nfs-server
exportfs -ra
cd "$DONNEES" && docker compose up -d >/dev/null
for _ in $(seq 30); do docker compose ps db | grep -q healthy && break; sleep 2; done
docker compose ps db | grep -q healthy || { echo "La base ne redémarre pas : voir « docker compose logs db »."; exit 1; }
df -h "$DONNEES" | tail -1
echo "Données sur le Volume. Ancienne copie : $DONNEES.avant-volume (à supprimer après vérification)."
