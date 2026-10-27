"""
Export PDF de la fiche de suivi d'un projet, même contenu que l'export Excel
mais mis en page pour la lecture/l'impression — mêmes cartes, mêmes badges
d'alerte (avec les libellés/couleurs paramétrés par l'organisation) et le
même historique complet que le tableau de bord à l'écran.
"""
import datetime

from django.utils.html import escape

from apps.core.vocabulaire import v
from apps.projects.taux import libelle_methode

from .services import construire_dashboard_suivi, ecart_texte, taux_de, valeur_attendue_a

STATUT_ACTIVITE_LABEL = {"NON_REALISEE": "Non réalisée", "EN_COURS": "En cours", "REALISEE": "Réalisée"}
STATUT_SOUS_ACTIVITE_LABEL = {"PLANIFIEE": "Planifiée", "EN_COURS": "En cours", "TERMINEE": "Terminée"}
STATUT_GLOBAL_LABEL = {"EN_RETARD": "En retard", "ATTEINT": "Atteint", "EN_COURS": "En cours"}
STATUT_GLOBAL_COULEUR = {"EN_RETARD": "#d03b3b", "ATTEINT": "#0ca30c", "EN_COURS": "#fab219"}


def _fmt(valeur, decimales=1):
    """Formate un nombre (int/float/Decimal) avec séparateur de milliers,
    en supprimant les zéros décimaux superflus (250.00 -> 250, 83.3 reste 83.3)."""
    if valeur is None:
        return "—"
    nombre = float(valeur)
    if decimales == 0:
        return f"{nombre:,.0f}"
    texte = f"{nombre:,.{decimales}f}"
    return texte.rstrip("0").rstrip(".") if "." in texte else texte


def _fmt_pct(valeur):
    return "—" if valeur is None else f"{valeur}%"


def _fmt_date(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _barre_progression(taux, couleur="#1c7ed6"):
    """Barre de progression HTML/CSS simple — largeur = taux (%), plafonnée à 100 pour l'affichage
    (un dépassement de cible reste visible dans le texte à côté, pas dans la barre)."""
    pct = max(0, min(100, taux)) if taux is not None else 0
    return (
        '<div style="background:#e9ecef;border-radius:4px;height:9px;width:100%;'
        f'margin:4px 0;overflow:hidden;"><div style="background:{couleur};height:100%;'
        f'width:{pct}%;"></div></div>'
    )


def _badge(texte, couleur):
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
        f'background:{couleur}22;color:{couleur};border:1px solid {couleur}66;'
        f'font-size:12px;font-weight:600;white-space:nowrap;">{escape(texte)}</span>'
    )


def _ligne_historique(cellules):
    tds = "".join(f'<td style="padding:3px 6px;border-bottom:1px solid #e5e5e5;">{c}</td>' for c in cellules)
    return f"<tr>{tds}</tr>"


def _table_historique(entetes, lignes):
    if not lignes:
        return '<p style="color:#888;font-size:12px;margin:2px 0 10px;">Aucune saisie pour le moment.</p>'
    ths = "".join(
        f'<th style="text-align:left;padding:3px 6px;border-bottom:2px solid #ccc;color:#666;'
        f'font-size:11px;text-transform:uppercase;">{escape(e)}</th>'
        for e in entetes
    )
    corps = "".join(lignes)
    return (
        f'<table style="width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 12px;">'
        f"<thead><tr>{ths}</tr></thead><tbody>{corps}</tbody></table>"
    )


