"""
Import en masse de la structuration stratégique (niveaux + éléments) depuis
un fichier Excel — évite de tout ressaisir à la main écran par écran.

Format "plan" (une colonne par niveau, comme un sommaire Word) plutôt qu'un
système de Code/Parent à taper à la main : trop technique pour un
utilisateur non-développeur (confusion constatée en usage réel). La
hiérarchie se déduit uniquement de la position :
- une ligne ne remplit qu'une seule colonne (= un seul niveau) ;
- son parent est le dernier élément rencontré dans la colonne immédiatement
  à sa gauche (ou plus à gauche encore si le niveau autorise le saut de
  niveau).

Tout est scopé à un CadreStrategique précis : plusieurs cadres coexistent
sans jamais se mélanger (niveaux et éléments propres à chacun).

Best-effort : une ligne en erreur est ignorée sans bloquer l'import des
autres, et tout est rapporté au client. Rejouable : réimporter le même
fichier met à jour les éléments déjà créés (même niveau, même nom, même
parent) plutôt que de les dupliquer.
"""
import io
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.langues import langue_active, vers_francais
from apps.core.vocabulaire import adapter_classeur

# Reconnaît le format "CODE — Nom" tel que généré par exporter_structuration
# (code = un seul mot sans espace, ex : "AXE1", "OR1.1") — permet de
# réimporter tel quel un export sans dupliquer les éléments qui ont un code
# (le rattachement se ferait sinon sur "CODE — Nom" entier, jamais égal au
# nom seul stocké en base).
RE_CODE_NOM = re.compile(r"^(\S+) — (.+)$")


def _decouper_code_nom(texte: str) -> tuple[str, str]:
    match = RE_CODE_NOM.match(texte)
    if match:
        return match.group(1), match.group(2)
    return "", texte

NOMS_NIVEAUX_EXEMPLE = ["Orientation stratégique", "Axe d'intervention"]

# Repère visuel des colonnes de niveau (noms libres), comme la feuille « Planification ».
COULEUR_NIVEAU = "FFF2CC"
DEBUT_LEGENDE = "En jaune :"
# Texte entier (pas de f-string) : il se traduit d'un bloc dans les modèles en d'autres langues.
LEGENDE_STRUCTURATION = (
    "En jaune : les niveaux de votre structuration, de gauche à droite. Leurs noms et leur nombre sont "
    "libres (ex : Plan → Programme → Résultat → Composante) — renommez, ajoutez ou supprimez des colonnes."
)
COMMENTAIRE_NIVEAU = (
    "Nom libre : renommez cette colonne, ou ajoutez des colonnes de niveau (à droite, ou entre deux "
    "colonnes : le niveau sera créé à cette position)."
)


def remplir_feuille_structuration(feuille, noms_colonnes, lignes_exemple=(), lignes_vides=20):
    """
    Feuille « Structuration » d'un modèle : ligne 1 = légende, ligne 2 = une
    colonne par niveau (en jaune, commentée), puis les éléments.
    """
    nb = max(len(noms_colonnes), 1)
    feuille.append([LEGENDE_STRUCTURATION])
    feuille.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(nb, 2))
    legende = feuille.cell(row=1, column=1)
    legende.font = Font(italic=True, color="7F6000")
    legende.fill = PatternFill("solid", fgColor=COULEUR_NIVEAU)
    legende.alignment = Alignment(wrap_text=True, vertical="center")
    feuille.row_dimensions[1].height = 32

    feuille.append(list(noms_colonnes))
    for cellule in feuille[2]:
        cellule.font = Font(bold=True)
        cellule.fill = PatternFill("solid", fgColor=COULEUR_NIVEAU)
        cellule.comment = Comment(COMMENTAIRE_NIVEAU, "Plateforme S&E")
    for ligne in lignes_exemple:
        feuille.append(ligne)
    for _ in range(lignes_vides):
        feuille.append([""] * nb)
    quadriller(feuille, min_row=2, max_col=nb)
    figer_entete(feuille, ligne_entete=2)
    for i in range(nb):
        feuille.column_dimensions[chr(ord("A") + i)].width = 42

