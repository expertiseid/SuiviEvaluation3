"""
Tableau de bord en PDF, Word et PowerPoint : les mêmes chiffres que l'écran (donnees_consolidees), avec
les mêmes filtres. Un contenu commun (chiffres clés, graphiques, tableaux) est mis en forme pour chaque
format : PDF (weasyprint) et Word (python-docx) avec des graphiques en image, PowerPoint (python-pptx) avec
de vrais graphiques, modifiables dans PowerPoint.
"""
import base64
import io
from html import escape

from django.utils import timezone

from apps.core.vocabulaire import v

from .excel import _filtres_en_clair, _libelles

PALETTE = ["#0C8A5F", "#1C7ED6", "#E8590C", "#7048E8", "#C2255C", "#F08C00", "#0C8599", "#495057"]
# Graphique par projet : au-delà, il devient illisible (le tableau donne toujours tous les projets).
PROJETS_MAX_GRAPHIQUE = 25


def _montant(valeur) -> str:
    try:
        return f"{float(valeur):,.0f}".replace(",", " ") + " FCFA"
    except (TypeError, ValueError):
        return "—"


def _entier(valeur) -> str:
    return f"{int(valeur or 0):,}".replace(",", " ")


def _pourcent(valeur) -> str:
    return "—" if valeur is None else f"{float(valeur):.1f} %"


def contenu(d: dict, filtres, organisation: str = "") -> dict:
    """Titre, chiffres clés, graphiques et tableaux du rapport, communs aux trois formats."""
    from apps.projects.models import Activite, Projet

    statuts_projet = _libelles(Projet._meta.get_field("statut").choices)
    statuts_activite = _libelles(Activite._meta.get_field("statut").choices)
    sexes = {"F": v("Femmes"), "M": v("Hommes")}
    budget = d.get("budget_detail") or {}
    cibles = d.get("cibles") or {}

    chiffres = [
        (v("Projets"), _entier(d.get("nombre_projets"))),
        (v("Budget total"), _montant(budget.get("total", d.get("budget_total")))),
        (v("dont fonds propres"), _montant(budget.get("fonds_propres"))),
        (v("dont financements des bailleurs"), _montant(budget.get("financements_bailleurs"))),
        (v("Bénéficiaires inscrits"), _entier(d.get("nombre_beneficiaires"))),
        (v("Cible totale"), _entier(cibles.get("totale"))),
    ]

    graphiques = []

    def camembert(titre, valeurs, couleurs=None):
        valeurs = [(libelle, n) for libelle, n in valeurs if n]
        if valeurs:
            graphiques.append({"titre": titre, "type": "camembert", "categories": [l for l, _ in valeurs],
                               "series": [{"nom": titre, "valeurs": [n for _, n in valeurs]}], "couleurs": couleurs})

    indicateurs = d.get("indicateurs_par_statut", [])
    camembert(v("Indicateurs par niveau d'alerte"), [(r["libelle"], r["count"]) for r in indicateurs],
              [r["couleur"] for r in indicateurs if r["count"]])
    camembert(v("Projets par statut"), [(statuts_projet.get(k, k), n) for k, n in d.get("projets_par_statut", {}).items()])
    camembert(v("Activités par statut"), [(statuts_activite.get(k, k), n) for k, n in d.get("activites_par_statut", {}).items()])
    camembert(v("Bénéficiaires par sexe"), [(sexes.get(k, k or v("Non renseigné")), n)
                                            for k, n in d.get("beneficiaires_par_sexe", {}).items()])
    execution = sorted(d.get("execution_par_projet", []), key=lambda r: r["code"])[:PROJETS_MAX_GRAPHIQUE]
    if execution:
        graphiques.append({
            "titre": v("Exécution par projet (%)"), "type": "barres", "categories": [r["code"] for r in execution],
            "series": [{"nom": v("Exécution physique (%)"), "valeurs": [r["physique"] or 0 for r in execution]},
                       {"nom": v("Exécution financière (%)"), "valeurs": [r["financier"] or 0 for r in execution]}],
        })
    bailleurs = sorted(d.get("projets_par_bailleur", []), key=lambda r: -float(r.get("montant") or 0))[:10]
    if bailleurs:
        graphiques.append({
            "titre": v("Montants par bailleur (FCFA)"), "type": "barres", "categories": [r["libelle"] for r in bailleurs],
            "series": [{"nom": v("Montant"), "valeurs": [float(r.get("montant") or 0) for r in bailleurs]}],
        })

    execution_de = {r["code"]: r for r in d.get("execution_par_projet", [])}
    beneficiaires_de = {r["code"]: r for r in d.get("beneficiaires_par_projet_sexe", [])}
    tableaux = [{
        "titre": v("Projets"),
        "entetes": [v("Code"), v("Projet"), v("Statut"), v("Budget"), v("Physique"), v("Financier"), v("Bénéf.")],
        "lignes": [[
            p["code"], p["nom"], statuts_projet.get(p["statut"], p["statut"]), _montant(p.get("budget_total")),
            _pourcent(execution_de.get(p["code"], {}).get("physique")),
            _pourcent(execution_de.get(p["code"], {}).get("financier")),
            _entier(sum(n for k, n in beneficiaires_de.get(p["code"], {}).items() if k != "code")),
        ] for p in sorted(d.get("projets", []), key=lambda p: p["code"])],
        "larges": [1],
    }]
    for titre, cle in ((v("Par bailleur"), "projets_par_bailleur"), (v("Par pays"), "projets_par_pays"),
                       (v("Par structure de mise en œuvre"), "projets_par_mise_en_oeuvre")):
        elements = d.get(cle, [])
        if elements:
            tableaux.append({
                "titre": titre, "entetes": [v("Libellé"), v("Projets"), v("Montant")],
                "lignes": [[r["libelle"], _entier(r["nombre"]), _montant(r.get("montant"))] for r in elements],
                "larges": [0],
            })

    return {
        "titre": v("Tableau de bord") + (f" — {organisation}" if organisation else ""),
        "sous_titre": v("Exporté le {0}").format(timezone.localtime().strftime("%d/%m/%Y %H:%M")),
        "filtres": v("Filtres : {0}").format(_filtres_en_clair(filtres, statuts_projet)),
        "chiffres": chiffres, "graphiques": graphiques, "tableaux": tableaux,
    }


