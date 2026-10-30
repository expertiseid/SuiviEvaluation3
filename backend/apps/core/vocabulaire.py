"""
Vocabulaire de la plateforme, choisi par l'Administrateur (ConfigurationMenu.vocabulaire) :
chaque terme (« projet », « cadre stratégique »...) peut être remplacé par celui de
l'organisation (« action », « programme »...), avec son pluriel et son genre.

adapter_texte() remplace les termes par défaut dans un texte de l'INTERFACE (jamais dans
les données saisies) en gardant les majuscules et en accordant les petits mots qui
précèdent le terme (un/une, le/la/l', ce/cette, du/de la/de l'...). Les adjectifs placés
après le terme ne sont pas accordés.

Doit rester identique à frontend/src/utils/vocabulaire.ts.
"""
import re

# (clé, singulier par défaut, pluriel par défaut, féminin par défaut)
TERMES = [
    ("tableau_de_bord", "tableau de bord", "tableaux de bord", False),
    ("planification", "planification", "planifications", True),
    ("cadre_strategique", "cadre stratégique", "cadres stratégiques", False),
    ("projet", "projet", "projets", False),
    ("indicateur", "indicateur", "indicateurs", False),
    ("suivi", "suivi", "suivis", False),
    ("beneficiaire", "bénéficiaire", "bénéficiaires", False),
    ("doublon", "doublon", "doublons", False),
    ("zone_administrative", "zone administrative", "zones administratives", True),
    ("document", "document", "documents", False),
    ("utilisateur", "utilisateur", "utilisateurs", False),
    ("alerte", "alerte", "alertes", True),
]
CLES_TERMES = {cle for cle, *_ in TERMES}

_LETTRE = r"A-Za-zÀ-ÖØ-öø-ÿŒœ"
_VOYELLE = re.compile(r"^[aeiouyhàâäéèêëîïôöùûüœAEIOUYHÀÂÄÉÈÊËÎÏÔÖÙÛÜŒ]")

# Petit mot qui précède le terme → (forme masculine, forme féminine, forme devant voyelle)
_DETERMINANTS = {
    "un": ("un", "une", None),
    "une": ("un", "une", None),
    "le": ("le", "la", "l'"),
    "la": ("le", "la", "l'"),
    "l'": ("le", "la", "l'"),
    "ce": ("ce", "cette", "cet"),
    "cet": ("ce", "cette", "cet"),
    "cette": ("ce", "cette", "cet"),
    "du": ("du", "de la", "de l'"),
    "de la": ("du", "de la", "de l'"),
    "de l'": ("du", "de la", "de l'"),
    "au": ("au", "à la", "à l'"),
    "à la": ("au", "à la", "à l'"),
    "à l'": ("au", "à la", "à l'"),
    "nouveau": ("nouveau", "nouvelle", "nouvel"),
    "nouvel": ("nouveau", "nouvelle", "nouvel"),
    "nouvelle": ("nouveau", "nouvelle", "nouvelle"),
    "aucun": ("aucun", "aucune", None),
    "aucune": ("aucun", "aucune", None),
    "chaque": ("chaque", "chaque", None),
    "de": ("de", "de", "d'"),
    "d'": ("de", "de", "d'"),
}
# Apostrophe typographique acceptée comme l'apostrophe droite.
for _cle in [c for c in _DETERMINANTS if "'" in c]:
    _DETERMINANTS[_cle.replace("'", "’")] = _DETERMINANTS[_cle]
_MOTIF_DETERMINANT = "|".join(sorted((re.escape(d) for d in _DETERMINANTS), key=len, reverse=True))


def _casse(modele: str, texte: str) -> str:
    """Applique au remplacement la casse du texte d'origine (MAJUSCULES, Majuscule initiale)."""
    if len(modele) > 1 and modele.isupper():
        return texte.upper()
    if modele[:1].isupper():
        return texte[:1].upper() + texte[1:]
    # Terme en minuscules dans la phrase : on garde la saisie de l'Administrateur si elle
    # est tout en majuscules (sigle, choix délibéré), sinon minuscule initiale.
    return texte if texte.isupper() else texte[:1].lower() + texte[1:]


def _accorder(determinant: str, feminin: bool, terme: str) -> str:
    masculin, feminin_forme, devant_voyelle = _DETERMINANTS[determinant.lower()]
    forme = feminin_forme if feminin else masculin
    # Élision (l', d', de l', à l') quel que soit le genre ; « cet » / « nouvel » seulement au masculin.
    if devant_voyelle and _VOYELLE.match(terme) and (devant_voyelle.endswith("'") or not feminin):
        forme = devant_voyelle
    return _casse(determinant, forme)


