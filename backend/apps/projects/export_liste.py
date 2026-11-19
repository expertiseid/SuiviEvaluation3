"""Export de la liste des projets (page Projets) : Excel, Word ou PDF, avec les colonnes de l'écran."""
import datetime
import io

from django.utils.html import escape

from apps.core.vocabulaire import v

TH = 'style="text-align:left;padding:5px 7px;background:#DCE6F1;font-size:11px;color:#1F4E78;"'
TH_D = 'style="text-align:right;padding:5px 7px;background:#DCE6F1;font-size:11px;color:#1F4E78;"'
TD = 'style="padding:4px 7px;border-bottom:1px solid #e5e5e5;vertical-align:top;"'
TD_D = 'style="padding:4px 7px;border-bottom:1px solid #e5e5e5;text-align:right;white-space:nowrap;vertical-align:top;"'
TD_CODE = 'style="padding:4px 7px;border-bottom:1px solid #e5e5e5;white-space:nowrap;vertical-align:top;"'
TOTAL = 'style="padding:5px 7px;font-weight:700;border-top:2px solid #1F4E78;"'
TOTAL_D = 'style="padding:5px 7px;font-weight:700;border-top:2px solid #1F4E78;text-align:right;white-space:nowrap;"'


def _date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _montant(valeur) -> str:
    return f"{round(float(valeur or 0)):,}".replace(",", " ")


def lignes(projets) -> list[dict]:
    return [{
        "nom": p.nom, "code": p.code,
        "bailleur": str(p.partenaire_bailleur) if p.partenaire_bailleur else "",
        "statut": p.get_statut_display(), "debut": p.date_debut, "fin": p.date_fin,
        "budget": p.budget_total or 0, "chef": p.chef_de_projet_nom or "",
    } for p in projets]


ENTETES = ("Projet", "Code", "Bailleur", "Statut", "Début", "Fin", "Budget (FCFA)", "Chef de projet")


def excel(donnees) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from apps.core.excel_utils import figer_entete, quadriller
    from apps.core.langues import traduire_classeur

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Projets"
    feuille.append(list(ENTETES))
    for cellule in feuille[1]:
        cellule.font = Font(bold=True, color="1F4E78")
        cellule.fill = PatternFill("solid", fgColor="DCE6F1")
        cellule.alignment = Alignment(vertical="center", wrap_text=True)
    for d in donnees:
        feuille.append([d["nom"], d["code"], d["bailleur"], d["statut"], d["debut"], d["fin"], float(d["budget"]), d["chef"]])
        feuille.cell(feuille.max_row, 5).number_format = feuille.cell(feuille.max_row, 6).number_format = "DD/MM/YYYY"
        feuille.cell(feuille.max_row, 7).number_format = "#,##0"
    feuille.append(["Total", f"{len(donnees)} projet(s)", "", "", "", "", sum(float(d["budget"]) for d in donnees), ""])
    for cellule in feuille[feuille.max_row]:
        cellule.font = Font(bold=True)
    feuille.cell(feuille.max_row, 7).number_format = "#,##0"
    for colonne, largeur in zip("ABCDEFGH", (60, 20, 30, 16, 12, 12, 18, 28)):
        feuille.column_dimensions[colonne].width = largeur
    quadriller(feuille, max_col=len(ENTETES))
    figer_entete(feuille)
    traduire_classeur(classeur)
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def html(donnees) -> str:
    titre = v("Liste des projets")
    entetes = "".join(f"<th {TH_D if e.startswith('Budget') else TH}>{escape(v(e))}</th>" for e in ENTETES)
    corps = "".join(
        f"<tr><td {TD}>{escape(d['nom'])}</td><td {TD_CODE}>{escape(d['code'])}</td><td {TD}>{escape(d['bailleur'])}</td>"
        f"<td {TD}>{escape(d['statut'])}</td><td {TD}>{_date(d['debut'])}</td><td {TD}>{_date(d['fin'])}</td>"
        f"<td {TD_D}>{_montant(d['budget'])}</td><td {TD}>{escape(d['chef'])}</td></tr>"
        for d in donnees
    )
    total = (f"<tr><td {TOTAL}>{escape(v('Total'))}</td><td {TOTAL} colspan=\"5\">{escape(v(f'{len(donnees)} projet(s)'))}</td>"
             f"<td {TOTAL_D}>{_montant(sum(float(d['budget']) for d in donnees))}</td><td {TOTAL}></td></tr>")
    return f"""
    <html>
    <head>
    <style>
      @page {{ size: A4 landscape; margin: 14mm 12mm; @bottom-right {{ content: counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 11px; }}
      h2 {{ margin-bottom: 2px; }}
      tr {{ page-break-inside: avoid; }}
    </style>
    </head>
    <body>
      <h2>{escape(titre)}</h2>
      <div style="color:#666;font-size:11px;margin-bottom:10px;">{escape(v('Généré le'))} {datetime.date.today().strftime('%d/%m/%Y')}</div>
      <table style="width:100%;border-collapse:collapse;font-size:11px;"><thead><tr>{entetes}</tr></thead><tbody>{corps}{total}</tbody></table>
    </body>
    </html>
    """
