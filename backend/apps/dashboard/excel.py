"""
Export Excel du tableau de bord consolidé : les mêmes chiffres que l'écran (donnees_consolidees), avec les
mêmes filtres, sur plusieurs feuilles — synthèse, projets, répartitions, évolutions mois par mois.
"""
import io
from decimal import Decimal

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.vocabulaire import v

ENTETE = Font(bold=True, color="FFFFFF")
FOND_ENTETE = PatternFill("solid", fgColor="1F4E78")
TITRE = Font(bold=True, size=13)
SECTION = Font(bold=True, size=11, color="1F4E78")
MONTANT = "#,##0"
POURCENT = '0.0" %"'


def _nombre(valeur):
    """Montants (Decimal ou texte) en nombre, pour qu'Excel puisse les additionner."""
    if isinstance(valeur, (Decimal, str)):
        try:
            return float(valeur)
        except ValueError:
            return valeur
    return valeur


def _entete(feuille, ligne, titres):
    for colonne, titre in enumerate(titres, start=1):
        cellule = feuille.cell(row=ligne, column=colonne, value=titre)
        cellule.font, cellule.fill = ENTETE, FOND_ENTETE
        cellule.alignment = Alignment(vertical="center", wrap_text=True)


def _tableau(feuille, ligne, titres, lignes, formats=None):
    """Tableau à en-tête coloré à partir de `ligne` ; rend la ligne suivant le tableau."""
    _entete(feuille, ligne, titres)
    for numero, valeurs in enumerate(lignes, start=ligne + 1):
        for colonne, valeur in enumerate(valeurs, start=1):
            cellule = feuille.cell(row=numero, column=colonne, value=_nombre(valeur))
            if formats and formats.get(colonne):
                cellule.number_format = formats[colonne]
    fin = ligne + len(lignes)
    quadriller(feuille, min_row=ligne, max_row=fin, min_col=1, max_col=len(titres))
    return fin + 2


def _largeurs(feuille, largeurs):
    for colonne, largeur in enumerate(largeurs, start=1):
        feuille.column_dimensions[get_column_letter(colonne)].width = largeur


def _libelles(choix):
    return {valeur: str(libelle) for valeur, libelle in choix}


def _filtres_en_clair(filtres, statuts_projet) -> str:
    periodes = {
        "actifs": v("En cours pendant la période"), "demarres": v("Ont commencé dans la période"),
        "demarres_fin_prevue": v("Ont commencé et doivent finir dans la période"),
        "demarres_termines": v("Ont commencé et se sont terminés (clôturés) dans la période"),
    }
    morceaux = []
    if filtres.get("annee"):
        morceaux.append(v("Année {0}").format(filtres["annee"]))
    if filtres.get("date_debut") or filtres.get("date_fin"):
        morceaux.append(v("Du {0} au {1}").format(filtres.get("date_debut") or "…", filtres.get("date_fin") or "…"))
    if filtres.get("statuts"):
        statuts = ", ".join(statuts_projet.get(s, s) for s in filtres["statuts"].split(",") if s)
        morceaux.append(v("Statuts : {0}").format(statuts))
    if filtres.get("periode"):
        morceaux.append(periodes.get(filtres["periode"], filtres["periode"]))
    return " · ".join(morceaux) or v("Aucun (tous les projets visibles)")