LIGNES_EXEMPLE = [
    ["Amplifier la diffusion des pratiques agroécologiques et de protection de l'environnement", ""],
    ["", "Le renforcement des capacités des producteurs et productrices"],
    ["", "Le renforcement de la structuration des producteurs et productrices accompagnés"],
]


def generer_modele_import(cadre_strategique) -> bytes:
    from .models import TypeNiveau

    from .import_chaine import COLONNE_CONTRIBUTION

    from apps.core.langues import langue_active, traduire

    from .fiche_excel import INSTRUCTIONS_FICHE, ajouter_feuilles_fiche, avec_fiche, traduire_classeur_document

    fiche = avec_fiche(cadre_strategique)
    niveaux = list(TypeNiveau.objects.filter(cadre_strategique=cadre_strategique).order_by("ordre"))
    # Programme, Pilier… sans niveaux : deux colonnes à renommer, sans exemple (il serait importé),
    # nommées dans la langue du modèle (ce seront les noms des niveaux créés à l'import).
    noms_colonnes = [n.nom_niveau for n in niveaux] if niveaux else (
        [traduire("Action"), traduire("Intervention")] if fiche else NOMS_NIVEAUX_EXEMPLE)
    if fiche and not cadre_strategique.document_parent_id:
        noms_colonnes = [*noms_colonnes, COLONNE_CONTRIBUTION]
    # Document rattaché à un maillon au-dessus : chaque élément peut préciser à quoi il contribue.
    if cadre_strategique.document_parent_id:
        noms_colonnes = [*noms_colonnes, COLONNE_CONTRIBUTION]

    wb = Workbook()
    feuille = wb.active
    feuille.title = "Structuration"
    remplir_feuille_structuration(feuille, noms_colonnes, [] if niveaux or fiche else LIGNES_EXEMPLE)

    instructions = wb.create_sheet("Instructions")
    if fiche:
        # Même présentation que le modèle d'un projet : Fiche, Financements, Structuration, Instructions.
        ajouter_feuilles_fiche(wb, cadre_strategique)
        wb.active = 0
        for ligne in [*INSTRUCTIONS_FICHE, ""]:
            instructions.append([ligne])
    instructions.append([f"Cadre stratégique : {cadre_strategique.nom}"])
    instructions.append(["Consignes"])
    instructions.append(["- Une colonne = un niveau de la hiérarchie (dans l'ordre, de gauche à droite), en jaune."])
    instructions.append(["- Le nombre de colonnes est libre : ajoute une colonne à droite pour un niveau plus fin, ou"])
    instructions.append(["  entre deux colonnes : le nouveau niveau est créé à cette position dans le cadre."])
    instructions.append(["- Sur chaque ligne, écris le nom de l'élément dans UNE SEULE colonne : celle de son niveau."])
    instructions.append(["- Son \"parent\" est déduit automatiquement : c'est le dernier élément écrit dans la"])
    instructions.append(["  colonne juste à gauche, au-dessus de cette ligne."])
    instructions.append(["- Exemple : une ligne \"Axe d'intervention\" se rattache au dernier \"Orientation"])
    instructions.append(["  stratégique\" écrit au-dessus d'elle."])
    instructions.append(["- Si le nom d'une colonne n'existe pas encore comme niveau dans ce cadre, il est"])
    instructions.append(["  créé automatiquement lors de l'import."])
    instructions.append(["- Réimporter le même fichier met à jour les éléments déjà importés (même nom, même"])
    instructions.append(["  position) au lieu de les dupliquer."])
    instructions.append(["- Colonne « Contribue à (code) » (dernière colonne, facultative) : code de l'élément d'un"])
    instructions.append(["  document d'un maillon au-dessus auquel l'élément de la ligne contribue."])

    buffer = io.BytesIO()
    # Dans une autre langue, la légende et le nom de la feuille « Structuration » sont aussi traduits
    # (pas les en-têtes : ce sont les noms des niveaux du cadre).
    if fiche:
        traduire_classeur_document(wb)
        if langue_active() == "fr":
            adapter_classeur(wb, feuilles={"Instructions"})
    else:
        adapter_classeur(wb, feuilles=None if langue_active() != "fr" else {"Instructions"})
    wb.save(buffer)
    return buffer.getvalue()


