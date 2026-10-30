"""
Exports Word (.docx) du suivi d'un projet et du suivi par période, mis en page pour Word.

Les exports PDF reposent sur des cartes encadrées (une par élément) que Word ne sait pas
reproduire : converties telles quelles, elles donnaient une longue suite de paragraphes sans
structure. Ici, le même contenu est présenté en tableaux — résumé chiffré, activités (bandeaux
de couleur par niveau, sous-activités), historique des saisies, indicateurs — en paysage, avec
les nombres au format français. Le HTML produit passe par apps.reports.word.html_vers_docx.
"""
import datetime

from django.utils.html import escape

from apps.core.vocabulaire import v

# Bandeaux par niveau (comme le tableau de la planification) et en-têtes.
FONDS_NIVEAUX = ["#A5D8FF", "#D0EBFF", "#E7F5FF", "#F1F8FF"]
FOND_ENTETE = "#DCE6F1"
STATUT_ACTIVITE = {"NON_REALISEE": "Non réalisée", "EN_COURS": "En cours", "REALISEE": "Réalisée"}
STATUT_SOUS_ACTIVITE = {"PLANIFIEE": "Planifiée", "EN_COURS": "En cours", "TERMINEE": "Terminée"}
STATUT_GLOBAL = {"EN_RETARD": "En retard", "ATTEINT": "Atteint", "EN_COURS": "En cours"}


def _nb(x, decimales=0) -> str:
    """Nombre au format français : espace pour les milliers, virgule décimale, sans zéros inutiles."""
    if x is None or x == "":
        return "—"
    texte = f"{float(x):,.{decimales}f}".replace(",", " ").replace(".", ",")
    if "," in texte:
        texte = texte.rstrip("0").rstrip(",")
    return texte


def _pct(x) -> str:
    return "—" if x is None else f"{_nb(x, 1)} %"


def _date(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d[:10])
    return d.strftime("%d/%m/%Y")


def _periode(debut, fin) -> str:
    return f"{_date(debut)} → {_date(fin)}" if debut or fin else "—"


def _tableau(entetes, lignes, largeurs=None) -> str:
    """Tableau : en-têtes ombrés ; ligne = (cellules, fond, gras) ; largeurs des colonnes en %."""
    largeurs = largeurs or [round(100 / len(entetes), 1)] * len(entetes)
    ths = "".join(
        f'<th style="background:{FOND_ENTETE};width:{l}%;">{escape(e)}</th>' for e, l in zip(entetes, largeurs)
    )
    corps = []
    for cellules, fond, gras in lignes:
        style = (f"background:{fond};" if fond else "") + ("font-weight:700;" if gras else "")
        corps.append("<tr>" + "".join(f'<td style="{style}">{c}</td>' for c in cellules) + "</tr>")
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(corps)}</tbody></table>"


def _page(titre, sous_titre, contenu) -> str:
    return f"""
    <html><head><style>@page {{ size: A4 landscape; }}</style></head><body>
      <h2>{escape(titre)}</h2>
      <p style="color:#666666;">{escape(sous_titre)}</p>
      {contenu}
    </body></html>"""


def _profondeurs(projet) -> tuple[dict, dict]:
    """(profondeur par élément, nom du niveau par profondeur) de la planification du projet."""
    from apps.projects.models import Activite, NiveauActivite

    parents = dict(Activite.objects.filter(projet=projet).values_list("id", "activite_parent_id"))

    def profondeur(i):
        p, n = 0, parents.get(i)
        while n is not None:
            p, n = p + 1, parents.get(n)
        return p

    noms = dict(NiveauActivite.objects.filter(projet=projet).values_list("profondeur", "nom_niveau"))
    return {i: profondeur(i) for i in parents}, noms


# --- Suivi du projet ------------------------------------------------------------------------

