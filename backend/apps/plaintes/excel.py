"""
Canevas Excel du paramétrage du mécanisme de plaintes (aller-retour) : le fichier téléchargé
contient la configuration actuelle ; complété ou corrigé hors ligne, il se réimporte.

Feuilles : « Mécanisme » (un réglage par ligne), « Types de retours », « Priorités »,
« Circuits » (une ligne par étape, dans l'ordre), « Catégories » (catégorie principale, puis
sous-catégorie), « Instructions » (jamais importée).

Import : rejouable (chaque élément est retrouvé par son nom, sans tenir compte des accents ni de
la casse) ; chaque ligne passe par les mêmes contrôles que la saisie à l'écran (serializers) ;
une ligne en erreur est ignorée et signalée avec sa feuille, sa ligne et la correction attendue.
Les étapes d'un circuit présent dans le fichier sont remplacées par celles du fichier. Rien
n'est supprimé : un élément absent du fichier reste tel quel.
"""
import io

from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.langues import correspond, langue_active, traduire_classeur

FEUILLE_MECANISME, FEUILLE_TYPES, FEUILLE_PRIORITES = "Mécanisme", "Types de retours", "Priorités"
FEUILLE_CIRCUITS, FEUILLE_CATEGORIES = "Circuits", "Catégories"
COLONNES_TYPES = ["Nom", "Description", "Actif (Oui / Non)"]
COLONNES_PRIORITES = ["Nom", "Urgente (Oui / Non)", "Délai (jours)", "Actif (Oui / Non)"]
COLONNES_CIRCUITS = ["Circuit", "Confidentiel (Oui / Non)", "Par défaut (Oui / Non)", "Étape", "Délai (jours)",
                     "Rôle responsable", "Personne responsable (identifiant)", "Clôture (Oui / Non)"]
COLONNES_CATEGORIES = ["Catégorie", "Sous-catégorie", "Description", "Sensible (Oui / Non)", "Circuit",
                       "Délai (jours)", "Actif (Oui / Non)"]
# Feuille « Mécanisme » : (libellé, champ).
REGLAGES = [
    ("Nom du mécanisme", "nom"),
    ("Plaintes anonymes autorisées (Oui / Non)", "anonymat_autorise"),
    ("Langues du formulaire public (fr ; en ; ar ; de ; es)", "langues"),
    ("Préfixe des numéros de dossier", "prefixe_numero"),
    ("Délais en jours ouvrés (Oui / Non)", "jours_ouvres"),
    ("Conservation des dossiers ordinaires (mois)", "conservation_ordinaire_mois"),
    ("Conservation des dossiers sensibles (mois)", "conservation_sensible_mois"),
    ("Texte d'information des plaignants", "texte_information"),
    ("Fichiers joints par les plaignants (Oui / Non)", "pieces_formulaire_public"),
    ("Taille maximale d'un fichier joint (Mo)", "taille_max_piece_mo"),
]
CHAMPS_OUI_NON = {"anonymat_autorise", "jours_ouvres", "pieces_formulaire_public"}
INSTRUCTIONS = [
    "Paramétrage du mécanisme de plaintes et retours",
    "",
    "- Ce fichier contient la configuration actuelle : complétez-la ou corrigez-la, puis réimportez-le",
    "  (Plaintes et retours › Paramétrage › Canevas Excel). Rien n'est supprimé : un élément absent du",
    "  fichier reste tel quel ; un élément présent est retrouvé par son nom et mis à jour.",
    "- Feuille « Mécanisme » : un réglage par ligne (colonne A = réglage, colonne B = valeur).",
    "- Feuille « Circuits » : une ligne par étape, dans l'ordre du traitement ; répétez le nom du circuit sur",
    "  chaque ligne. La dernière étape est l'étape de clôture. Dans un circuit confidentiel, chaque étape est",
    "  confiée à une personne (identifiant de connexion), jamais à un rôle.",
    "- Feuille « Catégories » : une ligne par catégorie principale (colonne « Sous-catégorie » vide), puis une",
    "  ligne par sous-catégorie (colonne « Catégorie » = la catégorie principale). Une catégorie sensible passe",
    "  par un circuit confidentiel. Les catégories liées à l'exploitation et aux abus sexuels restent sensibles.",
    "- Oui / Non : listes déroulantes. Cette feuille n'est jamais importée.",
]
JAUNE = PatternFill("solid", fgColor="FFF2CC")