def excel_tableau_de_bord(d: dict, filtres, organisation: str = "", blocs=None) -> bytes:
    """`blocs` : images des blocs comme à l'écran (apps.dashboard.fidele), en dernière feuille."""
    from apps.projects.models import Activite, Projet

    statuts_projet = _libelles(Projet._meta.get_field("statut").choices)
    statuts_activite = _libelles(Activite._meta.get_field("statut").choices)
    sexes = {"F": v("Femmes"), "M": v("Hommes")}

    wb = Workbook()

    # --- Synthèse ---------------------------------------------------------------------------
    synthese = wb.active
    synthese.title = v("Synthèse")
    synthese["A1"] = v("Tableau de bord") + (f" — {organisation}" if organisation else "")
    synthese["A1"].font = TITRE
    synthese["A2"] = v("Exporté le {0}").format(timezone.localtime().strftime("%d/%m/%Y %H:%M"))
    synthese["A3"] = v("Filtres : {0}").format(_filtres_en_clair(filtres, statuts_projet))
    budget = d.get("budget_detail") or {}
    cibles = d.get("cibles") or {}
    ligne = _tableau(synthese, 5, [v("Chiffre clé"), v("Valeur")], [
        [v("Projets"), d.get("nombre_projets", 0)],
        [v("Budget total"), budget.get("total", d.get("budget_total"))],
        [v("dont fonds propres"), budget.get("fonds_propres")],
        [v("dont financements des bailleurs"), budget.get("financements_bailleurs")],
        [v("Bénéficiaires inscrits"), d.get("nombre_beneficiaires", 0)],
        [v("Cible totale"), cibles.get("totale")],
        [v("Cible femmes"), cibles.get("femmes")],
        [v("Cible hommes"), cibles.get("hommes")],
    ], {2: MONTANT})
    for titre, entetes, lignes in (
        (v("Indicateurs par niveau d'alerte"), [v("Niveau"), v("Indicateurs")],
         [[r["libelle"], r["count"]] for r in d.get("indicateurs_par_statut", [])]),
        (v("Projets par statut"), [v("Statut"), v("Projets")],
         [[statuts_projet.get(k, k), n] for k, n in d.get("projets_par_statut", {}).items()]),
        (v("Activités par statut"), [v("Statut"), v("Activités")],
         [[statuts_activite.get(k, k), n] for k, n in d.get("activites_par_statut", {}).items()]),
        (v("Bénéficiaires par sexe"), [v("Sexe"), v("Bénéficiaires")],
         [[sexes.get(k, k or v("Non renseigné")), n] for k, n in d.get("beneficiaires_par_sexe", {}).items()]),
        (v("Zones couvertes"), [v("Niveau"), v("Zones")], [[r["niveau"], r["count"]] for r in d.get("zones_couvertes", [])]),
    ):
        synthese.cell(row=ligne, column=1, value=titre).font = SECTION
        ligne = _tableau(synthese, ligne + 1, entetes, lignes)
    _largeurs(synthese, [38, 22])

    # --- Projets ----------------------------------------------------------------------------
    projets = wb.create_sheet(v("Projets"))
    execution = {r["code"]: r for r in d.get("execution_par_projet", [])}
    activites = {r["code"]: r for r in d.get("activites_par_projet", [])}
    beneficiaires = {r["code"]: r for r in d.get("beneficiaires_par_projet_sexe", [])}
    lignes = []
    for p in sorted(d.get("projets", []), key=lambda p: p["code"]):
        a, b, e = activites.get(p["code"], {}), beneficiaires.get(p["code"], {}), execution.get(p["code"], {})
        lignes.append([
            p["code"], p["nom"], statuts_projet.get(p["statut"], p["statut"]), p.get("budget_total"),
            e.get("physique"), e.get("financier"),
            a.get("REALISEE", 0), a.get("EN_COURS", 0), a.get("NON_REALISEE", 0), a.get("SUSPENDUE", 0), a.get("ANNULEE", 0),
            b.get("F", 0), b.get("M", 0), sum(n for k, n in b.items() if k != "code"),
        ])
    _tableau(projets, 1, [
        v("Code"), v("Projet"), v("Statut"), v("Budget"), v("Exécution physique (%)"), v("Exécution financière (%)"),
        v("Activités réalisées"), v("Activités en cours"), v("Activités non réalisées"), v("Activités suspendues"), v("Activités annulées"),
        v("Bénéficiaires femmes"), v("Bénéficiaires hommes"), v("Bénéficiaires (total)"),
    ], lignes, {4: MONTANT, 5: POURCENT, 6: POURCENT})
    figer_entete(projets)
    _largeurs(projets, [18, 50, 15, 18, 14, 14, 12, 12, 12, 12, 12, 13, 13, 13])

    # --- Budget et efficience -------------------------------------------------------------------
    fi = d.get("finances") or {}
    if fi:
        feuille = wb.create_sheet(v("Budget"))
        ligne = _tableau(feuille, 1, [v("Budget et efficience"), v("Valeur")], [
            [v("Budget initial (FCFA)"), fi["budget_initial"]], [v("Budget révisé (FCFA)"), fi["budget_revise"]],
            [v("Engagé (FCFA)"), fi["engage"]], [v("Taux d'engagement (%)"), fi["taux_engagement"]],
            [v("Dépensé (FCFA)"), fi["depense"]], [v("Taux d'exécution financière (%)"), fi["taux_execution"]],
            [v("Dépense attendue à ce jour (FCFA)"), fi["depense_attendue_a_date"]], [v("Écart à ce jour (FCFA)"), fi["ecart_a_date"]],
            [v("Solde non engagé (FCFA)"), fi["solde_non_engage"]], [v("Reste à dépenser (FCFA)"), fi["reste_a_depenser"]],
            [v("Financements acquis (FCFA)"), fi["financements_acquis"]], [v("Reçus des bailleurs (FCFA)"), fi["financements_recus"]],
            [v("Taux de décaissement (%)"), fi["taux_decaissement"]], [v("Financement restant à trouver (FCFA)"), fi["besoin_de_financement"]],
            [v("Lignes en dépassement"), f"{fi['lignes_en_depassement']} / {fi['lignes_budgetees']}"],
            [v("Coût par bénéficiaire (FCFA)"), fi["cout_par_beneficiaire"]],
            [v("Coût moyen d'une activité réalisée (FCFA)"), fi["cout_par_activite_realisee"]],
        ], {2: MONTANT})
        feuille.cell(row=ligne, column=1, value=v("Exécution par projet")).font = SECTION
        ligne = _tableau(feuille, ligne + 1, [v("Projet"), v("Budget révisé (FCFA)"), v("Engagé (FCFA)"), v("Dépensé (FCFA)"),
                                                v("Exécution financière (%)"), v("Financements acquis (FCFA)"), v("Reçus des bailleurs (FCFA)")], [
            [p["code"], p["budget_revise"], p["engage"], p["depense"], p["taux_execution"], p["financements_acquis"], p["financements_recus"]]
            for p in fi["par_projet"]], {2: MONTANT, 3: MONTANT, 4: MONTANT, 6: MONTANT, 7: MONTANT})
        if fi["couts_unitaires"]:
            feuille.cell(row=ligne, column=1, value=v("Coûts unitaires : prévu et réel")).font = SECTION
            _tableau(feuille, ligne + 1, [v("Projet"), v("Activité"), v("Unité"), v("Prévu par unité (FCFA)"), v("Réel par unité (FCFA)"),
                                          v("Écart (%)")], [
                [u["projet"], u["libelle"], u["unite"], u["prevu"], u["reel"], u["ecart_pourcent"]] for u in fi["couts_unitaires"]],
                {4: MONTANT, 5: MONTANT})
        _largeurs(feuille, [42, 22, 18, 22, 22, 22, 22])

    # --- Avancement et retards des activités --------------------------------------------------
    av = d.get("avancement") or {}
    if av.get("prevues"):
        feuille = wb.create_sheet(v("Avancement"))
        ligne = _tableau(feuille, 1, [v("Activités de terrain"), v("Valeur")], [
            [v("Prévues"), av["prevues"]], [v("Démarrées"), av["demarrees"]], [v("Terminées"), av["terminees"]],
            [v("Suspendues"), av["suspendues"]], [v("Annulées (hors prévues)"), av["annulees"]],
            [v("Taux de démarrage (%)"), av["taux_demarrage"]], [v("Taux d'achèvement (%)"), av["taux_achevement"]],
            [v("Exécution à date (%)"), av["taux_execution_a_date"]], [v("En retard"), av["en_retard"]],
            [v("Retard moyen (jours)"), av["retard_moyen_jours"]],
            [v("Terminées dans les délais (%)"), av["terminees_dans_les_delais"]],
            [v("Durée moyenne de réalisation (jours)"), av["duree_moyenne_realisation_jours"]],
            [v("Sans responsable"), av["sans_responsable"]], [v("Sans dates"), av["sans_calendrier"]],
            [v("Sans budget"), av["sans_budget"]], [v("Avec justificatifs (%)"), av["avec_justificatifs"]],
            [v("Jalons atteints"), f"{av['jalons']['atteints']} / {av['jalons']['total']}"],
        ])
        feuille.cell(row=ligne, column=1, value=v("Retards par projet")).font = SECTION
        ligne = _tableau(feuille, ligne + 1, [v("Projet"), v("Activités"), v("Terminées"), v("En retard"), v("Retard moyen (jours)"),
                                                v("Exécution à date (%)")], [
            [p["code"], p["prevues"], p["terminees"], p["en_retard"], p["retard_moyen_jours"], p["taux_execution_a_date"]]
            for p in av["par_projet"]])
        if av["activites_en_retard"]:
            feuille.cell(row=ligne, column=1, value=v("Activités les plus en retard")).font = SECTION
            _tableau(feuille, ligne + 1, [v("Projet"), v("Code"), v("Activité"), v("Échéance"), v("Retard (jours)")], [
                [r["projet"], r["code"], r["libelle"], r["date_fin"], r["jours"]] for r in av["activites_en_retard"]])
        _largeurs(feuille, [40, 14, 50, 14, 16, 18])

    # --- Bénéficiaires et territoires --------------------------------------------------------
    te = d.get("territoires") or {}
    if te:
        feuille = wb.create_sheet(v("Territoires"))
        ligne = _tableau(feuille, 1, [v("Bénéficiaires et territoires"), v("Valeur")], [
            [v("Bénéficiaires directs"), te["directs"]], [v("Bénéficiaires indirects"), te["indirects"]],
            [v("Ménages renseignés"), te["menages"]], [v("Personnes de ces ménages"), te["personnes_des_menages"]],
            [v("Cible des projets"), te["cible"]], [v("Couverture de la cible (%)"), te["couverture_cible"]],
            [v("Maintien (%)"), te["taux_maintien"]], [v("Abandon (%)"), te["taux_abandon"]],
            [v("Paquet complet reçu (%)"), te["taux_paquet_complet"]],
            [v("Satisfaction moyenne (sur 5)"), te["satisfaction_moyenne"]], [v("Satisfaits (%)"), te["part_satisfaits"]],
            [v("Zones ciblées sans bénéficiaire"), f"{te['zones_sans_beneficiaire']} / {te['zones_ciblees']}"],
            [v("Bénéficiaires hors des zones du projet"), te["hors_zone"]],
            [v("Coordonnées non valides"), f"{te['coordonnees_invalides']} / {te['coordonnees_renseignees']}"],
            [v("Plaintes pour 1 000 bénéficiaires"), te["plaintes_pour_1000"]],
            [v("Plaintes récurrentes (%)"), te["taux_plaintes_recurrentes"]],
            [v("Participations aux activités"), te["participations"]],
            [v("Participations par bénéficiaire"), te["participations_par_beneficiaire"]],
            [v("Bénéficiaires ayant reçu plusieurs types d'appui (%)"), te["part_plusieurs_appuis"]],
            [v("Personnes vulnérables (%)"), te["part_vulnerables"]],
            *[[x["tranche"] or v("Âge non renseigné"), x["nombre"]] for x in te["par_age"]],
            *[[x["statut"], x["nombre"]] for x in te["par_statut"]],
            *[[f'{v("Couverture du groupe prioritaire (%)")} : {g["groupe"]}', g["couverture"]] for g in te["groupes_prioritaires"]],
        ])
        feuille.cell(row=ligne, column=1, value=v("Par territoire")).font = SECTION
        ligne = _tableau(feuille, ligne + 1, [v("Territoire"), v("Pays"), v("Bénéficiaires"), v("Femmes (%)"), v("Population"),
                                                v("Pour 1 000 habitants"), v("Abandon (%)")], [
            [t["zone"], t["pays"], t["beneficiaires"], t["part_femmes"], t["population"], t["pour_1000_habitants"], t["taux_abandon"]]
            for t in te["territoires"]], {5: MONTANT})
        if te["zones_sans_beneficiaire_exemples"]:
            feuille.cell(row=ligne, column=1, value=v("Zones ciblées sans bénéficiaire")).font = SECTION
            ligne = _tableau(feuille, ligne + 1, [v("Projet"), v("Zone"), v("Niveau")], [
                [z["projet"], z["zone"], z["niveau"]] for z in te["zones_sans_beneficiaire_exemples"]])
        if te["couches"]:
            feuille.cell(row=ligne, column=1, value=v("Couches importées")).font = SECTION
            _tableau(feuille, ligne + 1, [v("Couche"), v("Objets"), v("Surface (ha)"), v("Longueur (km)")], [
                [c["nom"], c["objets"], c["surface_ha"], c["longueur_km"]] for c in te["couches"]], {3: MONTANT})
        _largeurs(feuille, [42, 22, 16, 14, 16, 18, 14])

    # --- Qualité des données, rapports, risques et apprentissage ------------------------------
    qu, pi = d.get("qualite") or {}, d.get("pilotage") or {}
    if qu and pi:
        feuille = wb.create_sheet(v("Qualité et pilotage"))
        c, co = qu["completude"], qu["composantes"]
        ra, ri, re, ap = pi["rapports"], pi["risques"], pi["recommandations"], pi["apprentissage"]
        ligne = _tableau(feuille, 1, [v("Qualité des données"), v("Valeur")], [
            [v("Score de qualité (sur 100)"), qu["score"]],
            [v("Complétude (%)"), co["completude"]], [v("Saisies dans les délais (%)"), co["ponctualite"]],
            [v("Valeurs plausibles (%)"), co["plausibilite"]], [v("Doublons traités (%)"), co["doublons"]],
            [v("Complétude des activités (%)"), c["activites"]["completude"]], [v("Complétude des indicateurs (%)"), c["indicateurs"]["completude"]],
            [v("Complétude des bénéficiaires (%)"), c["beneficiaires"]["completude"]],
            [v("Valeurs atypiques"), f"{qu['atypiques']} / {qu['valeurs_verifiees']}"],
            [v("Doublons non traités"), qu["doublons_non_traites"]], [v("Saisies en attente d'approbation"), qu["approbations_en_attente"]],
            [v("Saisies validées (%)"), qu["taux_validation"]], [v("Saisies rejetées (%)"), qu["taux_rejet"]],
            [v("Délai fin de période → saisie (jours)"), qu["delai_saisie_jours"]],
            [v("Délai saisie → approbation (jours)"), qu["delai_validation_jours"]],
            [v("Valeurs d'indicateurs avec justificatif (%)"), qu["valeurs_justifiees"]],
        ])
        ligne = _tableau(feuille, ligne, [v("Rapports, risques et apprentissage"), v("Valeur")], [
            [v("Rapports attendus à ce jour"), ra["attendus_a_date"]], [v("Rapports reçus"), ra["recus"]], [v("Rapports validés"), ra["valides"]],
            [v("Rapports en retard"), ra["en_retard"]], [v("Rapports remis à temps (%)"), ra["taux_a_temps"]],
            [v("Rapports produits, parmi les échus (%)"), ra["taux_remis"]], [v("Délai moyen de validation (jours)"), ra["delai_validation_jours"]],
            [v("Rapports acceptés dès la 1re remise (%)"), ra["acceptes_premiere_soumission"]],
            [v("Risques recensés"), ri["total"]], [v("Risques maîtrisés ou clos"), ri["clos"]],
            [v("Risques graves avec mesures (%)"), ri["graves_avec_mesures"]],
            [v("Problèmes résolus"), ri["problemes_resolus"]], [v("Délai moyen de résolution (jours)"), ri["delai_resolution_jours"]],
            [v("Risques ouverts"), ri["ouverts"]], [v("Risques critiques"), ri["par_niveau"]["CRITIQUE"]], [v("Risques élevés"), ri["par_niveau"]["ELEVE"]],
            [v("Risques survenus"), ri["survenus"]], [v("Risques avec mesures d'atténuation (%)"), ri["avec_mesures"]],
            [v("Risques réévalués depuis moins de 3 mois (%)"), ri["suivis"]], [v("Revues de risque en retard"), ri["revue_en_retard"]],
            [v("Recommandations formulées"), re["total"]], [v("Recommandations retenues"), re["retenues"]], [v("Recommandations mises en œuvre (%)"), re["taux_mise_en_oeuvre"]],
            [v("Recommandations en retard"), re["en_retard"]],
            [v("Leçons apprises"), ap["lecons"]], [v("Bonnes pratiques"), ap["bonnes_pratiques"]], [v("Décisions documentées"), ap["decisions"]],
            [v("Mesures d'atténuation suivies"), ri["mesures"]], [v("Mesures d'atténuation réalisées (%)"), ri["taux_execution_mesures"]],
            [v("Mesures d'atténuation en retard"), ri["mesures_en_retard"]],
            [v("Leçons ayant entraîné un changement (%)"), ap["part_lecons_adaptees"]],
            [v("Documents obligatoires"), pi["documents_obligatoires"]["total"]],
            [v("Documents obligatoires disponibles (%)"), pi["documents_obligatoires"]["taux_disponibilite"]],
            [v("Documents obligatoires manquants après échéance"), pi["documents_obligatoires"]["manquants_echus"]],
            *[[f'{v("Recommandations mises en œuvre (%)")} : {o["libelle"]}', o["taux_mise_en_oeuvre"]] for o in re["par_origine"]],
            [v("Analyses partagées par lien"), pi["partages"]["liens"]], [v("Consultations des analyses partagées"), pi["partages"]["consultations"]],
        ])
        if qu["atypiques_exemples"]:
            feuille.cell(row=ligne, column=1, value=v("Valeurs atypiques")).font = SECTION
            ligne = _tableau(feuille, ligne + 1, [v("Projet"), v("Indicateur ou activité"), v("Valeur"), v("Unité")], [
                [x["projet"], x["libelle"], x["valeur"], x["unite"]] for x in qu["atypiques_exemples"]])
        if ri["graves_exemples"]:
            feuille.cell(row=ligne, column=1, value=v("Risques critiques et élevés")).font = SECTION
            _tableau(feuille, ligne + 1, [v("Projet"), v("Risque"), v("Criticité"), v("Dernière réévaluation")], [
                [x["projet"], f"{x['code']} {x['libelle']}", x["criticite"], x["derniere_revue"]] for x in ri["graves_exemples"]])
        _largeurs(feuille, [48, 60, 14, 22])

    # --- Performance des indicateurs, plaintes, performance par région ------------------------
    pe, pl = d.get("performance") or {}, d.get("plaintes") or {}
    if pe:
        feuille = wb.create_sheet(v("Indicateurs et plaintes"))
        ligne = _tableau(feuille, 1, [v("Performance des indicateurs"), v("Valeur")], [
            [v("Score de performance (sur 100)"), pe["score"]],
            [v("Indicateurs"), pe["total"]], [v("Indicateurs renseignés (%)"), pe["part_renseignes"]],
            [v("Cible atteinte"), pe["atteints"]], [v("Cible atteinte (%)"), pe["part_atteints"]],
            [v("En progrès (%)"), pe["part_en_progres"]], [v("En recul (%)"), pe["part_en_recul"]],
            *[[f'{v("Documents stratégiques")} : {x["type"]}', x["nombre"]] for x in pe["documents"]],
        ])
        if pe["par_niveau"]:
            ligne = _tableau(feuille, ligne, [v("Niveau"), v("Éléments"), v("Mesurés"), v("Atteints"), v("Atteints (%)")], [
                [x["niveau"], x["elements"], x["mesures"], x["atteints"], x["part"]] for x in pe["par_niveau"]])
        if len(pe["scores_projets"]) > 1:
            ligne = _tableau(feuille, ligne, [v("Projet"), v("Score de performance (sur 100)"), v("Indicateurs")], [
                [x["projet"], x["score"], x["indicateurs"]] for x in pe["scores_projets"]])
        tendances = {"progres": v("En progrès"), "recul": v("En recul"), "stable": v("Stable")}
        ligne = _tableau(feuille, ligne, [v("Indicateur"), v("Projet"), v("Unité"), v("Référence"), v("Valeur actuelle"), v("Cible"),
                                          v("Écart à la cible"), v("Taux d'atteinte (%)"), v("Tendance")], [
            [x["libelle"], x["projet"], x["unite"], x["reference"], x["actuelle"], x["cible"], x["ecart"], x["taux"],
             tendances.get(x["tendance"], "")] for x in pe["liste"]])
        if pl and pl["total"]:
            ligne = _tableau(feuille, ligne, [v("Plaintes et retours"), v("Valeur")], [
                [v("Retours reçus"), pl["total"]], [v("Ouverts"), pl["ouverts"]], [v("Clôturés"), pl["clotures"]], [v("En retard"), pl["en_retard"]],
                [v("Réponse apportée (%)"), pl["taux_resolution"]], [v("Accusés de réception (%)"), pl["taux_accuse"]],
                [v("Délai moyen d'accusé de réception (jours)"), pl["delai_accuse_moyen"]],
                [v("Délai moyen de traitement (jours)"), pl["delai_moyen"]], [v("Délai médian de traitement (jours)"), pl["delai_median"]],
                [v("Traités dans les délais (%)"), pl["dans_delais"]], [v("Réouvertures et recours (%)"), pl["taux_reouverture"]],
                [v("Satisfaction après traitement (%)"), pl["satisfaction"]],
                [v("Dossiers clôturés avec mesure corrective (%)"), pl["avec_mesure_corrective"]],
                [v("Mesures correctives réalisées (%)"), pl["mise_en_oeuvre_mesures"]],
            ])
            for titre, cle in ((v("Par type de retour"), "par_type"), (v("Par canal"), "par_canal"), (v("Par catégorie"), "par_categorie")):
                ligne = _tableau(feuille, ligne, [titre, v("Dossiers")], [[x["libelle"], x["nombre"]] for x in pl[cle]])
        for p in d.get("performance_territoires") or []:
            ligne = _tableau(feuille, ligne, [f'{p["niveau"]} ({p["pays"]})', v("Projets"), v("Activités"), v("Activités réalisées (%)"),
                                              v("Dépenses (FCFA)"), v("Réalisation des indicateurs (%)")], [
                [z["zone"], z["projets"], z["activites"], z["part_realisees"], z["depenses"], z["taux_indicateurs"]] for z in p["zones"]],
                {5: MONTANT})
        _largeurs(feuille, [60, 18, 14, 14, 16, 16, 14, 14, 14])

    # --- Répartitions ------------------------------------------------------------------------
    repartitions = wb.create_sheet(v("Répartitions"))
    ligne = 1
    groupes = [
        (v("Par pays"), d.get("projets_par_pays", [])),
        *[(v("Par zone — {0}").format(n["niveau"]), n.get("zones", [])) for n in d.get("projets_par_zone", [])],
        (v("Par bailleur"), d.get("projets_par_bailleur", [])),
        (v("Par membre du consortium"), d.get("projets_par_consortium", [])),
        (v("Par structure de mise en œuvre"), d.get("projets_par_mise_en_oeuvre", [])),
    ]
    for titre, elements in groupes:
        if not elements:
            continue
        repartitions.cell(row=ligne, column=1, value=titre).font = SECTION
        ligne = _tableau(repartitions, ligne + 1, [v("Libellé"), v("Projets"), v("Montant"), v("Codes des projets")], [
            [r["libelle"], r["nombre"], r.get("montant"), ", ".join(r.get("projets", []))] for r in elements
        ], {3: MONTANT})
    _largeurs(repartitions, [40, 10, 20, 90])

    # --- Évolutions mois par mois ------------------------------------------------------------
    for titre, cle, format_ in (
        (v("Dépenses cumulées par mois"), "depenses_par_mois", MONTANT),
        (v("Inscriptions par mois"), "inscriptions_par_mois", None),
    ):
        mois = d.get(cle, [])
        if not mois:
            continue
        feuille = wb.create_sheet(titre[:31])
        codes = [k for k in mois[0] if k != "mois"]
        formats = {c: format_ for c in range(2, len(codes) + 2)} if format_ else None
        _tableau(feuille, 1, [v("Mois"), *codes], [[m["mois"], *[m.get(c, 0) for c in codes]] for m in mois], formats)
        figer_entete(feuille)
        _largeurs(feuille, [10] + [16] * len(codes))

    if blocs:
        from .fidele import feuille_comme_a_l_ecran

        feuille_comme_a_l_ecran(wb, blocs)

    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