# --- Graphiques en image (PDF, Word) ----------------------------------------------------------------


def _image(graphique) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    categories, series = graphique["categories"], graphique["series"]
    if graphique["type"] == "camembert":
        figure, axe = plt.subplots(figsize=(5.2, 3.4), dpi=150)
        couleurs = graphique.get("couleurs") or PALETTE[:len(categories)]
        axe.pie(series[0]["valeurs"], labels=None, colors=couleurs, autopct="%1.0f %%", startangle=90,
                pctdistance=0.75, wedgeprops={"width": 0.45, "edgecolor": "white"}, textprops={"fontsize": 8})
        axe.legend([f"{c} ({n})" for c, n in zip(categories, series[0]["valeurs"])], loc="center left",
                   bbox_to_anchor=(1, 0.5), fontsize=8, frameon=False)
        axe.axis("equal")
    else:
        hauteur = max(2.6, 0.28 * len(categories) + 1)
        figure, axe = plt.subplots(figsize=(7.2, hauteur), dpi=150)
        epaisseur = 0.8 / len(series)
        positions = range(len(categories))
        for rang, serie in enumerate(series):
            axe.barh([p + rang * epaisseur for p in positions], serie["valeurs"], height=epaisseur,
                     color=PALETTE[rang % len(PALETTE)], label=serie["nom"])
        axe.set_yticks([p + epaisseur * (len(series) - 1) / 2 for p in positions], categories, fontsize=7)
        axe.invert_yaxis()
        axe.tick_params(axis="x", labelsize=7)
        axe.spines[["top", "right"]].set_visible(False)
        axe.grid(axis="x", color="#E9ECEF")
        axe.set_axisbelow(True)
        if len(series) > 1:
            axe.legend(fontsize=7, frameon=False, loc="lower right")
    figure.tight_layout()
    tampon = io.BytesIO()
    figure.savefig(tampon, format="png")
    plt.close(figure)
    return tampon.getvalue()


# --- PDF ---------------------------------------------------------------------------------------------


