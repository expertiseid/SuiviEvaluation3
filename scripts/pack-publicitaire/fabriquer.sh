#!/bin/bash
# Fabrique tout le pack publicitaire (5 langues) dans <dossier de sortie>. Mode d'emploi : LISEZMOI.md.
#   scripts/pack-publicitaire/fabriquer.sh ~/Pack-publicitaire-Expertise-ID-Monitora
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
DEPOT="$(cd "$ICI/../.." && pwd)"
SORTIE="${1:?Dossier de sortie manquant}"
TRAVAIL="${TRAVAIL:-$HOME/.cache/pack-monitora}"
mkdir -p "$TRAVAIL" && cd "$TRAVAIL"

echo "1/7 Outils (une seule fois)…"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q edge-tts numpy pillow "qrcode[pil]"
[ -d node_modules/gsap ] || { npm init -y >/dev/null; npm i -s ffmpeg-static@5.2.0 playwright-core@1.49.1 gsap@3.12.5 >/dev/null; }
FFMPEG="$TRAVAIL/node_modules/ffmpeg-static/ffmpeg"

echo "2/7 Sources, polices, logos…"
cp "$ICI"/*.json "$ICI"/*.py "$ICI"/*.js .
mkdir -p studio && cp "$ICI"/studio/* studio/
cp -R "$DEPOT/site-vitrine/vitrine/polices" "$DEPOT/site-vitrine/vitrine/polices.css" studio/
cp -R "$DEPOT/frontend/public/logos" "$DEPOT/frontend/public/logo-plateforme.svg" "$DEPOT/frontend/public/logo-expertise-id.png" studio/
cp node_modules/gsap/dist/gsap.min.js studio/
./venv/bin/python -c "import qrcode, qrcode.image.svg; qrcode.make('https://expertise-id-monitora.com', image_factory=qrcode.image.svg.SvgPathImage, border=1).save('studio/qr.svg')"

echo "3/7 Captures d'écran de la démonstration (5 langues)…"
for l in fr en es de ar; do mkdir -p "ecrans/$l"; node ecrans.js "$TRAVAIL/ecrans/$l" "$l"; done

echo "4/7 Voix off et musique…"
./venv/bin/python voix.py "$FFMPEG"
./venv/bin/python musique.py

echo "5/7 Vidéos (30 rendus, 3 à la fois)…"
for l in fr en es de ar; do for v in lancement presentation offres; do for f in h v; do echo "$v $l $f"; done; done; done \
  | xargs -P 3 -L 1 sh -c 'node rendre.js $0 $1 $2'

echo "6/7 Son, sous-titres et affiches…"
./venv/bin/python assembler.py "$FFMPEG" "$SORTIE"
for l in fr en es de ar; do node rendre_affiches.js "$l" "$SORTIE/$l/affiches"; done
./venv/bin/python -c "
import glob; from PIL import Image
for f in glob.glob('$SORTIE/*/affiches/*a4-impression*.png'): Image.open(f).convert('RGB').save(f[:-4] + '.pdf', resolution=300)"

echo "7/7 Terminé : $SORTIE (les textes et la page index.html sont à regénérer à part, voir LISEZMOI.md)."
