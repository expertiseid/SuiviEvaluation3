"""
Exports Excel/PDF de l'onglet « Planification par période » — mêmes
chiffres que l'écran (apps.suivi.services.construire_planification_periode),
même mise en forme que l'export de suivi du projet (export_excel /
export_pdf).
"""
import datetime
import io

from django.utils.html import escape
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from apps.core.vocabulaire import v
from apps.projects.taux import libelle_methode

from .export_excel import _entete, _largeurs
from .export_pdf import _badge, _barre_progression, _fmt, _fmt_date, _fmt_pct
from .services import SOURCE_SAISIE, construire_planification_periode, ecart_texte, taux_de, valeur_attendue_a

STATUT_COULEUR = {"Atteinte": "#0ca30c", "En retard": "#d03b3b", "En cours": "#1c7ed6"}

NOTE_AVANCEMENT = (
    "Éléments calculés autrement que par quantité (tâches, jalons, livrables, binaire, saisie manuelle, "
    "niveaux agrégés) : objectif et réalisé sont l'avancement en % à la fin de la période."
)


def _methode(ligne):
    return libelle_methode(ligne["methode"]) if ligne.get("methode") else ""


def _avancement(ligne):
    return ligne.get("mode") == "avancement"


def _titre(data):
    periode = data["periode"]
    return (
        f"{v('Planification ')}{periode['libelle']} ({_fmt_date(periode['date_debut'])} → {_fmt_date(periode['date_fin'])}) — {data['projet']['code']} — {data['projet']['nom']}"
    )


