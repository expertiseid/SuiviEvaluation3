"""
Planification d'un projet exportée comme à l'écran (mode Tableau de l'onglet Planification) ou
au format du canevas de remplissage — mêmes trois exports que pour un document stratégique
(apps.strategy.tableau) :

- « complet » : une ligne par élément (tous niveaux, bandeau de couleur pour ceux qui en
  regroupent d'autres) puis ses sous-activités, avec les attributs, les services, la
  programmation (trimestres de l'année choisie ou dates), le budget et le taux — Excel ou PDF ;
- « simple » : la structure seule (code, niveau, libellé), sans chiffres — Excel ou PDF ;
- « canevas » : la feuille « Planification » du modèle d'import, préremplie avec la planification
  actuelle ; complétée, elle se réimporte dans le projet (importer_planification, rejouable).
"""
import datetime
import io

from django.utils.html import escape

from apps.core.vocabulaire import v

from .models import Activite, MethodeCalcul, NiveauActivite, SousActivite


def _arbre(projet):
    """(racines, enfants par parent, sous-activités par élément), dans l'ordre de l'écran (création)."""
    elements = list(Activite.objects.filter(projet=projet).prefetch_related("structures"))
    enfants = {}
    for e in elements:
        enfants.setdefault(e.activite_parent_id, []).append(e)
    sous = {}
    for sa in SousActivite.objects.filter(activite__projet=projet):
        sous.setdefault(sa.activite_id, []).append(sa)
    return enfants.get(None, []), enfants, sous


def noms_niveaux(projet) -> dict:
    return dict(NiveauActivite.objects.filter(projet=projet).values_list("profondeur", "nom_niveau"))


def noms_attributs(projet, elements_et_sous) -> list:
    """Attributs libres utilisés, dans l'ordre des colonnes du fichier importé (comme utils/attributs.ts)."""
    noms = {n for o in elements_et_sous for n in (o.attributs or {})}
    ordre = list(projet.ordre_attributs or [])
    return sorted(noms, key=lambda n: (ordre.index(n) if n in ordre else len(ordre), n.casefold()))


def lignes_planification(projet) -> tuple[list, list]:
    """
    (lignes, attributs). Ligne : {"type": "element"|"sous-activite", "code", "libelle", "niveau",
    "profondeur", "groupe", "attributs", "services", "debut", "fin", "budget", "taux", "objet"}.
    Budget d'un élément sans budget propre = somme de ceux en dessous (comme à l'écran).
    """
    from .taux import ArbreTaux

    racines, enfants, sous = _arbre(projet)
    niveaux = noms_niveaux(projet)
    arbre_taux = ArbreTaux(projet)

    def budget(e):
        if e.budget_alloue is not None:
            return float(e.budget_alloue)
        valeurs = [b for b in (budget(x) for x in enfants.get(e.id, [])) if b is not None]
        return sum(valeurs) if valeurs else None

    lignes, objets = [], []

    def visiter(e, profondeur):
        objets.append(e)
        lignes.append({
            "type": "element", "code": e.code_activite, "libelle": e.libelle,
            "niveau": niveaux.get(profondeur, v("Activité")), "profondeur": profondeur,
            "groupe": bool(enfants.get(e.id)), "attributs": e.attributs or {},
            "services": ", ".join(str(s) for s in e.structures.all()),
            "debut": e.date_debut, "fin": e.date_fin, "budget": budget(e),
            "taux": arbre_taux.resultat(e.id).taux, "objet": e,
        })
        for enfant in enfants.get(e.id, []):
            visiter(enfant, profondeur + 1)
        for sa in sous.get(e.id, []):
            objets.append(sa)
            lignes.append({
                "type": "sous-activite", "code": "", "libelle": sa.libelle, "niveau": v("Sous-activité"),
                "profondeur": profondeur + 1, "groupe": False, "attributs": sa.attributs or {}, "services": "",
                "debut": sa.date_debut, "fin": sa.date_fin, "budget": None,
                "taux": float(sa.avancement) if sa.avancement is not None else None, "objet": sa,
            })

    for racine in racines:
        visiter(racine, 0)
    return lignes, noms_attributs(projet, objets)


