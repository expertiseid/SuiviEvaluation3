"""Registre des risques d'un projet (PDF et Word) : matrice probabilité × impact, registre, suivi."""
import datetime

from django.utils.html import escape

from apps.core.vocabulaire import v

NIVEAUX = {
    "CRITIQUE": ("Critique", "#c92a2a"),
    "ELEVE": ("Élevé", "#e8590c"),
    "MOYEN": ("Moyen", "#f59f00"),
    "FAIBLE": ("Faible", "#2f9e44"),
}
STATUTS = {"ACTIF": "Actif", "SURVENU": "Survenu", "MAITRISE": "Maîtrisé", "CLOS": "Clos"}


def _date(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _pastille(niveau):
    libelle, couleur = NIVEAUX[niveau]
    return (
        f'<span style="display:inline-block;padding:1px 8px;border-radius:9px;background:{couleur}22;'
        f'color:{couleur};border:1px solid {couleur}66;font-weight:600;font-size:10px;">{libelle}</span>'
    )


def html_registre_risques(projet) -> str:
    from apps.projects.models import Risque

    risques = list(
        Risque.objects.filter(projet=projet).select_related("responsable", "element").prefetch_related("evaluations__saisi_par")
    )
    risques.sort(key=lambda r: (r.statut in ("CLOS", "MAITRISE"), -r.criticite, r.code))
    td = 'style="padding:5px 6px;border:1px solid #d0d7de;vertical-align:top;font-size:10px;"'
    th = 'style="text-align:left;padding:6px;background:#1F4E78;color:#fff;font-size:10px;border:1px solid #1F4E78;"'

    # Résumé par niveau (risques encore ouverts).
    ouverts = [r for r in risques if r.statut in ("ACTIF", "SURVENU")]
    resume = " · ".join(
        f"{sum(1 for r in ouverts if r.niveau == cle)} {v(libelle).lower()}" for cle, (libelle, _c) in NIVEAUX.items()
    )

    # Matrice : impact en colonnes, probabilité en lignes (5 en haut).
    cases = []
    for p in range(5, 0, -1):
        cellules = [f'<td {td}><strong>{p}</strong></td>']
        for i in range(1, 6):
            couleur = NIVEAUX[Risque.niveau_pour(p * i)][1]
            codes = ", ".join(r.code for r in ouverts if r.probabilite == p and r.impact == i)
            cellules.append(
                f'<td style="width:17%;height:26px;text-align:center;font-size:10px;font-weight:700;border:1px solid #fff;'
                f'background:{couleur}33;color:#222;">{escape(codes)}</td>'
            )
        cases.append(f"<tr>{''.join(cellules)}</tr>")
    entete_impact = "".join(f'<td style="text-align:center;font-size:10px;font-weight:700;">{i}</td>' for i in range(1, 6))
    matrice = (
        '<table style="border-collapse:collapse;width:60%;margin:6px 0 4px;">'
        + "".join(cases)
        + f'<tr><td></td>{entete_impact}</tr></table>'
        + '<div style="font-size:10px;color:#666;margin-bottom:12px;">Lignes : probabilité (1 rare → 5 quasi certain) · '
        "colonnes : impact (1 négligeable → 5 majeur). Risques actifs ou survenus.</div>"
    )

    lignes = []
    for r in risques:
        responsable = str(r.responsable) if r.responsable else "—"
        element = f"<div style='color:#666;'>Élément : {escape(r.element.libelle)}</div>" if r.element else ""
        lignes.append(
            f"<tr><td {td}><strong>{escape(r.code)}</strong></td>"
            f"<td {td}><strong>{escape(r.libelle)}</strong><div>{escape(r.description)}</div>{element}</td>"
            f"<td {td}>{'Interne' if r.nature == 'INTERNE' else 'Externe'}<div style='color:#666;'>{escape(r.categorie)}</div></td>"
            f"<td {td}>P{r.probabilite} × I{r.impact} = {r.criticite}<div>{_pastille(r.niveau)}</div></td>"
            f"<td {td}>{escape(r.mesures_attenuation) or '—'}"
            + (f"<div style='color:#666;margin-top:3px;'>Si survenu : {escape(r.plan_contingence)}</div>" if r.plan_contingence else "")
            + f"</td><td {td}>{escape(responsable)}</td><td {td}>{STATUTS.get(r.statut, r.statut)}"
            f"<div style='color:#666;'>Revue : {_date(r.date_prochaine_revue)}</div></td></tr>"
        )
    corps_registre = "".join(lignes) or f'<tr><td {td} colspan="7">Aucun risque identifié.</td></tr>'
    registre = (
        f'<table style="width:100%;border-collapse:collapse;"><thead><tr><th {th}>Code</th><th {th} width="28%">Risque</th>'
        f"<th {th}>Nature</th><th {th}>Cotation</th><th {th} width='26%'>Mesures d'atténuation</th><th {th}>Responsable</th>"
        f"<th {th}>Statut</th></tr></thead><tbody>{corps_registre}</tbody></table>"
    )

    suivis = []
    for r in risques:
        evaluations = list(r.evaluations.all())
        if not evaluations:
            continue
        rangs = "".join(
            f"<tr><td {td}>{_date(e.date)}</td><td {td}>P{e.probabilite} × I{e.impact} "
            f"{_pastille(Risque.niveau_pour(e.probabilite * e.impact))}</td><td {td}>{STATUTS.get(e.statut, e.statut)}</td>"
            f"<td {td}>{escape(e.actions_menees) or '—'}</td><td {td}>{escape(e.commentaire) or '—'}</td></tr>"
            for e in evaluations
        )
        suivis.append(
            f"<h4 style='margin:10px 0 4px;'>{escape(r.code)} — {escape(r.libelle)}</h4>"
            f'<table style="width:100%;border-collapse:collapse;"><thead><tr><th {th}>Date</th><th {th}>Cotation</th>'
            f"<th {th}>Statut</th><th {th}>Actions menées</th><th {th}>Commentaire</th></tr></thead><tbody>{rangs}</tbody></table>"
        )

    return f"""
    <html><head><style>
      @page {{ size: A4 landscape; margin: 12mm 10mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 11px; }}
      h3 {{ margin-top: 16px; margin-bottom: 6px; border-bottom: 2px solid #1F4E78; padding-bottom: 3px; color: #1F4E78; }}
      tr {{ page-break-inside: avoid; }}
      thead {{ display: table-header-group; }}
    </style></head>
    <body>
      <h2 style="margin-bottom:2px;">Registre des risques — {escape(projet.nom)}</h2>
      <div style="color:#666;margin-bottom:8px;">{escape(projet.code)} · {len(risques)} risque(s), dont ouverts : {resume} · généré le {datetime.date.today().strftime('%d/%m/%Y')}</div>
      <h3>Matrice des risques</h3>{matrice}
      <h3>Registre</h3>{registre}
      {'<h3>Suivi des réévaluations</h3>' + ''.join(suivis) if suivis else ''}
    </body></html>
    """
