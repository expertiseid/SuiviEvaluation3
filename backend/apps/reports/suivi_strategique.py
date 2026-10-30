"""Rapport de suivi d'un document stratégique (PDF et Word) : par élément, calcul et renseignement."""
import datetime

from django.utils.html import escape

from apps.core.vocabulaire import v

ETATS = {"BON": ("Bonne progression", "#2f9e44"), "MOYEN": ("Progression moyenne", "#f59f00"), "INSUFFISANT": ("Progression insuffisante", "#c92a2a")}


def _pct(v):
    return "—" if v is None else f"{v:.1f} %".replace(".", ",")


def _nombre(v):
    return "—" if v is None else f"{float(v):,.2f}".replace(",", " ").rstrip("0").rstrip(".").replace(".", ",")


def html_suivi_strategique(cadre, projets_visibles) -> str:
    from apps.strategy.models import ElementStrategique
    from apps.strategy.chaine import activites_rattachees
    from apps.strategy.suivi import contribution_projets, indicateurs_element

    elements = list(ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre).select_related("type_niveau"))
    enfants = {}
    for e in elements:
        enfants.setdefault(e.element_parent_id, []).append(e)
    ids = {e.id for e in elements}
    arbres = {}
    rattachees = activites_rattachees(cadre, projets_visibles)
    td = 'style="padding:4px 6px;border:1px solid #d0d7de;font-size:10px;vertical-align:top;"'
    th = 'style="text-align:left;padding:4px 6px;background:#DCE6F1;color:#1F4E78;font-size:10px;border:1px solid #d0d7de;"'
    blocs = []

    def bloc(e, profondeur):
        calcule = contribution_projets(e, projets_visibles, arbres, rattachees)
        indicateurs = indicateurs_element(e)
        derniere = e.appreciations.order_by("-periode_fin", "-id").first()
        projets = ", ".join(p["code"] for p in calcule["projets"]) or v("aucun projet")
        lignes_ind = "".join(
            f"<tr><td {td}>{escape(i['libelle'])}<div style='color:#666;'>{escape(i['origine'])}</div></td>"
            f"<td {td}>{_nombre(i['valeur_reference'])}</td><td {td}>{_nombre(i['valeur_cible'])} {escape(i['unite'])}</td>"
            f"<td {td}>{_nombre(i['realise'])}</td><td {td}>{_pct(i['taux'])}</td></tr>"
            for i in indicateurs
        )
        tableau = (
            f'<table style="width:100%;border-collapse:collapse;margin:4px 0;"><thead><tr><th {th} width="50%">Indicateur</th>'
            f"<th {th}>Référence</th><th {th}>Cible</th><th {th}>Réalisé</th><th {th}>Taux</th></tr></thead><tbody>{lignes_ind}</tbody></table>"
            if indicateurs else ""
        )
        if derniere:
            libelle, couleur = ETATS[derniere.etat]
            periode = derniere.libelle_periode or f"{derniere.periode_debut:%d/%m/%Y} → {derniere.periode_fin:%d/%m/%Y}"
            appreciation = (
                f'<div style="margin-top:4px;padding:5px 8px;border-left:3px solid {couleur};background:#f8f9fa;font-size:11px;">'
                f'<strong>{escape(periode)}</strong> — <span style="color:{couleur};font-weight:700;">{libelle}</span>'
                + (f"<div>{escape(derniere.commentaire)}</div>" if derniere.commentaire else "")
                + (f"<div><strong>Difficultés :</strong> {escape(derniere.difficultes)}</div>" if derniere.difficultes else "")
                + (f"<div><strong>Recommandations :</strong> {escape(derniere.recommandations)}</div>" if derniere.recommandations else "")
                + "</div>"
            )
        else:
            appreciation = '<div style="color:#888;font-size:11px;">Pas encore d\'appréciation.</div>'
        titre = "h3" if profondeur == 0 else "h4"
        blocs.append(
            f'<div style="margin-left:{profondeur * 12}px;page-break-inside:avoid;">'
            f'<{titre} style="margin:12px 0 2px;color:#1F4E78;"><span style="font-size:10px;color:#7048e8;margin-right:6px;">{escape(e.type_niveau.nom_niveau)}</span>'
            f"{escape((e.code + ' ') if e.code else '')}{escape(e.nom)}</{titre}>"
            f'<div style="font-size:11px;color:#444;">Calculé depuis les projets ({escape(projets)}) : exécution physique {_pct(calcule["taux_physique"])}, '
            f'financière {_pct(calcule["taux_financier"])} ({_nombre(calcule["budget_realise"])} / {_nombre(calcule["budget_alloue"])} FCFA)</div>'
            f"{tableau}{appreciation}</div>"
        )
        for enfant in enfants.get(e.id, []):
            bloc(enfant, profondeur + 1)

    for racine in [e for e in elements if e.element_parent_id is None or e.element_parent_id not in ids]:
        bloc(racine, 0)
    return f"""
    <html><head><style>
      @page {{ size: A4; margin: 15mm 13mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; font-size: 11px; }}
    </style></head>
    <body>
      <h2 style="margin-bottom:2px;">Suivi du document stratégique — {escape(cadre.nom)}</h2>
      <div style="color:#666;margin-bottom:8px;">Généré le {datetime.date.today().strftime('%d/%m/%Y')}</div>
      {''.join(blocs) or '<p>Aucun élément.</p>'}
    </body></html>
    """