def annees_possibles(lignes) -> list:
    ans = [d.year for l in lignes for d in (l["debut"], l["fin"]) if d]
    return list(range(min(ans), max(ans) + 1)) if ans else [datetime.date.today().year]


def _bordure():
    from openpyxl.styles import Border, Side

    cote = Side(style="thin", color="A0AEC0")
    return Border(top=cote, bottom=cote, left=cote, right=cote)


def _entete_document(f, projet, titre):
    from openpyxl.styles import Font

    f.append([f"{projet.code} — {projet.nom}"])
    f["A1"].font = Font(bold=True, size=13)
    f.append([f"{titre} · {v('Exporté le')} {datetime.date.today().strftime('%d/%m/%Y')}"])
    f["A2"].font = Font(italic=True, color="666666")
    f.append([])


def exporter_complet_excel(projet, lignes, attributs, par_trimestre, annee) -> bytes:
    """Tableau de la planification en Excel : mêmes colonnes et bandeaux qu'à l'écran."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from apps.core.excel_utils import figer_entete
    from apps.core.vocabulaire import adapter_classeur
    from apps.strategy.tableau import ENTETE, FONDS_NIVEAUX, _date, prevu_au_trimestre

    avec_services = any(l["services"] for l in lignes)
    wb = Workbook()
    f = wb.active
    f.title = "Planification"
    _entete_document(f, projet, v("Planification"))
    programmation = [f"T{t}" for t in range(1, 5)] if par_trimestre else [v("Date début"), v("Date fin")]
    fixes = [v("Code activité"), v("Logique d'intervention"), *attributs] + ([v("Services")] if avec_services else [])
    nb = len(fixes) + len(programmation) + 2
    if par_trimestre:
        f.append([*fixes, f"{v('Programmation')} {annee}", "", "", "", v("Budget alloué (FCFA)"), v("Taux")])
        l1 = f.max_row
        f.append([""] * len(fixes) + programmation + ["", ""])
        l2 = f.max_row
        for col in [*range(1, len(fixes) + 1), nb - 1, nb]:
            f.merge_cells(start_row=l1, start_column=col, end_row=l2, end_column=col)
        f.merge_cells(start_row=l1, start_column=len(fixes) + 1, end_row=l1, end_column=len(fixes) + 4)
    else:
        f.append([*fixes, *programmation, v("Budget alloué (FCFA)"), v("Taux")])
        l1 = l2 = f.max_row
    for r in range(l1, l2 + 1):
        for c in range(1, nb + 1):
            cellule = f.cell(row=r, column=c)
            cellule.font = Font(bold=True)
            cellule.fill = PatternFill("solid", fgColor=ENTETE)
            cellule.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cellule.border = _bordure()
    for l in lignes:
        titre = l["type"] == "element" and l["groupe"]
        libelle = f"{l['niveau']} : {l['libelle']}" if titre else (
            f"    {v('Sous-activité')} : {l['libelle']}" if l["type"] == "sous-activite" else l["libelle"])
        prog = (["X" if prevu_au_trimestre(l["debut"], l["fin"], annee, t) else "" for t in range(1, 5)]
                if par_trimestre else [_date(l["debut"]), _date(l["fin"])])
        f.append([l["code"] or "", libelle, *[l["attributs"].get(n, "") for n in attributs],
                  *([l["services"]] if avec_services else []), *prog, l["budget"],
                  (l["taux"] / 100) if l["taux"] is not None else None])
        r = f.max_row
        for c in range(1, nb + 1):
            cellule = f.cell(row=r, column=c)
            cellule.border = _bordure()
            cellule.alignment = Alignment(vertical="center", wrap_text=1 < c <= len(fixes),
                                          horizontal="center" if c == 1 or len(fixes) < c <= nb - 2 else None)
            if titre:
                cellule.font = Font(bold=True)
                cellule.fill = PatternFill("solid", fgColor=FONDS_NIVEAUX[min(l["profondeur"], len(FONDS_NIVEAUX) - 1)])
        f.cell(row=r, column=nb - 1).number_format = "#,##0"
        f.cell(row=r, column=nb).number_format = "0.0%"
    from openpyxl.utils import get_column_letter

    largeurs = [14, 60, *([22] * len(attributs)), *([28] if avec_services else []),
                *([7] * 4 if par_trimestre else [13, 13]), 18, 10]
    for i, largeur in enumerate(largeurs, start=1):
        f.column_dimensions[get_column_letter(i)].width = largeur
    figer_entete(f, ligne_entete=l2)
    adapter_classeur(wb)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def _page(projet, titre, entete, corps, colonnes, paysage) -> str:
    vide = f'<tr><td colspan="{colonnes}" style="padding:8px;">{v("Aucun élément.")}</td></tr>'
    return f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A4{" landscape" if paysage else ""}; margin: 12mm 10mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; }}
      table {{ border-collapse: collapse; width: 100%; }}
      thead {{ display: table-header-group; }}
      tr {{ page-break-inside: avoid; }}
    </style></head><body>
      <div style="font-size:10px;color:#0b7285;font-weight:700;text-transform:uppercase;">{escape(titre)}</div>
      <h2 style="margin:2px 0 4px 0;font-size:17px;">{escape(projet.code)} — {escape(projet.nom)}</h2>
      <div style="font-size:10px;color:#666;margin-bottom:10px;">{v("Exporté le")} {datetime.date.today().strftime("%d/%m/%Y")}</div>
      <table><thead>{entete}</thead><tbody>{"".join(corps) or vide}</tbody></table>
    </body></html>"""


