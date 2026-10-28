"""
Version Word (.docx) des rapports : convertit le HTML qui sert déjà aux exports PDF, pour que
les deux formats aient toujours le même contenu. Conversion volontairement simple : titres,
paragraphes, tableaux (avec en-tête), gras / italique / couleurs, petits textes, sauts de page,
orientation paysage ; les barres de progression et éléments purement décoratifs sont omis
(les pourcentages restent écrits dans le texte).
"""
import io
import re
from html.parser import HTMLParser

ELEMENTS_VIDES = {"br", "hr", "img", "meta", "link", "input", "col", "wbr"}
BLOCS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "li", "section", "header", "footer", "thead", "tbody", "tr", "td", "th", "body", "html", "hr"}
IGNORES = {"head", "style", "script", "title", "svg"}
COULEUR_ENTETE = "1F4E78"


class Noeud:
    def __init__(self, balise, attributs=None, parent=None):
        self.balise = balise
        self.attributs = dict(attributs or {})
        self.parent = parent
        self.enfants = []

    @property
    def style(self):
        return _style(self.attributs.get("style", ""))


class Texte:
    balise = "#texte"

    def __init__(self, texte):
        self.texte = texte


def _style(texte) -> dict:
    regles = {}
    for regle in texte.split(";"):
        if ":" in regle:
            cle, valeur = regle.split(":", 1)
            regles[cle.strip().lower()] = valeur.strip().lower()
    return regles


