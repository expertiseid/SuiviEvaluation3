"""
Exports « comme à l'écran » du tableau de bord : chaque bloc affiché est capturé en image par le navigateur
(mêmes graphiques, couleurs, types et réglages d'apparence, blocs masqués exclus), puis assemblé ici en PDF ou
en Word avec la disposition de l'écran (grille de 12 colonnes : un bloc occupe 4, 6 ou 12 colonnes). Pour
Excel, les feuilles de données restent, et une dernière feuille reprend les images.
"""
import base64
import io
import json
from html import escape

from django.utils import timezone

from apps.core.vocabulaire import v

COLONNES = 12
IMAGES_MAX = 60
TAILLE_MAX = 8 * 1024 * 1024  # par image


class BlocInvalide(ValueError):
    pass


def lire_blocs(requete) -> list[dict]:
    """Blocs envoyés : « blocs » (JSON : [{titre, largeur}]) et une image PNG par bloc (image_0, image_1…)."""
    from PIL import Image

    try:
        descriptions = json.loads(requete.data.get("blocs") or "[]")
    except (TypeError, ValueError):
        raise BlocInvalide(v("Description des blocs illisible."))
    if not isinstance(descriptions, list) or not descriptions or len(descriptions) > IMAGES_MAX:
        raise BlocInvalide(v("Aucun bloc à exporter."))
    blocs = []
    for rang, description in enumerate(descriptions):
        fichier = requete.FILES.get(f"image_{rang}")
        if fichier is None or fichier.size > TAILLE_MAX:
            raise BlocInvalide(v("Image du bloc manquante ou trop lourde."))
        contenu = fichier.read()
        try:
            image = Image.open(io.BytesIO(contenu))
            image.verify()
            largeur_px, hauteur_px = Image.open(io.BytesIO(contenu)).size
        except Exception:
            raise BlocInvalide(v("Image du bloc illisible."))
        largeur = description.get("largeur") if isinstance(description, dict) else None
        blocs.append({
            "titre": str((description or {}).get("titre") or "")[:200],
            "largeur": largeur if largeur in (3, 4, 6, 8, 12) else COLONNES,
            "image": contenu, "px": (largeur_px, hauteur_px),
        })
    return blocs


def lignes_de_la_grille(blocs) -> list[list[dict]]:
    """Comme la grille de l'écran : les blocs se suivent sur une ligne tant que leurs largeurs tiennent dans 12."""
    lignes, ligne, occupe = [], [], 0
    for bloc in blocs:
        if ligne and occupe + bloc["largeur"] > COLONNES:
            lignes.append(ligne)
            ligne, occupe = [], 0
        ligne.append(bloc)
        occupe += bloc["largeur"]
    if ligne:
        lignes.append(ligne)
    return lignes


