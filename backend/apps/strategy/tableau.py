"""
Tableau d'un document stratégique (onglet « Arborescence & saisie », mode Tableau) : données,
lignes calculées comme à l'écran (frontend CadreTableau.tsx / calculsAxes.ts) et export Excel /
PDF — pour un document de n'importe quel maillon (cadre stratégique, programme, pilier…).

Une ligne par élément (bandeau de couleur par niveau quand il regroupe quelque chose), suivie
des éléments en dessous puis des activités des projets qui y sont rattachées. Un élément cumule
les activités de tout ce qui est en dessous : dates extrêmes, budget alloué sans double compte,
taux = moyenne des éléments les plus bas.
"""
import datetime
import io

from django.utils.html import escape

from apps.core.vocabulaire import v
from apps.projects.budgets import activites_comptees
from apps.projects.models import Activite
from apps.projects.taux import ArbreTaux

# Bandeaux par niveau, du plus haut au plus bas (teintes Mantine blue-3 → blue-0, comme à l'écran).
FONDS_NIVEAUX = ["74C0FC", "A5D8FF", "D0EBFF", "E7F5FF"]
ENTETE = "D3F9D8"


class _ArbresTaux:
    """Taux des éléments de plusieurs projets : un ArbreTaux par projet, chargé à la demande."""

    def __init__(self):
        self.arbres = {}

    def taux(self, activite):
        if activite.projet_id not in self.arbres:
            self.arbres[activite.projet_id] = ArbreTaux(activite.projet)
        return self.arbres[activite.projet_id].resultat(activite.id).taux


def donnees_recap_axes(cadre, projets_visibles, user=None) -> dict:
    """
    Éléments du document et activités qui y arrivent (chaîne des documents comprise, voir
    chaine.activites_rattachees), avec leurs budgets comptés sans double compte et leurs taux.
    Données de l'onglet « Axes & budgets » et du mode Tableau.

    Éléments et activités masqués à `user` (apps.core.masquage) : les éléments ne sont pas renvoyés ; les
    activités restent, sans libellé ni code et marquées « masquee », sur le premier élément visible au-dessus,
    pour que les totaux ne changent pas (l'écran ne les affiche pas en ligne).
    """
    from apps.core.masquage import activites_masquees, elements_masques

    from .chaine import activites_rattachees
    from .models import ElementStrategique

    tous_elements = list(ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre).select_related("type_niveau"))
    masques, masquees = elements_masques(user), activites_masquees(user)
    parent_element = {e.id: e.element_parent_id for e in tous_elements}

    def visible(element_id):
        while element_id is not None and element_id in masques:
            element_id = parent_element.get(element_id)
        return element_id

    elements = [e for e in tous_elements if e.id not in masques]
    rattachees = activites_rattachees(cadre, projets_visibles)
    element_de = {a.id: element for a, element in rattachees}
    cachee = {a.id for a, element in rattachees if a.id in masquees or element in masques}
    arbres_taux = _ArbresTaux()
    # Budgets sans double compte : calculés sur toutes les activités des projets concernés
    # (un niveau parent peut être rattaché à un autre élément du cadre que ses activités).
    activites = [a for a, _ in rattachees]
    toutes = list(
        Activite.objects.filter(projet__id__in={a.projet_id for a in activites}).only(
            "id", "activite_parent_id", "budget_alloue", "budget_realise"
        )
    )
    alloue_compte = activites_comptees(toutes, "budget_alloue")
    realise_compte = activites_comptees(toutes, "budget_realise")
    parent_de = {a.id: a.activite_parent_id for a in toutes}

    def ancetres(activite_id):
        resultat, courant = [], parent_de.get(activite_id)
        while courant is not None:
            resultat.append(courant)
            courant = parent_de.get(courant)
        return resultat

    return {
        "elements": [
            {
                "id": e.id,
                "code": e.code,
                "nom": e.nom,
                "type_niveau": e.type_niveau_id,
                "ordre_niveau": e.type_niveau.ordre,
                "element_parent": e.element_parent_id,
            }
            for e in elements
        ],
        "activites": [
            {
                "id": a.id,
                "code": "" if a.id in cachee else a.code_activite,
                "libelle": "" if a.id in cachee else a.libelle,
                "masquee": a.id in cachee,
                "projet_id": a.projet.id,
                "projet_code": a.projet.code,
                "axe": visible(element_de[a.id]),
                "budget_alloue": a.budget_alloue,
                "budget_realise": a.budget_realise,
                # Part comptée dans les totaux (0 si le détail est saisi en dessous).
                "budget_alloue_compte": a.budget_alloue if a.id in alloue_compte else 0,
                "budget_realise_compte": a.budget_realise if a.id in realise_compte else 0,
                # Éléments au-dessus : dans un groupe, un élément dont un élément en dessous
                # figure aussi n'entre pas dans la moyenne des taux (déjà compté via lui).
                "ancetres": ancetres(a.id),
                "taux_physique": arbres_taux.taux(a),
                "taux_financier": a.taux_execution_financiere,
                "date_debut": a.date_debut,
                "date_fin": a.date_fin,
            }
            for a in activites
        ],
    }


