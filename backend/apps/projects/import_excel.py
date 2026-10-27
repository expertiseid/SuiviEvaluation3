"""
Import d'un projet complet (fiche + planification à niveaux libres >
Sous-activité) depuis un classeur Excel — même
philosophie « best-effort » que l'import de structuration stratégique
(apps.strategy.services) : une ligne en erreur est ignorée sans bloquer
l'import des autres, tout est rapporté au client.
"""
import datetime
import io
import unicodedata

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.vocabulaire import adapter_classeur, ramener_classeur, v


def _normaliser_entete(texte: str) -> str:
    """
    Compare les en-têtes en ignorant accents/casse/tirets-vs-espaces/espaces
    en trop (ex : « Sous-activité » == « sous   activite ») — pour tolérer
    les petites variations de saisie d'un en-tête sans risquer de confondre
    une colonne avec une autre (comparaison toujours à un nom précis, jamais
    une déduction depuis le contenu des lignes).
    """
    sans_accents = "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.replace("-", " ").lower().split())

CHAMPS_PROJET = [
    ("Nom du projet", "Programme d'appui à la résilience communautaire"),
    ("Code du projet", "PRJ-2026-001"),
    ("Cadre stratégique", "Nom exact d'un cadre stratégique déjà créé (laisser vide si aucun)"),
    ("Rattachement dans le cadre stratégique", "Nom exact d'un élément du cadre (ex : Programme 2) — facultatif"),
    ("Pays (codes ISO séparés par ;)", "BF"),
    ("Budget total (FCFA)", 100000000),
    ("Fonds propres (FCFA)", 10000000),
    ("Date de début (AAAA-MM-JJ)", "2026-01-01"),
    ("Date de fin (AAAA-MM-JJ)", "2027-12-31"),
    ("Statut (EN_PREPARATION/EN_COURS/CLOTURE)", "EN_PREPARATION"),
    ("Type de mise en œuvre (DIRECT/CONSORTIUM)", "DIRECT"),
    ("Bailleur", "Fondation Grameen"),
    ("Partenaire de mise en œuvre", "ONG Sahel Solidarité"),
    ("Partenaires du consortium (séparés par ;)", ""),
    ("Chef de projet", "OUEDRAOGO Fatimata"),
    ("Utilisateurs affectés — identifiants séparés par ; (accès plateforme)", ""),
    ("Cible totale", 1000),
    ("Cible hommes", 400),
    ("Cible femmes", 600),
    ("Cible jeunes", 300),
    ("Cible PDI", 100),
]

# Les colonnes placées AVANT « Sous-activité » (sauf « Code ») sont les niveaux
# de la planification : leurs noms et leur nombre sont libres. Le modèle propose
# Objectif général → Objectif spécifique → Activité, mais une organisation peut
# les renommer (ex : Résultat → Pilier → Activité), en ajouter ou en retirer.
COLONNES_PLANIFICATION = [
    "Objectif général",
    "Objectif spécifique",
    "Code activité",
    "Activité",
    "Sous-activité",
    "Valeur de base",
    "Budget alloué (FCFA)",
    "Quantité prévue",
    "Unité",
    "Date début (AAAA-MM-JJ)",
    "Date fin (AAAA-MM-JJ)",
    "Commentaire",
    # Calcul du taux d'exécution (facultatifs, placés en fin pour ne pas décaler les anciens fichiers).
    "Méthode de calcul",
    "Poids (%)",
]

# Repère visuel des colonnes de niveau dans le modèle (en-têtes renommables).
COULEUR_NIVEAU = "FFF2CC"
COLONNES_NIVEAUX_MODELE = ("Objectif général", "Objectif spécifique", "Activité")
LEGENDE_NIVEAUX = (
    "En jaune : les niveaux de votre planification. Leurs noms sont libres (ex : Résultat, Pilier, Activité) — "
    "renommez ces en-têtes, ajoutez ou supprimez des colonnes de niveau, toujours avant « Sous-activité »."
)
COMMENTAIRE_NIVEAU = (
    "Nom libre : renommez cette colonne (ex : Résultat, Pilier). Vous pouvez aussi ajouter ou supprimer "
    "des colonnes de niveau, toujours avant « Sous-activité »."
)