class _Lecteur(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.racine = Noeud("racine")
        self.courant = self.racine
        self.styles = []
        self._dans_style = False

    def handle_starttag(self, balise, attributs):
        noeud = Noeud(balise, attributs, self.courant)
        self.courant.enfants.append(noeud)
        if balise == "style":
            self._dans_style = True
        if balise not in ELEMENTS_VIDES:
            self.courant = noeud

    def handle_startendtag(self, balise, attributs):
        self.courant.enfants.append(Noeud(balise, attributs, self.courant))

    def handle_endtag(self, balise):
        if balise == "style":
            self._dans_style = False
        noeud = self.courant
        while noeud is not self.racine and noeud.balise != balise:
            noeud = noeud.parent
        if noeud is not self.racine:
            self.courant = noeud.parent

    def handle_data(self, donnees):
        if self._dans_style:
            self.styles.append(donnees)
        elif donnees:
            self.courant.enfants.append(Texte(donnees))


def _couleur(valeur):
    """'#1c7ed6' / '#abc' → 'RRGGBB' (None sinon, ex. couleurs avec transparence)."""
    m = re.fullmatch(r"#([0-9a-f]{6}|[0-9a-f]{3})", (valeur or "").strip())
    if not m:
        return None
    hexa = m.group(1)
    return (hexa if len(hexa) == 6 else "".join(c * 2 for c in hexa)).upper()


def _taille_pt(valeur):
    m = re.fullmatch(r"([\d.]+)px", (valeur or "").strip())
    return round(float(m.group(1)) * 0.75, 1) if m else None


def _masque(noeud) -> bool:
    if isinstance(noeud, Texte):
        return False
    style = noeud.style
    return noeud.balise in IGNORES or style.get("display") == "none"


def _decoratif(noeud) -> bool:
    """Barre de progression : bloc sans texte (fond coloré + largeur en %)."""
    return isinstance(noeud, Noeud) and noeud.balise == "div" and not _texte_brut(noeud).strip()


def _texte_brut(noeud) -> str:
    if isinstance(noeud, Texte):
        return noeud.texte
    if _masque(noeud):
        return ""
    return "".join(_texte_brut(e) for e in noeud.enfants)


def _contient_bloc(noeud) -> bool:
    return any(isinstance(e, Noeud) and e.balise in BLOCS and not _masque(e) for e in noeud.enfants)


class _Redacteur:
    def __init__(self, document):
        from docx.shared import Pt

        self.document = document
        self.Pt = Pt

    # --- Texte en ligne ---------------------------------------------------------------
    def runs(self, paragraphe, noeud, format_=None):
        """Ajoute au paragraphe le texte d'un nœud en ligne, avec gras/italique/couleur/taille."""
        format_ = dict(format_ or {})
        if isinstance(noeud, Texte):
            texte = re.sub(r"\s+", " ", noeud.texte)
            if not texte.strip() and not paragraphe.runs:
                return
            run = paragraphe.add_run(texte)
            run.bold = format_.get("gras")
            run.italic = format_.get("italique")
            if format_.get("couleur"):
                from docx.shared import RGBColor

                run.font.color.rgb = RGBColor.from_string(format_["couleur"])
            if format_.get("taille"):
                run.font.size = self.Pt(format_["taille"])
            return
        if _masque(noeud) or _decoratif(noeud):
            return
        if noeud.balise == "br":
            paragraphe.add_run().add_break()
            return
        style = noeud.style
        if noeud.balise in ("strong", "b") or style.get("font-weight") in ("600", "700", "bold"):
            format_["gras"] = True
        if noeud.balise in ("em", "i") or style.get("font-style") == "italic":
            format_["italique"] = True
        if _couleur(style.get("color")):
            format_["couleur"] = _couleur(style.get("color"))
        if _taille_pt(style.get("font-size")):
            format_["taille"] = _taille_pt(style.get("font-size"))
        # Pastille (fond arrondi) : écrite entre crochets pour rester repérable.
        pastille = noeud.balise == "span" and "border-radius" in style and "background" in style
        if pastille:
            format_["gras"] = True
            paragraphe.add_run(" [")
        for enfant in noeud.enfants:
            self.runs(paragraphe, enfant, format_)
        if pastille:
            paragraphe.add_run("] ")
        elif noeud.balise == "span" and ("margin-right" in style or "margin-left" in style):
            paragraphe.add_run(" ")  # espacement CSS entre deux éléments en ligne

    def paragraphe(self, conteneur, noeuds, style_bloc=None):
        if not noeuds or not "".join(_texte_brut(n) for n in noeuds).strip():
            return
        p = conteneur.add_paragraph()
        p.paragraph_format.space_after = self.Pt(3)
        format_ = {}
        style_bloc = style_bloc or {}
        if _couleur(style_bloc.get("color")):
            format_["couleur"] = _couleur(style_bloc.get("color"))
        if _taille_pt(style_bloc.get("font-size")):
            format_["taille"] = _taille_pt(style_bloc.get("font-size"))
        if style_bloc.get("font-weight") in ("600", "700", "bold"):
            format_["gras"] = True
        for n in noeuds:
            self.runs(p, n, format_)
        if style_bloc.get("text-align") == "right":
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # --- Blocs ---------------------------------------------------------------------------
    def blocs(self, conteneur, noeud):
        """Écrit les enfants d'un nœud bloc : les suites d'éléments en ligne forment un paragraphe."""
        en_ligne = []
        for enfant in noeud.enfants:
            if isinstance(enfant, Noeud) and (_masque(enfant) or _decoratif(enfant)):
                continue
            if isinstance(enfant, Noeud) and enfant.balise in BLOCS:
                self.paragraphe(conteneur, en_ligne, noeud.style if isinstance(noeud, Noeud) else None)
                en_ligne = []
                self.bloc(conteneur, enfant)
            else:
                en_ligne.append(enfant)
        self.paragraphe(conteneur, en_ligne, noeud.style if isinstance(noeud, Noeud) else None)

    def bloc(self, conteneur, noeud):
        style = noeud.style
        if style.get("page-break-before") == "always" and conteneur is self.document:
            self.document.add_page_break()
        if noeud.balise in ("h1", "h2", "h3", "h4", "h5", "h6"):
            niveau = min(int(noeud.balise[1]), 4)
            if conteneur is self.document:
                titre = self.document.add_heading(level=niveau)
            else:
                titre = conteneur.add_paragraph()
                format_ = {"gras": True}
            for enfant in noeud.enfants:
                self.runs(titre, enfant, None if conteneur is self.document else format_)
        elif noeud.balise == "table":
            self.tableau(conteneur, noeud)
        elif noeud.balise == "li":
            p = conteneur.add_paragraph(style="List Bullet")
            for enfant in noeud.enfants:
                self.runs(p, enfant)
        elif noeud.balise == "hr":
            return
        elif _contient_bloc(noeud):
            self.blocs(conteneur, noeud)
        else:
            self.paragraphe(conteneur, noeud.enfants, style)
        if style.get("page-break-after") == "always" and conteneur is self.document:
            self.document.add_page_break()

    def tableau(self, conteneur, noeud):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        lignes = []

        def collecter(n):
            for e in n.enfants:
                if isinstance(e, Noeud) and not _masque(e):
                    if e.balise == "tr":
                        lignes.append(e)
                    elif e.balise in ("thead", "tbody", "tfoot"):
                        collecter(e)

        collecter(noeud)
        cellules = [[c for c in l.enfants if isinstance(c, Noeud) and c.balise in ("td", "th")] for l in lignes]
        cellules = [c for c in cellules if c]
        if not cellules:
            return
        largeur = max(sum(int(c.attributs.get("colspan", 1) or 1) for c in ligne) for ligne in cellules)
        table = conteneur.add_table(rows=len(cellules), cols=largeur)
        table.style = "Table Grid"
        for i, ligne in enumerate(cellules):
            j = 0
            for cellule in ligne:
                etendue = int(cellule.attributs.get("colspan", 1) or 1)
                cible = table.cell(i, j)
                if etendue > 1:
                    cible = cible.merge(table.cell(i, min(j + etendue - 1, largeur - 1)))
                cible.paragraphs[0]._element.getparent().remove(cible.paragraphs[0]._element)
                if _contient_bloc(cellule):
                    self.blocs(cible, cellule)
                else:
                    self.paragraphe(cible, cellule.enfants, cellule.style)
                if not cible.paragraphs:
                    cible.add_paragraph()
                entete = cellule.balise == "th"
                fond = _couleur(cellule.style.get("background") or cellule.style.get("background-color"))
                if entete or fond:
                    proprietes = cible._tc.get_or_add_tcPr()
                    ombre = OxmlElement("w:shd")
                    ombre.set(qn("w:val"), "clear")
                    ombre.set(qn("w:fill"), "DCE6F1" if entete and not fond else fond)
                    proprietes.append(ombre)
                for p in cible.paragraphs:
                    p.paragraph_format.space_after = self.Pt(0)
                    for run in p.runs:
                        run.font.size = run.font.size or self.Pt(8.5)
                        if entete:
                            run.bold = True
                j += etendue
        self.document.add_paragraph().paragraph_format.space_after = self.Pt(2)


def html_vers_docx(html: str) -> bytes:
    """Document Word (.docx) équivalent au HTML d'un rapport PDF."""
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Mm, Pt, RGBColor

    lecteur = _Lecteur()
    lecteur.feed(html)
    document = Document()

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    for niveau in range(1, 5):
        titre = document.styles[f"Heading {niveau}"]
        titre.font.color.rgb = RGBColor.from_string(COULEUR_ENTETE)
        titre.font.name = "Calibri"

    section = document.sections[0]
    css = " ".join(lecteur.styles).lower()
    paysage = bool(re.search(r"@page\s*{[^}]*landscape", css))
    section.page_width, section.page_height = (Mm(297), Mm(210)) if paysage else (Mm(210), Mm(297))
    section.orientation = WD_ORIENT.LANDSCAPE if paysage else WD_ORIENT.PORTRAIT
    for cote in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, cote, Mm(15))

    corps = next((n for n in _parcourir(lecteur.racine) if isinstance(n, Noeud) and n.balise == "body"), lecteur.racine)
    _Redacteur(document).blocs(document, corps)
    sortie = io.BytesIO()
    document.save(sortie)
    return sortie.getvalue()


TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def reponse_docx(html: str, nom_fichier: str):
    """Réponse HTTP de téléchargement du rapport au format Word."""
    from django.http import HttpResponse

    response = HttpResponse(html_vers_docx(html), content_type=TYPE_DOCX)
    response["Content-Disposition"] = f"attachment; filename={nom_fichier}.docx"
    return response


def _parcourir(noeud):
    yield noeud
    for enfant in getattr(noeud, "enfants", []):
        yield from _parcourir(enfant)
