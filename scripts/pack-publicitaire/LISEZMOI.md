# Pack publicitaire Expertise-ID Monitora

Fabrique, dans les 5 langues de la plateforme (fr, en, es, de, ar) :

- **3 vidéos de 30 s** (lancement, présentation, offres), en paysage 16:9 et en vertical 9:16, avec voix off,
  musique et sous-titres (.srt) ;
- **7 affiches** (publication 1080×1350, story 1080×1920, A4 à imprimer en PNG et PDF 300 dpi).

```bash
scripts/pack-publicitaire/fabriquer.sh ~/Pack-publicitaire-Expertise-ID-Monitora
```

Prérequis : Python 3, Node.js, Google Chrome. Durée : environ 30 minutes (les vidéos sont dessinées image par image).

## Fichiers

| Fichier | Rôle |
|---|---|
| `textes.json` | Tous les textes, par langue : voix off, mots à l'écran, affiches, publications. |
| `scenes.json` | Découpage prévu de chaque vidéo (le découpage réel suit la longueur des phrases). |
| `voix.py` | Voix off (voix neuronales Microsoft via edge-tts) ; cale les scènes sur la voix, 30 s au total. |
| `musique.py` | Musique de fond composée par le programme (libre de droits), un « whoosh » par scène. |
| `studio/studio.js` | Animations (GSAP) des 3 vidéos ; `window.seek(t)` dessine l'image à l'instant t. |
| `rendre.js` | Rendu image par image (30 i/s) en MP4 muet ; `apercu` : quelques images clés pour vérifier. |
| `assembler.py` | Son final : voix + musique qui s'efface sous la voix, −16 LUFS ; sous-titres. |
| `studio/affiches.js`, `rendre_affiches.js` | Les 7 affiches. |
| `ecrans.js` | Captures des écrans de la démonstration (bouton « Essayer la démo »). |

Changer un prix ou un texte : modifier `textes.json` (et les montants dans `studio/studio.js` / `studio/affiches.js`
pour les prix), puis relancer. Voix : pour une diffusion commerciale importante, préférer un service sous
licence (Azure Speech) ou un comédien ; les scripts sont générés dans `textes/` du pack.