# ------------------------------------------------------------------------- lignes du tableau


def _moyenne(valeurs):
    definies = [float(x) for x in valeurs if x is not None]
    return round(sum(definies) / len(definies), 1) if definies else None


def _totaux(activites) -> tuple:
    """(budget alloué sans double compte, taux moyen des éléments les plus bas) — calculsAxes.totaux."""
    au_dessus = {i for a in activites for i in a["ancetres"]}
    derniers = [a for a in activites if a["id"] not in au_dessus]
    alloue = sum(float(a["budget_alloue_compte"] or 0) for a in activites)
    return alloue, _moyenne(a["taux_physique"] for a in derniers)


def _bornes(activites) -> tuple:
    debuts = sorted(a["date_debut"] for a in activites if a["date_debut"])
    fins = sorted(a["date_fin"] for a in activites if a["date_fin"])
    return (debuts[0] if debuts else None, fins[-1] if fins else None)


def prevu_au_trimestre(debut, fin, annee, trimestre) -> bool:
    """L'élément est-il prévu pendant ce trimestre (ses dates le recoupent) ?"""
    if not debut and not fin:
        return False
    debut_t = datetime.date(annee, trimestre * 3 - 2, 1)
    fin_t = datetime.date(annee, trimestre * 3, 31 if trimestre in (1, 4) else 30)
    return (debut or fin) <= fin_t and (fin or debut) >= debut_t


def lignes_tableau(cadre, projets_visibles, user=None) -> list:
    """
    Lignes du tableau, dans l'ordre de l'écran : {"type", "code", "libelle", "rang", "groupe",
    "debut", "fin", "budget", "taux"}. `rang` : rang du niveau (0 = le plus haut) ; `groupe` :
    élément qui regroupe des éléments ou des activités (bandeau de couleur, en gras).
    """
    from .models import TypeNiveau

    donnees = donnees_recap_axes(cadre, projets_visibles, user)
    niveaux = list(TypeNiveau.objects.filter(cadre_strategique=cadre).order_by("ordre"))
    rang = {n.id: i for i, n in enumerate(niveaux)}
    nom_niveau = {n.id: n.nom_niveau for n in niveaux}
    enfants = {}
    for e in donnees["elements"]:  # ordre de l'écran : niveau, puis ordre de création
        enfants.setdefault(e["element_parent"], []).append(e)
    directes = {}
    for a in donnees["activites"]:
        if a["axe"] is not None:
            directes.setdefault(a["axe"], []).append(a)

    def aplatir(e):
        sous = [aplatir(x) for x in enfants.get(e["id"], [])]
        propres = directes.get(e["id"], [])
        activites = propres + [a for _, acts in sous for a in acts]
        debut, fin = _bornes(activites)
        budget, taux = _totaux(activites) if activites else (None, None)
        ligne = {
            "type": "element", "code": e["code"], "libelle": f"{nom_niveau.get(e['type_niveau'], '')} : {e['nom']}",
            "rang": rang.get(e["type_niveau"], 0), "groupe": bool(sous or propres),
            "debut": debut, "fin": fin, "budget": budget, "taux": taux,
        }
        lignes = [ligne] + [l for ls, _ in sous for l in ls]
        lignes += [
            {"type": "activite", "code": a["code"], "libelle": f"{a['libelle']} ({a['projet_code']})", "rang": None,
             "groupe": False, "debut": a["date_debut"], "fin": a["date_fin"],
             "budget": float(a["budget_alloue"]) if a["budget_alloue"] is not None else None, "taux": a["taux_physique"]}
            for a in propres if not a["masquee"]
        ]
        return lignes, activites

    return [l for racine in enfants.get(None, []) for l in aplatir(racine)[0]]


def annees_possibles(lignes) -> list:
    """Années couvertes par les dates des activités (au moins l'année en cours)."""
    ans = [d.year for l in lignes if l["type"] == "activite" for d in (l["debut"], l["fin"]) if d]
    return list(range(min(ans), max(ans) + 1)) if ans else [datetime.date.today().year]


def _date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _montant(m) -> str:
    return f"{m:,.0f}".replace(",", " ") if m is not None else ""


