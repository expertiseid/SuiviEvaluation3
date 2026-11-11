"""
Cadre logique d'un projet : matrice logique d'intervention / indicateurs (référence, cible,
réalisé) / sources de vérification / hypothèses, construite depuis la planification (chaque
niveau librement nommé est une ligne) et les indicateurs qui y sont rattachés. Les indicateurs
rattachés au projet lui-même forment la première ligne.
"""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.html import escape

from apps.core.langues import traduire_modele
from apps.core.vocabulaire import v
from apps.projects.attributs import ordonner


def _nombre(valeur):
    if valeur is None:
        return None
    return float(valeur)


def _indicateur(indicateur, realises):
    from apps.indicators.services import taux_realisation

    realise = realises.get(indicateur.id, Decimal("0"))
    return {
        "id": indicateur.id,
        "libelle": indicateur.libelle,
        "unite": indicateur.unite,
        "reference": _nombre(indicateur.valeur_reference),
        "cible": _nombre(indicateur.valeur_cible),
        "realise": _nombre(realise),
        "taux": taux_realisation(realise, indicateur.valeur_cible) if indicateur.valeur_cible else None,
    }


def construire_cadre_logique(projet, masquees=frozenset()) -> dict:
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.projects.models import Activite, NiveauActivite
    from apps.projects.taux import ArbreTaux

    # Éléments masqués à l'utilisateur (apps.core.masquage) et leurs indicateurs : absents.
    activites = list(Activite.objects.filter(projet=projet).exclude(id__in=masquees).order_by("id"))
    indicateurs = list(Indicateur.objects.filter(projet=projet)) + list(
        Indicateur.objects.filter(activite__projet=projet).exclude(activite_id__in=masquees).order_by("id")
    )
    # Saisies approuvées uniquement (manager par défaut).
    realises = dict(
        ValeurIndicateur.objects.filter(indicateur__in=indicateurs)
        .values("indicateur").annotate(t=Sum("valeur_realisee")).values_list("indicateur", "t")
    )
    par_activite = defaultdict(list)
    for i in indicateurs:
        if i.activite_id:
            par_activite[i.activite_id].append(_indicateur(i, realises))
    noms_niveaux = {n.profondeur: n.nom_niveau for n in NiveauActivite.objects.filter(projet=projet)}
    enfants = defaultdict(list)
    for a in activites:
        enfants[a.activite_parent_id].append(a)
    arbre = ArbreTaux(projet)

    lignes = []
    indicateurs_projet = [_indicateur(i, realises) for i in indicateurs if i.projet_id]
    if indicateurs_projet:
        lignes.append({
            "id": None, "profondeur": 0, "niveau": v("Projet"), "code": projet.code, "libelle": projet.nom,
            "description": "", "indicateurs": indicateurs_projet, "sources_verification": "", "hypotheses": "",
            "attributs": {}, "avancement": arbre.taux_projet().taux,
        })

    def parcourir(activite, profondeur):
        lignes.append({
            "id": activite.id,
            "profondeur": profondeur,
            "niveau": noms_niveaux.get(profondeur, "Activité"),
            "code": activite.code_activite,
            "libelle": activite.libelle,
            "description": activite.description,
            "indicateurs": par_activite.get(activite.id, []),
            "sources_verification": activite.sources_verification,
            "hypotheses": activite.hypotheses,
            "attributs": {n: activite.attributs[n] for n in ordonner(activite.attributs or {}, projet.ordre_attributs)},
            "avancement": arbre.resultat(activite.id).taux,
        })
        for enfant in enfants.get(activite.id, []):
            parcourir(enfant, profondeur + 1)

    for racine in enfants.get(None, []):
        parcourir(racine, 0)
    return {"projet": {"id": projet.id, "code": projet.code, "nom": projet.nom}, "lignes": lignes}


def _fmt(valeur):
    if valeur is None:
        return "—"
    texte = f"{valeur:,.2f}".replace(",", " ").rstrip("0").rstrip(".")
    return texte.replace(".", ",")