def _bloc_indicateur(indicateur, aujourdhui):
    cible = indicateur["valeur_cible"]
    depart = indicateur["valeur_reference"] or 0
    debut_p = indicateur["periode_debut_planifiee"]
    fin_p = indicateur["periode_fin_planifiee"]
    realise = indicateur["historique"][-1]["valeur_cumulee"] if indicateur["historique"] else None
    attendu = valeur_attendue_a(aujourdhui, debut_p, fin_p, depart, cible) if debut_p and fin_p else None
    palier = indicateur["palier_actuel"]
    badge = (
        _badge(f"{palier['libelle']} · {indicateur['taux_actuel']}%", palier["couleur"])
        if palier
        else _badge(f"{indicateur['taux_actuel']}%", "#666")
    )

    lignes = []
    for h in reversed(indicateur["historique"]):
        attendu_ligne = valeur_attendue_a(h["periode_fin"], debut_p, fin_p, depart, cible) if debut_p and fin_p else None
        ecart = ecart_texte(h["valeur_cumulee"], attendu_ligne, indicateur["unite"])
        lignes.append(
            _ligne_historique(
                [
                    f"{_fmt_date(h['periode_debut'])} → {_fmt_date(h['periode_fin'])}",
                    f"{_fmt(h['valeur_realisee'])} {escape(indicateur['unite'])}",
                    f"{_fmt(h['valeur_cumulee'])} {escape(indicateur['unite'])} ({h['taux']}%)",
                    (
                        f"{_fmt(attendu_ligne, 0)} {escape(indicateur['unite'])}"
                        + (f" ({taux_de(attendu_ligne, cible)}%)" if attendu_ligne is not None else "")
                        + (f" · {escape(ecart)}" if ecart else "")
                    )
                    if attendu_ligne is not None
                    else "—",
                ]
            )
        )

    planifie = f"Planifié : {_fmt_date(debut_p)} → {_fmt_date(fin_p)}" if debut_p and fin_p else "Non planifié"
    attendu_txt = (
        f"Attendu aujourd'hui : {_fmt(attendu, 0)} {escape(indicateur['unite'])} ({taux_de(attendu, cible)}%)"
        if attendu is not None
        else ""
    )

    return f"""
    <div style="border:1px solid #ddd;border-radius:6px;padding:10px 14px;margin-bottom:10px;page-break-inside:avoid;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong style="font-size:14px;">{escape(indicateur['libelle'])}</strong>
        {badge}
      </div>
      <div style="font-size:12px;color:#666;margin-top:2px;">{planifie}</div>
      <div style="font-size:13px;margin-top:4px;">
        Réalisé : <strong>{_fmt(realise)} / {_fmt(cible)} {escape(indicateur['unite'])}</strong>
        ({indicateur['taux_actuel']}%) — Référence : {_fmt(depart)} {escape(indicateur['unite'])}
        {f"<br/>{attendu_txt}" if attendu_txt else ""}
      </div>
      {_barre_progression(indicateur['taux_actuel'], palier['couleur'] if palier else '#1c7ed6')}
      {_table_historique(["Période", "Cette période", "Cumul", "Attendu"], lignes)}
    </div>
    """


def _bloc_sous_activite(sa, aujourdhui):
    cible = sa["quantite_prevue"]
    debut = sa["date_debut"]
    fin = sa["date_fin"]
    realise = sa["historique"][-1]["quantite_cumulee"] if sa["historique"] else None
    taux = taux_de(realise, cible)
    attendu = valeur_attendue_a(aujourdhui, debut, fin, 0, cible) if debut and fin and cible else None
    planifie = f"Planifié : {_fmt_date(debut)} → {_fmt_date(fin)}" if debut and fin else "Non planifié"

    lignes = []
    for h in reversed(sa["historique"]):
        cumule = h["quantite_cumulee"]
        attendu_ligne = valeur_attendue_a(h["periode_fin"], debut, fin, 0, cible) if debut and fin and cible else None
        ecart = ecart_texte(cumule, attendu_ligne, sa["unite_quantite"])
        lignes.append(
            _ligne_historique(
                [
                    f"{_fmt_date(h['periode_debut'])} → {_fmt_date(h['periode_fin'])}",
                    f"{_fmt(h['quantite_realisee'])} {escape(sa['unite_quantite'])}",
                    f"{_fmt(cumule)} {escape(sa['unite_quantite'])}" + (f" ({taux_de(cumule, cible)}%)" if cumule is not None else ""),
                    (
                        f"{_fmt(attendu_ligne, 0)} {escape(sa['unite_quantite'])}"
                        + (f" ({taux_de(attendu_ligne, cible)}%)" if attendu_ligne is not None else "")
                        + (f" · {escape(ecart)}" if ecart else "")
                    )
                    if attendu_ligne is not None
                    else "—",
                    escape(STATUT_SOUS_ACTIVITE_LABEL.get(h["statut"], h["statut"] or "")),
                ]
            )
        )

    return f"""
    <div style="border:1px dashed #ccc;border-radius:5px;padding:8px 12px;margin:6px 0 6px 16px;page-break-inside:avoid;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:13px;font-weight:600;">{escape(sa['libelle'])}</span>
        <span style="font-size:11px;color:#666;">{escape(STATUT_SOUS_ACTIVITE_LABEL.get(sa['statut'], sa['statut']))}</span>
      </div>
      <div style="font-size:12px;color:#666;">{planifie}</div>
      {f'<div style="font-size:12px;margin-top:2px;">Réalisé : <strong>{_fmt(realise)} / {_fmt(cible)} {escape(sa["unite_quantite"])}</strong> ({_fmt_pct(taux)})' + (f" — Attendu aujourd'hui : {_fmt(attendu, 0)} {escape(sa['unite_quantite'])}" if attendu is not None else "") + '</div>' + _barre_progression(taux, '#1c7ed6') if cible is not None else ""}
      {_table_historique(["Période", "Cette période", "Cumul", "Attendu", "Statut"], lignes)}
    </div>
    """


