"""
Rapport financier d'un projet, seul (sans le volet physique), avec les sections au choix :
sources de financement (fonds propres, bailleurs, rallonges), rallonges et leurs motifs,
exécution budgétaire par composante, détail par élément de la planification, dépenses par
trimestre. Facultativement limité à une période (dépenses saisies entre deux dates).

Mêmes règles que le reste de la plateforme : seules les saisies approuvées comptent, et un
budget n'est compté qu'au niveau le plus bas où il est saisi (apps.projects.budgets).
PDF et Word partagent le même HTML (apps.reports.word).
"""
import datetime
import io
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.html import escape

from apps.core.vocabulaire import v

SECTIONS = {
    "sources": "Sources de financement",
    "rallonges": "Rallonges de fonds",
    "execution": "Exécution budgétaire par composante",
    "detail": "Détail par élément de la planification",
    "trimestres": "Dépenses par trimestre",
}


def _montant(valeur) -> str:
    if valeur is None:
        return "—"
    return f"{Decimal(valeur):,.0f}".replace(",", " ") + " FCFA"


def _taux(depense, prevu):
    if not prevu:
        return None
    return round(float(depense or 0) / float(prevu) * 100, 1)


def _pct(valeur) -> str:
    return "—" if valeur is None else f"{valeur:.1f} %".replace(".", ",")