def exporter_structuration(cadre_strategique) -> bytes:
    """
    Export au même format "plan" que le modèle d'import (une colonne par
    niveau) mais rempli avec les éléments réels du cadre — le fichier généré
    est donc lui-même réimportable tel quel (voir importer_structuration).
    """
    from .models import ElementStrategique, TypeNiveau

    from .import_chaine import COLONNE_CONTRIBUTION

    niveaux = list(TypeNiveau.objects.filter(cadre_strategique=cadre_strategique).order_by("ordre"))
    noms_colonnes = [n.nom_niveau for n in niveaux]
    colonne_par_niveau = {n.id: i for i, n in enumerate(niveaux)}

    elements = list(
        ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre_strategique).select_related(
            "type_niveau", "contribue_a__type_niveau__cadre_strategique"
        )
    )
    avec_contribution = bool(cadre_strategique.document_parent_id) or any(e.contribue_a_id for e in elements)
    if avec_contribution:
        noms_colonnes = [*noms_colonnes, COLONNE_CONTRIBUTION]
    enfants_par_parent: dict = {}
    for element in elements:
        enfants_par_parent.setdefault(element.element_parent_id, []).append(element)
    for liste in enfants_par_parent.values():
        liste.sort(key=lambda e: (e.code or "", e.nom))

    wb = Workbook()
    feuille = wb.active
    feuille.title = "Structuration"
    feuille.append(noms_colonnes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    for i in range(len(noms_colonnes)):
        feuille.column_dimensions[chr(ord("A") + i)].width = 42

    def visiter(element):
        colonne = colonne_par_niveau.get(element.type_niveau_id)
        if colonne is not None:
            ligne = [""] * len(noms_colonnes)
            ligne[colonne] = f"{element.code} — {element.nom}" if element.code else element.nom
            if avec_contribution and element.contribue_a_id:
                cible = element.contribue_a
                ligne[-1] = f"{cible.type_niveau.cadre_strategique.nom} / {cible.code or cible.nom}"
            feuille.append(ligne)
        for enfant in enfants_par_parent.get(element.id, []):
            visiter(enfant)

    for racine in enfants_par_parent.get(None, []):
        visiter(racine)

    for _ in range(15):
        feuille.append([""] * len(noms_colonnes))
    quadriller(feuille, max_col=len(noms_colonnes))
    figer_entete(feuille)

    from .fiche_excel import INSTRUCTIONS_FICHE, ajouter_feuilles_fiche, avec_fiche, traduire_classeur_document

    if avec_fiche(cadre_strategique):
        # Même format que le modèle (réimportable tel quel) : Fiche, Financements, Structuration.
        ajouter_feuilles_fiche(wb, cadre_strategique)
        instructions = wb.create_sheet("Instructions")
        for ligne in INSTRUCTIONS_FICHE:
            instructions.append([ligne])
        instructions.column_dimensions["A"].width = 110
        wb.active = 0
    # Autre langue : la structure du fichier est traduite, les données restent telles quelles.
    traduire_classeur_document(wb)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _niveaux_des_colonnes(noms_colonnes, cadre_strategique):
    """
    Niveau (TypeNiveau) de chaque colonne : un niveau existant de ce cadre (même
    nom, sans tenir compte de la casse), ou un nouveau niveau créé à la position
    de sa colonne — juste sous le niveau de la colonne de gauche (tout en haut
    pour la première colonne). La chaîne des niveaux est ensuite renumérotée
    (ordre et niveau_parent), comme le fait l'écran de configuration. Les
    niveaux existants ne changent jamais d'ordre entre eux.
    """
    from .models import TypeNiveau

    chaine = list(TypeNiveau.objects.filter(cadre_strategique=cadre_strategique).order_by("ordre"))
    par_nom = {n.nom_niveau.strip().lower(): n for n in chaine}
    avant_insertion = list(chaine)
    types_par_colonne = []
    for i, nom in enumerate(noms_colonnes):
        cle = nom.strip().lower()
        if cle not in par_nom:
            nouveau = TypeNiveau.objects.create(cadre_strategique=cadre_strategique, nom_niveau=nom.strip(), ordre=0)
            position = chaine.index(types_par_colonne[i - 1]) + 1 if i > 0 else 0
            chaine.insert(position, nouveau)
            par_nom[cle] = nouveau
        types_par_colonne.append(par_nom[cle])

    for rang, niveau in enumerate(chaine, start=1):
        parent = chaine[rang - 2] if rang > 1 else None
        if niveau.ordre != rang or niveau.niveau_parent_id != (parent.id if parent else None):
            niveau.ordre = rang
            niveau.niveau_parent = parent
            niveau.save(update_fields=["ordre", "niveau_parent"])

    # Un niveau inséré au-dessus d'un niveau existant : les éléments déjà saisis de ce
    # niveau restent rattachés à leur ancien parent, on le signale.
    avertissements = []
    for niveau in chaine:
        if niveau in avant_insertion:
            continue
        rang = chaine.index(niveau)
        if rang + 1 < len(chaine) and chaine[rang + 1] in avant_insertion:
            dessous = chaine[rang + 1]
            avertissements.append(
                {
                    "ligne": 0,
                    "message": f"Niveau « {niveau.nom_niveau} » inséré au-dessus de « {dessous.nom_niveau} » : "
                    f"les éléments « {dessous.nom_niveau} » déjà saisis et absents du fichier gardent leur "
                    "ancien rattachement.",
                }
            )
    return types_par_colonne, avertissements


def importer_structuration(fichier, cadre_strategique) -> dict:
    """
    Import de la structuration d'un document. Feuille lue : « Structuration », sinon la première
    feuille qui n'est pas « Instructions » (jamais le mode d'emploi). Une feuille « Fiche » (modèle
    d'un programme, d'une composante…) renseigne aussi la fiche et les bailleurs du document, avant la
    structuration. Un fichier de la chaîne des documents (feuilles « Documents » et « Éléments »)
    importé ici est importé comme tel.
    """
    from .fiche_excel import FEUILLE_FICHE, FEUILLE_FINANCEMENTS, importer_fiche
    from .import_chaine import FEUILLE_DOCUMENTS, FEUILLE_ELEMENTS, _trouver_feuille

    wb = load_workbook(fichier, data_only=True)
    if _trouver_feuille(wb, FEUILLE_DOCUMENTS) is not None and _trouver_feuille(wb, FEUILLE_ELEMENTS) is not None:
        return _importer_fichier_chaine(fichier)
    erreurs_fiche, avertissements_fiche = [], []
    if _trouver_feuille(wb, FEUILLE_FICHE) is not None:
        erreurs_fiche, avertissements_fiche = importer_fiche(wb, cadre_strategique)
    ignorees = {"instructions", FEUILLE_FICHE.lower(), FEUILLE_FINANCEMENTS.lower()}
    feuille = _trouver_feuille(wb, "Structuration") or next(
        (f for f in wb.worksheets if str(vers_francais(f.title)).strip().lower() not in ignorees), None
    )
    if feuille is not None and not _a_des_elements(feuille):
        # Structuration laissée vide (seulement la légende et les en-têtes) : aucun niveau créé.
        feuille = None
    if feuille is None:
        rapport = {"niveaux_crees": 0, "elements_crees": 0, "elements_mis_a_jour": 0, "erreurs": [], "avertissements": []}
    else:
        rapport = importer_structuration_depuis_feuille(feuille, cadre_strategique)
    rapport["erreurs"] = [*erreurs_fiche, *rapport["erreurs"]]
    rapport["avertissements"] = [*avertissements_fiche, *rapport.get("avertissements", [])]
    rapport["fiche_mise_a_jour"] = _trouver_feuille(wb, FEUILLE_FICHE) is not None
    return rapport


def _meme_entete(saisie, francais) -> bool:
    """
    L'en-tête saisi désigne-t-il cet en-tête français ? Dans toutes les langues, sans tenir compte
    des accents, de la casse ni des espaces (« Contribue a (code) », « Contributes to (code) »).
    """
    from apps.core.langues import correspond

    return correspond(str(saisie or ""), francais)


def _a_des_elements(feuille) -> bool:
    """Au moins une ligne d'élément sous les en-têtes (la légende du modèle ne compte pas)."""
    lignes = [l for l in feuille.iter_rows(values_only=True) if any(c not in (None, "") for c in l)]
    if lignes and str(vers_francais(str(lignes[0][0] or ""))).startswith(DEBUT_LEGENDE):
        lignes = lignes[1:]
    return len(lignes) > 1


def _importer_fichier_chaine(fichier) -> dict:
    """Fichier de la chaîne importé depuis la page d'un document : compte rendu au format de la structuration."""
    from .import_chaine import importer_chaine

    fichier.seek(0)
    rapport = importer_chaine(fichier)
    avertissements = [
        {"ligne": 1, "message": (
            f"Fichier de la chaîne des documents : {rapport['documents_crees']} document(s) créé(s), "
            f"{rapport['documents_mis_a_jour']} mis à jour."
        )},
        *rapport["avertissements"],
    ]
    return {
        "niveaux_crees": 0,
        "elements_crees": rapport["elements_crees"],
        "elements_mis_a_jour": rapport["elements_mis_a_jour"] + rapport["documents_mis_a_jour"] + rapport["documents_crees"],
        "erreurs": rapport["erreurs"],
        "avertissements": avertissements,
    }


def importer_structuration_depuis_feuille(feuille, cadre_strategique) -> dict:
    from .models import ElementStrategique, TypeNiveau

    lignes = list(feuille.iter_rows(min_row=1, values_only=True))
    # Ligne de légende du modèle (au-dessus des en-têtes) : ignorée.
    premiere_ligne = 1
    # (éventuellement traduite : un modèle téléchargé dans une autre langue)
    if lignes and lignes[0] and str(vers_francais(str(lignes[0][0] or ""))).startswith(DEBUT_LEGENDE):
        lignes, premiere_ligne = lignes[1:], 2
    if not lignes:
        return {"niveaux_crees": 0, "elements_crees": 0, "elements_mis_a_jour": 0, "erreurs": [], "avertissements": []}

    from .import_chaine import COLONNE_CONTRIBUTION, resoudre_contribution

    noms_colonnes = [str(c).strip() if c else "" for c in lignes[0]]
    while noms_colonnes and not noms_colonnes[-1]:
        noms_colonnes.pop()
    # Colonne « Contribue à (code) » : pas un niveau, lue à part (elle peut être traduite).
    colonne_contribution = next(
        (i for i, nom in enumerate(noms_colonnes) if _meme_entete(nom, COLONNE_CONTRIBUTION)), None
    )
    if colonne_contribution is not None:
        noms_colonnes = noms_colonnes[:colonne_contribution]

    if not noms_colonnes:
        return {
            "niveaux_crees": 0,
            "elements_crees": 0,
            "elements_mis_a_jour": 0,
            "erreurs": [{"ligne": premiere_ligne, "message": "Aucune colonne de niveau trouvée sur la ligne d'en-têtes."}],
            "avertissements": [],
        }

    niveaux_avant = TypeNiveau.objects.filter(cadre_strategique=cadre_strategique).count()
    types_par_colonne, avertissements = _niveaux_des_colonnes(noms_colonnes, cadre_strategique)

    elements_existants: dict[tuple[int, str, int | None], ElementStrategique] = {
        (e.type_niveau_id, e.nom.strip().lower(), e.element_parent_id): e
        for e in ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre_strategique)
    }
    dernier_par_colonne: list[ElementStrategique | None] = [None] * len(noms_colonnes)
    elements_crees = 0
    elements_mis_a_jour = 0
    erreurs = []

    for numero, ligne in enumerate(lignes[1:], start=premiere_ligne + 1):
        cellules = list(ligne[: len(noms_colonnes)])
        colonnes_remplies = [i for i, v in enumerate(cellules) if v not in (None, "")]

        if not colonnes_remplies:
            continue
        if len(colonnes_remplies) > 1:
            erreurs.append(
                {"ligne": numero, "message": "Une seule colonne doit être remplie par ligne — ligne ignorée."}
            )
            continue

        idx = colonnes_remplies[0]
        code, nom = _decouper_code_nom(str(cellules[idx]).strip())
        type_niveau = types_par_colonne[idx]

        element_parent = None
        if idx > 0:
            if dernier_par_colonne[idx - 1] is not None:
                element_parent = dernier_par_colonne[idx - 1]
            elif type_niveau.saut_niveau_autorise:
                for j in range(idx - 2, -1, -1):
                    if dernier_par_colonne[j] is not None:
                        element_parent = dernier_par_colonne[j]
                        break
            if element_parent is None:
                erreurs.append(
                    {
                        "ligne": numero,
                        "message": f"Aucun élément « {noms_colonnes[idx - 1]} » renseigné au-dessus pour rattacher cette ligne — ligne ignorée.",
                    }
                )
                continue

        cle = (type_niveau.id, nom.lower(), element_parent.id if element_parent else None)
        existant = elements_existants.get(cle)
        instance = existant or ElementStrategique(type_niveau=type_niveau, code="")
        instance.type_niveau = type_niveau
        instance.element_parent = element_parent
        instance.nom = nom
        if code:
            instance.code = code

        try:
            instance.clean()
        except DjangoValidationError as exc:
            erreurs.append({"ligne": numero, "message": " ".join(exc.messages)})
            continue

        instance.save()
        texte_contribution = ligne[colonne_contribution] if colonne_contribution is not None and colonne_contribution < len(ligne) else None
        if texte_contribution not in (None, ""):
            from .chaine import controler_contribution

            cible, message = resoudre_contribution(cadre_strategique, texte_contribution)
            erreurs_contribution = [message] if cible is None else controler_contribution(instance, cible)[0]
            if erreurs_contribution:
                erreurs.append({"ligne": numero, "message": f"{instance} : {' '.join(erreurs_contribution)}"})
            else:
                for message in controler_contribution(instance, cible)[1]:
                    avertissements.append({"ligne": numero, "message": f"{instance} : {message}"})
                instance.contribue_a = cible
                instance.save(update_fields=["contribue_a", "updated_at"])
        elements_existants[cle] = instance
        dernier_par_colonne[idx] = instance
        for j in range(idx + 1, len(dernier_par_colonne)):
            dernier_par_colonne[j] = None

        if existant:
            elements_mis_a_jour += 1
        else:
            elements_crees += 1

    return {
        "niveaux_crees": TypeNiveau.objects.filter(cadre_strategique=cadre_strategique).count() - niveaux_avant,
        "elements_crees": elements_crees,
        "elements_mis_a_jour": elements_mis_a_jour,
        "erreurs": erreurs,
        "avertissements": avertissements,
    }


