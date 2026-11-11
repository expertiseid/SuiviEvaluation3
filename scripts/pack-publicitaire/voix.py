"""Voix off : une phrase par scène (edge-tts), accélérée si elle dépasse sa scène ; écrit voix/placements.json."""
import asyncio, json, math, os, re, subprocess, sys

import edge_tts

ICI = os.path.dirname(os.path.abspath(__file__))
FFMPEG = sys.argv[1]
textes = json.load(open(f"{ICI}/textes.json"))
scenes = json.load(open(f"{ICI}/scenes.json"))


def duree(fichier):
    sortie = subprocess.run([FFMPEG, "-i", fichier], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", sortie).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def dire(texte, voix, vitesse, fichier):
    """Déjà faite (même texte, voix, vitesse) : gardée. Sinon jusqu'à 8 essais, espacés (le service refuse parfois)."""
    cle = f"{voix}|{vitesse}|{texte}"
    if os.path.exists(fichier) and os.path.exists(fichier + ".txt") and open(fichier + ".txt").read() == cle:
        return
    for essai in range(8):
        nom = voix if essai < 6 else voix.replace("MultilingualNeural", "Neural")
        try:
            await edge_tts.Communicate(texte, nom, rate=f"{vitesse:+d}%").save(fichier)
            open(fichier + ".txt", "w").write(cle)
            await asyncio.sleep(0.6)
            return
        except Exception:
            await asyncio.sleep(3 + 2 * essai)
    raise RuntimeError(f"Pas de voix pour : {texte}")


TOTAL = 30.0
MARGE = 0.5  # silence après chaque phrase


async def main():
    """
    Le découpage en scènes suit la voix : chaque scène dure le temps de sa phrase (vitesse naturelle), plus une
    part du temps qui reste, selon la durée prévue dans scenes.json. Si les phrases ne tiennent pas en 30 s, elles
    sont toutes un peu accélérées (même vitesse pour toute la vidéo).
    """
    placements = {}
    for langue, t in textes.items():
        for video, conf in scenes.items():
            voix = t["voix"][conf["voix"]]
            dossier = f"{ICI}/voix/{langue}/{video}"
            os.makedirs(dossier, exist_ok=True)
            prevues = {k: f - d for k, (d, f) in conf["scenes"].items()}
            vitesse = 0
            for _ in range(4):
                durees = {}
                for scene in prevues:
                    fichier = f"{dossier}/{scene}.mp3"
                    await dire(t[video][scene]["voix"], voix, vitesse, fichier)
                    durees[scene] = duree(fichier)
                besoin = sum(d + MARGE for d in durees.values()) + 0.3
                if besoin <= TOTAL or vitesse >= 25:
                    break
                vitesse = min(25, vitesse + max(3, math.ceil((besoin / TOTAL - 1) * 100) + 1))
            reste = max(0.0, TOTAL - besoin)
            poids = {k: max(0.0, prevues[k] - durees[k] - MARGE) for k in prevues}
            total_poids = sum(poids.values()) or 1.0
            liste, temps, debut_scene = [], {}, 0.0
            for scene in prevues:
                longueur = durees[scene] + MARGE + reste * poids[scene] / total_poids
                if scene == list(prevues)[0]:
                    longueur += 0.3
                temps[scene] = [round(debut_scene, 3), round(debut_scene + longueur, 3)]
                depart = debut_scene + (0.3 if scene == list(prevues)[0] else 0.12)
                liste.append({"scene": scene, "debut": round(depart, 2), "duree": round(durees[scene], 2), "fichier": f"{dossier}/{scene}.mp3"})
                debut_scene += longueur
            temps[list(prevues)[-1]][1] = max(TOTAL, round(debut_scene, 3))
            placements.setdefault(langue, {})[video] = {"vitesse": vitesse, "voix": liste, "scenes": temps}
            print(langue, video, "vitesse", vitesse, "fin", round(debut_scene, 1))
    json.dump(placements, open(f"{ICI}/voix/placements.json", "w"), indent=1, ensure_ascii=False)


asyncio.run(main())