def html_complet(projet, lignes, attributs, par_trimestre, annee) -> str:
    from apps.strategy.tableau import ENTETE, FONDS_NIVEAUX, _date, _montant, _taux, prevu_au_trimestre

    bord = "border:1px solid #a0aec0;"
    avec_services = any(l["services"] for l in lignes)
    th = f'style="{bord}background:#{ENTETE};padding:5px 6px;font-size:9px;text-align:center;"'
    fixes = [v("Code activité"), v("Logique d'intervention"), *attributs] + ([v("Services")] if avec_services else [])
    if par_trimestre:
        entete = ("<tr>" + "".join(f'<th rowspan="2" {th}>{escape(n)}</th>' for n in fixes)
                  + f'<th colspan="4" {th}>{v("Programmation")} {annee}</th>'
                  + f'<th rowspan="2" {th}>{v("Budget alloué (FCFA)")}</th><th rowspan="2" {th}>{v("Taux")}</th></tr>'
                  + "<tr>" + "".join(f"<th {th}>T{t}</th>" for t in range(1, 5)) + "</tr>")
    else:
        entete = ("<tr>" + "".join(f"<th {th}>{escape(n)}</th>" for n in
                                   [*fixes, v("Date début"), v("Date fin"), v("Budget alloué (FCFA)"), v("Taux")]) + "</tr>")
    corps = []
    for l in lignes:
        titre = l["type"] == "element" and l["groupe"]
        fond = f"background:#{FONDS_NIVEAUX[min(l['profondeur'], len(FONDS_NIVEAUX) - 1)]};font-weight:700;" if titre else ""
        td = f'style="{bord}{fond}padding:4px 5px;font-size:9px;'
        if titre:
            libelle = f"{escape(l['niveau'])} : {escape(l['libelle'])}"
        elif l["type"] == "sous-activite":
            libelle = f'<span style="color:#888;">{v("Sous-activité")} :</span> {escape(l["libelle"])}'
        else:
            libelle = escape(l["libelle"])
        retrait = "padding-left:16px;" if l["type"] == "sous-activite" else ""
        cellules = [f'<td {td}text-align:center;">{escape(l["code"] or "")}</td>', f'<td {td}{retrait}">{libelle}</td>']
        cellules += [f'<td {td}">{escape(str(l["attributs"].get(n, "")))}</td>' for n in attributs]
        if avec_services:
            cellules.append(f'<td {td}">{escape(l["services"])}</td>')
        if par_trimestre:
            cellules += [f'<td {td}text-align:center;">{"X" if prevu_au_trimestre(l["debut"], l["fin"], annee, t) else ""}</td>'
                         for t in range(1, 5)]
        else:
            cellules += [f'<td {td}white-space:nowrap;">{_date(l["debut"])}</td>', f'<td {td}white-space:nowrap;">{_date(l["fin"])}</td>']
        cellules += [f'<td {td}text-align:right;white-space:nowrap;">{_montant(l["budget"])}</td>',
                     f'<td {td}text-align:center;white-space:nowrap;color:#0b7285;">{_taux(l["taux"]) if l["taux"] is not None or l["type"] == "element" else ""}</td>']
        corps.append("<tr>" + "".join(cellules) + "</tr>")
    return _page(projet, v("Planification"), entete, corps, len(fixes) + 6, paysage=True)