def _oui_non(valeur) -> str:
    return "Oui" if valeur else "Non"


def _feuille(wb, titre, colonnes, lignes, largeurs, oui_non=()):
    feuille = wb.create_sheet(titre)
    feuille.append(colonnes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
        cellule.fill = JAUNE
    for ligne in lignes:
        feuille.append(ligne)
    for _ in range(15):
        feuille.append([""] * len(colonnes))
    quadriller(feuille, max_col=len(colonnes))
    figer_entete(feuille)
    for i, largeur in enumerate(largeurs):
        feuille.column_dimensions[chr(ord("A") + i)].width = largeur
    if oui_non:
        liste = DataValidation(type="list", formula1='"Oui,Non"', allow_blank=True)
        for nom in oui_non:
            lettre = chr(ord("A") + colonnes.index(nom))
            liste.add(f"{lettre}2:{lettre}{feuille.max_row}")
        feuille.add_data_validation(liste)
    return feuille


def exporter_parametrage() -> bytes:
    from .models import Categorie, Circuit, Mecanisme, Priorite, TypeRetour

    mecanisme = Mecanisme.courant()
    wb = Workbook()
    reglages = wb.active
    reglages.title = FEUILLE_MECANISME
    for libelle, champ in REGLAGES:
        valeur = getattr(mecanisme, champ)
        if champ in CHAMPS_OUI_NON:
            valeur = _oui_non(valeur)
        elif champ == "langues":
            valeur = " ; ".join(valeur)
        reglages.append([libelle, valeur])
    for cellule in reglages["A"]:
        cellule.font = Font(bold=True)
        cellule.fill = JAUNE
    reglages.column_dimensions["A"].width = 56
    reglages.column_dimensions["B"].width = 80
    quadriller(reglages, max_col=2)

    _feuille(wb, FEUILLE_TYPES, COLONNES_TYPES,
             [[t.nom, t.description, _oui_non(t.actif)] for t in TypeRetour.objects.all()], [30, 60, 16], ["Actif (Oui / Non)"])
    _feuille(wb, FEUILLE_PRIORITES, COLONNES_PRIORITES,
             [[p.nom, _oui_non(p.urgente), p.delai_jours, _oui_non(p.actif)] for p in Priorite.objects.all()],
             [24, 20, 14, 16], ["Urgente (Oui / Non)", "Actif (Oui / Non)"])
    lignes = []
    for c in Circuit.objects.prefetch_related("etapes__role", "etapes__responsable"):
        for e in c.etapes.order_by("ordre", "id"):
            lignes.append([c.nom, _oui_non(c.sensible), _oui_non(c.par_defaut), e.nom, e.delai_jours,
                           e.role.libelle if e.role_id else "", e.responsable.username if e.responsable_id else "",
                           _oui_non(e.est_cloture)])
    _feuille(wb, FEUILLE_CIRCUITS, COLONNES_CIRCUITS, lignes, [34, 18, 18, 40, 13, 26, 28, 16],
             ["Confidentiel (Oui / Non)", "Par défaut (Oui / Non)", "Clôture (Oui / Non)"])
    lignes = []
    for c in Categorie.objects.filter(parent__isnull=True).select_related("circuit").prefetch_related("sous_categories"):
        lignes.append([c.nom, "", c.description, _oui_non(c.sensible), c.circuit.nom if c.circuit_id else "",
                       c.delai_jours, _oui_non(c.actif)])
        for s in c.sous_categories.select_related("circuit").order_by("ordre", "nom"):
            lignes.append([c.nom, s.nom, s.description, _oui_non(s.sensible), s.circuit.nom if s.circuit_id else "",
                           s.delai_jours, _oui_non(s.actif)])
    _feuille(wb, FEUILLE_CATEGORIES, COLONNES_CATEGORIES, lignes, [40, 36, 50, 18, 30, 13, 16],
             ["Sensible (Oui / Non)", "Actif (Oui / Non)"])
    instructions = wb.create_sheet("Instructions")
    for texte in INSTRUCTIONS:
        instructions.append([texte])
    instructions["A1"].font = Font(bold=True, size=13)
    instructions.column_dimensions["A"].width = 110

    if langue_active() != "fr":
        # Structure traduite (feuilles, en-têtes, Oui/Non, consignes) ; les données restent telles quelles.
        oui_non = {"Oui", "Non"}

        def garder(feuille, cellule):
            if feuille.title == "Instructions" or cellule.row == 1 and feuille.title != FEUILLE_MECANISME:
                return False
            if feuille.title == FEUILLE_MECANISME and cellule.column == 1:
                return False
            return cellule.value not in oui_non

        traduire_classeur(wb, garder=garder)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


# --- Import --------------------------------------------------------------------------------

def _texte(v) -> str:
    return str(v).strip() if v not in (None, "") else ""


def _bool(v, defaut=None):
    texte = _texte(v)
    if not texte:
        return defaut
    if correspond(texte, "Oui") or texte.lower() in ("yes", "1", "true", "vrai", "x"):
        return True
    if correspond(texte, "Non") or texte.lower() in ("no", "0", "false", "faux"):
        return False
    raise ValueError(f"« {texte} » : écrivez Oui ou Non.")


def _entier(v):
    texte = _texte(v)
    if not texte:
        return None
    try:
        nombre = int(float(texte.replace(",", ".")))
    except ValueError:
        raise ValueError(f"« {texte} » n'est pas un nombre entier.")
    if nombre < 0:
        raise ValueError("Le nombre ne peut pas être négatif.")
    return nombre


def _trouver(wb, nom):
    return next((f for f in wb.worksheets if correspond(f.title, nom)), None)


def _lignes(feuille, colonnes):
    """[(numéro, {colonne: valeur})] des lignes non vides ; en-têtes reconnus dans toutes les langues."""
    lignes = list(feuille.iter_rows(values_only=True))
    if not lignes:
        return []
    index = {}
    for nom in colonnes:
        i = next((i for i, c in enumerate(lignes[0]) if c is not None and correspond(str(c), nom)), None)
        if i is not None:
            index[nom] = i
    return [
        (numero, {nom: (ligne[i] if i < len(ligne) else None) for nom, i in index.items()})
        for numero, ligne in enumerate(lignes[1:], start=2)
        if any(c not in (None, "") for c in ligne)
    ]


def _messages(erreurs) -> str:
    """Messages d'un serializer, à plat."""
    sortie = []
    for valeur in (erreurs.values() if isinstance(erreurs, dict) else [erreurs]):
        for message in valeur if isinstance(valeur, list) else [valeur]:
            sortie.append(str(message))
    return " ".join(sortie)


@transaction.atomic
def importer_parametrage(fichier) -> dict:
    from apps.accounts.models import Role, User

    from .models import Categorie, Circuit, EtapeCircuit, Mecanisme, Priorite, TypeRetour
    from .serializers import CategorieSerializer, CircuitSerializer, MecanismeSerializer, PrioriteSerializer, TypeRetourSerializer

    wb = load_workbook(fichier, data_only=True)
    rapport = {"crees": 0, "mis_a_jour": 0, "erreurs": []}

    def erreur(feuille, ligne, message):
        rapport["erreurs"].append({"ligne": ligne, "message": f"[{feuille}] {message}"})

    def enregistrer(feuille, numero, serializer_classe, instance, donnees):
        serializer = serializer_classe(instance, data=donnees, partial=instance is not None)
        if not serializer.is_valid():
            erreur(feuille, numero, _messages(serializer.errors))
            return None
        objet = serializer.save()
        rapport["mis_a_jour" if instance else "crees"] += 1
        return objet

    # Mécanisme : un réglage par ligne.
    feuille = _trouver(wb, FEUILLE_MECANISME)
    if feuille is not None:
        donnees = {}
        for numero, ligne in enumerate(feuille.iter_rows(values_only=True), start=1):
            if not ligne or ligne[0] in (None, ""):
                continue
            champ = next((c for libelle, c in REGLAGES if correspond(str(ligne[0]), libelle)), None)
            valeur = ligne[1] if len(ligne) > 1 else None
            if champ is None or valeur in (None, ""):
                continue
            try:
                if champ in CHAMPS_OUI_NON:
                    donnees[champ] = _bool(valeur)
                elif champ == "langues":
                    donnees[champ] = [x.strip().lower() for x in str(valeur).replace(",", ";").split(";") if x.strip()]
                elif champ.startswith("conservation") or champ == "taille_max_piece_mo":
                    donnees[champ] = _entier(valeur)
                else:
                    donnees[champ] = _texte(valeur)
            except ValueError as exc:
                erreur(FEUILLE_MECANISME, numero, str(exc))
        if donnees:
            serializer = MecanismeSerializer(Mecanisme.courant(), data=donnees, partial=True)
            if serializer.is_valid():
                serializer.save()
                rapport["mis_a_jour"] += 1
            else:
                erreur(FEUILLE_MECANISME, 0, _messages(serializer.errors))

    # Types de retours et priorités : retrouvés par leur nom.
    for nom_feuille, colonnes, modele, serializer_classe in (
        (FEUILLE_TYPES, COLONNES_TYPES, TypeRetour, TypeRetourSerializer),
        (FEUILLE_PRIORITES, COLONNES_PRIORITES, Priorite, PrioriteSerializer),
    ):
        feuille = _trouver(wb, nom_feuille)
        for numero, v in (_lignes(feuille, colonnes) if feuille is not None else []):
            nom = _texte(v.get("Nom"))
            if not nom:
                erreur(nom_feuille, numero, "Nom manquant — ligne ignorée.")
                continue
            try:
                donnees = {"nom": nom}
                if modele is TypeRetour and "Description" in v:
                    donnees["description"] = _texte(v.get("Description"))
                if modele is Priorite:
                    urgente = _bool(v.get("Urgente (Oui / Non)"))
                    if urgente is not None:
                        donnees["urgente"] = urgente
                    if "Délai (jours)" in v:
                        donnees["delai_jours"] = _entier(v.get("Délai (jours)"))
                actif = _bool(v.get("Actif (Oui / Non)"))
                if actif is not None:
                    donnees["actif"] = actif
            except ValueError as exc:
                erreur(nom_feuille, numero, str(exc))
                continue
            enregistrer(nom_feuille, numero, serializer_classe, modele.objects.filter(nom__iexact=nom).first(), donnees)

    # Circuits : une ligne par étape ; les étapes d'un circuit du fichier sont remplacées.
    feuille = _trouver(wb, FEUILLE_CIRCUITS)
    etapes_par_circuit: dict = {}
    roles = list(Role.objects.all())
    for numero, v in (_lignes(feuille, COLONNES_CIRCUITS) if feuille is not None else []):
        nom = _texte(v.get("Circuit"))
        if not nom:
            erreur(FEUILLE_CIRCUITS, numero, "Nom du circuit manquant — ligne ignorée.")
            continue
        try:
            etape = {
                "numero": numero, "nom": _texte(v.get("Étape")), "delai_jours": _entier(v.get("Délai (jours)")),
                "est_cloture": bool(_bool(v.get("Clôture (Oui / Non)"), False)),
            }
            texte_role = _texte(v.get("Rôle responsable"))
            etape["role"] = next((r for r in roles if correspond(texte_role, r.libelle) or texte_role.upper() == r.code), None) \
                if texte_role else None
            if texte_role and etape["role"] is None:
                raise ValueError(f"Rôle « {texte_role} » inconnu (voir Utilisateurs › Rôles).")
            identifiant = _texte(v.get("Personne responsable (identifiant)"))
            etape["responsable"] = User.objects.filter(username__iexact=identifiant).first() if identifiant else None
            if identifiant and etape["responsable"] is None:
                raise ValueError(f"Personne « {identifiant} » inconnue (identifiant de connexion).")
            entete = etapes_par_circuit.setdefault(nom.lower(), {"nom": nom, "etapes": [], "sensible": None, "par_defaut": None})
            for cle, colonne in (("sensible", "Confidentiel (Oui / Non)"), ("par_defaut", "Par défaut (Oui / Non)")):
                valeur = _bool(v.get(colonne))
                if valeur is not None:
                    entete[cle] = valeur
        except ValueError as exc:
            erreur(FEUILLE_CIRCUITS, numero, str(exc))
            continue
        if not etape["nom"]:
            erreur(FEUILLE_CIRCUITS, numero, "Nom de l'étape manquant — ligne ignorée.")
            continue
        entete["etapes"].append(etape)
    for donnees_circuit in etapes_par_circuit.values():
        circuit = Circuit.objects.filter(nom__iexact=donnees_circuit["nom"]).first()
        premiere = donnees_circuit["etapes"][0]["numero"] if donnees_circuit["etapes"] else 0
        sensible = donnees_circuit["sensible"] if donnees_circuit["sensible"] is not None else (circuit.sensible if circuit else False)
        refus = [e for e in donnees_circuit["etapes"] if sensible and e["role"] is not None]
        for e in refus:
            erreur(FEUILLE_CIRCUITS, e["numero"], "Un circuit confidentiel est confié à des personnes, pas à un rôle : "
                   "laissez « Rôle responsable » vide et indiquez la personne.")
        if refus:
            continue
        donnees = {"nom": donnees_circuit["nom"]}
        if donnees_circuit["sensible"] is not None:
            donnees["sensible"] = donnees_circuit["sensible"]
        if donnees_circuit["par_defaut"] is not None:
            donnees["par_defaut"] = donnees_circuit["par_defaut"]
        if circuit is not None and "sensible" in donnees and donnees["sensible"] != circuit.sensible:
            circuit.etapes.all().delete()  # les étapes sont remplacées : la règle des rôles s'applique aux nouvelles
        circuit = enregistrer(FEUILLE_CIRCUITS, premiere, CircuitSerializer, circuit, donnees)
        if circuit is None or not donnees_circuit["etapes"]:
            continue
        circuit.etapes.all().delete()
        for ordre, e in enumerate(donnees_circuit["etapes"], start=1):
            EtapeCircuit.objects.create(circuit=circuit, nom=e["nom"], ordre=ordre, delai_jours=e["delai_jours"],
                                        role=e["role"], responsable=e["responsable"], est_cloture=e["est_cloture"])

    # Catégories : principales d'abord, puis sous-catégories.
    feuille = _trouver(wb, FEUILLE_CATEGORIES)
    lignes = _lignes(feuille, COLONNES_CATEGORIES) if feuille is not None else []
    for passe in ("principales", "sous"):
        for numero, v in lignes:
            principale, sous = _texte(v.get("Catégorie")), _texte(v.get("Sous-catégorie"))
            if (passe == "principales") == bool(sous):
                continue
            if not principale:
                erreur(FEUILLE_CATEGORIES, numero, "Colonne « Catégorie » vide — ligne ignorée.")
                continue
            parent = None
            if sous:
                parent = Categorie.objects.filter(parent__isnull=True, nom__iexact=principale).first()
                if parent is None:
                    erreur(FEUILLE_CATEGORIES, numero, f"Catégorie principale « {principale} » introuvable — ajoutez sa ligne.")
                    continue
            nom = sous or principale
            try:
                donnees = {"nom": nom, "parent": parent.pk if parent else None}
                if "Description" in v and _texte(v.get("Description")):
                    donnees["description"] = _texte(v.get("Description"))
                for cle, colonne in (("sensible", "Sensible (Oui / Non)"), ("actif", "Actif (Oui / Non)")):
                    valeur = _bool(v.get(colonne))
                    if valeur is not None:
                        donnees[cle] = valeur
                if "Délai (jours)" in v:
                    donnees["delai_jours"] = _entier(v.get("Délai (jours)"))
                nom_circuit = _texte(v.get("Circuit"))
                if nom_circuit:
                    circuit = Circuit.objects.filter(nom__iexact=nom_circuit).first()
                    if circuit is None:
                        raise ValueError(f"Circuit « {nom_circuit} » introuvable (feuille Circuits).")
                    donnees["circuit"] = circuit.pk
                elif "Circuit" in v:
                    donnees["circuit"] = None
            except ValueError as exc:
                erreur(FEUILLE_CATEGORIES, numero, str(exc))
                continue
            existante = Categorie.objects.filter(parent=parent, nom__iexact=nom).first()
            enregistrer(FEUILLE_CATEGORIES, numero, CategorieSerializer, existante, donnees)
    return rapport
