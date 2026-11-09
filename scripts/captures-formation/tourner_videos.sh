#!/bin/bash
cd $(dirname $0)
F=~/Library/Caches/ms-playwright/ffmpeg-1013/ffmpeg-mac
V=/Users/macbookpro/Suivi-evaluation/SuiviEvaluation3/frontend/public/videos
for l in fr en ar es de; do
  NODE_PATH=/private/tmp/claude-502/-Users-macbookpro-Suivi-evaluation/3fdfdbdf-5f0d-4c37-ae7a-43f9521f0f53/scratchpad/deck/node_modules node video.js $l > tournage-$l.log 2>&1 || { echo "ECHEC $l"; tail -3 tournage-$l.log; continue; }
  $F -hide_banner -loglevel error -i brut-$l.webm -c copy -y $V/presentation-$l.webm
  $F -hide_banner -loglevel error -ss 2.5 -i $V/presentation-$l.webm -frames:v 1 -y img/affiche-$l.png
  NODE_PATH=/private/tmp/claude-502/-Users-macbookpro-Suivi-evaluation/3fdfdbdf-5f0d-4c37-ae7a-43f9521f0f53/scratchpad/deck/node_modules node -e 'require("sharp")(process.argv[1]).webp({quality:80}).toFile(process.argv[2])' img/affiche-$l.png $V/affiche-$l.webp
  echo "OK $l $(cat chapitres-$l.json)"
done
python3 -c "
import json
d={l: json.load(open('chapitres-%s.json'%l)) for l in ['fr','en','ar','es','de']}
json.dump(d, open('$V/chapitres.json','w'), ensure_ascii=False, indent=1)
print('chapitres.json écrit')"
