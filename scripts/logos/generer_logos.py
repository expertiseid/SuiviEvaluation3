"""Logos d'Expertise-ID Monitora, dans les 5 langues de la plateforme.

Produit, pour le site vitrine (site-vitrine/vitrine/) et la plateforme (frontend/public/) :
  - logo-plateforme.svg        : le symbole seul (celui du modèle, docs/logos/source/) — icône d'onglet, petits formats ;
  - logos/logo-<langue>.svg    : symbole + « Expertise-ID Monitora » + devise (en-têtes) ;
  - logos/logo-complet-<langue>.svg : le même avec la phrase d'accroche en dessous (grands formats).
Une copie de tout va dans docs/logos/.

Les textes sont convertis en tracés : le logo s'affiche à l'identique partout, sans police à charger.
Polices libres (licence OFL) téléchargées au premier lancement dans scripts/logos/polices/ :
Montserrat (nom, devise) et Noto Sans Arabic (arabe).

Lancement (outils Python dans un environnement à part) :
    python3 -m venv /tmp/venv-logos && /tmp/venv-logos/bin/pip install fonttools uharfbuzz brotli pillow
    /tmp/venv-logos/bin/python scripts/logos/generer_logos.py
"""

import base64
import io
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RACINE = Path(__file__).resolve().parents[2]
POLICES = Path(__file__).resolve().parent / "polices"
SOURCES = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FICHIERS_POLICES = {
    "Montserrat.ttf": "montserrat/Montserrat%5Bwght%5D.ttf",
    "Montserrat-Italic.ttf": "montserrat/Montserrat-Italic%5Bwght%5D.ttf",
    "NotoSansArabic.ttf": "notosansarabic/NotoSansArabic%5Bwdth,wght%5D.ttf",
}

# Couleurs du logo.
MARINE = "#123d82"
VERT = "#2fa64a"

# Devise et phrase d'accroche, par langue (la phrase tient sur deux lignes).
TEXTES = {
    "fr": (["Suivre", "Évaluer", "Décider"],
           ["Une plateforme au service du suivi-évaluation", "pour un impact durable"]),
    "en": (["Monitor", "Evaluate", "Decide"],
           ["A platform serving monitoring and evaluation", "for lasting impact"]),
    "es": (["Seguir", "Evaluar", "Decidir"],
           ["Una plataforma al servicio del seguimiento y la evaluación", "para un impacto duradero"]),
    "de": (["Verfolgen", "Bewerten", "Entscheiden"],
           ["Eine Plattform im Dienst von Monitoring und Evaluierung", "für nachhaltige Wirkung"]),
    "it": (["Monitorare", "Valutare", "Decidere"],
           ["Una piattaforma al servizio del monitoraggio e della valutazione", "per un impatto duraturo"]),
    "ar": (["متابعة", "تقييم", "قرار"],
           ["منصة في خدمة المتابعة والتقييم", "من أجل أثر مستدام"]),
}


# --------------------------------------------------------------------------- polices et texte en tracés

def telecharger_polices():
    POLICES.mkdir(exist_ok=True)
    for nom, chemin in FICHIERS_POLICES.items():
        if not (POLICES / nom).exists():
            with urllib.request.urlopen(SOURCES + chemin) as reponse:
                (POLICES / nom).write_bytes(reponse.read())