def _coupure(image, debut, fin):
    """Ligne de coupe entre debut et fin : la plus unie (blanc, bordure) dans le dernier quart, sinon fin."""
    gris = image.convert("L")
    largeur = gris.width
    meilleure, ecart_min = fin, None
    for y in range(fin, max(debut + 1, fin - (fin - debut) // 4), -1):
        ligne = gris.crop((0, y, largeur, y + 1)).getdata()
        valeurs = list(ligne)
        ecart = max(valeurs) - min(valeurs)
        if ecart_min is None or ecart < ecart_min:
            meilleure, ecart_min = y, ecart
            if ecart == 0:
                break
    return meilleure


def decouper(lignes, rapport_max: float) -> list[list[dict]]:
    """
    Un bloc seul sur sa ligne et plus haut que la page (hauteur ÷ largeur > rapport_max, selon sa largeur dans la
    grille) est découpé en morceaux d'une page, plutôt que réduit jusqu'à être illisible.
    """
    from PIL import Image

    resultat = []
    for ligne in lignes:
        bloc = ligne[0]
        largeur_px, hauteur_px = bloc["px"]
        limite = rapport_max * COLONNES / bloc["largeur"]
        if len(ligne) > 1 or hauteur_px / largeur_px <= limite:
            resultat.append(ligne)
            continue
        image = Image.open(io.BytesIO(bloc["image"])).convert("RGB")
        pas, y = int(largeur_px * limite), 0
        while y < hauteur_px:
            fin = hauteur_px if y + pas >= hauteur_px else _coupure(image, y, y + pas)
            tampon = io.BytesIO()
            image.crop((0, y, largeur_px, fin)).save(tampon, format="PNG")
            resultat.append([{**bloc, "image": tampon.getvalue(), "px": (largeur_px, fin - y)}])
            y = fin
    return resultat


def entete(titre: str, filtres_texte: str = "") -> dict:
    return {"titre": titre, "sous_titre": v("Exporté le {0}").format(timezone.localtime().strftime("%d/%m/%Y %H:%M")),
            "filtres": filtres_texte}


# --- PDF ---------------------------------------------------------------------------------------------


def pdf(e: dict, blocs: list[dict]) -> bytes:
    """A4 paysage ; une ligne de blocs ne se coupe pas entre deux pages ; un bloc trop haut est réduit à la page."""
    from weasyprint import HTML

    morceaux = [
        "<style>@page{size:A4 landscape;margin:10mm}body{font-family:sans-serif;color:#212529;margin:0}"
        "h1{font-size:15pt;color:#0B5345;margin:0}.gris{color:#6C757D;margin:2px 0;font-size:8.5pt}"
        "table.ligne{width:100%;border-collapse:separate;border-spacing:0 0;margin-top:3mm;page-break-inside:avoid}"
        "table.ligne td{vertical-align:top;padding:0 1.5mm}table.ligne td:first-child{padding-left:0}"
        "table.ligne td:last-child{padding-right:0}"
        "img{display:block;max-width:100%;max-height:178mm;margin:0 auto}</style>",
        f"<h1>{escape(e['titre'])}</h1><p class='gris'>{escape(e['sous_titre'])}</p>",
        f"<p class='gris'>{escape(e['filtres'])}</p>" if e["filtres"] else "",
    ]
    # Page utile : 277 × 178 mm.
    for ligne in decouper(lignes_de_la_grille(blocs), 178 / 277):
        cellules = []
        for bloc in ligne:
            image = base64.b64encode(bloc["image"]).decode()
            cellules.append(f"<td style='width:{bloc['largeur'] / COLONNES * 100:.2f}%'>"
                            f"<img src='data:image/png;base64,{image}' alt='{escape(bloc['titre'])}'></td>")
        reste = COLONNES - sum(b["largeur"] for b in ligne)
        if reste > 0:
            cellules.append(f"<td style='width:{reste / COLONNES * 100:.2f}%'></td>")
        morceaux.append("<table class='ligne'><tr>" + "".join(cellules) + "</tr></table>")
    return HTML(string="".join(morceaux)).write_pdf()


# --- Word --------------------------------------------------------------------------------------------


def word(e: dict, blocs: list[dict]) -> bytes:
    """A4 paysage ; les blocs d'une même ligne côte à côte (tableau sans bordure), chacun réduit à la page."""
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    marge = Cm(1.2)
    for cote in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, cote, marge)
    utile = (section.page_width - 2 * marge) / 360000  # cm
    hauteur_max = (section.page_height - 2 * marge) / 360000 - 1.2
    document.styles["Normal"].font.size = Pt(9)

    titre = document.add_paragraph()
    run = titre.add_run(e["titre"])
    run.bold, run.font.size, run.font.color.rgb = True, Pt(16), RGBColor(0x0B, 0x53, 0x45)
    for texte in (e["sous_titre"], e["filtres"]):
        if texte:
            ligne = document.add_paragraph().add_run(texte)
            ligne.font.color.rgb, ligne.font.size = RGBColor(0x6C, 0x75, 0x7D), Pt(8.5)

    def largeur_image(bloc, place_cm):
        """Largeur (cm) qui tient dans la place et dans la hauteur de la page, proportions gardées."""
        largeur_px, hauteur_px = bloc["px"]
        return min(place_cm, hauteur_max * largeur_px / hauteur_px)

    def sans_bordure(tableau):
        bordures = OxmlElement("w:tblBorders")
        for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
            element = OxmlElement(f"w:{cote}")
            element.set(qn("w:val"), "nil")
            bordures.append(element)
        tableau._tbl.tblPr.append(bordures)

    for ligne in decouper(lignes_de_la_grille(blocs), hauteur_max / utile):
        if len(ligne) == 1:
            bloc = ligne[0]
            paragraphe = document.add_paragraph()
            paragraphe.alignment = WD_ALIGN_PARAGRAPH.CENTER if bloc["largeur"] == COLONNES else WD_ALIGN_PARAGRAPH.LEFT
            paragraphe.add_run().add_picture(io.BytesIO(bloc["image"]), width=Cm(largeur_image(bloc, utile * bloc["largeur"] / COLONNES)))
            continue
        tableau = document.add_table(rows=1, cols=len(ligne))
        tableau.autofit = False
        sans_bordure(tableau)
        for cellule, bloc in zip(tableau.rows[0].cells, ligne):
            place = utile * bloc["largeur"] / COLONNES
            cellule.width = Cm(place)
            cellule.paragraphs[0].add_run().add_picture(io.BytesIO(bloc["image"]), width=Cm(largeur_image(bloc, place - 0.3)))
        document.add_paragraph()

    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


# --- Excel : dernière feuille --------------------------------------------------------------------------


def feuille_comme_a_l_ecran(classeur, blocs: list[dict], nom: str = "") -> None:
    """Ajoute au classeur une dernière feuille où les blocs sont placés comme sur l'écran (taille réelle)."""
    from openpyxl.drawing.image import Image as ImageExcel

    feuille = classeur.create_sheet((nom or v("Comme à l'écran"))[:31])
    feuille.sheet_view.showGridLines = False
    colonne_px, ligne_px, ecart = 64, 20, 12
    largeur_ecran = 1400  # largeur de référence d'une ligne de 12 colonnes (pixels)
    for colonne in range(1, 40):
        feuille.column_dimensions[feuille.cell(row=1, column=colonne).column_letter].width = 8.43
    y = 2 * ligne_px
    for ligne in lignes_de_la_grille(blocs):
        x, hauteur_ligne = 0, 0
        for bloc in ligne:
            largeur_px, hauteur_px = bloc["px"]
            largeur = largeur_ecran * bloc["largeur"] / COLONNES - ecart
            hauteur = largeur * hauteur_px / largeur_px
            image = ImageExcel(io.BytesIO(bloc["image"]))
            image.width, image.height = largeur, hauteur
            feuille.add_image(image, f"{feuille.cell(row=1, column=int(x // colonne_px) + 1).column_letter}{int(y // ligne_px) + 1}")
            x += largeur + ecart
            hauteur_ligne = max(hauteur_ligne, hauteur)
        y += hauteur_ligne + ecart