LIGNES_EXEMPLE_PLANIFICATION = [
    ["Améliorer la sécurité alimentaire des ménages vulnérables"] + [""] * 13,
    ["", "Renforcer les capacités techniques des producteurs"] + [""] * 12,
    [
        "",
        "",
        "A1.1",
        "Former les producteurs aux techniques agroécologiques",
        "",
        0,
        2000000,
        300,
        "producteurs",
        "2026-02-01",
        "2026-06-30",
        "",
        "Par tâches pondérées",
        "",
    ],
    [
        "", "", "", "", "Session de formation en zone rurale", "", "", 100, "producteurs", "2026-02-01", "2026-03-31", "",
        "", 60,
    ],
    [
        "", "", "", "", "Suivi des parcelles de démonstration", "", "", 20, "parcelles", "2026-04-01", "2026-06-30", "",
        "", 40,
    ],
]


def generer_feuille_projet(wb):
    feuille = wb.active
    feuille.title = "Projet"
    for cle, exemple in CHAMPS_PROJET:
        feuille.append([cle, exemple])
    for ligne in feuille.iter_rows(min_col=1, max_col=1):
        ligne[0].font = Font(bold=True)
    quadriller(feuille, max_col=2)
    feuille.column_dimensions["A"].width = 42
    feuille.column_dimensions["B"].width = 48
    return feuille


def generer_feuille_planification(wb, avec_exemple=True):
    feuille = wb.create_sheet("Planification")
    nb_colonnes = len(COLONNES_PLANIFICATION)

    # Ligne 1 : légende ; ligne 2 : en-têtes (l'import retrouve seul la ligne
    # d'en-têtes, voir _ligne_entetes). Les en-têtes de niveau sont en jaune et
    # commentés, pour qu'on voie tout de suite qu'ils sont renommables.
    feuille.append([LEGENDE_NIVEAUX])
    feuille.merge_cells(start_row=1, start_column=1, end_row=1, end_column=nb_colonnes)
    legende = feuille.cell(row=1, column=1)
    legende.font = Font(italic=True, color="7F6000")
    legende.fill = PatternFill("solid", fgColor=COULEUR_NIVEAU)
    legende.alignment = Alignment(wrap_text=True, vertical="center")
    feuille.row_dimensions[1].height = 32

    feuille.append(COLONNES_PLANIFICATION)
    for cellule in feuille[2]:
        cellule.font = Font(bold=True)
        if cellule.value in COLONNES_NIVEAUX_MODELE:
            cellule.fill = PatternFill("solid", fgColor=COULEUR_NIVEAU)
            cellule.comment = Comment(COMMENTAIRE_NIVEAU, "Plateforme S&E")
    if avec_exemple:
        for ligne in LIGNES_EXEMPLE_PLANIFICATION:
            feuille.append(ligne)

    # Lignes vides supplémentaires déjà quadrillées, pour que la saisie
    # manuelle qui suit les exemples reste visuellement dans le tableau au
    # lieu de flotter sans repère de colonnes.
    lignes_vides_supplementaires = 20
    for _ in range(lignes_vides_supplementaires):
        feuille.append([""] * nb_colonnes)

    quadriller(feuille, min_row=2, max_col=nb_colonnes)
    figer_entete(feuille, ligne_entete=2)

    # Méthode de calcul : liste déroulante (libellés de MethodeCalcul).
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    from .models import MethodeCalcul

    colonne = get_column_letter(COLONNES_PLANIFICATION.index("Méthode de calcul") + 1)
    liste = DataValidation(type="list", formula1='"' + ",".join(MethodeCalcul.labels) + '"', allow_blank=True)
    liste.add(f"{colonne}3:{colonne}{feuille.max_row}")
    feuille.add_data_validation(liste)

    largeurs = {"A": 34, "B": 34, "C": 14, "D": 40, "E": 34, "F": 14, "G": 16, "H": 14, "I": 14, "J": 16, "K": 16,
                "L": 24, "M": 24, "N": 11}
    for colonne, largeur in largeurs.items():
        feuille.column_dimensions[colonne].width = largeur

    return feuille