class Police:
    """Une graisse d'une police variable, prête à mettre du texte en forme (HarfBuzz) et en tracés."""

    def __init__(self, fichier, **axes):
        source = TTFont(POLICES / fichier)
        axes = {a: v for a, v in axes.items() if a in {ax.axisTag for ax in source["fvar"].axes}}
        self.font = instancer.instantiateVariableFont(source, axes)
        tampon = io.BytesIO()
        self.font.save(tampon)
        self.hb = hb.Font(hb.Face(tampon.getvalue()))
        self.glyphes = self.font.getGlyphSet()
        self.noms = self.font.getGlyphOrder()
        self.em = self.font["head"].unitsPerEm
        os2 = self.font["OS/2"]
        self.hauteur_x = os2.sxHeight / self.em
        self.hauteur_cap = os2.sCapHeight / self.em

    def mettre_en_forme(self, texte):
        tampon = hb.Buffer()
        tampon.add_str(texte)
        tampon.guess_segment_properties()
        hb.shape(self.hb, tampon, {"kern": True, "liga": True})
        # Pour l'arabe, HarfBuzz rend les glyphes déjà dans l'ordre visuel (de gauche à droite).
        return list(zip(tampon.glyph_infos, tampon.glyph_positions))

    def largeur(self, texte, taille):
        return sum(p.x_advance for _, p in self.mettre_en_forme(texte)) * taille / self.em

    def traces(self, texte, taille, x, y, sauter=()):
        """Chemin SVG du texte, ligne de base en (x, y). Renvoie (d, positions des glyphes)."""
        echelle = taille / self.em
        morceaux, positions = [], []
        curseur = 0
        for i, (info, pos) in enumerate(self.mettre_en_forme(texte)):
            gx = x + (curseur + pos.x_offset) * echelle
            gy = y - pos.y_offset * echelle
            positions.append((gx, pos.x_advance * echelle))
            if i not in sauter:
                stylo = SVGPathPen(self.glyphes, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
                self.glyphes[self.noms[info.codepoint]].draw(
                    TransformPen(stylo, (echelle, 0, 0, -echelle, gx, gy)))
                morceaux.append(stylo.getCommands())
            curseur += pos.x_advance
        return " ".join(m for m in morceaux if m), positions


# --------------------------------------------------------------------------- symbole

# Le symbole est celui du modèle fourni (docs/logos/source/modele-logo.png), découpé et détouré une fois
# pour toutes dans docs/logos/source/symbole.png : il est intégré tel quel dans chaque logo.
SYMBOLE = RACINE / "docs/logos/source/symbole.png"
DEFS = """
  <linearGradient id="camembert" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#1f8fc9"/><stop offset="1" stop-color="#123d82"/>
  </linearGradient>"""


def symbole(x, y, hauteur, pixels):
    """Le symbole en image intégrée (WebP), `pixels` de haut, placé en (x, y) sur `hauteur` unités."""
    from PIL import Image

    image = Image.open(SYMBOLE)
    largeur = hauteur * image.width / image.height
    if pixels < image.height:
        image = image.resize((round(image.width * pixels / image.height), pixels), Image.LANCZOS)
    tampon = io.BytesIO()
    image.save(tampon, "WEBP", quality=92, method=6)
    donnees = base64.b64encode(tampon.getvalue()).decode()
    return (f'<image x="{x:.1f}" y="{y:.1f}" width="{largeur:.1f}" height="{hauteur:.1f}" '
            f'href="data:image/webp;base64,{donnees}"/>'), largeur


def svg(largeur, hauteur, contenu, titre):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur:.0f} {hauteur:.0f}" '
            f'role="img" aria-label="{titre}">\n<defs>{DEFS}\n</defs>\n  {contenu}\n</svg>\n')


# --------------------------------------------------------------------------- logos avec texte

def camembert(cx, cy, r):
    """Le « o » de Monitora : un disque avec un quart vert."""
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="url(#camembert)"/>'
            f'<path d="M{cx:.1f} {cy:.1f} V{cy - r:.1f} A{r:.1f} {r:.1f} 0 0 1 {cx + r:.1f} {cy:.1f} Z" '
            f'fill="{VERT}" stroke="#ffffff" stroke-width="{r * 0.12:.1f}" stroke-linejoin="round"/>')


def ligne_de_mots(police, mots, taille, centre, y, rtl):
    """Mots séparés par des points verts, centrés sur `centre`."""
    espace = taille * 0.75
    largeurs = [police.largeur(m, taille) for m in mots]
    total = sum(largeurs) + espace * (len(mots) - 1)
    ordre = list(zip(mots, largeurs))[::-1] if rtl else list(zip(mots, largeurs))
    x, morceaux = centre - total / 2, []
    for i, (mot, larg) in enumerate(ordre):
        d, _ = police.traces(mot, taille, x, y)
        morceaux.append(f'<path d="{d}" fill="{MARINE}"/>')
        x += larg
        if i < len(ordre) - 1:
            morceaux.append(f'<circle cx="{x + espace / 2:.1f}" cy="{y - taille * 0.3:.1f}" r="{taille * 0.1:.1f}" fill="{VERT}"/>')
            x += espace
    return morceaux, total