# --- Un graphique seul, en Excel natif -----------------------------------------------------------

LIGNES_MAX_GRAPHIQUE = 2000


def excel_graphique(titre: str, entetes: list, lignes: list, type_graphique: str = "colonnes", series: int | None = None) -> bytes:
    """
    Les données d'un graphique du tableau de bord (première colonne : catégories ; suivantes : séries) et un
    graphique Excel natif relié à ces cellules : modifier une valeur met le graphique à jour.
    """
    from openpyxl.chart import AreaChart, BarChart, DoughnutChart, LineChart, Reference

    wb = Workbook()
    feuille = wb.active
    feuille.title = (titre or v("Graphique"))[:31].replace("/", "-")
    feuille["A1"] = titre
    feuille["A1"].font = TITRE
    lignes = [ligne[:len(entetes)] for ligne in lignes[:LIGNES_MAX_GRAPHIQUE]]
    _tableau(feuille, 3, entetes, lignes, {c: MONTANT for c in range(2, len(entetes) + 1)})
    _largeurs(feuille, [36] + [18] * (len(entetes) - 1))
    numeriques = [c for c in range(2, len(entetes) + 1)
                  if any(isinstance(_nombre(l[c - 1]), (int, float)) for l in lignes if len(l) >= c)]
    if series:
        numeriques = [c for c in numeriques if c <= 1 + series]  # seules les premières colonnes sont tracées
    # Tableau ou cartes de chiffres (unités différentes, ex. chiffres clés) : les données, sans graphique.
    if lignes and numeriques and type_graphique not in ("tableau", "cartes"):
        fin = 3 + len(lignes)
        if type_graphique == "camembert":
            graphique = DoughnutChart()
            graphique.holeSize = 50
            numeriques = numeriques[:1]
        elif type_graphique in ("courbes",):
            graphique = LineChart()
        elif type_graphique == "aires":
            graphique = AreaChart()
        else:
            graphique = BarChart()
            graphique.type = "bar" if type_graphique == "barres" else "col"
            if type_graphique == "colonnes-empilees":
                graphique.grouping, graphique.overlap = "stacked", 100
        graphique.title = titre
        graphique.height, graphique.width = max(7.5, min(20, 0.6 * len(lignes) + 4)), 18
        for colonne in numeriques:
            graphique.add_data(Reference(feuille, min_col=colonne, min_row=3, max_row=fin), titles_from_data=True)
        graphique.set_categories(Reference(feuille, min_col=1, min_row=4, max_row=fin))
        feuille.add_chart(graphique, f"{get_column_letter(len(entetes) + 2)}3")
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