def generer_modele_import_projet() -> bytes:
    from apps.indicators.import_excel import generer_feuille_paliers_alerte

    wb = Workbook()
    generer_feuille_projet(wb)
    generer_feuille_planification(wb)
    generer_feuille_paliers_alerte(wb)

    instructions = wb.create_sheet("Instructions")
    instructions.append(["Consignes"])
    instructions.append(["- Feuille « Projet » : une ligne = un champ (colonne A = nom du champ, colonne B = valeur)."])
    instructions.append(["- Nom du projet, Code du projet, Date de début et Date de fin sont obligatoires."])
    instructions.append(["- Le code du projet doit être unique — l'import est refusé s'il existe déjà."])
    instructions.append([
        "- « Utilisateurs affectés » : identifiants (username) de comptes déjà créés sur la plateforme, séparés "
        "par « ; ». C'est ce qui donne réellement accès au projet une fois connecté — le champ « Chef de "
        "projet » n'est qu'un intitulé affiché, il ne donne aucun accès à lui seul. Un identifiant inconnu "
        "est ignoré avec un avertissement, sans bloquer le reste de l'import."
    ])
    instructions.append([
        "- « Rattachement dans le cadre stratégique » (facultatif) : nom exact de l'élément du cadre dont relève "
        "le projet (un programme, un axe, un pilier... n'importe quel niveau du cadre)."
    ])
    instructions.append([
        "- Feuille « Planification » : toutes les colonnes placées AVANT « Sous-activité » (sauf « Code ») sont "
        "les niveaux de la planification du projet, du plus haut au plus bas (en jaune dans le modèle). Leurs "
        "noms et leur nombre sont LIBRES : renomme, ajoute ou retire des colonnes de niveau comme tu veux (ex : « Résultat », « Pilier », "
        "« Activité »). Le nom de chaque colonne devient le nom affiché de ce niveau."
    ])
    instructions.append([
        "- Sur chaque ligne, remplis UNE SEULE colonne de niveau : son rattachement est déduit automatiquement "
        "(le dernier élément du niveau immédiatement supérieur renseigné au-dessus)."
    ])
    instructions.append([
        "- Une colonne de note ou de remarque doit être placée APRÈS « Commentaire », sinon elle serait lue "
        "comme un niveau."
    ])
    instructions.append([
        "- Les colonnes Code / Valeur de base / Budget alloué / Quantité prévue / Unité / Date début / Date fin / "
        "Commentaire s'appliquent à l'élément de la même ligne, quel que soit son niveau, ou à la Sous-activité "
        "(Code, Valeur de base, Budget alloué et Commentaire uniquement pour un élément de niveau)."
    ])
    instructions.append([
        "- Méthode de calcul (facultative, liste déroulante) : comment calculer le taux d'exécution de l'élément "
        "de la ligne — Par quantité, Par tâches pondérées (ses sous-activités), Par jalons pondérés, Par livrables, "
        "Binaire, Saisie manuelle. Vide : celle du niveau au-dessus, sinon du projet, sinon de l'organisation."
    ])
    instructions.append([
        "- Poids (%) (facultatif) : sur une ligne de Sous-activité, poids de la tâche (méthode « tâches pondérées », "
        "les poids des sous-activités d'un élément totalisant 100) ; sur un élément, son poids quand le niveau "
        "au-dessus agrège par « moyenne pondérée par les poids »."
    ])
    instructions.append([
        "- Valeur de base : niveau avant le démarrage de l'activité (comme la Valeur de référence d'un "
        "indicateur) — permet de tracer la progression attendue dans le temps, pas seulement 0 → cible."
    ])
    instructions.append(["- Réimporter le même fichier met à jour les éléments déjà importés (même nom, même position)."])
    instructions.append([
        "- Feuille « Grilles d'alerte » (facultative) : pour donner au projet, ou à une activité précise "
        "(par son libellé exact) créée dans la feuille « Planification » ci-dessus, sa propre grille de "
        "paliers plutôt que d'hériter de la grille globale — une ligne par palier, plusieurs lignes pour la "
        "même portée forment sa grille complète."
    ])

    buffer = io.BytesIO()
    adapter_classeur(wb)
    wb.save(buffer)
    return buffer.getvalue()