def adapter_texte(texte: str, vocabulaire: dict | None) -> str:
    """Remplace les termes par défaut par ceux du vocabulaire, dans un texte d'interface."""
    if not texte or not vocabulaire:
        return texte
    for cle, singulier, pluriel, feminin_defaut in TERMES:
        choix = vocabulaire.get(cle) or {}
        nouveau_singulier = (choix.get("singulier") or "").strip()
        nouveau_pluriel = (choix.get("pluriel") or "").strip()
        if not nouveau_singulier and not nouveau_pluriel:
            continue
        nouveau_singulier = nouveau_singulier or singulier
        nouveau_pluriel = nouveau_pluriel or nouveau_singulier
        feminin = bool(choix.get("feminin", feminin_defaut))
        for ancien, nouveau, est_pluriel in ((pluriel, nouveau_pluriel, True), (singulier, nouveau_singulier, False)):
            motif = re.compile(
                rf"(?:(?<![{_LETTRE}])({_MOTIF_DETERMINANT})(\s*))?(?<![{_LETTRE}])({re.escape(ancien)})(?![{_LETTRE}])",
                re.IGNORECASE,
            )

            def remplacer(m, nouveau=nouveau, est_pluriel=est_pluriel):
                determinant, espace, terme = m.group(1), m.group(2) or "", m.group(3)
                remplacement = _casse(terme, nouveau)
                if determinant and not est_pluriel:
                    forme = _accorder(determinant, feminin, remplacement)
                    espace = "" if forme.endswith("'") else (espace or " ")
                    # Garde l'apostrophe typographique si le texte d'origine l'utilisait.
                    if "’" in determinant:
                        forme = forme.replace("'", "’")
                    return f"{forme}{espace}{remplacement}"
                return f"{determinant or ''}{espace}{remplacement}"

            texte = motif.sub(remplacer, texte)
    return texte


# --- Vocabulaire courant (ConfigurationMenu), avec un court cache -------------------------

_cache = {"vocabulaire": None, "instant": 0.0}
DUREE_CACHE_SECONDES = 10


def vocabulaire_courant() -> dict:
    import time

    from apps.dashboard.models import ConfigurationMenu

    if _cache["vocabulaire"] is None or time.monotonic() - _cache["instant"] > DUREE_CACHE_SECONDES:
        _cache["vocabulaire"] = ConfigurationMenu.courante().vocabulaire or {}
        _cache["instant"] = time.monotonic()
    return _cache["vocabulaire"]


def oublier_vocabulaire():
    """À appeler après une modification du vocabulaire."""
    _cache["vocabulaire"] = None


def v(texte: str) -> str:
    """
    Adapte un texte fixe (titre, en-tête, message) au vocabulaire de l'organisation ; dans un
    fichier produit dans une autre langue (voir apps.core.langues), le traduit.
    """
    from .langues import langue_active, traduire_texte_fixe

    if langue_active() != "fr":
        return traduire_texte_fixe(texte)
    return adapter_texte(texte, vocabulaire_courant())


def ramener_terme(texte: str) -> str:
    """
    Valeur saisie dans une cellule avec le vocabulaire de l'organisation (ex : « Action »)
    → terme par défaut correspondant (« Projet ») ; inchangée sinon.
    """
    vocabulaire = vocabulaire_courant()
    propre = (texte or "").strip().lower()
    for cle, singulier, pluriel, _ in TERMES:
        choix = vocabulaire.get(cle) or {}
        formes = {(choix.get("singulier") or "").strip().lower(), (choix.get("pluriel") or "").strip().lower()} - {""}
        if propre and propre in formes:
            return singulier[:1].upper() + singulier[1:]
    return texte


# --- Modèles Excel ----------------------------------------------------------------------
# Les modèles d'import sont générés avec le vocabulaire de l'organisation (noms de feuilles,
# en-têtes, consignes). À l'import, les noms adaptés sont ramenés aux noms par défaut, pour
# que les fonctions d'import n'aient qu'un seul jeu de noms à reconnaître.

# Feuilles dont les en-têtes sont des données (noms des niveaux du cadre) : jamais adaptées.
FEUILLES_A_EN_TETES_LIBRES = {"Structuration"}


def _en_tete_libre(feuille, cellule) -> bool:
    """Structuration : en-têtes = noms des niveaux du cadre (données), en ligne 1 ou 2."""
    return (
        feuille.title in FEUILLES_A_EN_TETES_LIBRES
        and cellule.row <= 2
        and not str(cellule.value or "").startswith("En jaune")
    )