def exporter_complet_pdf(projet, lignes, attributs, par_trimestre, annee) -> bytes:
    from weasyprint import HTML

    from apps.core.langues import traduire_html

    return HTML(string=traduire_html(html_complet(projet, lignes, attributs, par_trimestre, annee))).write_pdf()


def exporter_simple_excel(projet, lignes) -> bytes:
    """Structure seule : Code, Niveau, Élément (en retrait selon la profondeur)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from apps.core.excel_utils import figer_entete
    from apps.core.vocabulaire import adapter_classeur
    from apps.strategy.tableau import ENTETE, FONDS_NIVEAUX

    wb = Workbook()
    f = wb.active
    f.title = "Structure"
    _entete_document(f, projet, v("Structure de la planification"))
    f.append([v("Code activité"), v("Niveau"), v("Élément")])
    ligne_entete = f.max_row
    for c in range(1, 4):
        cellule = f.cell(row=ligne_entete, column=c)
        cellule.font = Font(bold=True)
        cellule.fill = PatternFill("solid", fgColor=ENTETE)
        cellule.border = _bordure()
    for l in lignes:
        f.append([l["code"] or "", l["niveau"], l["libelle"]])
        r = f.max_row
        for c in range(1, 4):
            cellule = f.cell(row=r, column=c)
            cellule.border = _bordure()
            cellule.alignment = Alignment(vertical="center", wrap_text=c == 3, indent=l["profondeur"] * 2 if c == 3 else 0)
            if l["groupe"]:
                cellule.font = Font(bold=True)
                cellule.fill = PatternFill("solid", fgColor=FONDS_NIVEAUX[min(l["profondeur"], len(FONDS_NIVEAUX) - 1)])
            elif l["type"] == "sous-activite" and c == 2:
                cellule.font = Font(color="888888")
    for col, largeur in zip("ABC", [14, 24, 90]):
        f.column_dimensions[col].width = largeur
    figer_entete(f, ligne_entete=ligne_entete)
    adapter_classeur(wb)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def exporter_simple_pdf(projet, lignes) -> bytes:
    from weasyprint import HTML

    from apps.core.langues import traduire_html
    from apps.strategy.tableau import ENTETE, FONDS_NIVEAUX

    bord = "border:1px solid #a0aec0;"
    th = f'style="{bord}background:#{ENTETE};padding:5px 6px;font-size:10px;text-align:left;"'
    entete = f'<tr><th {th}>{v("Code activité")}</th><th {th}>{v("Niveau")}</th><th {th}>{v("Élément")}</th></tr>'
    corps = []
    for l in lignes:
        fond = f"background:#{FONDS_NIVEAUX[min(l['profondeur'], len(FONDS_NIVEAUX) - 1)]};font-weight:700;" if l["groupe"] else ""
        td = f'style="{bord}{fond}padding:4px 6px;font-size:10px;'
        couleur = "color:#888;" if l["type"] == "sous-activite" else ""
        corps.append(
            f'<tr><td {td}white-space:nowrap;">{escape(l["code"] or "")}</td>'
            f'<td {td}white-space:nowrap;{couleur}">{escape(l["niveau"])}</td>'
            f'<td {td}padding-left:{6 + l["profondeur"] * 14}px;">{escape(l["libelle"])}</td></tr>'
        )
    html = _page(projet, v("Structure de la planification"), entete, corps, 3, paysage=False)
    return HTML(string=traduire_html(html)).write_pdf()


# ------------------------------------------------------------------------------------ canevas


def exporter_canevas(projet) -> bytes:
    """
    Feuille « Planification » du modèle d'import, préremplie : une colonne par niveau du projet
    (noms des niveaux), « Code activité », les attributs (« Attribut : … »), puis les colonnes de
    données. Réimportée dans le projet, elle met à jour les éléments (même libellé, même parent)
    et ajoute les nouvelles lignes, sans rien dupliquer.
    """
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    from apps.core.excel_utils import figer_entete, quadriller

    from .attributs import PREFIXE
    from .import_excel import COLONNES_PLANIFICATION, COMMENTAIRE_NIVEAU, COULEUR_ATTRIBUT, COULEUR_NIVEAU, LEGENDE_NIVEAUX

    racines, enfants, sous = _arbre(projet)
    niveaux = noms_niveaux(projet)
    profondeur_max = 0

    def profondeur_de(e, p=0):
        nonlocal profondeur_max
        profondeur_max = max(profondeur_max, p)
        for x in enfants.get(e.id, []):
            profondeur_de(x, p + 1)

    for r in racines:
        profondeur_de(r)
    nb_niveaux = max(profondeur_max + 1, len(niveaux), 1)
    colonnes_niveaux = [niveaux.get(p, v("Activité") if p == nb_niveaux - 1 else f"{v('Niveau')} {p + 1}") for p in range(nb_niveaux)]
    objets = [e for liste in enfants.values() for e in liste] + [sa for liste in sous.values() for sa in liste]
    attributs = noms_attributs(projet, objets)
    donnees = COLONNES_PLANIFICATION[COLONNES_PLANIFICATION.index("Sous-activité"):]
    entetes = ["Code activité", *colonnes_niveaux, *[f"{PREFIXE} : {n}" for n in attributs], *donnees]
    i = {nom: entetes.index(nom) for nom in donnees}
    methodes = dict(MethodeCalcul.choices)

    wb = Workbook()
    f = wb.active
    f.title = "Planification"
    f.append([LEGENDE_NIVEAUX])
    f.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(entetes))
    f.cell(row=1, column=1).font = Font(italic=True, color="7F6000")
    f.cell(row=1, column=1).fill = PatternFill("solid", fgColor=COULEUR_NIVEAU)
    f.cell(row=1, column=1).alignment = Alignment(wrap_text=True, vertical="center")
    f.row_dimensions[1].height = 32
    f.append(entetes)
    for c, nom in enumerate(entetes, start=1):
        cellule = f.cell(row=2, column=c)
        cellule.font = Font(bold=True)
        if nom in colonnes_niveaux:
            cellule.fill = PatternFill("solid", fgColor=COULEUR_NIVEAU)
            cellule.comment = Comment(COMMENTAIRE_NIVEAU, "Plateforme S&E")
        elif nom.startswith(f"{PREFIXE} :"):
            cellule.fill = PatternFill("solid", fgColor=COULEUR_ATTRIBUT)

    def valeur(x):
        return float(x) if x is not None else ""

    def ecrire_element(e, p):
        ligne = [""] * len(entetes)
        ligne[0] = e.code_activite or ""
        ligne[1 + p] = e.libelle
        for k, n in enumerate(attributs):
            ligne[1 + nb_niveaux + k] = (e.attributs or {}).get(n, "")
        ligne[i["Valeur de base"]] = valeur(e.valeur_reference)
        ligne[i["Budget alloué (FCFA)"]] = valeur(e.budget_alloue)
        ligne[i["Quantité prévue"]] = valeur(e.quantite_prevue)
        ligne[i["Unité"]] = e.unite_quantite
        ligne[i["Date début (AAAA-MM-JJ)"]] = e.date_debut.isoformat() if e.date_debut else ""
        ligne[i["Date fin (AAAA-MM-JJ)"]] = e.date_fin.isoformat() if e.date_fin else ""
        ligne[i["Commentaire"]] = e.commentaire
        ligne[i["Méthode de calcul"]] = methodes.get(e.methode_calcul, "") if e.methode_calcul else ""
        ligne[i["Poids (%)"]] = valeur(e.poids)
        f.append(ligne)
        for x in enfants.get(e.id, []):
            ecrire_element(x, p + 1)
        for sa in sous.get(e.id, []):
            ligne = [""] * len(entetes)
            ligne[i["Sous-activité"]] = sa.libelle
            for k, n in enumerate(attributs):
                ligne[1 + nb_niveaux + k] = (sa.attributs or {}).get(n, "")
            ligne[i["Quantité prévue"]] = valeur(sa.quantite_prevue)
            ligne[i["Unité"]] = sa.unite_quantite
            ligne[i["Date début (AAAA-MM-JJ)"]] = sa.date_debut.isoformat() if sa.date_debut else ""
            ligne[i["Date fin (AAAA-MM-JJ)"]] = sa.date_fin.isoformat() if sa.date_fin else ""
            ligne[i["Poids (%)"]] = valeur(sa.poids)
            f.append(ligne)

    for r in racines:
        ecrire_element(r, 0)
    for _ in range(20):
        f.append([""] * len(entetes))
    quadriller(f, min_row=2, max_col=len(entetes))
    figer_entete(f, ligne_entete=2)
    colonne = get_column_letter(i["Méthode de calcul"] + 1)
    liste = DataValidation(type="list", formula1='"' + ",".join(MethodeCalcul.labels) + '"', allow_blank=True)
    liste.add(f"{colonne}3:{colonne}{f.max_row}")
    f.add_data_validation(liste)
    for c, nom in enumerate(entetes, start=1):
        f.column_dimensions[get_column_letter(c)].width = 34 if nom in colonnes_niveaux or nom == "Sous-activité" else 16

    instructions = wb.create_sheet("Instructions")
    for texte in [
        f"{projet.code} — {projet.nom} : canevas de la planification",
        "",
        "- Une colonne par niveau (en jaune), de gauche à droite ; sur chaque ligne, une seule colonne de niveau",
        "  remplie : son parent est le dernier élément du niveau juste à gauche, au-dessus.",
        "- « Sous-activité » : une ligne sous l'élément qu'elle détaille.",
        "- « Attribut : … » (en bleu) : informations libres de l'élément ou de la sous-activité de la ligne.",
        "- Réimporter le fichier dans le projet (onglet Planification › « Importer depuis Excel ») met à jour",
        "  les éléments existants (même libellé, même parent) et ajoute les nouveaux, sans doublon.",
        "  Les lignes retirées du fichier ne sont pas supprimées du projet.",
    ]:
        instructions.append([texte])
    instructions.column_dimensions["A"].width = 110

    from apps.core.vocabulaire import adapter_classeur

    adapter_classeur(wb)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()