def _texte(champs, cle, defaut=""):
    v = champs.get(cle)
    return str(v).strip() if v not in (None, "") else defaut


def _nombre(champs, cle, defaut=0):
    v = champs.get(cle)
    if v in (None, ""):
        return defaut
    try:
        return float(v)
    except (TypeError, ValueError):
        return defaut


def _entier_ou_none(champs, cle):
    v = champs.get(cle)
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _date(champs, cle):
    v = champs.get(cle)
    if not v:
        return None
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.date() if isinstance(v, datetime.datetime) else v
    try:
        return datetime.datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _resoudre_partenaire(nom, type_):
    from apps.partners.models import Partenaire

    nom = (nom or "").strip()
    if not nom:
        return None
    existant = Partenaire.objects.filter(nom__iexact=nom, type=type_).first()
    return existant or Partenaire.objects.create(nom=nom, type=type_)


def _lire_champs_cle_valeur(feuille) -> dict:
    champs = {}
    for row in feuille.iter_rows(min_row=1, values_only=True):
        if not row or not row[0]:
            continue
        cle = str(row[0]).strip()
        champs[cle] = row[1] if len(row) > 1 else None
    return champs


def methode_depuis_texte(texte):
    """
    Méthode de calcul saisie dans un fichier (libellé « Par tâches pondérées », code
    « TACHES », ou mot-clé « tâches ») → code de MethodeCalcul ; None si inconnue.
    """
    from .models import MethodeCalcul

    saisi = _normaliser_entete(str(texte))
    for code, libelle in MethodeCalcul.choices:
        if saisi in (_normaliser_entete(code), _normaliser_entete(libelle)):
            return code
    mots_cles = {"quantite": "QUANTITE", "tache": "TACHES", "jalon": "JALONS", "livrable": "LIVRABLES",
                 "binaire": "BINAIRE", "manuel": "MANUELLE"}
    return next((code for mot, code in mots_cles.items() if mot in saisi), None)


def _ligne_entetes(lignes) -> int:
    """
    Index de la ligne d'en-têtes de la feuille « Planification » : la
    première (parmi les 10 premières) qui contient « Sous-activité » ou une
    colonne de données connue — le modèle place une légende au-dessus, et un
    ancien fichier sans légende a ses en-têtes en première ligne.
    """
    reperes = {_normaliser_entete(n) for n in ("Sous-activité", "Quantité prévue", "Budget alloué (FCFA)", "Unité")}
    for i, ligne in enumerate(lignes[:10]):
        if any(c and _normaliser_entete(str(c)) in reperes for c in ligne):
            return i
    return 0