def pdf(c: dict) -> bytes:
    from weasyprint import HTML

    morceaux = [
        "<style>@page{size:A4 landscape;margin:14mm}body{font-family:sans-serif;font-size:9pt;color:#212529}"
        "h1{font-size:16pt;color:#0B5345;margin:0}h2{font-size:11.5pt;color:#1F4E78;margin:14px 0 6px}"
        ".gris{color:#6C757D;margin:2px 0}.chiffres{margin:10px 0}"
        ".chiffre{display:inline-block;vertical-align:top;border:1px solid #DEE2E6;border-radius:6px;padding:6px 10px;"
        "margin:0 6px 6px 0;width:52mm}.chiffre b{display:block;font-size:12pt}"
        "table.grille,table.grille td{border:none;padding:0 6px 6px 0;vertical-align:top}"
        ".graphique img{height:62mm;max-width:100%}.large img{width:100%}"
        "table{border-collapse:collapse;width:100%;margin-bottom:8px}th{background:#1F4E78;color:#fff;text-align:left}"
        "th,td{border:1px solid #CED4DA;padding:3px 5px;font-size:8pt}tr{page-break-inside:avoid}</style>",
        f"<h1>{escape(c['titre'])}</h1><p class='gris'>{escape(c['sous_titre'])}</p><p class='gris'>{escape(c['filtres'])}</p>",
        "<div class='chiffres'>",
        *[f"<div class='chiffre'>{escape(libelle)}<b>{escape(valeur)}</b></div>" for libelle, valeur in c["chiffres"]],
        "</div>",
    ]

    def bloc(g, classe="graphique"):
        image = base64.b64encode(_image(g)).decode()
        return f"<div class='{classe}'><h2>{escape(g['titre'])}</h2><img src='data:image/png;base64,{image}'></div>"

    # Camemberts deux par ligne (une ligne de tableau ne se coupe pas entre deux pages), barres en pleine largeur.
    camemberts = [g for g in c["graphiques"] if g["type"] == "camembert"]
    morceaux.append("<table class='grille'>" + "".join(
        "<tr>" + "".join(f"<td style='width:50%'>{bloc(g)}</td>" for g in camemberts[i:i + 2]) + "</tr>"
        for i in range(0, len(camemberts), 2)) + "</table>")
    morceaux += [bloc(g, "large") for g in c["graphiques"] if g["type"] != "camembert"]
    for t in c["tableaux"]:
        morceaux.append(f"<h2>{escape(t['titre'])}</h2><table><thead><tr>"
                        + "".join(f"<th>{escape(e)}</th>" for e in t["entetes"]) + "</tr></thead><tbody>"
                        + "".join("<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in ligne) + "</tr>" for ligne in t["lignes"])
                        + "</tbody></table>")
    return HTML(string="".join(morceaux)).write_pdf()


# --- Word --------------------------------------------------------------------------------------------


def word(c: dict) -> bytes:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for marge in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, marge, Cm(1.5))
    document.styles["Normal"].font.size = Pt(9)

    def fond(cellule, couleur):
        proprietes = cellule._tc.get_or_add_tcPr()
        ombre = OxmlElement("w:shd")
        ombre.set(qn("w:val"), "clear")
        ombre.set(qn("w:fill"), couleur)
        proprietes.append(ombre)

    document.add_heading(c["titre"], level=0)
    for ligne in (c["sous_titre"], c["filtres"]):
        document.add_paragraph(ligne).runs[0].font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

    document.add_heading(v("Chiffres clés"), level=1)
    tableau = document.add_table(rows=0, cols=2)
    tableau.style = "Table Grid"
    for libelle, valeur in c["chiffres"]:
        cellules = tableau.add_row().cells
        cellules[0].text, cellules[1].text = libelle, valeur
        cellules[1].paragraphs[0].runs[0].bold = True

    for g in c["graphiques"]:
        document.add_heading(g["titre"], level=1)
        document.add_picture(io.BytesIO(_image(g)), width=Cm(16 if g["type"] == "camembert" else 22))

    for t in c["tableaux"]:
        document.add_heading(t["titre"], level=1)
        tableau = document.add_table(rows=1, cols=len(t["entetes"]))
        tableau.style = "Table Grid"
        for cellule, entete in zip(tableau.rows[0].cells, t["entetes"]):
            cellule.text = entete
            cellule.paragraphs[0].runs[0].bold = True
            cellule.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            fond(cellule, "1F4E78")
        for ligne in t["lignes"]:
            for cellule, valeur in zip(tableau.add_row().cells, ligne):
                cellule.text = str(valeur)
                cellule.paragraphs[0].runs[0].font.size = Pt(8)

    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


# --- PowerPoint --------------------------------------------------------------------------------------