def _date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def donnees_financieres(projet, debut=None, fin=None) -> dict:
    """Chiffres du rapport ; `debut`/`fin` limitent les dépenses à celles saisies sur cette période."""
    from apps.partners.models import RallongeFinancement
    from apps.projects.budgets import ids_comptes
    from apps.projects.models import Activite, NiveauActivite
    from apps.suivi.models import PointSuivi

    # --- Sources --------------------------------------------------------------------
    financements = []
    for f in projet.financements.select_related("bailleur").order_by("bailleur__nom"):
        rallonges = f.montant_rallonges
        financements.append({
            "bailleur": f.bailleur.nom, "initial": f.montant_finance, "rallonges": rallonges, "total": f.montant_finance + rallonges,
        })
    total_bailleurs = sum((f["total"] for f in financements), Decimal("0"))
    cout_total = projet.fonds_propres + total_bailleurs
    rallonges = [
        {"date": r.date, "bailleur": r.financement.bailleur.nom, "montant": r.montant, "motif": r.motif}
        for r in RallongeFinancement.objects.filter(financement__projet=projet).select_related("financement__bailleur").order_by("date", "id")
    ]

    # --- Dépenses par élément (saisies approuvées, sur la période demandée) ---------
    activites = list(Activite.objects.filter(projet=projet).order_by("id"))
    points = PointSuivi.objects.filter(activite__projet=projet, budget_realise__isnull=False)
    if debut:
        points = points.filter(periode_fin__gte=debut)
    if fin:
        points = points.filter(periode_fin__lte=fin)
    depense_propre = dict(points.values("activite").annotate(t=Sum("budget_realise")).values_list("activite", "t"))

    enfants = defaultdict(list)
    for a in activites:
        enfants[a.activite_parent_id].append(a)
    alloues = ids_comptes((a.id, a.activite_parent_id, a.budget_alloue) for a in activites)
    depenses = ids_comptes((a.id, a.activite_parent_id, depense_propre.get(a.id)) for a in activites)
    noms_niveaux = {n.profondeur: n.nom_niveau for n in NiveauActivite.objects.filter(projet=projet)}

    def sous_arbre(activite):
        pile, ids = [activite], []
        while pile:
            courant = pile.pop()
            ids.append(courant)
            pile.extend(enfants.get(courant.id, []))
        return ids

    def chiffres(activite):
        branche = sous_arbre(activite)
        prevu = sum((a.budget_alloue for a in branche if a.id in alloues), Decimal("0"))
        depense = sum((depense_propre[a.id] for a in branche if a.id in depenses), Decimal("0"))
        return prevu, depense

    lignes = []

    def parcourir(activite, profondeur):
        prevu, depense = chiffres(activite)
        lignes.append({
            "profondeur": profondeur,
            "niveau": noms_niveaux.get(profondeur - 1, "Activité"),  # profondeur commence à 0 ; « Activité » par défaut
            "code": activite.code_activite,
            "libelle": activite.libelle,
            "prevu": prevu,
            "depense": depense,
            "taux": _taux(depense, prevu),
            "solde": prevu - depense,
        })
        for enfant in enfants.get(activite.id, []):
            parcourir(enfant, profondeur + 1)

    for racine in enfants.get(None, []):
        parcourir(racine, 1)
    # Composantes : premier niveau qui en compte plusieurs (un objectif général unique au
    # sommet n'apporte rien au tableau par composante).
    profondeur_composantes = 1
    while sum(1 for l in lignes if l["profondeur"] == profondeur_composantes) == 1 and any(
        l["profondeur"] == profondeur_composantes + 1 for l in lignes
    ):
        profondeur_composantes += 1
    composantes = [l for l in lignes if l["profondeur"] == profondeur_composantes]
    total_prevu = sum((l["prevu"] for l in composantes), Decimal("0"))
    total_depense = sum((l["depense"] for l in composantes), Decimal("0"))

    # --- Dépenses par trimestre (fin de la période saisie) --------------------------
    par_trimestre = defaultdict(Decimal)
    for fin_periode, montant in points.filter(activite_id__in=depenses).values_list("periode_fin", "budget_realise"):
        par_trimestre[(fin_periode.year, (fin_periode.month - 1) // 3 + 1)] += montant
    trimestres, cumul = [], Decimal("0")
    for (annee, t), montant in sorted(par_trimestre.items()):
        cumul += montant
        trimestres.append({"libelle": f"T{t} {annee}", "montant": montant, "cumul": cumul, "taux_cumul": _taux(cumul, total_prevu)})

    return {
        "projet": {"code": projet.code, "nom": projet.nom, "date_debut": projet.date_debut, "date_fin": projet.date_fin},
        "periode": {"debut": debut, "fin": fin},
        "fonds_propres": projet.fonds_propres,
        "financements": financements,
        "total_bailleurs": total_bailleurs,
        "total_rallonges": sum((r["montant"] for r in rallonges), Decimal("0")),
        "cout_total": cout_total,
        "rallonges": rallonges,
        "composantes": composantes,
        "lignes": lignes,
        "total_prevu": total_prevu,
        "total_depense": total_depense,
        "taux_execution": _taux(total_depense, total_prevu),
        "non_reparti": cout_total - total_prevu,
        "trimestres": trimestres,
    }


# --- HTML (PDF et Word) -------------------------------------------------------------

TH = 'style="text-align:left;padding:5px 7px;background:#DCE6F1;font-size:11px;color:#1F4E78;"'
TH_D = 'style="text-align:right;padding:5px 7px;background:#DCE6F1;font-size:11px;color:#1F4E78;"'
TD = 'style="padding:4px 7px;border-bottom:1px solid #e5e5e5;vertical-align:top;"'
TD_D = 'style="padding:4px 7px;border-bottom:1px solid #e5e5e5;text-align:right;white-space:nowrap;vertical-align:top;"'
TOTAL = 'style="padding:5px 7px;font-weight:700;border-top:2px solid #1F4E78;text-align:right;white-space:nowrap;"'
TOTAL_G = 'style="padding:5px 7px;font-weight:700;border-top:2px solid #1F4E78;"'


def _tableau(entetes, lignes, total=None):
    ths = "".join(f"<th {TH_D if droite else TH}>{escape(e)}</th>" for e, droite in entetes)
    corps = "".join(lignes)
    pied = f"<tr>{total}</tr>" if total else ""
    return f'<table style="width:100%;border-collapse:collapse;font-size:12px;margin:6px 0 14px;"><thead><tr>{ths}</tr></thead><tbody>{corps}{pied}</tbody></table>'


def _carte(titre, valeur, detail="", alerte=False):
    couleur = "#d03b3b" if alerte else "#666"
    return (
        '<div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:10px;">'
        f'<div style="font-size:11px;color:#666;text-transform:uppercase;">{escape(titre)}</div>'
        f'<div style="font-size:18px;font-weight:700;">{escape(valeur)}</div>'
        + (f'<div style="font-size:11px;color:{couleur};">{escape(detail)}</div>' if detail else "")
        + "</div>"
    )


def html_rapport_financier(d, sections) -> str:
    projet, periode = d["projet"], d["periode"]
    if periode["debut"] or periode["fin"]:
        portee = f"Dépenses du {_date(periode['debut'])} au {_date(periode['fin'])}" if periode["debut"] and periode["fin"] else (
            f"Dépenses à partir du {_date(periode['debut'])}" if periode["debut"] else f"Dépenses jusqu'au {_date(periode['fin'])}"
        )
    else:
        portee = "Toutes les dépenses saisies"
    blocs = []

    blocs.append(
        '<div style="display:flex;gap:10px;margin-bottom:6px;">'
        + _carte("Coût total du projet", _montant(d["cout_total"]),
                 f"dont {_montant(d['total_rallonges'])} de rallonges" if d["total_rallonges"] else "")
        + _carte("Budget planifié", _montant(d["total_prevu"]), (
            f"non réparti : {_montant(d['non_reparti'])}" if d["non_reparti"] > 0
            else f"dépasse le coût total de {_montant(-d['non_reparti'])}" if d["non_reparti"] < 0
            else "entièrement réparti"
        ), alerte=d["non_reparti"] < 0)
        + _carte("Dépensé", _montant(d["total_depense"]), f"exécution : {_pct(d['taux_execution'])}")
        + "</div>"
    )

    if "sources" in sections:
        lignes = [
            f"<tr><td {TD}>Fonds propres</td><td {TD_D}>{_montant(d['fonds_propres'])}</td><td {TD_D}>—</td>"
            f"<td {TD_D}>{_montant(d['fonds_propres'])}</td><td {TD_D}>{_pct(_taux(d['fonds_propres'], d['cout_total']))}</td></tr>"
        ]
        for f in d["financements"]:
            lignes.append(
                f"<tr><td {TD}>{escape(f['bailleur'])}</td><td {TD_D}>{_montant(f['initial'])}</td>"
                f"<td {TD_D}>{_montant(f['rallonges']) if f['rallonges'] else '—'}</td><td {TD_D}>{_montant(f['total'])}</td>"
                f"<td {TD_D}>{_pct(_taux(f['total'], d['cout_total']))}</td></tr>"
            )
        total = (
            f"<td {TOTAL_G}>Total</td><td {TOTAL}>{_montant(d['fonds_propres'] + sum((f['initial'] for f in d['financements']), Decimal('0')))}</td>"
            f"<td {TOTAL}>{_montant(d['total_rallonges'])}</td><td {TOTAL}>{_montant(d['cout_total'])}</td><td {TOTAL}>100 %</td>"
        )
        blocs.append(f"<h3>{SECTIONS['sources']}</h3>" + _tableau(
            [("Source", False), ("Montant initial", True), ("Rallonges", True), ("Total", True), ("Part", True)], lignes, total
        ))

    if "rallonges" in sections:
        if d["rallonges"]:
            lignes = [
                f"<tr><td {TD}>{_date(r['date'])}</td><td {TD}>{escape(r['bailleur'])}</td><td {TD_D}>{_montant(r['montant'])}</td>"
                f"<td {TD}>{escape(r['motif'])}</td></tr>"
                for r in d["rallonges"]
            ]
            contenu = _tableau([("Date", False), ("Bailleur", False), ("Montant", True), ("Motif", False)], lignes,
                               f"<td {TOTAL_G} colspan=\"2\">Total</td><td {TOTAL}>{_montant(d['total_rallonges'])}</td><td {TOTAL_G}></td>")
        else:
            contenu = '<p style="color:#888;">Aucune rallonge de fonds.</p>'
        blocs.append(f"<h3>{SECTIONS['rallonges']}</h3>{contenu}")

    def ligne_execution(l, gras=False, retrait=0):
        style_libelle = f'style="padding:4px 7px 4px {7 + retrait * 14}px;border-bottom:1px solid #e5e5e5;vertical-align:top;{"font-weight:700;" if gras else ""}"'
        niveau = f'<span style="font-size:10px;color:#7048e8;margin-right:6px;">{escape(l["niveau"])}</span>' if l["niveau"] else ""
        code = f'<span style="color:#888;margin-right:4px;">{escape(l["code"])}</span>' if l["code"] else ""
        couleur = "#d03b3b" if l["solde"] < 0 else "#222"
        return (
            f"<tr><td {style_libelle}>{niveau}{code}{escape(l['libelle'])}</td><td {TD_D}>{_montant(l['prevu'])}</td>"
            f"<td {TD_D}>{_montant(l['depense'])}</td><td {TD_D}>{_pct(l['taux'])}</td>"
            f'<td style="padding:4px 7px;border-bottom:1px solid #e5e5e5;text-align:right;white-space:nowrap;vertical-align:top;color:{couleur};">{_montant(l["solde"])}</td></tr>'
        )

    entetes_execution = [("Élément", False), ("Prévu", True), ("Dépensé", True), ("Taux", True), ("Solde", True)]
    total_execution = (
        f"<td {TOTAL_G}>Total</td><td {TOTAL}>{_montant(d['total_prevu'])}</td><td {TOTAL}>{_montant(d['total_depense'])}</td>"
        f"<td {TOTAL}>{_pct(d['taux_execution'])}</td><td {TOTAL}>{_montant(d['total_prevu'] - d['total_depense'])}</td>"
    )
    if "execution" in sections:
        contenu = _tableau(entetes_execution, [ligne_execution(l, gras=True) for l in d["composantes"]], total_execution) if d["composantes"] else (
            f'<p style="color:#888;">{v("Aucune activité planifiée pour ce projet.")}</p>'
        )
        blocs.append(f"<h3>{SECTIONS['execution']}</h3>{contenu}")

    if "detail" in sections and d["lignes"]:
        lignes = [ligne_execution(l, gras=l["profondeur"] == 1, retrait=l["profondeur"] - 1) for l in d["lignes"]]
        blocs.append(f'<h3 style="page-break-before:always;">{SECTIONS["detail"]}</h3>' + _tableau(entetes_execution, lignes, total_execution))

    if "trimestres" in sections:
        if d["trimestres"]:
            lignes = [
                f"<tr><td {TD}>{t['libelle']}</td><td {TD_D}>{_montant(t['montant'])}</td><td {TD_D}>{_montant(t['cumul'])}</td>"
                f"<td {TD_D}>{_pct(t['taux_cumul'])}</td></tr>"
                for t in d["trimestres"]
            ]
            contenu = _tableau([("Trimestre", False), ("Dépensé", True), ("Cumul", True), ("Cumul / prévu", True)], lignes)
        else:
            contenu = '<p style="color:#888;">Aucune dépense saisie sur la période.</p>'
        blocs.append(f"<h3>{SECTIONS['trimestres']}</h3>{contenu}")

    aujourdhui = datetime.date.today()
    return f"""
    <html>
    <head>
    <style>
      @page {{ size: A4; margin: 16mm 14mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 12px; }}
      h2 {{ margin-bottom: 2px; }}
      h3 {{ margin-top: 20px; margin-bottom: 6px; border-bottom: 2px solid #1F4E78; padding-bottom: 4px; color: #1F4E78; }}
      tr {{ page-break-inside: avoid; }}
    </style>
    </head>
    <body>
      <h2>Rapport financier — {escape(projet['nom'])}</h2>
      <div style="color:#666;font-size:12px;margin-bottom:12px;">
        {escape(projet['code'])} · {_date(projet['date_debut'])} → {_date(projet['date_fin'])} · {escape(portee)} · généré le {aujourdhui.strftime('%d/%m/%Y')}
      </div>
      {''.join(blocs)}
    </body>
    </html>
    """


def excel_rapport_financier(d, sections) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    classeur = Workbook()
    entete = Font(bold=True, color="FFFFFF")
    fond = PatternFill("solid", fgColor="1F4E78")
    format_montant = '# ##0" FCFA"'

    def feuille(titre, colonnes, lignes, largeurs):
        ws = classeur.create_sheet(titre[:31])
        ws.append(colonnes)
        for cellule in ws[1]:
            cellule.font, cellule.fill = entete, fond
        for ligne in lignes:
            ws.append(ligne)
        for i, largeur in enumerate(largeurs, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = largeur
        for ligne in ws.iter_rows(min_row=2):
            for cellule in ligne:
                if isinstance(cellule.value, (int, float, Decimal)) and cellule.column > 1:
                    cellule.number_format = format_montant
        return ws

    resume = classeur.active
    resume.title = "Résumé"
    p = d["projet"]
    for ligne in (
        ("Rapport financier", f"{p['code']} — {p['nom']}"),
        ("Coût total", d["cout_total"]),
        ("dont rallonges", d["total_rallonges"]),
        ("Budget planifié", d["total_prevu"]),
        ("Dépensé", d["total_depense"]),
        ("Taux d'exécution (%)", d["taux_execution"]),
    ):
        resume.append(ligne)
    resume["A1"].font = Font(bold=True, size=13)
    for cellule in ("B2", "B3", "B4", "B5"):
        resume[cellule].number_format = format_montant
    resume.column_dimensions["A"].width, resume.column_dimensions["B"].width = 26, 60

    if "sources" in sections:
        lignes = [("Fonds propres", d["fonds_propres"], None, d["fonds_propres"])]
        lignes += [(f["bailleur"], f["initial"], f["rallonges"], f["total"]) for f in d["financements"]]
        feuille("Sources", ["Source", "Montant initial", "Rallonges", "Total"], lignes, [36, 20, 20, 20])
    if "rallonges" in sections:
        ws = feuille("Rallonges", ["Date", "Bailleur", "Montant", "Motif"], [(r["date"], r["bailleur"], r["montant"], r["motif"]) for r in d["rallonges"]], [12, 30, 20, 70])
        for ligne in ws.iter_rows(min_row=2):
            ligne[0].number_format = "DD/MM/YYYY"
            ligne[3].alignment = Alignment(wrap_text=True, vertical="top")
    colonnes = ["Niveau", "Code", "Élément", "Prévu", "Dépensé", "Taux (%)", "Solde"]
    if "execution" in sections:
        feuille("Exécution", colonnes, [(l["niveau"], l["code"], l["libelle"], l["prevu"], l["depense"], l["taux"], l["solde"]) for l in d["composantes"]], [18, 10, 60, 18, 18, 10, 18])
    if "detail" in sections:
        feuille("Détail", colonnes, [(l["niveau"], l["code"], "    " * (l["profondeur"] - 1) + l["libelle"], l["prevu"], l["depense"], l["taux"], l["solde"]) for l in d["lignes"]], [18, 10, 60, 18, 18, 10, 18])
    if "trimestres" in sections:
        feuille("Trimestres", ["Trimestre", "Dépensé", "Cumul", "Cumul / prévu (%)"], [(t["libelle"], t["montant"], t["cumul"], t["taux_cumul"]) for t in d["trimestres"]], [14, 20, 20, 18])
    for ws in classeur.worksheets[1:]:
        for ligne in ws.iter_rows(min_row=2):
            for cellule in ligne:
                if ws.cell(row=1, column=cellule.column).value in ("Taux (%)", "Cumul / prévu (%)"):
                    cellule.number_format = "0.0"
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()