def exporter_periode_excel(periode) -> bytes:
    data = construire_planification_periode(periode)
    aujourdhui = datetime.date.today()
    wb = Workbook()

    feuille = wb.active
    feuille.title = v('Planification')
    feuille.append([_titre(data)])
    feuille.cell(row=1, column=1).font = Font(bold=True, size=13)
    totaux = data["totaux"]
    feuille.append(
        [
            f"Généré le {aujourdhui.strftime('%d/%m/%Y')} · budget prévu sur la période : "
            f"{_fmt(totaux['budget_prevu'], 0)} FCFA · réalisé : {_fmt(totaux['budget_realise'], 0)} FCFA · "
            f"objectifs définis pour {totaux['nb_definis']} élément(s) sur {totaux['nb_elements']}"
        ]
    )
    feuille.cell(row=2, column=1).font = Font(italic=True, color="666666")
    feuille.append([NOTE_AVANCEMENT])
    feuille.cell(row=3, column=1).font = Font(italic=True, color="666666")
    colonnes = [
        "Niveau", "Code", "Libellé", "Méthode de calcul", "Unité",
        "Objectif global", "Budget global (FCFA)", "Dates globales",
        "Objectif période", "Budget prévu période (FCFA)", "Dates prévues période",
        "Réalisé période", "Taux physique (%)", "Budget réalisé période (FCFA)", "Taux financier (%)",
        "Statut", "Commentaire",
    ]
    _entete(feuille, colonnes, ligne=4)

    def dates(debut, fin):
        return f"{_fmt_date(debut)} → {_fmt_date(fin)}" if (debut or fin) else ""

    for ligne in data["lignes"]:
        planifie = ligne["source"] == SOURCE_SAISIE
        feuille.append(
            [
                ligne["niveau"],
                ligne["code"],
                ligne["libelle"],
                _methode(ligne),
                ligne["unite"],
                ligne["global_quantite"],
                ligne["global_budget"],
                dates(ligne["global_debut"], ligne["global_fin"]),
                ligne.get("prevu_quantite"),
                ligne.get("prevu_budget"),
                dates(ligne.get("debut_prevu"), ligne.get("fin_prevue")) if planifie else "",
                ligne["realise_quantite"],
                ligne.get("taux"),
                ligne.get("budget_realise"),
                ligne.get("taux_financier"),
                ligne["statut"],
                ligne["commentaire"],
            ]
        )
        feuille.cell(row=feuille.max_row, column=3).alignment = Alignment(indent=ligne["profondeur"], wrap_text=True)
        if not planifie:
            for cellule in feuille[feuille.max_row]:
                cellule.font = Font(color="888888")
    _largeurs(feuille, [16, 10, 50, 22, 12, 12, 16, 24, 14, 18, 24, 14, 10, 18, 10, 16, 40])

    feuille_indic = wb.create_sheet(v('Indicateurs'))
    _entete(
        feuille_indic,
        [v('Indicateur'), "Unité", "Cible globale", "Cible période", "Réalisé période", "Taux (%)", "Statut", "Commentaire"],
    )
    for indicateur in data["indicateurs"]:
        feuille_indic.append(
            [
                indicateur["libelle"],
                indicateur["unite"],
                indicateur["valeur_cible"],
                indicateur["prevu_quantite"],
                indicateur["realise_quantite"],
                indicateur["taux"],
                indicateur["statut"],
                indicateur["commentaire"],
            ]
        )
    _largeurs(feuille_indic, [60, 12, 14, 14, 14, 10, 18, 40])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def exporter_periode_pdf(periode) -> bytes:
    from weasyprint import HTML

    data = construire_planification_periode(periode)
    aujourdhui = datetime.date.today()
    totaux = data["totaux"]
    cellule = 'style="padding:4px 6px;border-bottom:1px solid #e5e5e5;vertical-align:top;"'

    def valeurs(ligne, unite, avec_budget):
        if ligne["source"] != SOURCE_SAISIE:
            realise = f"{_fmt(ligne['realise_quantite'])} {escape(unite)}"
            if avec_budget:
                realise += f"<br>{_fmt(ligne['budget_realise'], 0)} FCFA"
            return (
                '<td style="color:#999;font-style:italic;padding:4px 6px;'
                f'border-bottom:1px solid #e5e5e5;">Objectif à définir</td><td {cellule}>{realise}</td>'
            )
        prevu = f"{_fmt(ligne['prevu_quantite'])} {escape(unite)}"
        realise = f"{_fmt(ligne['realise_quantite'] or 0)} {escape(unite)} ({_fmt_pct(ligne['taux'])})"
        if avec_budget:
            prevu += f"<br>{_fmt(ligne['prevu_budget'], 0)} FCFA"
            realise += f"<br>{_fmt(ligne['budget_realise'] or 0, 0)} FCFA ({_fmt_pct(ligne['taux_financier'])})"
        if ligne.get("debut_prevu") or ligne.get("fin_prevue"):
            prevu += f'<br><span style="color:#666;">{_fmt_date(ligne["debut_prevu"])} → {_fmt_date(ligne["fin_prevue"])}</span>'
        realise += _barre_progression(ligne["taux"], STATUT_COULEUR.get(ligne["statut"], "#1c7ed6"))
        realise += _badge(ligne["statut"], STATUT_COULEUR.get(ligne["statut"], "#666"))
        if ligne.get("commentaire"):
            realise += f'<div style="color:#666;font-style:italic;">{escape(ligne["commentaire"])}</div>'
        return f"<td {cellule}>{prevu}</td><td {cellule}>{realise}</td>"

    lignes_html = []
    for ligne in data["lignes"]:
        globale = f"{_fmt(ligne['global_quantite'])} {escape(ligne['unite'])}"
        if ligne["type"] == "activite":
            globale += f"<br>{_fmt(ligne['global_budget'], 0)} FCFA"
        if ligne["global_debut"] or ligne["global_fin"]:
            globale += f'<br><span style="color:#666;">{_fmt_date(ligne["global_debut"])} → {_fmt_date(ligne["global_fin"])}</span>'
        code = f"{escape(ligne['code'])} " if ligne["code"] else ""
        lignes_html.append(
            "<tr>"
            f'<td {cellule}><div style="padding-left:{ligne["profondeur"] * 12}px;">'
            f'<span style="color:#7048e8;font-size:8px;text-transform:uppercase;">{escape(ligne["niveau"])}</span><br>'
            f"{code}{escape(ligne['libelle'])}"
            f'<br><span style="color:#666;font-size:8px;">{escape(_methode(ligne))}</span></div></td>'
            f"<td {cellule}>{globale}</td>"
            f"{valeurs(ligne, ligne['unite'], ligne['type'] == 'activite')}"
            "</tr>"
        )

    indicateurs_html = "".join(
        "<tr>"
        f"<td {cellule}>{escape(i['libelle'])}</td>"
        f"<td {cellule}>{_fmt(i['valeur_cible'])} {escape(i['unite'])}</td>"
        f"{valeurs(i, i['unite'], False)}"
        "</tr>"
        for i in data["indicateurs"]
    )

    entete_tableau = (
        '<tr style="background:#1F4E78;color:white;font-size:9px;text-transform:uppercase;">'
        '<th style="padding:5px;text-align:left;">{}</th><th style="padding:5px;text-align:left;">Global</th>'
        '<th style="padding:5px;text-align:left;">Prévu sur la période</th>'
        '<th style="padding:5px;text-align:left;">Réalisé sur la période</th></tr>'
    )

    html_content = f"""
    <html>
    <head>
    <style>
      @page {{ size: A4 landscape; margin: 14mm 12mm; }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 10px; }}
      h3 {{ margin-top: 18px; margin-bottom: 6px; border-bottom: 2px solid #1F4E78; padding-bottom: 4px; color: #1F4E78; }}
      table {{ width: 100%; border-collapse: collapse; }}
      tr {{ page-break-inside: avoid; }}
    </style>
    </head>
    <body>
      <h2 style="margin-bottom:2px;">{escape(_titre(data))}</h2>
      <div style="color:#666;margin-bottom:10px;">
        Généré le {aujourdhui.strftime('%d/%m/%Y')} · budget prévu : <b>{_fmt(totaux['budget_prevu'], 0)} FCFA</b>
        · réalisé : <b>{_fmt(totaux['budget_realise'], 0)} FCFA</b>
        · objectifs définis pour {totaux['nb_definis']} élément(s) sur {totaux['nb_elements']}
        <br>{NOTE_AVANCEMENT}
      </div>
      <h3>{v('Planification')}</h3>
      <table>{entete_tableau.format("Élément")}{"".join(lignes_html)}</table>
      <h3>{v('Indicateurs')}</h3>
      {f'<table>{entete_tableau.format(v('Indicateur'))}{indicateurs_html}</table>' if indicateurs_html else v('<p style="color:#888;">Aucun indicateur rattaché à ce projet.</p>')}
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()


# ---------------------------------------------------------------------------
# Export du « Suivi par période » (module Suivi) : même présentation que
# l'export du suivi global (cartes, barres, historique des saisies avec cumul
# et attendu), mais limité aux saisies de la période et rapporté aux
# objectifs fixés pour la période.
# ---------------------------------------------------------------------------

STATUT_SAISIE_LABEL = {
    "NON_REALISEE": "Non réalisée", "EN_COURS": "En cours", "REALISEE": "Réalisée",
    "PLANIFIEE": "Planifiée", "TERMINEE": "Terminée",
}


def _titre_suivi(data):
    periode = data["periode"]
    dates = f"du {_fmt_date(periode['date_debut'])} au {_fmt_date(periode['date_fin'])}"
    if not periode["libelle"]:
        nom = dates
    elif _fmt_date(periode["date_debut"]) in periode["libelle"]:
        nom = periode["libelle"]  # le nom porte déjà les dates : pas de répétition
    else:
        nom = f"{periode['libelle']} — {dates}"
    return f"{v('Suivi par période — ')}{nom} — {data['projet']['code']} — {data['projet']['nom']}"


def _fenetre(element, data):
    """Fenêtre de la progression attendue : dates prévues sur la période, sinon la période entière."""
    return (
        element.get("debut_prevu") or data["periode"]["date_debut"],
        element.get("fin_prevue") or data["periode"]["date_fin"],
    )


def _historique_periode(element, data):
    """
    Saisies de la période avec cumul (dans la période), taux, attendu et écart — comme l'historique
    du suivi global. Élément suivi en avancement (%) : les quantités ne font pas le taux, pas de
    cumul ni d'attendu en quantité.
    """
    debut, fin = _fenetre(element, data)
    cible = None if _avancement(element) else element["prevu_quantite"]
    budget = element.get("prevu_budget")
    cumul = 0.0
    cumul_budget = 0.0
    lignes = []
    for s in element["saisies"]:
        cumul += float(s["quantite"] or 0)
        cumul_budget += float(s["budget"] or 0)
        attendu = valeur_attendue_a(s["periode_fin"], debut, fin, 0, cible) if cible is not None else None
        lignes.append(
            {
                **s,
                "cumul": None if _avancement(element) else cumul,
                "taux_cumul": taux_de(cumul, cible),
                "cumul_budget": cumul_budget,
                "taux_budget": taux_de(cumul_budget, budget),
                "attendu": attendu,
                "taux_attendu": taux_de(attendu, cible) if attendu is not None else None,
                "ecart": ecart_texte(cumul, attendu, element["unite"]) if attendu is not None else "",
            }
        )
    return lignes


def exporter_suivi_periode_excel(periode) -> bytes:
    data = construire_planification_periode(periode)
    aujourdhui = datetime.date.today()
    totaux = data["totaux"]
    wb = Workbook()

    resume = wb.active
    resume.title = "Résumé"
    resume.append([_titre_suivi(data)])
    resume.cell(row=1, column=1).font = Font(bold=True, size=14)
    resume.append([f"Généré le {aujourdhui.strftime('%d/%m/%Y')}"])
    resume.cell(row=2, column=1).font = Font(italic=True, color="666666")
    resume.append([NOTE_AVANCEMENT])
    resume.cell(row=3, column=1).font = Font(italic=True, color="666666")
    _entete(resume, [v('Indicateur de la période'), "Valeur"], ligne=4)
    resume.append(["Exécution physique de la période (%)", totaux["taux_physique"] if totaux["taux_physique"] is not None else "—"])
    resume.append(["Exécution financière de la période (%)", totaux["taux_financier"] if totaux["taux_financier"] is not None else "—"])
    resume.append(["Budget prévu sur la période (FCFA)", float(totaux["budget_prevu"])])
    resume.append(["Budget dépensé sur la période (FCFA)", float(totaux["budget_realise"])])
    resume.append(["Éléments avec objectifs définis", f"{totaux['nb_definis']} / {totaux['nb_elements']}"])
    _largeurs(resume, [42, 22])

    def nombre(valeur):
        return float(valeur) if valeur is not None else None

    elements = data["lignes"]
    feuille = wb.create_sheet("Activités")
    _entete(
        feuille,
        [
            "Niveau", "Code", "Libellé", "Méthode de calcul", "Unité", "Objectif période", "Réalisé période", "Taux physique (%)",
            "Attendu aujourd'hui", "Budget prévu période (FCFA)", "Budget réalisé période (FCFA)",
            "Taux financier (%)", "Statut", "Nombre de saisies",
        ],
    )
    for l in elements:
        debut, fin = _fenetre(l, data)
        attendu = (
            valeur_attendue_a(aujourdhui, debut, fin, 0, l["prevu_quantite"])
            if l["prevu_quantite"] is not None and not _avancement(l)
            else None
        )
        feuille.append(
            [
                l["niveau"], l["code"], l["libelle"], _methode(l), l["unite"],
                nombre(l["prevu_quantite"]), nombre(l["realise_quantite"]), l["taux"],
                round(attendu, 1) if attendu is not None else None,
                nombre(l.get("prevu_budget")), nombre(l.get("budget_realise")), l.get("taux_financier"),
                l["statut"], len(l["saisies"]),
            ]
        )
        feuille.cell(row=feuille.max_row, column=3).alignment = Alignment(indent=l["profondeur"], wrap_text=True)
    _largeurs(feuille, [16, 10, 46, 22, 12, 14, 14, 12, 14, 18, 18, 12, 14, 12])

    hist = wb.create_sheet("Activités — saisies")
    _entete(
        hist,
        [
            "Élément", "Période début", "Période fin", "Quantité réalisée", "Cumul période", "Taux (%)",
            "Attendu", "Écart", "Budget réalisé (FCFA)", "Cumul budget (FCFA)", "Taux financier (%)",
            "Statut", "Commentaire",
        ],
    )
    for l in elements:
        avec_budget = l["type"] == "activite"
        for h in _historique_periode(l, data):
            hist.append(
                [
                    f"{l['code']} {l['libelle']}".strip(), h["periode_debut"], h["periode_fin"],
                    nombre(h["quantite"]), h["cumul"], h["taux_cumul"],
                    round(h["attendu"], 1) if h["attendu"] is not None else None, h["ecart"],
                    nombre(h["budget"]) if avec_budget else None,
                    h["cumul_budget"] if avec_budget else None,
                    h["taux_budget"] if avec_budget else None,
                    STATUT_SAISIE_LABEL.get(h["statut"], h["statut"]), h["commentaire"],
                ]
            )
    _largeurs(hist, [40, 13, 13, 14, 13, 10, 12, 34, 16, 16, 12, 14, 34])

    indic = wb.create_sheet(v('Indicateurs'))
    _entete(indic, [v('Indicateur'), "Unité", "Cible globale", "Objectif période", "Réalisé période", "Taux (%)", "Statut"])
    for i in data["indicateurs"]:
        indic.append(
            [i["libelle"], i["unite"], nombre(i["valeur_cible"]), nombre(i["prevu_quantite"]),
             nombre(i["realise_quantite"]), i["taux"], i["statut"]]
        )
    _largeurs(indic, [50, 12, 14, 14, 14, 10, 14])

    indic_hist = wb.create_sheet(v('Indicateurs — saisies'))
    _entete(
        indic_hist,
        [v('Indicateur'), "Période début", "Période fin", "Valeur réalisée", "Cumul période", "Taux (%)", "Attendu", "Écart", "Commentaire"],
    )
    for i in data["indicateurs"]:
        for h in _historique_periode(i, data):
            indic_hist.append(
                [i["libelle"], h["periode_debut"], h["periode_fin"], nombre(h["quantite"]), h["cumul"], h["taux_cumul"],
                 round(h["attendu"], 1) if h["attendu"] is not None else None, h["ecart"], h["commentaire"]]
            )
    _largeurs(indic_hist, [50, 13, 13, 14, 13, 10, 12, 34, 34])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _bloc_suivi_periode(element, data, aujourdhui):
    unite = escape(element["unite"])
    avec_budget = element["type"] == "activite"
    cible = element["prevu_quantite"]
    debut, fin = _fenetre(element, data)
    couleur = STATUT_COULEUR.get(element["statut"], "#1c7ed6")
    est_sous = element["type"] == "sous_activite"
    retrait = max(element.get("profondeur", 1) - 1, 0) * 16

    if element["type"] == "indicateur":
        entete = f'<strong style="font-size:15px;">{escape(element["libelle"])}</strong>'
        globale = f"Cible globale : {_fmt(element['valeur_cible'])} {unite}"
    else:
        code = f'<span style="font-size:11px;color:#888;margin-right:6px;">{escape(element["code"])}</span>' if element["code"] else ""
        entete = (
            f'<span style="font-size:10px;color:#7048e8;text-transform:uppercase;margin-right:6px;">{escape(element["niveau"])}</span>'
            f'{code}<strong style="font-size:{14 if est_sous else 15}px;">{escape(element["libelle"])}</strong>'
        )
        globale = f"Global : {_fmt(element['global_quantite'])} {unite}"
        if element.get("methode"):
            globale = f"Méthode : {escape(_methode(element))} · " + globale
        if avec_budget:
            globale += f" · {_fmt(element['global_budget'], 0)} FCFA"

    if element["source"] != SOURCE_SAISIE:
        badge = _badge("Objectif non défini", "#e8590c")
        avancement = (
            f'<div style="font-size:13px;margin-top:6px;">Réalisé sur la période : '
            f"<strong>{_fmt(element['realise_quantite'])} {unite}</strong>"
            + (f" · {_fmt(element['budget_realise'], 0)} FCFA" if avec_budget else "")
            + "</div>"
        )
    elif _avancement(element):
        badge = _badge(element["statut"], couleur)
        avancement = (
            f'<div style="font-size:12px;color:#666;margin-top:4px;">Prévu sur la période : {_fmt_date(debut)} → {_fmt_date(fin)}</div>'
            f'<div style="font-size:13px;margin-top:6px;">Avancement à la fin de la période : '
            f"<strong>{_fmt(element['realise_quantite'])} % atteint pour {_fmt(cible)} % visé</strong> "
            f"({_fmt_pct(element['taux'])} de l'objectif)</div>"
            + _barre_progression(element["taux"], couleur)
        )
    else:
        badge = _badge(element["statut"], couleur)
        attendu = valeur_attendue_a(aujourdhui, debut, fin, 0, cible) if cible is not None else None
        avancement = (
            f'<div style="font-size:12px;color:#666;margin-top:4px;">Prévu sur la période : {_fmt_date(debut)} → {_fmt_date(fin)}</div>'
            f'<div style="font-size:13px;margin-top:6px;">Avancement physique : '
            f"<strong>{_fmt(element['realise_quantite'])} / {_fmt(cible)} {unite}</strong> ({_fmt_pct(element['taux'])})"
            + (f" — Attendu aujourd'hui : {_fmt(attendu, 0)} {unite}" if attendu is not None else "")
            + "</div>"
            + _barre_progression(element["taux"], couleur)
        )
        if avec_budget and element["prevu_budget"] is not None:
            attendu_budget = valeur_attendue_a(aujourdhui, debut, fin, 0, element["prevu_budget"])
            avancement += (
                f'<div style="font-size:13px;">Avancement financier : '
                f"<strong>{_fmt(element['budget_realise'], 0)} / {_fmt(element['prevu_budget'], 0)} FCFA</strong> "
                f"({_fmt_pct(element['taux_financier'])}) — Attendu aujourd'hui : {_fmt(attendu_budget, 0)} FCFA</div>"
                + _barre_progression(element["taux_financier"], "#12b886")
            )

    lignes = []
    par_quantite = not _avancement(element)
    for h in reversed(_historique_periode(element, data)):
        cellules = [f"{_fmt_date(h['periode_debut'])} → {_fmt_date(h['periode_fin'])}"]
        if par_quantite:
            cellules += [
                f"{_fmt(h['quantite'])} {unite}",
                f"{_fmt(h['cumul'])} {unite}" + (f" ({h['taux_cumul']}%)" if h["taux_cumul"] is not None else ""),
            ]
        else:
            cellules.append(STATUT_SAISIE_LABEL.get(h["statut"], h["statut"]) or "—")
        if avec_budget:
            cellules.append(f"{_fmt(h['budget'], 0)} FCFA" if h["budget"] else "—")
        if par_quantite:
            cellules.append(
                f"{_fmt(h['attendu'], 0)} {unite} ({h['taux_attendu']}%)" + (f" · {escape(h['ecart'])}" if h["ecart"] else "")
                if h["attendu"] is not None
                else "—"
            )
        cellules.append(escape(h["commentaire"]) if h["commentaire"] else "")
        tds = "".join(f'<td style="padding:4px 6px;border-bottom:1px solid #e5e5e5;">{c}</td>' for c in cellules)
        lignes.append(f"<tr>{tds}</tr>")
    entetes = (
        ["Saisie"]
        + (["Quantité", "Cumul période"] if par_quantite else ["Statut"])
        + (["Budget"] if avec_budget else [])
        + (["Attendu"] if par_quantite else [])
        + ["Commentaire"]
    )
    if lignes:
        ths = "".join(
            f'<th style="text-align:left;padding:4px 6px;border-bottom:2px solid #ccc;color:#666;font-size:11px;'
            f'text-transform:uppercase;">{e}</th>'
            for e in entetes
        )
        tableau = (
            '<table style="width:100%;border-collapse:collapse;font-size:12px;margin:6px 0 4px;">'
            f"<thead><tr>{ths}</tr></thead><tbody>{''.join(lignes)}</tbody></table>"
        )
    else:
        tableau = '<p style="color:#888;font-size:12px;margin:4px 0;">Aucune saisie sur cette période.</p>'

    bordure = "1px dashed #ccc" if est_sous else "1px solid #ddd"
    return f"""
    <div style="border:{bordure};border-radius:6px;padding:10px 14px;margin:0 0 10px {retrait}px;page-break-inside:avoid;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <span>{entete}</span>{badge}
      </div>
      <div style="font-size:12px;color:#666;margin-top:2px;">{globale}</div>
      {avancement}
      {tableau}
    </div>
    """


def exporter_suivi_periode_pdf(periode) -> bytes:
    from weasyprint import HTML

    data = construire_planification_periode(periode)
    aujourdhui = datetime.date.today()
    totaux = data["totaux"]

    activites_html = []
    for ligne in data["lignes"]:
        activites_html.append(_bloc_suivi_periode(ligne, data, aujourdhui))
    indicateurs_html = "".join(_bloc_suivi_periode(i, data, aujourdhui) for i in data["indicateurs"]) or (
        v('<p style="color:#888;">Aucun indicateur rattaché à ce projet.</p>')
    )

    def carte(titre, valeur, barre=""):
        return (
            '<div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:10px;">'
            f'<div style="font-size:11px;color:#666;text-transform:uppercase;">{titre}</div>'
            f'<div style="font-size:22px;font-weight:700;">{valeur}</div>{barre}</div>'
        )

    html_content = f"""
    <html>
    <head>
    <style>
      @page {{ size: A4; margin: 16mm 14mm; }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 13px; }}
      h2 {{ margin-bottom: 2px; font-size: 20px; }}
      h3 {{ margin-top: 22px; margin-bottom: 8px; border-bottom: 2px solid #1F4E78; padding-bottom: 4px; color: #1F4E78; font-size: 17px; }}
    </style>
    </head>
    <body>
      <h2>{escape(_titre_suivi(data))}</h2>
      <div style="color:#666;font-size:13px;margin-bottom:12px;">Généré le {aujourdhui.strftime('%d/%m/%Y')}</div>
      <div style="display:flex;gap:10px;">
        {carte("Exécution physique de la période", _fmt_pct(totaux["taux_physique"]), _barre_progression(totaux["taux_physique"], "#1c7ed6"))}
        {carte("Exécution financière de la période", _fmt_pct(totaux["taux_financier"]), _barre_progression(totaux["taux_financier"], "#12b886"))}
        {carte("Budget dépensé / prévu", f'{_fmt(totaux["budget_realise"], 0)} / {_fmt(totaux["budget_prevu"], 0)} FCFA')}
      </div>
      <h3>Activités</h3>
      {"".join(activites_html) or v('<p style="color:#888;">Aucune activité planifiée pour ce projet.</p>')}
      <h3>{v('Indicateurs')}</h3>
      {indicateurs_html}
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()
