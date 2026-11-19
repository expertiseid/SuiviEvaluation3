"""
Export « bien fait » de la fiche de suivi d'un projet : reprend TOUTES les
informations affichées sur le tableau de bord de suivi (exécution globale,
indicateurs, activités et sous-activités avec leur historique complet), réparties
sur plusieurs feuilles lisibles et filtrables — plutôt qu'un import, ce fichier est un
document de restitution (bailleur, rapport, archive). Sous-activités juste sous leur
activité (libellé en italique), dans les activités comme dans leur historique ; niveaux
de regroupement en gras et colorés, comme dans l'export Word.
"""
import datetime
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.core.langues import traduire_classeur
from apps.core.vocabulaire import v
from apps.projects.attributs import ordonner
from apps.projects.taux import libelle_methode

from .services import construire_dashboard_suivi, ecart_texte, taux_de, valeur_attendue_a

COULEUR_ENTETE = "1F4E78"
COULEUR_TITRE = "D9E2F3"

STATUT_ACTIVITE_LABEL = {"NON_REALISEE": "Non réalisée", "EN_COURS": "En cours", "REALISEE": "Réalisée",
                         "SUSPENDUE": "Suspendue", "ANNULEE": "Annulée"}
STATUT_SOUS_ACTIVITE_LABEL = {"PLANIFIEE": "Planifiée", "EN_COURS": "En cours", "TERMINEE": "Terminée"}


def _entete(feuille, colonnes, ligne=1):
    feuille.append(colonnes)
    for cellule in feuille[ligne]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill("solid", fgColor=COULEUR_ENTETE)
        cellule.alignment = Alignment(vertical="center", wrap_text=True)
    # Une référence texte plutôt que feuille.cell(...) : cette dernière CRÉE
    # la cellule visée, ce qui décale ws.max_row et fait sauter une ligne au
    # prochain .append() — piège classique d'openpyxl.
    feuille.freeze_panes = f"A{ligne + 1}"
    feuille.auto_filter.ref = f"A{ligne}:{get_column_letter(len(colonnes))}{ligne}"


def _largeurs(feuille, largeurs):
    for i, largeur in enumerate(largeurs, start=1):
        feuille.column_dimensions[get_column_letter(i)].width = largeur