def importer_planification(feuille, projet) -> dict:
    """
    Importe la feuille « Planification » dans la planification du projet.

    Toutes les colonnes placées avant « Sous-activité » (hors colonnes de
    données connues et colonnes « Code… ») sont les niveaux de la
    planification, du plus haut au plus bas — leurs noms et leur nombre sont
    libres (ex : « Objectif général » → « Objectif spécifique » → « Activité »,
    ou « Résultat » → « Pilier » → « Activité »). Chaque niveau devient une
    profondeur d'Activite (via activite_parent) et le nom de la colonne
    devient le nom affiché de ce niveau pour ce projet (NiveauActivite), sauf
    s'il est déjà nommé.
    """
    from .models import Activite, NiveauActivite, SousActivite

    resultat = {"elements_crees": 0, "sous_activites_creees": 0, "niveaux": [], "erreurs": []}

    lignes = list(feuille.iter_rows(min_row=1, values_only=True))
    if not lignes:
        return resultat

    ligne_entetes = _ligne_entetes(lignes)
    entetes = [str(c).strip() if c else "" for c in lignes[ligne_entetes]]
    entetes_normalises = [_normaliser_entete(e) for e in entetes]

    def index(nom):
        nom_normalise = _normaliser_entete(nom)
        return entetes_normalises.index(nom_normalise) if nom_normalise in entetes_normalises else None

    idx_sa = index("Sous-activité")
    idx_code = next((i for i, e in enumerate(entetes_normalises) if e.startswith("code")), None)
    idx_valeur_ref = index("Valeur de base")
    idx_budget = index("Budget alloué (FCFA)")
    idx_qte = index("Quantité prévue")
    idx_unite = index("Unité")
    idx_debut = index("Date début (AAAA-MM-JJ)")
    idx_fin = index("Date fin (AAAA-MM-JJ)")
    idx_commentaire = index("Commentaire")
    idx_methode = index("Méthode de calcul")
    idx_poids = index("Poids (%)")

    colonnes_donnees = {
        i
        for i in (
            idx_sa, idx_code, idx_valeur_ref, idx_budget, idx_qte, idx_unite, idx_debut, idx_fin, idx_commentaire,
            idx_methode, idx_poids,
        )
        if i is not None
    }
    # Une colonne = un niveau, sans devinette sur son contenu : toute colonne
    # nommée avant « Sous-activité » (ou avant la première colonne de données
    # s'il n'y a pas de Sous-activité) est un niveau.
    borne_fin = idx_sa if idx_sa is not None else min((colonnes_donnees - {idx_code}) | {len(entetes)})
    idx_niveaux = [
        i
        for i in range(0, borne_fin)
        if i not in colonnes_donnees and entetes[i] and not entetes_normalises[i].startswith("code")
    ]
    resultat["niveaux"] = [entetes[i] for i in idx_niveaux]

    if not idx_niveaux:
        resultat["erreurs"].append(
            {"ligne": 1, "message": "Aucune colonne de niveau trouvée avant « Sous-activité »."}
        )
        return resultat

    profondeurs_existantes = set(NiveauActivite.objects.filter(projet=projet).values_list("profondeur", flat=True))
    for profondeur, idx in enumerate(idx_niveaux):
        if profondeur not in profondeurs_existantes:
            NiveauActivite.objects.create(projet=projet, profondeur=profondeur, nom_niveau=entetes[idx])

    def valeur(ligne, idx):
        if idx is None or idx >= len(ligne):
            return None
        return ligne[idx]

    def date_cellule(ligne, idx):
        v = valeur(ligne, idx)
        if not v:
            return None
        if isinstance(v, (datetime.date, datetime.datetime)):
            return v.date() if isinstance(v, datetime.datetime) else v
        try:
            return datetime.datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    dernier_par_niveau: list = [None] * len(idx_niveaux)

    for numero, ligne in enumerate(lignes[ligne_entetes + 1 :], start=ligne_entetes + 2):
        if not any(ligne):
            continue

        profondeurs_remplies = [p for p, idx in enumerate(idx_niveaux) if valeur(ligne, idx)]
        if len(profondeurs_remplies) > 1:
            resultat["erreurs"].append(
                {"ligne": numero, "message": "Une seule colonne de niveau doit être remplie par ligne — ligne ignorée."}
            )
            continue

        if profondeurs_remplies:
            profondeur = profondeurs_remplies[0]
            parent = dernier_par_niveau[profondeur - 1] if profondeur > 0 else None
            if profondeur > 0 and parent is None:
                nom_niveau_parent = entetes[idx_niveaux[profondeur - 1]]
                resultat["erreurs"].append(
                    {
                        "ligne": numero,
                        "message": f"Aucun élément « {nom_niveau_parent} » renseigné au-dessus pour rattacher "
                        "cette ligne — ligne ignorée.",
                    }
                )
                continue

            nom = str(valeur(ligne, idx_niveaux[profondeur])).strip()
            existant = Activite.objects.filter(projet=projet, activite_parent=parent, libelle__iexact=nom).first()
            element = existant or Activite(projet=projet, activite_parent=parent, libelle=nom)
            element.libelle = nom
            if valeur(ligne, idx_code):
                element.code_activite = str(valeur(ligne, idx_code)).strip()
            if valeur(ligne, idx_valeur_ref) not in (None, ""):
                element.valeur_reference = valeur(ligne, idx_valeur_ref)
            if valeur(ligne, idx_budget) not in (None, ""):
                element.budget_alloue = valeur(ligne, idx_budget)
            if valeur(ligne, idx_qte) not in (None, ""):
                element.quantite_prevue = valeur(ligne, idx_qte)
            if valeur(ligne, idx_unite):
                element.unite_quantite = str(valeur(ligne, idx_unite)).strip()
            date_debut = date_cellule(ligne, idx_debut)
            if date_debut:
                element.date_debut = date_debut
            date_fin = date_cellule(ligne, idx_fin)
            if date_fin:
                element.date_fin = date_fin
            if valeur(ligne, idx_commentaire):
                element.commentaire = str(valeur(ligne, idx_commentaire)).strip()
            if valeur(ligne, idx_methode):
                methode = methode_depuis_texte(valeur(ligne, idx_methode))
                if methode is None:
                    resultat["erreurs"].append(
                        {
                            "ligne": numero,
                            "message": f"Méthode de calcul inconnue « {valeur(ligne, idx_methode)} » — laissée vide "
                            "(héritée du niveau au-dessus ou du projet).",
                        }
                    )
                else:
                    element.methode_calcul = methode
            if valeur(ligne, idx_poids) not in (None, ""):
                element.poids = valeur(ligne, idx_poids)
            try:
                element.clean()
            except Exception as exc:  # ValidationError du modèle
                resultat["erreurs"].append({"ligne": numero, "message": str(exc)})
                continue
            element.save()
            if not existant:
                resultat["elements_crees"] += 1

            dernier_par_niveau[profondeur] = element
            for j in range(profondeur + 1, len(dernier_par_niveau)):
                dernier_par_niveau[j] = None
            continue

        if idx_sa is not None and valeur(ligne, idx_sa):
            element = next((a for a in reversed(dernier_par_niveau) if a is not None), None)
            if not element:
                resultat["erreurs"].append(
                    {"ligne": numero, "message": v('Aucun élément de planification défini au-dessus — ligne ignorée.')}
                )
                continue
            nom = str(valeur(ligne, idx_sa)).strip()
            existant = SousActivite.objects.filter(activite=element, libelle__iexact=nom).first()
            sa = existant or SousActivite(activite=element, libelle=nom)
            sa.libelle = nom
            if valeur(ligne, idx_qte) not in (None, ""):
                sa.quantite_prevue = valeur(ligne, idx_qte)
            if valeur(ligne, idx_poids) not in (None, ""):
                sa.poids = valeur(ligne, idx_poids)
            if valeur(ligne, idx_unite):
                sa.unite_quantite = str(valeur(ligne, idx_unite)).strip()
            date_debut = date_cellule(ligne, idx_debut)
            if date_debut:
                sa.date_debut = date_debut
            date_fin = date_cellule(ligne, idx_fin)
            if date_fin:
                sa.date_fin = date_fin
            sa.save()
            if not existant:
                resultat["sous_activites_creees"] += 1
            continue

    return resultat