def powerpoint(c: dict) -> bytes:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.util import Inches, Pt

    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Inches(13.333), Inches(7.5)
    vide = presentation.slide_layouts[6]
    vert, bleu, gris = RGBColor(0x0B, 0x53, 0x45), RGBColor(0x1F, 0x4E, 0x78), RGBColor(0x6C, 0x75, 0x7D)

    def texte(diapo, contenu, x, y, l, h, taille=14, gras=False, couleur=None):
        cadre = diapo.shapes.add_textbox(Inches(x), Inches(y), Inches(l), Inches(h)).text_frame
        cadre.word_wrap = True
        paragraphe = cadre.paragraphs[0]
        paragraphe.text = contenu
        paragraphe.runs[0].font.size, paragraphe.runs[0].font.bold = Pt(taille), gras
        if couleur is not None:
            paragraphe.runs[0].font.color.rgb = couleur
        return cadre

    def titre(diapo, contenu):
        texte(diapo, contenu, 0.5, 0.3, 12.3, 0.8, 26, True, bleu)

    # Couverture et chiffres clés.
    diapo = presentation.slides.add_slide(vide)
    texte(diapo, c["titre"], 0.8, 2.3, 11.7, 1.2, 36, True, vert)
    texte(diapo, c["sous_titre"], 0.8, 3.6, 11.7, 0.5, 16, couleur=gris)
    texte(diapo, c["filtres"], 0.8, 4.1, 11.7, 0.8, 14, couleur=gris)

    diapo = presentation.slides.add_slide(vide)
    titre(diapo, v("Chiffres clés"))
    for rang, (libelle, valeur) in enumerate(c["chiffres"]):
        x, y = 0.6 + (rang % 3) * 4.1, 1.6 + (rang // 3) * 2.6
        forme = diapo.shapes.add_shape(1, Inches(x), Inches(y), Inches(3.8), Inches(2.2))
        forme.fill.solid()
        forme.fill.fore_color.rgb = RGBColor(0xF1, 0xF3, 0xF5)
        forme.line.color.rgb = RGBColor(0xDE, 0xE2, 0xE6)
        cadre = forme.text_frame
        cadre.word_wrap = True
        cadre.paragraphs[0].text = libelle
        cadre.paragraphs[0].runs[0].font.size, cadre.paragraphs[0].runs[0].font.color.rgb = Pt(14), gris
        suite = cadre.add_paragraph()
        suite.text = valeur
        suite.runs[0].font.size, suite.runs[0].font.bold, suite.runs[0].font.color.rgb = Pt(24), True, vert

    # Un graphique par diapositive (natif : modifiable dans PowerPoint).
    for g in c["graphiques"]:
        diapo = presentation.slides.add_slide(vide)
        titre(diapo, g["titre"])
        donnees = CategoryChartData()
        donnees.categories = g["categories"]
        for serie in g["series"]:
            donnees.add_series(serie["nom"], serie["valeurs"])
        type_ = XL_CHART_TYPE.DOUGHNUT if g["type"] == "camembert" else XL_CHART_TYPE.BAR_CLUSTERED
        graphique = diapo.shapes.add_chart(type_, Inches(0.6), Inches(1.3), Inches(12.1), Inches(5.9), donnees).chart
        graphique.has_legend = g["type"] == "camembert" or len(g["series"]) > 1
        if graphique.has_legend:
            graphique.legend.position, graphique.legend.include_in_layout = XL_LEGEND_POSITION.RIGHT, False
            graphique.legend.font.size = Pt(12)
        plot = graphique.plots[0]
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(10)
        if g["type"] == "camembert":
            plot.data_labels.show_percentage, plot.data_labels.show_value = True, False
            plot.data_labels.number_format, plot.data_labels.number_format_is_linked = "0%", False
            couleurs = g.get("couleurs") or PALETTE
            for rang, point in enumerate(plot.series[0].points):
                point.format.fill.solid()
                point.format.fill.fore_color.rgb = RGBColor.from_string(couleurs[rang % len(couleurs)].lstrip("#").upper())
        else:
            graphique.category_axis.reverse_order = True
            graphique.category_axis.tick_labels.font.size = Pt(9 if len(g["categories"]) > 12 else 11)
            graphique.value_axis.tick_labels.font.size = Pt(10)
            for rang, serie in enumerate(plot.series):
                serie.format.fill.solid()
                serie.format.fill.fore_color.rgb = RGBColor.from_string(PALETTE[rang % len(PALETTE)].lstrip("#").upper())

    # Tableaux : 14 lignes par diapositive.
    for t in c["tableaux"]:
        for debut in range(0, max(1, len(t["lignes"])), 14):
            lignes = t["lignes"][debut:debut + 14]
            diapo = presentation.slides.add_slide(vide)
            titre(diapo, t["titre"] + (f" ({debut // 14 + 1})" if len(t["lignes"]) > 14 else ""))
            forme = diapo.shapes.add_table(len(lignes) + 1, len(t["entetes"]), Inches(0.5), Inches(1.3), Inches(12.3),
                                           Inches(0.4 * (len(lignes) + 1)))
            tableau = forme.table
            for colonne in range(len(t["entetes"])):
                tableau.columns[colonne].width = Inches(4.5 if colonne in t.get("larges", []) else
                                                       (12.3 - 4.5 * len(t.get("larges", []))) / max(1, len(t["entetes"]) - len(t.get("larges", []))))
            for rang, ligne in enumerate([t["entetes"], *lignes]):
                for colonne, valeur in enumerate(ligne):
                    cellule = tableau.cell(rang, colonne)
                    cellule.text = str(valeur)
                    cellule.text_frame.paragraphs[0].runs[0].font.size = Pt(11 if rang == 0 else 10)

    tampon = io.BytesIO()
    presentation.save(tampon)
    return tampon.getvalue()
