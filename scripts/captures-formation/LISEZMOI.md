# Captures annotées du cours en ligne

Scripts Playwright qui ouvrent la démo locale (http://localhost:5192), remplissent les formulaires
(la démo ne conserve rien) et enregistrent les captures avec des cadres rouges numérotés dans
`frontend/public/formation/guide/`. Les numéros correspondent, dans l'ordre, aux « reperes » des
blocs `capture` de `backend/apps/formation/contenu.py`.

Prérequis : `npm install playwright-core sharp` dans un dossier de travail, Google Chrome installé.

    NODE_PATH=<dossier>/node_modules node guide_tout.js

Ordre conseillé : guide_projets.js, guide_projets2.js, guide_planif.js, guide_planif2.js,
guide_tout.js, guide_complements.js, guide_doc.js, guide_reprises.js (le dernier corrige les
captures dont un repère n'avait pas été trouvé). Vérifier ensuite chaque image : un message
« repère introuvable » signale un cadre manquant.

# Vidéo de présentation, une par langue

`video.js <langue>` (fr, en, ar, es, de) filme la démo dans cette langue avec les légendes de
`video_textes.json` ; `tourner_videos.sh` tourne les 5 langues et écrit, dans
`frontend/public/videos/` : `presentation-<langue>.webm`, `affiche-<langue>.webp` et
`chapitres.json` (seconde de début de chaque chapitre, par langue). Le site vitrine et les leçons
de la formation lisent ces fichiers (une seule copie, servie par la plateforme) et choisissent la
vidéo de la langue affichée. Adapter les chemins (NODE_PATH, ffmpeg de Playwright) en tête du script.