def _bloc_activite(activite, aujourdhui):
    # Taux hors quantités (tâches, jalons, livrables, binaire, manuel, agrégé) : la barre
    # suit la méthode, l'historique montre statut et budget sans quantités.
    par_quantite = activite["methode_calcul_effective"] == "QUANTITE"
    cible = activite["quantite_prevue"] if par_quantite else None
    depart = activite["valeur_reference"] or 0
    debut = activite["date_debut"]
    fin = activite["date_fin"]
    budget = activite["budget_alloue"]
    realise = activite["historique"][-1]["quantite_cumulee"] if activite["historique"] else None
    budget_realise = activite["historique"][-1]["budget_cumule"] if activite["historique"] else None
    attendu_phys = valeur_attendue_a(aujourdhui, debut, fin, depart, cible) if debut and fin and cible else None
    attendu_fin = valeur_attendue_a(aujourdhui, debut, fin, 0, budget) if debut and fin and budget else None
    planifie = f"Planifié : {_fmt_date(debut)} → {_fmt_date(fin)}" if debut and fin else "Non planifié"

    palier_activite = activite.get("palier_actuel")
    couleur_activite = palier_activite["couleur"] if palier_activite else "#1c7ed6"

    avancement = (
        f'<div style="font-size:12px;color:#666;margin-top:2px;">Méthode de calcul : '
        f"{escape(libelle_methode(activite['methode_calcul_effective']))}</div>"
    )
    if not par_quantite:
        avancement += (
            f'<div style="font-size:13px;margin-top:4px;">Avancement physique : '
            f"<strong>{_fmt_pct(activite['taux_realisation'])}</strong></div>"
            + _barre_progression(activite["taux_realisation"], couleur_activite)
        )
    if cible is not None:
        avancement += (
            f'<div style="font-size:13px;margin-top:4px;">Avancement physique : '
            f"<strong>{_fmt(realise)} / {_fmt(cible)} {escape(activite['unite_quantite'])}</strong> "
            f"({_fmt_pct(activite['taux_realisation'])})"
        )
        if attendu_phys is not None:
            avancement += f" — Attendu aujourd'hui : {_fmt(attendu_phys, 0)} {escape(activite['unite_quantite'])}"
        avancement += "</div>"
        avancement += _barre_progression(activite["taux_realisation"], couleur_activite)
    if budget is not None:
        avancement += (
            f'<div style="font-size:13px;">Avancement financier : '
            f"<strong>{_fmt(budget_realise, 0)} / {_fmt(budget, 0)} FCFA</strong> "
            f"({_fmt_pct(activite['taux_execution_financiere'])})"
        )
        if attendu_fin is not None:
            avancement += f" — Attendu aujourd'hui : {_fmt(attendu_fin, 0)} FCFA"
        avancement += "</div>"
        avancement += _barre_progression(activite["taux_execution_financiere"], "#12b886")

    lignes = []
    for h in reversed(activite["historique"]):
        if not par_quantite:
            lignes.append(
                _ligne_historique(
                    [
                        f"{_fmt_date(h['periode_debut'])} → {_fmt_date(h['periode_fin'])}",
                        f"{_fmt(h['budget_realise'], 0)} FCFA" if h["budget_realise"] else "—",
                        escape(STATUT_ACTIVITE_LABEL.get(h["statut"], h["statut"] or "")),
                        escape(h["commentaire"] or ""),
                    ]
                )
            )
            continue
        cumule = h["quantite_cumulee"]
        attendu_ligne = valeur_attendue_a(h["periode_fin"], debut, fin, depart, cible) if debut and fin and cible else None
        ecart = ecart_texte(cumule, attendu_ligne, activite["unite_quantite"])
        budget_cumule = h["budget_cumule"]
        lignes.append(
            _ligne_historique(
                [
                    f"{_fmt_date(h['periode_debut'])} → {_fmt_date(h['periode_fin'])}",
                    f"{_fmt(h['quantite_realisee'])} {escape(activite['unite_quantite'])}",
                    (f"{_fmt(cumule)} {escape(activite['unite_quantite'])}" + (f" ({taux_de(cumule, cible)}%)" if cumule is not None else "")) if cumule is not None else "—",
                    f"{_fmt(h['budget_realise'], 0)} FCFA" + (f" — cumul {_fmt(budget_cumule, 0)}" if budget_cumule is not None else "") if h["budget_realise"] else "—",
                    (
                        f"{_fmt(attendu_ligne, 0)} {escape(activite['unite_quantite'])}"
                        + (f" ({taux_de(attendu_ligne, cible)}%)" if attendu_ligne is not None else "")
                        + (f" · {escape(ecart)}" if ecart else "")
                    )
                    if attendu_ligne is not None
                    else "—",
                    escape(STATUT_ACTIVITE_LABEL.get(h["statut"], h["statut"] or "")),
                ]
            )
        )

    sous_activites_html = "".join(_bloc_sous_activite(sa, aujourdhui) for sa in activite["sous_activites"])

    return f"""
    <div style="border:1px solid #ddd;border-radius:6px;padding:10px 14px;margin-bottom:10px;page-break-inside:avoid;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>
          {f'<span style="font-size:11px;color:#888;margin-right:6px;">{escape(activite["code_activite"])}</span>' if activite["code_activite"] else ""}
          <strong style="font-size:14px;">{escape(activite['libelle'])}</strong>
        </span>
        {_badge(STATUT_ACTIVITE_LABEL.get(activite['statut'], activite['statut']), '#555')}
      </div>
      <div style="font-size:12px;color:#666;margin-top:2px;">{planifie}</div>
      {avancement}
      {_table_historique(["Période", "Quantité", "Cumul", "Budget", "Attendu", "Statut"] if par_quantite else ["Période", "Budget", "Statut", "Commentaire"], lignes)}
      {sous_activites_html}
    </div>
    """


