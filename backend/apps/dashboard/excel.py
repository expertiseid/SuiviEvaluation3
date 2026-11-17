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


def excel_tableau_de_bord(d: dict, filtres, organisation: str = "") -> bytes:
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
            a.get("REALISEE", 0), a.get("EN_COURS", 0), a.get("NON_REALISEE", 0),
            b.get("F", 0), b.get("M", 0), sum(n for k, n in b.items() if k != "code"),
        ])
    _tableau(projets, 1, [
        v("Code"), v("Projet"), v("Statut"), v("Budget"), v("Exécution physique (%)"), v("Exécution financière (%)"),
        v("Activités réalisées"), v("Activités en cours"), v("Activités non réalisées"),
        v("Bénéficiaires femmes"), v("Bénéficiaires hommes"), v("Bénéficiaires (total)"),
    ], lignes, {4: MONTANT, 5: POURCENT, 6: POURCENT})
    figer_entete(projets)
    _largeurs(projets, [18, 50, 15, 18, 14, 14, 12, 12, 12, 13, 13, 13])

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

    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