def exporter_suivi_excel(projet) -> bytes:
    data = construire_dashboard_suivi(projet)
    aujourdhui = datetime.date.today()

    wb = Workbook()

    # ---------- Résumé ----------
    resume = wb.active
    resume.title = "Résumé"
    resume.append([f"{v('Suivi — ')}{data['projet']['code']} — {data['projet']['nom']}"])
    resume.cell(row=1, column=1).font = Font(bold=True, size=14)
    resume.append([f"Généré le {aujourdhui.strftime('%d/%m/%Y')}"])
    resume.cell(row=2, column=1).font = Font(italic=True, color="666666")
    resume.append([])
    _entete(resume, [v('Indicateur global'), "Valeur"], ligne=4)
    physique = data["taux_execution_physique_global"]
    financier = data["taux_execution_financiere_global"]
    statut_global_label = {"EN_RETARD": "En retard", "ATTEINT": "Atteint", "EN_COURS": "En cours"}.get(
        data["statut_global"], data["statut_global"]
    )
    resume.append(["Exécution physique globale (%)", physique if physique is not None else "—"])
    resume.append(["Exécution financière globale (%)", financier if financier is not None else "—"])
    resume.append(["Statut global", statut_global_label])
    resume.append([v("Nombre d'indicateurs"), len(data["indicateurs"])])
    resume.append(["Nombre d'activités", len(data["activites"])])
    _largeurs(resume, [34, 20])

    # ---------- Indicateurs (résumé) ----------
    ws_indic = wb.create_sheet(v('Indicateurs'))
    colonnes = [
        "Libellé",
        "Unité",
        "Valeur de référence",
        "Cible",
        "Réalisé cumulé",
        "Taux (%)",
        "Statut",
        "Planifié début",
        "Planifié fin",
        "Attendu aujourd'hui",
        "Taux attendu (%)",
        "Écart",
    ]
    _entete(ws_indic, colonnes)
    for indicateur in data["indicateurs"]:
        cible = indicateur["valeur_cible"]
        depart = indicateur["valeur_reference"] or 0
        debut_p = indicateur["periode_debut_planifiee"]
        fin_p = indicateur["periode_fin_planifiee"]
        realise = indicateur["historique"][-1]["valeur_cumulee"] if indicateur["historique"] else None
        attendu = valeur_attendue_a(aujourdhui, debut_p, fin_p, depart, cible) if debut_p and fin_p else None
        ws_indic.append(
            [
                indicateur["libelle"],
                indicateur["unite"],
                float(depart),
                float(cible),
                float(realise) if realise is not None else None,
                indicateur["taux_actuel"],
                indicateur["palier_actuel"]["libelle"] if indicateur["palier_actuel"] else "—",
                debut_p,
                fin_p,
                round(attendu, 1) if attendu is not None else None,
                taux_de(attendu, cible) if attendu is not None else None,
                ecart_texte(realise, attendu, indicateur["unite"]),
            ]
        )
    _largeurs(ws_indic, [38, 10, 14, 12, 14, 10, 14, 14, 14, 16, 14, 38])

    # ---------- Indicateurs — historique ----------
    ws_indic_hist = wb.create_sheet(v('Indicateurs — historique'))
    colonnes = [
        v('Indicateur'),
        "Période début",
        "Période fin",
        "Valeur réalisée",
        "Cumul",
        "Taux cumul (%)",
        "Attendu",
        "Taux attendu (%)",
        "Écart",
        "Commentaire",
    ]
    _entete(ws_indic_hist, colonnes)
    for indicateur in data["indicateurs"]:
        cible = indicateur["valeur_cible"]
        depart = indicateur["valeur_reference"] or 0
        debut_p = indicateur["periode_debut_planifiee"]
        fin_p = indicateur["periode_fin_planifiee"]
        for h in indicateur["historique"]:
            attendu = valeur_attendue_a(h["periode_fin"], debut_p, fin_p, depart, cible) if debut_p and fin_p else None
            ws_indic_hist.append(
                [
                    indicateur["libelle"],
                    h["periode_debut"],
                    h["periode_fin"],
                    float(h["valeur_realisee"]),
                    float(h["valeur_cumulee"]),
                    h["taux"],
                    round(attendu, 1) if attendu is not None else None,
                    taux_de(attendu, cible) if attendu is not None else None,
                    ecart_texte(h["valeur_cumulee"], attendu, indicateur["unite"]),
                    h["commentaire"],
                ]
            )
    _largeurs(ws_indic_hist, [38, 13, 13, 13, 12, 12, 12, 14, 38, 30])

    # ---------- Activités : sous-activités juste sous leur activité, niveaux de regroupement mis en avant ----------
    from apps.projects.models import Activite

    from .export_word import FONDS_NIVEAUX, _profondeurs

    profondeurs, _noms_niveaux = _profondeurs(projet)
    groupes = set(Activite.objects.filter(projet=projet, enfants__isnull=False).values_list("id", flat=True))
    ws_act = wb.create_sheet("Activités")
    colonnes = [
        "Code", "Libellé", "Statut", "Méthode de calcul", "Début prévu", "Fin prévu", "Début effectif", "Fin effectif",
        "Valeur de référence", "Quantité prévue", "Unité", "Réalisé cumulé", "Taux physique (%)",
        "Attendu physique aujourd'hui", "Budget alloué (FCFA)", "Budget réalisé cumulé (FCFA)", "Taux financier (%)",
        "Attendu financier aujourd'hui (FCFA)",
    ]
    # Attributs libres (« Lieu de mise en œuvre », « Priorité »…) : une colonne chacun, en fin de tableau.
    noms_attributs = ordonner(list(dict.fromkeys(
        nom for a in data["activites"] for e in [a, *a["sous_activites"]] for nom in e.get("attributs") or {})), projet.ordre_attributs)
    _entete(ws_act, colonnes + noms_attributs)

    def mettre_en_forme(feuille, fond=None, gras=False, italique=False):
        for cellule in feuille[feuille.max_row]:
            if fond:
                cellule.fill = PatternFill("solid", fgColor=fond.lstrip("#"))
            if gras or italique:
                cellule.font = Font(bold=gras, italic=italique)

    ws_hist = wb.create_sheet("Activités — historique")
    _entete(ws_hist, [
        "Activité", "Période début", "Période fin", "Quantité réalisée", "Cumul quantité", "Taux physique (%)",
        "Attendu physique", "Écart physique", "Budget réalisé (FCFA)", "Cumul budget (FCFA)", "Taux financier (%)",
        "Attendu financier (FCFA)", "Écart financier", "Statut", "Commentaire",
    ])

    for activite in data["activites"]:
        profondeur = profondeurs.get(activite["id"], 0)
        groupe = activite["id"] in groupes
        fond = FONDS_NIVEAUX[min(profondeur, len(FONDS_NIVEAUX) - 1)] if groupe else None
        # Taux hors quantités (tâches, jalons, livrables, binaire, manuel, agrégé) : pas de
        # quantités ni d'attendu en quantité, le taux vient de la méthode.
        par_quantite = activite["methode_calcul_effective"] == "QUANTITE"
        cible = activite["quantite_prevue"] if par_quantite else None
        depart = activite["valeur_reference"] or 0
        debut, fin = activite["date_debut"], activite["date_fin"]
        budget = activite["budget_alloue"]
        realise = activite["historique"][-1]["quantite_cumulee"] if activite["historique"] and par_quantite else None
        budget_realise = activite["historique"][-1]["budget_cumule"] if activite["historique"] else None
        attendu_phys = valeur_attendue_a(aujourdhui, debut, fin, depart, cible) if debut and fin and cible else None
        attendu_fin = valeur_attendue_a(aujourdhui, debut, fin, 0, budget) if debut and fin and budget else None
        ws_act.append([
            activite["code_activite"], activite["libelle"], STATUT_ACTIVITE_LABEL.get(activite["statut"], activite["statut"]),
            libelle_methode(activite["methode_calcul_effective"]), debut, fin,
            activite.get("date_debut_reelle"), activite.get("date_fin_reelle"),
            float(depart), float(cible) if cible is not None else None, activite["unite_quantite"] if par_quantite else "%",
            float(realise) if realise is not None else None, activite["taux_realisation"],
            round(attendu_phys, 1) if attendu_phys is not None else None,
            float(budget) if budget is not None else None, float(budget_realise) if budget_realise is not None else None,
            activite["taux_execution_financiere"], round(attendu_fin, 1) if attendu_fin is not None else None,
            *[(activite.get("attributs") or {}).get(nom) for nom in noms_attributs],
        ])
        mettre_en_forme(ws_act, fond, gras=groupe)
        for h in activite["historique"]:
            cumule = h["quantite_cumulee"] if par_quantite else None
            attendu = valeur_attendue_a(h["periode_fin"], debut, fin, depart, cible) if debut and fin and cible else None
            budget_cumule = h["budget_cumule"]
            attendu_budget = valeur_attendue_a(h["periode_fin"], debut, fin, 0, budget) if debut and fin and budget else None
            ws_hist.append([
                activite["libelle"], h["periode_debut"], h["periode_fin"],
                float(h["quantite_realisee"]) if h["quantite_realisee"] is not None and par_quantite else None,
                float(cumule) if cumule is not None else None, taux_de(cumule, cible),
                round(attendu, 1) if attendu is not None else None, ecart_texte(cumule, attendu, activite["unite_quantite"]),
                float(h["budget_realise"]) if h["budget_realise"] is not None else None,
                float(budget_cumule) if budget_cumule is not None else None, taux_de(budget_cumule, budget),
                round(attendu_budget, 1) if attendu_budget is not None else None,
                ecart_texte(budget_cumule, attendu_budget, "FCFA"), STATUT_ACTIVITE_LABEL.get(h["statut"], h["statut"]),
                h["commentaire"],
            ])
        # Sous-activités juste sous leur activité (libellé en italique) ; pas de budget propre.
        for sa in activite["sous_activites"]:
            cible_sa = sa["quantite_prevue"]
            debut_sa, fin_sa = sa["date_debut"], sa["date_fin"]
            realise_sa = sa["historique"][-1]["quantite_cumulee"] if sa["historique"] else None
            attendu_sa = valeur_attendue_a(aujourdhui, debut_sa, fin_sa, 0, cible_sa) if debut_sa and fin_sa and cible_sa else None
            ws_act.append([
                "", sa["libelle"], STATUT_SOUS_ACTIVITE_LABEL.get(sa["statut"], sa["statut"]), "", debut_sa, fin_sa, None, None,
                None, float(cible_sa) if cible_sa is not None else None, sa["unite_quantite"],
                float(realise_sa) if realise_sa is not None else None, taux_de(realise_sa, cible_sa),
                round(attendu_sa, 1) if attendu_sa is not None else None, None, None, None, None,
                *[(sa.get("attributs") or {}).get(nom) for nom in noms_attributs],
            ])
            mettre_en_forme(ws_act, italique=True)
            for h in sa["historique"]:
                cumule = h["quantite_cumulee"]
                attendu = valeur_attendue_a(h["periode_fin"], debut_sa, fin_sa, 0, cible_sa) if debut_sa and fin_sa and cible_sa else None
                ws_hist.append([
                    sa["libelle"], h["periode_debut"], h["periode_fin"],
                    float(h["quantite_realisee"]) if h["quantite_realisee"] is not None else None,
                    float(cumule) if cumule is not None else None, taux_de(cumule, cible_sa),
                    round(attendu, 1) if attendu is not None else None, ecart_texte(cumule, attendu, sa["unite_quantite"]),
                    None, None, None, None, "", STATUT_SOUS_ACTIVITE_LABEL.get(h["statut"], h["statut"]), h["commentaire"],
                ])
                mettre_en_forme(ws_hist, italique=True)
    _largeurs(ws_act, [12, 38, 14, 24, 12, 12, 12, 12, 14, 14, 10, 14, 14, 18, 16, 18, 14, 18] + [24] * len(noms_attributs))
    _largeurs(ws_hist, [34, 13, 13, 14, 12, 14, 14, 34, 16, 14, 14, 16, 34, 14, 30])

    # Activités avant les indicateurs dans l'ordre des onglets (Résumé en tête).
    ordre = ["Résumé", "Activités", "Activités — historique", v('Indicateurs'), v('Indicateurs — historique')]
    wb._sheets.sort(key=lambda feuille: ordre.index(feuille.title))
    wb.active = 0

    buffer = io.BytesIO()
    traduire_classeur(wb)
    wb.save(buffer)
    return buffer.getvalue()