def html_suivi_word(projet) -> str:
    from apps.projects.models import Activite
    from apps.projects.taux import libelle_methode

    from .services import construire_dashboard_suivi, taux_de

    data = construire_dashboard_suivi(projet)
    profondeurs, noms_niveaux = _profondeurs(projet)
    groupes = set(Activite.objects.filter(projet=projet, enfants__isnull=False).values_list("id", flat=True))
    aujourdhui = datetime.date.today()

    resume = _tableau(
        [v("Exécution physique globale"), v("Exécution financière globale"), v("Statut global")],
        [([_pct(data["taux_execution_physique_global"]), _pct(data["taux_execution_financiere_global"]),
           escape(STATUT_GLOBAL.get(data["statut_global"], data["statut_global"] or ""))], None, True)],
    )

    lignes, saisies = [], []
    for a in data["activites"]:
        profondeur = profondeurs.get(a["id"], 0)
        groupe = a["id"] in groupes
        dernier = a["historique"][-1] if a["historique"] else None
        par_quantite = a["methode_calcul_effective"] == "QUANTITE"
        unite = escape(a["unite_quantite"] or "")
        physique = (f"{_nb(dernier['quantite_cumulee'] if dernier else None, 2)} / {_nb(a['quantite_prevue'], 2)} {unite}"
                    if par_quantite and a["quantite_prevue"] is not None else "")
        financier = (f"{_nb(dernier['budget_cumule'] if dernier else None)} / {_nb(a['budget_alloue'])}"
                     if a["budget_alloue"] is not None else "")
        attributs = " · ".join(f"{escape(k)} : {escape(str(x))}" for k, x in (a.get("attributs") or {}).items())
        libelle = escape(a["libelle"]) + (f'<br/><span style="color:#666666;font-size:11px;">{attributs}</span>' if attributs else "")
        lignes.append(([
            escape(a["code_activite"] or ""), escape(noms_niveaux.get(profondeur, "Activité")), libelle,
            _periode(a["date_debut"], a["date_fin"]), escape(libelle_methode(a["methode_calcul_effective"])),
            physique, _pct(a["taux_realisation"]), financier, _pct(a["taux_execution_financiere"]),
            escape(STATUT_ACTIVITE.get(a["statut"], a["statut"] or "")),
        ], FONDS_NIVEAUX[min(profondeur, len(FONDS_NIVEAUX) - 1)] if groupe else None, groupe))
        for h in a["historique"]:
            saisies.append(([
                escape(a["code_activite"] or ""), escape(a["libelle"]), _periode(h["periode_debut"], h["periode_fin"]),
                f"{_nb(h['quantite_realisee'], 2)} {unite}" if h.get("quantite_realisee") is not None else "—",
                f"{_nb(h['quantite_cumulee'], 2)} {unite}" if h.get("quantite_cumulee") is not None else "—",
                _nb(h["budget_realise"]) if h.get("budget_realise") else "—",
                escape(STATUT_ACTIVITE.get(h["statut"], h["statut"] or "")), escape(h.get("commentaire") or ""),
            ], None, False))
        for sa in a["sous_activites"]:
            dernier_sa = sa["historique"][-1] if sa["historique"] else None
            unite_sa = escape(sa["unite_quantite"] or "")
            realise_sa = dernier_sa["quantite_cumulee"] if dernier_sa else None
            lignes.append(([
                "", escape(v("Sous-activité")), f'<span style="font-style:italic;">{escape(sa["libelle"])}</span>',
                _periode(sa["date_debut"], sa["date_fin"]), "",
                f"{_nb(realise_sa, 2)} / {_nb(sa['quantite_prevue'], 2)} {unite_sa}" if sa["quantite_prevue"] is not None else "",
                _pct(taux_de(realise_sa, sa["quantite_prevue"])), "", "",
                escape(STATUT_SOUS_ACTIVITE.get(sa["statut"], sa["statut"] or "")),
            ], None, False))
            for h in sa["historique"]:
                saisies.append(([
                    "", escape(sa["libelle"]), _periode(h["periode_debut"], h["periode_fin"]),
                    f"{_nb(h['quantite_realisee'], 2)} {unite_sa}" if h.get("quantite_realisee") is not None else "—",
                    f"{_nb(h['quantite_cumulee'], 2)} {unite_sa}" if h.get("quantite_cumulee") is not None else "—",
                    "—", escape(STATUT_SOUS_ACTIVITE.get(h["statut"], h["statut"] or "")), escape(h.get("commentaire") or ""),
                ], None, False))

    activites = _tableau(
        [v("Code"), v("Niveau"), v("Élément"), v("Planifié"), v("Méthode de calcul"), v("Réalisé / prévu"),
         v("Taux physique"), v("Dépensé / budget (FCFA)"), v("Taux financier"), v("Statut")],
        lignes,
        [6, 9, 25, 10, 10, 11, 7, 11, 6, 5],
    ) if lignes else f"<p>{v('Aucune activité planifiée pour ce projet.')}</p>"
    historique = _tableau(
        [v("Code"), v("Élément"), v("Période"), v("Quantité"), v("Cumul"), v("Budget (FCFA)"), v("Statut"), v("Commentaire")],
        saisies,
        [6, 28, 13, 10, 10, 10, 8, 15],
    ) if saisies else f"<p>{v('Aucune saisie pour le moment.')}</p>"

    lignes_ind, saisies_ind = [], []
    for i in data["indicateurs"]:
        unite = escape(i["unite"] or "")
        realise = i["historique"][-1]["valeur_cumulee"] if i["historique"] else None
        palier = i["palier_actuel"]
        lignes_ind.append(([
            escape(i["libelle"]), _periode(i["periode_debut_planifiee"], i["periode_fin_planifiee"]),
            f"{_nb(i['valeur_reference'], 2)} {unite}", f"{_nb(i['valeur_cible'], 2)} {unite}",
            f"{_nb(realise, 2)} {unite}", _pct(i["taux_actuel"]), escape(palier["libelle"]) if palier else "",
        ], None, False))
        for h in i["historique"]:
            saisies_ind.append(([
                escape(i["libelle"]), _periode(h["periode_debut"], h["periode_fin"]),
                f"{_nb(h['valeur_realisee'], 2)} {unite}", f"{_nb(h['valeur_cumulee'], 2)} {unite}", _pct(h.get("taux")),
            ], None, False))
    indicateurs = _tableau(
        [v("Indicateur"), v("Planifié"), v("Référence"), v("Cible"), v("Réalisé"), v("Taux"), v("Niveau d'alerte")], lignes_ind,
        [34, 14, 11, 11, 11, 7, 12],
    ) if lignes_ind else f"<p>{v('Aucun indicateur rattaché à ce projet.')}</p>"
    if saisies_ind:
        indicateurs += f"<h4>{v('Valeurs saisies')}</h4>" + _tableau(
            [v("Indicateur"), v("Période"), v("Valeur de la période"), v("Cumul"), v("Taux")], saisies_ind, [40, 18, 15, 15, 12])

    contenu = (f"{resume}<h3>{v('Activités')}</h3>{activites}<h3>{v('Historique des saisies')}</h3>{historique}"
               f"<h3>{v('Indicateurs')}</h3>{indicateurs}")
    return _page(f"{v('Suivi')} — {projet.nom}", f"{projet.code} · {v('généré le')} {aujourdhui:%d/%m/%Y}", contenu)