# Couleurs par profondeur (bandeau de gauche), comme l'arbre de planification à l'écran.
COULEURS = ["#0c8a5f", "#1c7ed6", "#7048e8", "#e8590c", "#c2255c", "#495057"]


def _pct(valeur):
    return "" if valeur is None else f"{valeur:.1f} %".replace(".", ",")


def _cellule_indicateurs(indicateurs):
    if not indicateurs:
        return VIDE
    blocs = []
    for i in indicateurs:
        taux = f" ({_pct(i['taux'])})" if i["taux"] is not None else ""
        blocs.append(
            f'<div style="margin-bottom:5px;"><div>{escape(i["libelle"])}</div>'
            f'<div style="color:#555;font-size:10px;">Réf. {_fmt(i["reference"])} · Cible {_fmt(i["cible"])} {escape(i["unite"])} · '
            f"<strong>{traduire_modele('Réalisé {0}', _fmt(i['realise']))}</strong>{taux}</div></div>"
        )
    return "".join(blocs)


VIDE = '<span style="color:#aaa;">—</span>'


def _attributs(attributs):
    """Attributs libres de l'élément (« Responsable : … »), sous son libellé."""
    return "".join(
        f'<div style="font-size:9px;color:#555;">{escape(nom)} : <strong>{escape(valeur)}</strong></div>'
        for nom, valeur in (attributs or {}).items()
    )


def html_cadre_logique(data) -> str:
    td = 'style="padding:6px 8px;border:1px solid #d0d7de;vertical-align:top;font-size:11px;"'
    lignes = []
    for l in data["lignes"]:
        couleur = COULEURS[min(l["profondeur"], len(COULEURS) - 1)] if l["id"] else "#1F4E78"
        code = f'<span style="margin-right:4px;color:#888;">{escape(l["code"])}</span>' if l["code"] else ""
        avancement = (
            f'<div style="color:#555;font-size:10px;margin-top:3px;">Avancement : {_pct(l["avancement"])}</div>'
            if l["avancement"] is not None else ""
        )
        style_logique = (
            f'style="padding:6px 8px 6px {8 + l["profondeur"] * 10}px;border:1px solid #d0d7de;'
            f'border-left:4px solid {couleur};vertical-align:top;font-size:11px;"'
        )
        lignes.append(
            f"<tr><td {style_logique}>"
            f'<div style="font-size:9px;color:{couleur};font-weight:700;text-transform:uppercase;">{escape(l["niveau"])}</div>'
            f'<div style="font-weight:{700 if l["profondeur"] == 0 else 500};">{code}{escape(l["libelle"])}</div>'
            f"{_attributs(l['attributs'])}{avancement}</td>"
            f"<td {td}>{_cellule_indicateurs(l['indicateurs'])}</td>"
            f"<td {td}>{escape(l['sources_verification']) or VIDE}</td>"
            f"<td {td}>{escape(l['hypotheses']) or VIDE}</td></tr>"
        )
    th = 'style="text-align:left;padding:7px 8px;background:#1F4E78;color:#fff;font-size:11px;border:1px solid #1F4E78;"'
    corps = "".join(lignes) or f'<tr><td colspan="4" {td}>{v("Aucune activité planifiée pour ce projet.")}</td></tr>'
    return f"""
    <html><head><style>
      @page {{ size: A4 landscape; margin: 12mm 10mm; @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 9px; color: #888; }} }}
      body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #222; }}
      tr {{ page-break-inside: avoid; }}
      thead {{ display: table-header-group; }}
    </style></head>
    <body>
      <h2 style="margin-bottom:2px;">Cadre logique — {escape(data['projet']['nom'])}</h2>
      <div style="color:#666;font-size:11px;margin-bottom:10px;">{escape(data['projet']['code'])} · généré le {datetime.date.today().strftime('%d/%m/%Y')}</div>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr>
          <th {th} width="30%">Logique d'intervention</th><th {th} width="34%">Indicateurs (référence, cible, réalisé)</th>
          <th {th} width="18%">Sources de vérification</th><th {th} width="18%">Hypothèses / risques</th>
        </tr></thead>
        <tbody>{corps}</tbody>
      </table>
    </body></html>
    """
