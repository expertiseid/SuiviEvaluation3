"""Planche contact des images d'aperçu : python planche.py <dossier> <sortie.jpg>"""
import sys, glob
from PIL import Image, ImageDraw
fichiers = sorted(glob.glob(sys.argv[1] + "/*.jpg"))
ims = [Image.open(f) for f in fichiers]
w, h = ims[0].size
colonnes = 4 if w > h else 6
lw = 480 if w > h else 270
lh = int(h * lw / w)
lignes = (len(ims) + colonnes - 1) // colonnes
planche = Image.new("RGB", (colonnes * (lw + 6), lignes * (lh + 24)), "white")
d = ImageDraw.Draw(planche)
for i, (im, f) in enumerate(zip(ims, fichiers)):
    x, y = (i % colonnes) * (lw + 6), (i // colonnes) * (lh + 24)
    planche.paste(im.resize((lw, lh)), (x, y + 20))
    d.text((x + 4, y + 4), f.split("/")[-1][:-4] + " s", fill="black")
planche.save(sys.argv[2], quality=85)