def exporter_suivi_pdf(projet) -> bytes:
    from weasyprint import HTML

    data = construire_dashboard_suivi(projet)
    aujourdhui = datetime.date.today()

    indicateurs_html = "".join(_bloc_indicateur(i, aujourdhui) for i in data["indicateurs"]) or (
        f'<p style="color:#888;">{v("Aucun indicateur rattaché à ce projet.")}</p>'
    )
    activites_html = "".join(_bloc_activite(a, aujourdhui) for a in data["activites"]) or (
        f'<p style="color:#888;">{v("Aucune activité planifiée pour ce projet.")}</p>'
    )

    statut_global = data["statut_global"]
    html_content = f"""
    <html>
    <head>
    <style>
      @page {{ size: A4; margin: 16mm 14mm; }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 13px; }}
      h2 {{ margin-bottom: 2px; }}
      h3 {{ margin-top: 22px; margin-bottom: 8px; border-bottom: 2px solid #1F4E78; padding-bottom: 4px; color: #1F4E78; }}
    </style>
    </head>
    <body>
      <h2>{v('Suivi')} — {escape(data['projet']['nom'])}</h2>
      <div style="color:#666;font-size:13px;margin-bottom:12px;">
        {escape(data['projet']['code'])} · généré le {aujourdhui.strftime('%d/%m/%Y')}
      </div>

      <div style="display:flex;gap:10px;">
        <div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:10px;">
          <div style="font-size:11px;color:#666;text-transform:uppercase;">Exécution physique globale</div>
          <div style="font-size:22px;font-weight:700;">{_fmt_pct(data['taux_execution_physique_global'])}</div>
          {_barre_progression(data['taux_execution_physique_global'], '#1c7ed6')}
        </div>
        <div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:10px;">
          <div style="font-size:11px;color:#666;text-transform:uppercase;">Exécution financière globale</div>
          <div style="font-size:22px;font-weight:700;">{_fmt_pct(data['taux_execution_financiere_global'])}</div>
          {_barre_progression(data['taux_execution_financiere_global'], '#12b886')}
        </div>
        <div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:10px;">
          <div style="font-size:11px;color:#666;text-transform:uppercase;">Statut global</div>
          <div style="font-size:16px;font-weight:700;margin-top:4px;">
            {_badge(STATUT_GLOBAL_LABEL.get(statut_global, statut_global), STATUT_GLOBAL_COULEUR.get(statut_global, '#666'))}
          </div>
        </div>
      </div>

      <h3>Activités</h3>
      {activites_html}

      <h3>{v('Indicateurs')}</h3>
      {indicateurs_html}
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()