# --- Suivi par période ----------------------------------------------------------------------

def html_suivi_periode_word(periode) -> str:
    from .export_periode import _titre_suivi
    from .services import construire_planification_periode

    data = construire_planification_periode(periode)
    totaux = data["totaux"]
    aujourdhui = datetime.date.today()

    resume = _tableau(
        [v("Exécution physique de la période"), v("Exécution financière de la période"), v("Budget dépensé / prévu (FCFA)"),
         v("Éléments avec objectifs définis")],
        [([_pct(totaux["taux_physique"]), _pct(totaux["taux_financier"]),
           f"{_nb(totaux['budget_realise'])} / {_nb(totaux['budget_prevu'])}", f"{totaux['nb_definis']} / {totaux['nb_elements']}"],
          None, True)],
    )

    parents = {l["parent_id"] for l in data["lignes"] if l["type"] == "activite"}
    lignes, saisies = [], []
    for l in data["lignes"]:
        activite = l["type"] == "activite"
        groupe = activite and l["id"] in parents
        avancement = l["mode"] == "avancement"
        unite = "%" if avancement else escape(l["unite"] or "")
        defini = l["source"] == "saisi"
        libelle = escape(l["libelle"]) if activite else f'<span style="font-style:italic;">{escape(l["libelle"])}</span>'
        lignes.append(([
            escape(l["code"] or ""), escape(l["niveau"] if activite else v("Sous-activité")), libelle, unite,
            _nb(l["prevu_quantite"], 2) if defini else escape(v("À définir")), _periode(l["debut_prevu"], l["fin_prevue"]) if defini else "",
            _nb(l["realise_quantite"], 2), _pct(l["taux"]),
            (_nb(l["prevu_budget"]) if defini else "") if activite else "", _nb(l["budget_realise"]) if activite else "",
            _pct(l["taux_financier"]) if activite else "", escape(v(l["statut"])),
        ], FONDS_NIVEAUX[min(l["profondeur"], len(FONDS_NIVEAUX) - 1)] if groupe else None, groupe))
        for s in l["saisies"]:
            saisies.append(([
                escape(l["code"] or ""), escape(l["libelle"]), _periode(s["periode_debut"], s["periode_fin"]),
                f"{_nb(s['quantite'], 2)} {unite}" if s["quantite"] is not None else "—",
                _nb(s["budget"]) if s["budget"] else "—", escape(v(s["statut"] or "")), escape(s["commentaire"] or ""),
            ], None, False))

    activites = _tableau(
        [v("Code"), v("Niveau"), v("Élément"), v("Unité"), v("Objectif"), v("Prévu sur la période"), v("Réalisé"), v("Taux"),
         v("Budget prévu"), v("Dépensé"), v("Taux financier"), v("Statut")],
        lignes,
        [6, 9, 22, 7, 7, 11, 7, 6, 8, 8, 5, 4],
    ) if lignes else f"<p>{v('Aucune activité planifiée pour ce projet.')}</p>"
    historique = _tableau(
        [v("Code"), v("Élément"), v("Saisie"), v("Quantité"), v("Budget (FCFA)"), v("Statut"), v("Commentaire")], saisies,
        [6, 30, 14, 11, 11, 9, 19],
    ) if saisies else f"<p>{v('Aucune saisie sur cette période.')}</p>"
    indicateurs = _tableau(
        [v("Indicateur"), v("Unité"), v("Cible globale"), v("Objectif"), v("Réalisé"), v("Taux"), v("Statut")],
        [([escape(i["libelle"]), escape(i["unite"] or ""), _nb(i["valeur_cible"], 2),
           _nb(i["prevu_quantite"], 2) if i["source"] == "saisi" else escape(v("À définir")),
           _nb(i["realise_quantite"], 2), _pct(i["taux"]), escape(v(i["statut"]))], None, False) for i in data["indicateurs"]],
        [38, 10, 11, 11, 11, 8, 11],
    ) if data["indicateurs"] else f"<p>{v('Aucun indicateur rattaché à ce projet.')}</p>"

    contenu = (f"{resume}<h3>{v('Activités')}</h3>{activites}<h3>{v('Saisies de la période')}</h3>{historique}"
               f"<h3>{v('Indicateurs')}</h3>{indicateurs}")
    return _page(_titre_suivi(data), f"{v('Généré le')} {aujourdhui:%d/%m/%Y}", contenu)
