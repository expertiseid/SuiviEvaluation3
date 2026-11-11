"""
Assemblage final de chaque vidéo : image (rendus/*-muet.mp4) + voix placées au bon moment + musique qui
s'efface quand la voix parle (compression déclenchée par la voix), volume normalisé pour les réseaux
sociaux (-16 LUFS). Écrit aussi les sous-titres (.srt). python assembler.py <ffmpeg> <dossier de sortie>
"""
import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
FFMPEG, SORTIE = sys.argv[1], sys.argv[2]
textes = json.load(open(f"{ICI}/textes.json"))
placements = json.load(open(f"{ICI}/voix/placements.json"))
NOMS = {"lancement": "01-lancement", "presentation": "02-presentation", "offres": "03-offres"}
FORMATS = {"h": "paysage-16x9", "v": "vertical-9x16"}


def horodatage(s):
    h, reste = divmod(s, 3600)
    m, sec = divmod(reste, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(round((sec % 1) * 1000)):03d}"


def sous_titres(langue, video, fichier):
    lignes = []
    for i, v in enumerate(placements[langue][video]["voix"], 1):
        texte = textes[langue][video][v["scene"]]["voix"]
        lignes += [str(i), f"{horodatage(v['debut'])} --> {horodatage(v['debut'] + v['duree'] + 0.2)}", texte, ""]
    open(fichier, "w", encoding="utf-8").write("\n".join(lignes))


def assembler(langue, video, fmt):
    muet = f"{ICI}/rendus/{video}-{langue}-{fmt}-muet.mp4"
    if not os.path.exists(muet):
        return False
    dossier = f"{SORTIE}/{langue}/videos"
    os.makedirs(dossier, exist_ok=True)
    final = f"{dossier}/{NOMS[video]}-{FORMATS[fmt]}-{langue}.mp4"
    voix = placements[langue][video]["voix"]
    entrees = ["-i", muet, "-i", f"{ICI}/musique/{video}.wav"]
    for v in voix:
        entrees += ["-i", v["fichier"]]
    filtres = []
    for i, v in enumerate(voix):
        ms = int(v["debut"] * 1000)
        filtres.append(f"[{i + 2}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume=1.6[v{i}]")
    filtres.append("".join(f"[v{i}]" for i in range(len(voix))) + f"amix=inputs={len(voix)}:normalize=0,apad=whole_dur=30[voixbus]")
    filtres.append("[voixbus]asplit=2[voixa][voixb]")
    filtres.append("[1:a]volume=0.55[mus]")
    filtres.append("[mus][voixa]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[musduck]")
    filtres.append("[musduck][voixb]amix=inputs=2:normalize=0,atrim=0:30,loudnorm=I=-16:TP=-1.5:LRA=11[audio]")
    commande = [FFMPEG, "-y", "-loglevel", "error", *entrees, "-filter_complex", ";".join(filtres),
                "-map", "0:v", "-map", "[audio]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-t", "30", "-movflags", "+faststart", final]
    subprocess.run(commande, check=True)
    sous_titres(langue, video, final[:-4] + ".srt")
    return True


if __name__ == "__main__":
    faits = 0
    for langue in textes:
        for video in NOMS:
            for fmt in FORMATS:
                if assembler(langue, video, fmt):
                    faits += 1
    print(faits, "vidéos assemblées")