def adapter_classeur(wb, feuilles=None):
    """
    Adapte tous les textes d'un modèle (feuilles, cellules, commentaires) au vocabulaire de
    l'organisation, ou les traduit s'il est produit dans une autre langue.
    """
    from .langues import langue_active, traduire_classeur

    if langue_active() != "fr":
        return traduire_classeur(wb, feuilles=feuilles, garder=_en_tete_libre)
    vocabulaire = vocabulaire_courant()
    if not vocabulaire:
        return wb
    for feuille in list(wb.worksheets):
        if feuilles is not None and feuille.title not in feuilles:
            continue
        for ligne in feuille.iter_rows():
            for cellule in ligne:
                if _en_tete_libre(feuille, cellule):
                    continue
                if isinstance(cellule.value, str):
                    cellule.value = adapter_texte(cellule.value, vocabulaire)
                if cellule.comment is not None:
                    cellule.comment.text = adapter_texte(cellule.comment.text, vocabulaire)
        feuille.title = adapter_texte(feuille.title, vocabulaire)[:31]
    return wb


def _normaliser(texte: str) -> str:
    import unicodedata

    sans_accents = "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.replace("-", " ").replace("’", "'").lower().split())


def libelles_des_modeles() -> set:
    """Noms de feuilles, en-têtes et champs fixes de tous les modèles d'import."""
    from apps.beneficiaries.services.import_excel import COLONNES as COLONNES_BENEFICIAIRES
    from apps.indicators.import_excel import COLONNES as COLONNES_INDICATEURS
    from apps.indicators.import_excel import COLONNES_PALIERS
    from apps.planification.services import CHAMPS_CADRE
    from apps.projects.import_excel import CHAMP_BAILLEUR_UNIQUE, CHAMPS_PROJET, COLONNES_FINANCEMENTS, COLONNES_PLANIFICATION
    from apps.strategy.import_chaine import COLONNES_DOCUMENTS, COLONNES_ELEMENTS, COLONNES_FICHE, COLONNES_MAILLONS
    from apps.strategy.fiche_excel import CHAMPS_FICHE
    from apps.suivi.canevas import libelles_canevas
    from apps.suivi.canevas_periode import libelles_canevas_periode

    return (
        {
            "Projet", "Planification", "Grilles d'alerte", "Instructions", "Indicateurs", "Bénéficiaires",
            "Cadre stratégique", "Structuration", "Financements", CHAMP_BAILLEUR_UNIQUE,
        }
        | {cle for cle, _ in CHAMPS_PROJET}
        | {cle for cle, _ in CHAMPS_CADRE}
        | set(COLONNES_PLANIFICATION)
        | set(COLONNES_FINANCEMENTS)
        | set(COLONNES_INDICATEURS)
        | set(COLONNES_PALIERS)
        | set(COLONNES_BENEFICIAIRES)
        | {"Maillons", "Documents", "Éléments"} | set(COLONNES_MAILLONS) | set(COLONNES_DOCUMENTS) | set(COLONNES_FICHE) | set(COLONNES_ELEMENTS)
        | {"Fiche"} | {libelle for libelle, _ in CHAMPS_FICHE}
        | libelles_canevas()
        | libelles_canevas_periode()
    )


def ramener_classeur(wb):
    """
    Classeur rempli à partir d'un modèle généré avec le vocabulaire de l'organisation, ou dans
    une autre langue : ramène noms de feuilles, en-têtes et noms de champs aux libellés par
    défaut, en français. Seuls les libellés fixes connus sont concernés — jamais les données
    ni les en-têtes de niveaux (noms libres). Sans effet sur un classeur aux noms par défaut.
    """
    from .langues import formes, titre_feuille

    vocabulaire = vocabulaire_courant()
    correspondances = {}
    for libelle in libelles_des_modeles():
        variantes = formes(libelle)
        if vocabulaire:
            variantes.add(adapter_texte(libelle, vocabulaire))
        for variante in variantes - {libelle}:
            correspondances[_normaliser(variante)] = libelle
            # Nom de feuille : raccourci à 31 caractères dans le modèle traduit.
            correspondances.setdefault(_normaliser(titre_feuille(variante)), libelle)
    if not correspondances:
        return wb
    for feuille in wb.worksheets:
        defaut = correspondances.get(_normaliser(feuille.title))
        if defaut:
            feuille.title = defaut
    for feuille in wb.worksheets:
        if feuille.title in FEUILLES_A_EN_TETES_LIBRES:
            continue
        # En-têtes : les premières lignes ; noms de champs : la première colonne (feuilles clé-valeur).
        for ligne in feuille.iter_rows(max_row=min(feuille.max_row, 3)):
            for cellule in ligne:
                if isinstance(cellule.value, str):
                    cellule.value = correspondances.get(_normaliser(cellule.value), cellule.value)
        for (cellule,) in feuille.iter_rows(min_col=1, max_col=1):
            if isinstance(cellule.value, str):
                cellule.value = correspondances.get(_normaliser(cellule.value), cellule.value)
    return wb
