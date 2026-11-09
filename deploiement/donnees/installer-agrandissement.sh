#!/bin/bash
# Agrandissement automatique du Volume Hetzner (données des clients, /srv/monitora), à lancer en
# administrateur sur le serveur de données, une seule fois :
#   ssh -t alex@37.27.193.28 sudo bash installer-agrandissement.sh
# Demande la clé (API Token Hetzner, Lecture et écriture) : tapée sur le serveur, jamais affichée,
# gardée dans /etc/monitora/hetzner.env (lisible par root seulement).
#
# Toutes les 15 minutes : si le Volume est rempli à 80 % ou plus, il est agrandi d'un quart (au moins
# 10 Go), sans coupure, jusqu'au plafond (1 000 Go, à changer dans /etc/monitora/agrandissement.conf).
# Un Volume ne peut pas rapetisser : le plafond évite une facture qui s'emballe.
# Essai à la main : sudo agrandir-volume-monitora --essai 10   (ajoute 10 Go tout de suite)
# Journal : journalctl -u agrandir-volume-monitora
set -euo pipefail
LIEN=$(ls /dev/disk/by-id/scsi-0HC_Volume_* 2>/dev/null | head -1)
[ -n "$LIEN" ] || { echo "Aucun Volume Hetzner branché."; exit 1; }
VOLUME_ID=${LIEN##*_}

echo "1/3 Clé Hetzner…"
install -d -m 700 /etc/monitora
read -r -s -p "Collez la clé Hetzner puis appuyez sur Entrée (rien ne s'affiche, c'est normal) : " CLE; echo
CLE=$(printf %s "$CLE" | tr -d '[:space:]')
CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $CLE" "https://api.hetzner.cloud/v1/volumes/$VOLUME_ID")
[ "$CODE" = 200 ] || { echo "Clé refusée par Hetzner (code $CODE) : vérifiez-la (projet du serveur, Lecture et écriture)."; exit 1; }
( umask 077; printf 'HCLOUD_TOKEN=%s\n' "$CLE" > /etc/monitora/hetzner.env )
unset CLE
[ -f /etc/monitora/agrandissement.conf ] || cat > /etc/monitora/agrandissement.conf <<'EOF'
# Agrandissement automatique du Volume (agrandir-volume-monitora)
SEUIL=80        # % rempli à partir duquel le Volume est agrandi
PLAFOND=1000    # Go : taille au-delà de laquelle il n'est plus agrandi tout seul
EOF

echo "2/3 Programme d'agrandissement…"
cat > /usr/local/bin/agrandir-volume-monitora <<'EOF'
#!/bin/bash
# Agrandit le Volume Hetzner de /srv/monitora quand il est rempli à SEUIL % (voir installer-agrandissement.sh).
set -euo pipefail
. /etc/monitora/hetzner.env
. /etc/monitora/agrandissement.conf
DONNEES=/srv/monitora
LIEN=$(ls /dev/disk/by-id/scsi-0HC_Volume_* | head -1)
VOLUME_ID=${LIEN##*_}
API=https://api.hetzner.cloud/v1
appel() { curl -sf -H "Authorization: Bearer $HCLOUD_TOKEN" -H "Content-Type: application/json" "$@"; }
champ() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval('d' + sys.argv[1]))" "$1"; }

REMPLI=$(df --output=pcent "$DONNEES" | tail -1 | tr -dc 0-9)
TAILLE=$(appel "$API/volumes/$VOLUME_ID" | champ "['volume']['size']")
if [ "${1:-}" = "--essai" ]; then
  NOUVELLE=$((TAILLE + ${2:-10}))
elif [ "$REMPLI" -ge "$SEUIL" ]; then
  AJOUT=$(( (TAILLE / 4 + 9) / 10 * 10 )); [ "$AJOUT" -ge 10 ] || AJOUT=10
  NOUVELLE=$((TAILLE + AJOUT))
  [ "$NOUVELLE" -le "$PLAFOND" ] || NOUVELLE=$PLAFOND
  if [ "$NOUVELLE" -le "$TAILLE" ]; then
    echo "Volume rempli à $REMPLI % mais plafond atteint ($PLAFOND Go) : agrandissement à décider à la main."; exit 0
  fi
else
  exit 0
fi

echo "Volume rempli à $REMPLI % : $TAILLE Go → $NOUVELLE Go…"
ACTION=$(appel -X POST -d "{\"size\": $NOUVELLE}" "$API/volumes/$VOLUME_ID/actions/resize" | champ "['action']['id']")
for _ in $(seq 60); do
  ETAT=$(appel "$API/actions/$ACTION" | champ "['action']['status']")
  [ "$ETAT" = running ] || break; sleep 5
done
[ "$ETAT" = success ] || { echo "Hetzner n'a pas agrandi le Volume (état : $ETAT)."; exit 1; }
# Le système voit la nouvelle taille du disque, puis la place s'étend (sans coupure).
DISQUE=$(readlink -f "$LIEN")
echo 1 > "/sys/class/block/$(basename "$DISQUE")/device/rescan"
sleep 2
resize2fs "$DISQUE"
df -h "$DONNEES" | tail -1
EOF
chmod 755 /usr/local/bin/agrandir-volume-monitora

echo "3/3 Vérification toutes les 15 minutes…"
cat > /etc/systemd/system/agrandir-volume-monitora.service <<'EOF'
[Unit]
Description=Agrandit le Volume des données Monitora quand il se remplit
RequiresMountsFor=/srv/monitora

[Service]
Type=oneshot
ExecStart=/usr/local/bin/agrandir-volume-monitora
EOF
cat > /etc/systemd/system/agrandir-volume-monitora.timer <<'EOF'
[Unit]
Description=Vérifie le remplissage du Volume Monitora toutes les 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now agrandir-volume-monitora.timer >/dev/null
systemctl start agrandir-volume-monitora.service
echo "Prêt : le Volume $VOLUME_ID ($(df -h --output=size /srv/monitora | tail -1 | tr -d ' ')) sera agrandi tout seul à partir de 80 %."