def importer_projet(fichier, cadre_strategique_impose=None) -> dict:
    """
    Crée un projet (feuille « Projet ») et sa planification (feuille
    « Planification ») depuis un classeur Excel. `cadre_strategique_impose`
    permet à l'import combiné (apps.planification) d'imposer le cadre
    stratégique qu'il vient de créer, sans passer par la colonne « Cadre
    stratégique » de la feuille.
    """
    from apps.indicators.import_excel import importer_paliers_alerte

    from .models import Activite, Projet

    wb = ramener_classeur(load_workbook(fichier, data_only=True))
    resultat = importer_projet_depuis_wb(wb, cadre_strategique_impose=cadre_strategique_impose)

    if resultat.get("projet_id") and "Grilles d'alerte" in wb.sheetnames:
        projet = Projet.objects.get(id=resultat["projet_id"])
        activites_par_nom = {
            a.libelle.strip().lower(): a
            for a in Activite.objects.filter(projet=projet)
        }
        resultat_paliers = importer_paliers_alerte(
            wb["Grilles d'alerte"], projet=projet, activites_par_nom=activites_par_nom
        )
        resultat["grilles_alerte_creees"] = resultat_paliers["grilles_creees"]
        resultat["erreurs"] += [
            {"ligne": e["ligne"], "message": f"{v("[Grilles d'alerte] ")}{e['message']}"} for e in resultat_paliers["erreurs"]
        ]

    return resultat


def importer_projet_depuis_wb(wb, cadre_strategique_impose=None) -> dict:
    from django.contrib.auth import get_user_model

    from apps.strategy.models import CadreStrategique, ElementStrategique

    from .models import Projet

    User = get_user_model()

    if "Projet" not in wb.sheetnames:
        return {"projet_id": None, "erreurs": [{"ligne": 0, "message": v('Feuille « Projet » introuvable.')}], "avertissements": []}

    champs = _lire_champs_cle_valeur(wb["Projet"])
    erreurs = []
    avertissements = []

    nom = _texte(champs, "Nom du projet")
    code = _texte(champs, "Code du projet")
    if not nom or not code:
        erreurs.append({"ligne": 0, "message": v('Nom du projet et Code du projet sont obligatoires.')})
        return {"projet_id": None, "erreurs": erreurs, "avertissements": avertissements}

    if Projet.objects.filter(code=code).exists():
        erreurs.append({"ligne": 0, "message": f"{v('Un projet avec le code « ')}{code} » existe déjà — import annulé."})
        return {"projet_id": None, "erreurs": erreurs, "avertissements": avertissements}

    date_debut = _date(champs, "Date de début (AAAA-MM-JJ)")
    date_fin = _date(champs, "Date de fin (AAAA-MM-JJ)")
    if not date_debut or not date_fin:
        erreurs.append(
            {"ligne": 0, "message": "Date de début et Date de fin sont obligatoires, au format AAAA-MM-JJ."}
        )
        return {"projet_id": None, "erreurs": erreurs, "avertissements": avertissements}

    cadre = cadre_strategique_impose
    if cadre is None:
        nom_cadre = _texte(champs, "Cadre stratégique")
        if nom_cadre:
            cadre = CadreStrategique.objects.filter(nom__iexact=nom_cadre).first()
            if not cadre:
                avertissements.append(
                    {"ligne": 0, "message": f"{v('Cadre stratégique « ')}{nom_cadre} » introuvable — laissé vide."}
                )

    element_strategique = None
    nom_element = _texte(champs, "Rattachement dans le cadre stratégique")
    if nom_element:
        elements = ElementStrategique.objects.filter(nom__iexact=nom_element)
        if cadre is not None:
            elements = elements.filter(type_niveau__cadre_strategique=cadre)
        element_strategique = elements.first()
        if element_strategique is None:
            avertissements.append(
                {"ligne": 0, "message": f"Élément « {nom_element} » introuvable dans le cadre — rattachement laissé vide."}
            )
        elif cadre is None:
            cadre = element_strategique.type_niveau.cadre_strategique

    pays = [c.strip().upper() for c in _texte(champs, "Pays (codes ISO séparés par ;)").split(";") if c.strip()]

    statut_brut = _texte(champs, "Statut (EN_PREPARATION/EN_COURS/CLOTURE)", "EN_PREPARATION").upper()
    statut = statut_brut if statut_brut in dict(Projet.Statut.choices) else Projet.Statut.EN_PREPARATION

    type_brut = _texte(champs, "Type de mise en œuvre (DIRECT/CONSORTIUM)", "DIRECT").upper()
    type_mise_en_oeuvre = (
        type_brut if type_brut in dict(Projet.TypeMiseEnOeuvre.choices) else Projet.TypeMiseEnOeuvre.DIRECT
    )

    bailleur = _resoudre_partenaire(_texte(champs, "Bailleur"), "BAILLEUR")
    partenaire_mise_en_oeuvre = _resoudre_partenaire(_texte(champs, "Partenaire de mise en œuvre"), "MISE_EN_OEUVRE")
    noms_consortium = [c.strip() for c in _texte(champs, "Partenaires du consortium (séparés par ;)").split(";") if c.strip()]
    partenaires_consortium = [p for p in (_resoudre_partenaire(n, "MISE_EN_OEUVRE") for n in noms_consortium) if p]

    identifiants_affectes = [
        i.strip()
        for i in _texte(champs, "Utilisateurs affectés — identifiants séparés par ; (accès plateforme)").split(";")
        if i.strip()
    ]
    utilisateurs_affectes = []
    for identifiant in identifiants_affectes:
        utilisateur = User.objects.filter(username__iexact=identifiant).first()
        if utilisateur:
            utilisateurs_affectes.append(utilisateur)
        else:
            avertissements.append(
                {"ligne": 0, "message": f"{v('Utilisateur « ')}{identifiant}{v(' » introuvable — non affecté au projet.')}"}
            )

    projet = Projet.objects.create(
        nom=nom,
        code=code,
        pays=pays,
        cadre_strategique=cadre,
        element_strategique=element_strategique,
        budget_total=_nombre(champs, "Budget total (FCFA)"),
        fonds_propres=_nombre(champs, "Fonds propres (FCFA)"),
        date_debut=date_debut,
        date_fin=date_fin,
        statut=statut,
        type_mise_en_oeuvre=type_mise_en_oeuvre,
        partenaire_bailleur=bailleur,
        partenaire_mise_en_oeuvre=partenaire_mise_en_oeuvre,
        chef_de_projet_nom=_texte(champs, "Chef de projet"),
        cible_totale=_entier_ou_none(champs, "Cible totale"),
        cible_hommes=_entier_ou_none(champs, "Cible hommes"),
        cible_femmes=_entier_ou_none(champs, "Cible femmes"),
        cible_jeunes=_entier_ou_none(champs, "Cible jeunes"),
        cible_pdi=_entier_ou_none(champs, "Cible PDI"),
    )
    if partenaires_consortium:
        projet.partenaires_consortium.set(partenaires_consortium)
    if utilisateurs_affectes:
        projet.utilisateurs_affectes.set(utilisateurs_affectes)

    resultat_plan = {"elements_crees": 0, "sous_activites_creees": 0, "niveaux": [], "erreurs": []}
    if "Planification" in wb.sheetnames:
        resultat_plan = importer_planification(wb["Planification"], projet)

    return {
        "projet_id": projet.id,
        "projet_code": projet.code,
        **resultat_plan,
        "erreurs": erreurs + resultat_plan["erreurs"],
        "avertissements": avertissements,
    }