def supprimer_cadre_strategique_cascade(cadre):
    """
    TypeNiveau/ElementStrategique sont en PROTECT (même logique que Projet :
    ne jamais perdre une arborescence par accident via un autre chemin de
    code), donc la suppression volontaire d'un cadre stratégique doit
    désimbriquer manuellement, des feuilles vers la racine, dans une
    transaction — même pattern que apps.projects.services.supprimer_projet_cascade.

    Les éléments sont supprimés feuille par feuille en suivant leur
    element_parent réel plutôt que le TypeNiveau.ordre attendu : un
    réordonnancement des niveaux après coup peut désynchroniser les deux,
    et supprimer par ordre supposé lèverait alors un ProtectedError.
    """
    from .models import ElementStrategique, TypeNiveau

    with transaction.atomic():
        restants = {e.id: e for e in ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre)}
        while restants:
            parents_references = {e.element_parent_id for e in restants.values() if e.element_parent_id}
            feuilles = [eid for eid in restants if eid not in parents_references]
            if not feuilles:
                break
            ElementStrategique.objects.filter(id__in=feuilles).delete()
            for eid in feuilles:
                restants.pop(eid)

        niveaux_desc = list(TypeNiveau.objects.filter(cadre_strategique=cadre).order_by("-ordre"))
        for niveau in niveaux_desc:
            niveau.delete()
        cadre.delete()