def _taux(t) -> str:
    return "—" if t is None else f"{t:g} %".replace(".", ",")


# --------------------------------------------------------------------------------- exports


def exporter_tableau_excel(cadre, lignes, par_trimestre, annee) -> bytes:
    """Classeur Excel du tableau, mêmes colonnes et mêmes bandeaux de couleur qu'à l'écran."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    from apps.core.excel_utils import figer_entete
    from apps.core.vocabulaire import adapter_classeur

    wb = Workbook()
    f = wb.active
    f.title = "Tableau"
    titre_doc = f"{cadre.type_document.nom if cadre.type_document_id else v('Cadre stratégique')} : {cadre.nom}"
    f.append([titre_doc])
    f["A1"].font = Font(bold=True, size=13)
    f.append([v("Exporté le") + " " + datetime.date.today().strftime("%d/%m/%Y")])
    f["A2"].font = Font(italic=True, color="666666")
    f.append([])

    programmation = [f"T{t}" for t in range(1, 5)] if par_trimestre else [v("Date début"), v("Date fin")]
    nb = 2 + len(programmation) + 2
    entete1 = [v("Code"), v("Logique d'intervention")]
    entete1 += [f"{v('Programmation')} {annee}", "", "", ""] if par_trimestre else programmation
    entete1 += [v("Budget alloué (FCFA)"), v("Taux")]
    f.append(entete1)
    l1 = f.max_row
    if par_trimestre:
        f.append(["", ""] + programmation + ["", ""])
        l2 = f.max_row
        for col in (1, 2, nb - 1, nb):
            f.merge_cells(start_row=l1, start_column=col, end_row=l2, end_column=col)
        f.merge_cells(start_row=l1, start_column=3, end_row=l1, end_column=6)
    else:
        l2 = l1
    bord = Side(style="thin", color="A0AEC0")
    for r in range(l1, l2 + 1):
        for c in range(1, nb + 1):
            cellule = f.cell(row=r, column=c)
            cellule.font = Font(bold=True)
            cellule.fill = PatternFill("solid", fgColor=ENTETE)
            cellule.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cellule.border = Border(top=bord, bottom=bord, left=bord, right=bord)

    for l in lignes:
        titre = l["type"] == "element" and l["groupe"]
        if par_trimestre:
            prog = ["X" if prevu_au_trimestre(l["debut"], l["fin"], annee, t) else "" for t in range(1, 5)]
        else:
            prog = [_date(l["debut"]), _date(l["fin"])]
        libelle = l["libelle"] if l["type"] == "element" else f"    {l['libelle']}"
        f.append([l["code"] or "", libelle, *prog, l["budget"], (l["taux"] / 100) if l["taux"] is not None else None])
        r = f.max_row
        for c in range(1, nb + 1):
            cellule = f.cell(row=r, column=c)
            cellule.border = Border(top=bord, bottom=bord, left=bord, right=bord)
            cellule.alignment = Alignment(vertical="center", wrap_text=c == 2, horizontal="center" if c != 2 and c < nb - 1 else None)
            if titre:
                cellule.font = Font(bold=True)
                cellule.fill = PatternFill("solid", fgColor=FONDS_NIVEAUX[min(l["rang"], len(FONDS_NIVEAUX) - 1)])
        f.cell(row=r, column=nb - 1).number_format = "#,##0"
        f.cell(row=r, column=nb).number_format = "0.0%"
    for col, largeur in zip("ABCDEFGH", [12, 70, *([7] * 4 if par_trimestre else [13, 13]), 18, 10]):
        f.column_dimensions[col].width = largeur
    figer_entete(f, ligne_entete=l2)
    adapter_classeur(wb)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def html_tableau(cadre, lignes, par_trimestre, annee) -> str:
    """Page HTML (paysage) du tableau, pour l'export PDF."""
    bord = "border:1px solid #a0aec0;"
    th = f'style="{bord}background:#{ENTETE};padding:5px 6px;font-size:10px;text-align:center;"'
    if par_trimestre:
        entete = (
            f'<tr><th rowspan="2" {th}>{v("Code")}</th><th rowspan="2" {th}>{escape(v("Logique d'intervention"))}</th>'
            f'<th colspan="4" {th}>{v("Programmation")} {annee}</th>'
            f'<th rowspan="2" {th}>{v("Budget alloué (FCFA)")}</th><th rowspan="2" {th}>{v("Taux")}</th></tr>'
            "<tr>" + "".join(f'<th {th}>T{t}</th>' for t in range(1, 5)) + "</tr>"
        )
    else:
        entete = (
            f'<tr><th {th}>{v("Code")}</th><th {th}>{escape(v("Logique d'intervention"))}</th>'
            f'<th {th}>{v("Date début")}</th><th {th}>{v("Date fin")}</th>'
            f'<th {th}>{v("Budget alloué (FCFA)")}</th><th {th}>{v("Taux")}</th></tr>'
        )
    corps = []
    for l in lignes:
        titre = l["type"] == "element" and l["groupe"]
        fond = f"background:#{FONDS_NIVEAUX[min(l['rang'], len(FONDS_NIVEAUX) - 1)]};" if titre else ""
        poids = "font-weight:700;" if titre else ""
        td = f'style="{bord}{fond}{poids}padding:4px 6px;font-size:10px;'
        if par_trimestre:
            prog = "".join(
                f'<td {td}text-align:center;">{"X" if prevu_au_trimestre(l["debut"], l["fin"], annee, t) else ""}</td>'
                for t in range(1, 5)
            )
        else:
            prog = f'<td {td}white-space:nowrap;">{_date(l["debut"])}</td><td {td}white-space:nowrap;">{_date(l["fin"])}</td>'
        retrait = "padding-left:18px;" if l["type"] == "activite" else ""
        corps.append(
            f'<tr><td {td}text-align:center;">{escape(l["code"] or "")}</td>'
            f'<td {td}{retrait}">{escape(l["libelle"])}</td>{prog}'
            f'<td {td}text-align:right;white-space:nowrap;">{_montant(l["budget"])}</td>'
            f'<td {td}text-align:center;white-space:nowrap;color:#0b7285;">{_taux(l["taux"])}</td></tr>'
        )
    maillon = escape(cadre.type_document.nom if cadre.type_document_id else v("Cadre stratégique"))
    vide = f'<tr><td colspan="8" style="padding:8px;">{v("Aucun élément.")}</td></tr>'
    return f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A4 landscape; margin: 12mm 10mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; }}
      table {{ border-collapse: collapse; width: 100%; }}
      thead {{ display: table-header-group; }}
      tr {{ page-break-inside: avoid; }}
    </style></head><body>
      <div style="font-size:10px;color:#7048e8;font-weight:700;text-transform:uppercase;">{maillon}</div>
      <h2 style="margin:2px 0 4px 0;font-size:17px;">{escape(cadre.nom)}</h2>
      <div style="font-size:10px;color:#666;margin-bottom:10px;">{v("Exporté le")} {datetime.date.today().strftime("%d/%m/%Y")}</div>
      <table><thead>{entete}</thead><tbody>{"".join(corps) or vide}</tbody></table>
    </body></html>"""


def exporter_tableau_pdf(cadre, lignes, par_trimestre, annee) -> bytes:
    from weasyprint import HTML

    from apps.core.langues import traduire_html

    return HTML(string=traduire_html(html_tableau(cadre, lignes, par_trimestre, annee))).write_pdf()


# ------------------------------------------------------------------- export simple (structure)


def lignes_simples(cadre, user=None) -> list:
    """
    Structure seule du document : ses éléments dans l'ordre de l'arbre, sans activités ni
    chiffres — {"code", "niveau", "nom", "rang", "profondeur", "contribue_a", "groupe"}.
    """
    from .models import ElementStrategique, TypeNiveau

    niveaux = list(TypeNiveau.objects.filter(cadre_strategique=cadre).order_by("ordre"))
    rang = {n.id: i for i, n in enumerate(niveaux)}
    from apps.core.masquage import elements_masques

    elements = list(
        ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre)
        .exclude(id__in=elements_masques(user))
        .select_related("type_niveau", "contribue_a")
    )
    enfants = {}
    for e in elements:
        enfants.setdefault(e.element_parent_id, []).append(e)
    lignes = []

    def visiter(e, profondeur):
        lignes.append({
            "code": e.code, "niveau": e.type_niveau.nom_niveau, "nom": e.nom, "rang": rang.get(e.type_niveau_id, 0),
            "profondeur": profondeur, "groupe": e.id in enfants,
            "contribue_a": str(e.contribue_a) if e.contribue_a_id else "",
        })
        for enfant in enfants.get(e.id, []):
            visiter(enfant, profondeur + 1)

    for racine in enfants.get(None, []):
        visiter(racine, 0)
    return lignes


def _titre_document(cadre) -> str:
    return f"{cadre.type_document.nom if cadre.type_document_id else v('Cadre stratégique')} : {cadre.nom}"


def exporter_simple_excel(cadre, lignes) -> bytes:
    """Structure du document en Excel : Code, Niveau, Élément (en retrait selon la profondeur), Contribue à."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    from apps.core.excel_utils import figer_entete
    from apps.core.vocabulaire import adapter_classeur

    wb = Workbook()
    f = wb.active
    f.title = "Structure"
    f.append([_titre_document(cadre)])
    f["A1"].font = Font(bold=True, size=13)
    f.append([v("Exporté le") + " " + datetime.date.today().strftime("%d/%m/%Y")])
    f["A2"].font = Font(italic=True, color="666666")
    f.append([])
    avec_contribution = any(l["contribue_a"] for l in lignes)
    entetes = [v("Code"), v("Niveau"), v("Élément")] + ([v("Contribue à")] if avec_contribution else [])
    f.append(entetes)
    ligne_entete = f.max_row
    bord = Side(style="thin", color="A0AEC0")
    for c in range(1, len(entetes) + 1):
        cellule = f.cell(row=ligne_entete, column=c)
        cellule.font = Font(bold=True)
        cellule.fill = PatternFill("solid", fgColor=ENTETE)
        cellule.border = Border(top=bord, bottom=bord, left=bord, right=bord)
    for l in lignes:
        f.append([l["code"] or "", l["niveau"], l["nom"]] + ([l["contribue_a"]] if avec_contribution else []))
        r = f.max_row
        for c in range(1, len(entetes) + 1):
            cellule = f.cell(row=r, column=c)
            cellule.border = Border(top=bord, bottom=bord, left=bord, right=bord)
            cellule.alignment = Alignment(vertical="center", wrap_text=c >= 3, indent=l["profondeur"] * 2 if c == 3 else 0)
            if l["groupe"]:
                cellule.font = Font(bold=True)
                cellule.fill = PatternFill("solid", fgColor=FONDS_NIVEAUX[min(l["rang"], len(FONDS_NIVEAUX) - 1)])
    for col, largeur in zip("ABCD", [14, 24, 80, 50]):
        f.column_dimensions[col].width = largeur
    figer_entete(f, ligne_entete=ligne_entete)
    adapter_classeur(wb)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def html_simple(cadre, lignes) -> str:
    """Structure du document en page HTML (portrait), pour l'export PDF."""
    bord = "border:1px solid #a0aec0;"
    avec_contribution = any(l["contribue_a"] for l in lignes)
    th = f'style="{bord}background:#{ENTETE};padding:5px 6px;font-size:10px;text-align:left;"'
    entete = (
        f'<tr><th {th}>{v("Code")}</th><th {th}>{v("Niveau")}</th><th {th}>{v("Élément")}</th>'
        + (f'<th {th}>{v("Contribue à")}</th>' if avec_contribution else "") + "</tr>"
    )
    corps = []
    for l in lignes:
        fond = f"background:#{FONDS_NIVEAUX[min(l['rang'], len(FONDS_NIVEAUX) - 1)]};font-weight:700;" if l["groupe"] else ""
        td = f'style="{bord}{fond}padding:4px 6px;font-size:10px;'
        corps.append(
            f'<tr><td {td}white-space:nowrap;">{escape(l["code"] or "")}</td>'
            f'<td {td}white-space:nowrap;">{escape(l["niveau"])}</td>'
            f'<td {td}padding-left:{6 + l["profondeur"] * 14}px;">{escape(l["nom"])}</td>'
            + (f'<td {td}color:#7048e8;">{escape(l["contribue_a"])}</td>' if avec_contribution else "") + "</tr>"
        )
    maillon = escape(cadre.type_document.nom if cadre.type_document_id else v("Cadre stratégique"))
    vide = f'<tr><td colspan="4" style="padding:8px;">{v("Aucun élément.")}</td></tr>'
    return f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 12mm 10mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; }}
      table {{ border-collapse: collapse; width: 100%; }}
      thead {{ display: table-header-group; }}
      tr {{ page-break-inside: avoid; }}
    </style></head><body>
      <div style="font-size:10px;color:#7048e8;font-weight:700;text-transform:uppercase;">{maillon}</div>
      <h2 style="margin:2px 0 4px 0;font-size:17px;">{escape(cadre.nom)}</h2>
      <div style="font-size:10px;color:#666;margin-bottom:10px;">{v("Exporté le")} {datetime.date.today().strftime("%d/%m/%Y")}</div>
      <table><thead>{entete}</thead><tbody>{"".join(corps) or vide}</tbody></table>
    </body></html>"""


def exporter_simple_pdf(cadre, lignes) -> bytes:
    from weasyprint import HTML

    from apps.core.langues import traduire_html

    return HTML(string=traduire_html(html_simple(cadre, lignes))).write_pdf()