def logo(langue, polices, complet, pixels):
    devise, accroche = TEXTES[langue]
    rtl = langue == "ar"
    gras, italique = polices["gras"], polices["ar_moyen" if rtl else "italique"]
    police_accroche = polices["ar_leger" if rtl else "italique_leger"]

    # Symbole à gauche (330 de haut), nom et devise à droite.
    image, larg_symbole = symbole(0, 0, 336, pixels)
    x0, taille_m = larg_symbole + 30, 150
    largeur_m = gras.largeur("Monitora", taille_m)
    taille_e = taille_m * 0.9 * largeur_m / gras.largeur("Expertise-ID", taille_m)
    base_e, base_m = 120, 120 + taille_m * 0.95
    haut = [image]
    d, _ = gras.traces("Expertise-", taille_e, x0, base_e)
    haut.append(f'<path d="{d}" fill="{MARINE}"/>')
    d, _ = gras.traces("ID", taille_e, x0 + gras.largeur("Expertise-", taille_e), base_e)
    haut.append(f'<path d="{d}" fill="{VERT}"/>')
    d, positions = gras.traces("Monitora", taille_m, x0, base_m, sauter={1})
    haut.append(f'<path d="{d}" fill="{MARINE}"/>')
    ox, olarg = positions[1]
    haut.append(camembert(ox + olarg / 2, base_m - taille_m * gras.hauteur_x / 2, taille_m * gras.hauteur_x * 0.58))
    trait = base_m + 26
    haut.append(f'<rect x="{x0}" y="{trait}" width="{largeur_m:.1f}" height="4" rx="2" fill="{VERT}"/>')
    # Devise sur toute la largeur du trait (lisible même en petit), sans dépasser 70 de haut.
    _, larg = ligne_de_mots(italique, devise, 100, 0, 0, rtl)
    taille_d = min(70, 100 * largeur_m * 0.94 / larg)
    morceaux, _ = ligne_de_mots(italique, devise, taille_d, x0 + largeur_m / 2, trait + 18 + taille_d, rtl)
    haut += morceaux
    largeur, hauteur = x0 + largeur_m + 10, max(trait + 40 + taille_d, 336)
    if not complet:
        return svg(largeur, hauteur, "\n  ".join(haut), "Expertise-ID Monitora")

    # Phrase d'accroche centrée en dessous, filets de part et d'autre de la première ligne.
    taille_a, bas, lignes = 40, [], []
    for phrase in accroche:
        d, _ = police_accroche.traces(phrase, taille_a, 0, 0)
        lignes.append((d, police_accroche.largeur(phrase, taille_a)))
    largeur_totale = max(largeur, lignes[0][1] + 2 * 160, max(l for _, l in lignes))
    centre, y = largeur_totale / 2, hauteur + 70
    for n, (d, larg) in enumerate(lignes):
        bas.append(f'<path d="{d}" fill="{MARINE}" transform="translate({centre - larg / 2:.1f} {y:.1f})"/>')
        if n == 0:
            for xf in (centre - larg / 2 - 150, centre + larg / 2 + 30):
                bas.append(f'<rect x="{xf:.1f}" y="{y - taille_a * 0.32:.1f}" width="120" height="3" fill="{MARINE}"/>')
        y += taille_a * 1.35
    contenu = [f'<g transform="translate({(largeur_totale - largeur) / 2:.1f} 0)">', *haut, "</g>", *bas]
    return svg(largeur_totale, y - taille_a * 0.6, "\n  ".join(contenu), "Expertise-ID Monitora")


def main():
    telecharger_polices()
    polices = {
        "gras": Police("Montserrat.ttf", wght=800),
        "italique": Police("Montserrat-Italic.ttf", wght=600),
        "italique_leger": Police("Montserrat-Italic.ttf", wght=500),
        "ar_moyen": Police("NotoSansArabic.ttf", wght=600, wdth=100),
        "ar_leger": Police("NotoSansArabic.ttf", wght=500, wdth=100),
    }
    # Sur le site et la plateforme, symbole léger (affiché petit) ; dans docs/logos, pleine définition.
    for dossier, pixels in ((RACINE / "frontend/public", 240), (RACINE / "site-vitrine/vitrine", 240), (RACINE / "docs/logos", 2000)):
        # Symbole seul, centré dans un carré de 200 (il est plus large que haut).
        _, larg = symbole(0, 0, 200, 1)
        hauteur = 200 * 200 / larg
        image, _ = symbole(0, (200 - hauteur) / 2, hauteur, pixels)
        fichiers = {"logo-plateforme.svg": svg(200, 200, image, "Expertise-ID Monitora")}
        for langue in TEXTES:
            fichiers[f"logos/logo-{langue}.svg"] = logo(langue, polices, complet=False, pixels=pixels)
            fichiers[f"logos/logo-complet-{langue}.svg"] = logo(langue, polices, complet=True, pixels=pixels)
        for nom, contenu in fichiers.items():
            (dossier / nom).parent.mkdir(parents=True, exist_ok=True)
            (dossier / nom).write_text(contenu, encoding="utf-8")
    print(f"{len(fichiers)} logos écrits dans frontend/public, site-vitrine/vitrine et docs/logos.")


if __name__ == "__main__":
    main()
