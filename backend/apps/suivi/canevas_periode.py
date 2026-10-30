"""
Canevas des objectifs d'une période (onglet « Planification par période »), sur le modèle du
canevas de suivi (apps.suivi.canevas) — même présentation, mêmes identifiants (Exx, Sxx, Ixx),
même import en deux temps (aperçu puis validation) et mêmes modes — à la différence qu'on y
définit les objectifs de la période au lieu d'y saisir le réalisé.

Le classeur est prérempli avec toute la planification du projet (niveaux, éléments,
sous-activités : niveau, code, libellé, méthode de calcul, unité, quantité et budget globaux, en
gris) et ses indicateurs ; les colonnes bleues portent les objectifs de la période (quantité ou
avancement visé, budget, début et fin prévus, commentaire), déjà remplies pour ceux qui sont
définis.

Import : analyser_canevas_periode() décrit ligne par ligne ce qui sera ajouté ou modifié, et
les erreurs rattachées à une cellule (mêmes contrôles que la saisie à l'écran :
TranchePlanifieeSerializer) ; importer_canevas_periode() enregistre les lignes valides.
Mode « ajout » : un objectif déjà défini n'est jamais remplacé (ligne ignorée et signalée) ;
mode « mise_a_jour » : il est remplacé, l'aperçu montrant l'ancienne et la nouvelle valeur.
Une ligne dont les cellules bleues sont vides, ou inchangées, ne change rien.
"""
import datetime
import io
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill

from apps.core.langues import correspond
from apps.core.vocabulaire import adapter_classeur

from .canevas import COL_COMMENTAIRE, COL_ID, COULEUR_ERREUR, MODE_AJOUT, Ligne, _feuille, _totaux

FEUILLE_OBJECTIFS = "Objectifs de la période"
FEUILLE_INDICATEURS = "Indicateurs"
COL_OBJECTIF = "Objectif de la période"
COL_BUDGET = "Budget de la période (FCFA)"
COL_DEBUT = "Début prévu (AAAA-MM-JJ)"
COL_FIN = "Fin prévue (AAAA-MM-JJ)"
COL_CIBLE = "Cible de la période"

LECTURE_OBJECTIFS = ["Niveau", "Code", "Libellé", "Méthode de calcul", "Unité", "Quantité prévue", "Budget alloué (FCFA)"]
SAISIE_OBJECTIFS = [COL_OBJECTIF, COL_BUDGET, COL_DEBUT, COL_FIN, COL_COMMENTAIRE]
COLONNES_OBJECTIFS = [COL_ID, *LECTURE_OBJECTIFS, *SAISIE_OBJECTIFS]
LECTURE_INDICATEURS = ["Libellé", "Unité", "Valeur cible"]
COLONNES_INDICATEURS = [COL_ID, *LECTURE_INDICATEURS, COL_CIBLE, COL_COMMENTAIRE]


def libelles_canevas_periode() -> set:
    """Libellés fixes du canevas (vocabulaire et traductions)."""
    return {FEUILLE_OBJECTIFS, FEUILLE_INDICATEURS, *COLONNES_OBJECTIFS, *COLONNES_INDICATEURS}


# --- Génération ---------------------------------------------------------------------------

def _n(x):
    return float(x) if x is not None else None


def _d(x):
    return x.isoformat() if x else None


def generer_canevas_periode(periode) -> bytes:
    from apps.projects.models import MethodeCalcul

    from .services import construire_planification_periode

    donnees = construire_planification_periode(periode)
    projet = periode.projet
    objectifs = []
    for l in donnees["lignes"]:
        activite = l["type"] == "activite"
        if activite:
            methode = "Agrégé" if l["methode"] == "AGREGATION" else MethodeCalcul(l["methode"]).label
        else:
            methode = ""
        objectifs.append([
            f"{'E' if activite else 'S'}{l['id']}", l["niveau"] if activite else "Sous-activité", l["code"],
            "  " * l["profondeur"] + l["libelle"], methode, l["unite"], _n(l["global_quantite"]), _n(l["global_budget"]),
            _n(l["prevu_quantite"]), _n(l["prevu_budget"]) if activite else None,
            _d(l["debut_prevu"]), _d(l["fin_prevue"]), l["commentaire"] or "",
        ])
    indicateurs = [
        [f"I{i['id']}", i["libelle"], i["unite"], _n(i["valeur_cible"]), _n(i["prevu_quantite"]), i["commentaire"] or ""]
        for i in donnees["indicateurs"]
    ]

    wb = Workbook()
    _feuille(wb, FEUILLE_OBJECTIFS, COLONNES_OBJECTIFS, set(LECTURE_OBJECTIFS), objectifs, premiere=True)
    _feuille(wb, FEUILLE_INDICATEURS, COLONNES_INDICATEURS, set(LECTURE_INDICATEURS), indicateurs)
    instructions = wb.create_sheet("Instructions")
    for texte in [
        f"Objectifs de la période « {periode.libelle} » ({periode.date_debut:%d/%m/%Y} → {periode.date_fin:%d/%m/%Y}) — "
        f"{projet.code} — {projet.nom}",
        "- Colonnes grises : informations, à ne pas modifier (l'identifiant relie chaque ligne à la plateforme).",
        "- Colonnes bleues : objectifs de la période, à compléter. Une ligne sans saisie, ou inchangée, est ignorée.",
        "- « Objectif de la période » : quantité à réaliser PENDANT la période (unité de l'élément) ; pour un niveau "
        "agrégé ou une autre méthode que « Par quantité » (unité %), avancement visé à la fin de la période (0 à 100).",
        "- Budget de la période : éléments de la planification uniquement (pas les sous-activités).",
        "- Début et fin prévus : dans la période (AAAA-MM-JJ ou JJ/MM/AAAA).",
        "- Feuille « Indicateurs » : cible de l'indicateur sur la période.",
        "- À l'import, un aperçu montre ce qui sera ajouté ou modifié, et les cellules en erreur, avant validation.",
        "- Mode « ajouter » : un objectif déjà défini n'est jamais remplacé. Mode « mettre à jour » : il est remplacé.",
    ]:
        instructions.append([texte])
    instructions.column_dimensions["A"].width = 130
    adapter_classeur(wb)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# --- Analyse ------------------------------------------------------------------------------

def _trouver(wb, nom):
    return next((f for f in wb.worksheets if correspond(f.title, nom)), None)


def _lire(feuille, colonnes):
    """[(numéro, {colonne française: valeur})] ; en-têtes reconnus dans toutes les langues."""
    lignes = list(feuille.iter_rows(min_row=1, values_only=True))
    if not lignes:
        return [], list(colonnes)
    index = {}
    for nom in colonnes:
        i = next((i for i, c in enumerate(lignes[0]) if c is not None and correspond(str(c), nom)), None)
        if i is not None:
            index[nom] = i
    manquantes = [c for c in colonnes if c not in index]
    return [
        (numero, {nom: (valeurs[i] if i < len(valeurs) else None) for nom, i in index.items()})
        for numero, valeurs in enumerate(lignes[1:], start=2)
    ], manquantes


def _vide(x):
    return x is None or (isinstance(x, str) and not x.strip())


def _nombre(ligne, colonne, valeur):
    if _vide(valeur):
        return None
    try:
        nombre = Decimal(str(valeur).replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".").rstrip("%"))
    except InvalidOperation:
        ligne.erreur(colonne, f"« {valeur} » n'est pas un nombre.")
        return None
    if nombre < 0:
        ligne.erreur(colonne, "La valeur ne peut pas être négative.")
        return None
    return nombre


def _date(ligne, colonne, valeur):
    if _vide(valeur):
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    for format_ in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(str(valeur).strip()[:10], format_).date()
        except ValueError:
            continue
    ligne.erreur(colonne, f"Date « {valeur} » illisible (AAAA-MM-JJ ou JJ/MM/AAAA).")
    return None


def _fmt(x):
    if x is None or x == "":
        return "—"
    if isinstance(x, Decimal):
        return f"{x.normalize():f}"
    return str(x)


def analyser_canevas_periode(fichier, periode, mode=MODE_AJOUT):
    """Analyse complète du fichier, sans rien enregistrer. Renvoie (lignes, erreurs_generales)."""
    from apps.indicators.services import indicateurs_pour_projet
    from apps.projects.models import Activite, SousActivite

    from .models import TranchePlanifiee
    from .serializers import TranchePlanifieeSerializer

    wb = load_workbook(fichier, data_only=True)
    projet = periode.projet
    elements = {f"E{a.id}": ("activite", a) for a in Activite.objects.filter(projet=projet)}
    elements |= {f"S{s.id}": ("sous_activite", s) for s in SousActivite.objects.filter(activite__projet=projet)}
    elements |= {f"I{i.id}": ("indicateur", i) for i in indicateurs_pour_projet(projet.id)}
    tranches = {
        (t.activite_id, t.sous_activite_id, t.indicateur_id): t for t in TranchePlanifiee.objects.filter(periode=periode)
    }
    resultat, generales, vus = [], [], set()

    def traiter(nom_feuille, numero, valeurs, colonnes_saisie):
        identifiant = str(valeurs.get(COL_ID) or "").strip().upper()
        saisies = {c: valeurs.get(c) for c in colonnes_saisie}
        if not identifiant or all(_vide(x) for x in saisies.values()):
            return
        ligne = Ligne(feuille=nom_feuille, numero=numero, identifiant=identifiant,
                      libelle=str(valeurs.get("Libellé") or "").strip())
        resultat.append(ligne)
        if identifiant in vus:
            ligne.erreur(COL_ID, "Identifiant présent plusieurs fois dans le fichier.")
            return
        vus.add(identifiant)
        if identifiant not in elements:
            ligne.erreur(COL_ID, "Identifiant inconnu ou d'un autre projet — ligne ignorée.")
            return
        type_, objet = elements[identifiant]
        if (nom_feuille == FEUILLE_INDICATEURS) != (type_ == "indicateur"):
            ligne.erreur(COL_ID, "Cet identifiant ne correspond pas à cette feuille.")
            return
        nouveau = {
            "cible": _nombre(ligne, COL_CIBLE if type_ == "indicateur" else COL_OBJECTIF,
                             saisies.get(COL_CIBLE if type_ == "indicateur" else COL_OBJECTIF)),
            "budget": _nombre(ligne, COL_BUDGET, saisies.get(COL_BUDGET)),
            "date_debut_prevue": _date(ligne, COL_DEBUT, saisies.get(COL_DEBUT)),
            "date_fin_prevue": _date(ligne, COL_FIN, saisies.get(COL_FIN)),
            "commentaire": str(saisies.get(COL_COMMENTAIRE) or "").strip(),
        }
        if nouveau["budget"] is not None and type_ != "activite":
            ligne.erreur(COL_BUDGET, "Budget réservé aux éléments de la planification (pas aux sous-activités).")
        for colonne, date in ((COL_DEBUT, nouveau["date_debut_prevue"]), (COL_FIN, nouveau["date_fin_prevue"])):
            if date and not (periode.date_debut <= date <= periode.date_fin):
                ligne.erreur(colonne, f"Hors de la période ({periode.date_debut:%d/%m/%Y} → {periode.date_fin:%d/%m/%Y}).")
        if ligne.erreurs:
            return
        cle = (objet.id if type_ == "activite" else None, objet.id if type_ == "sous_activite" else None,
               objet.id if type_ == "indicateur" else None)
        existante = tranches.get(cle)
        if existante is not None:
            anciens = {c: getattr(existante, c) for c in nouveau}
            anciens["commentaire"] = anciens["commentaire"] or ""
            differences = [c for c in nouveau if anciens[c] != nouveau[c]]
            if not differences:
                resultat.remove(ligne)  # inchangée : rien à faire
                return
            if mode == MODE_AJOUT:
                ligne.actions.append(("ignoree", "Objectif déjà défini pour la période — conservé (mode « ajouter »)."))
                return
        serializer = TranchePlanifieeSerializer(existante, data={"periode": periode.id, type_: objet.id, **nouveau})
        if not serializer.is_valid():
            for champ, messages in serializer.errors.items():
                colonne = {"cible": COL_OBJECTIF, "budget": COL_BUDGET, "date_debut_prevue": COL_DEBUT,
                           "date_fin_prevue": COL_FIN}.get(champ, COL_OBJECTIF)
                for message in messages if isinstance(messages, list) else [messages]:
                    ligne.erreur(colonne, str(message))
            return
        libelles = {"cible": "Objectif", "budget": "Budget", "date_debut_prevue": "Début prévu",
                    "date_fin_prevue": "Fin prévue", "commentaire": "Commentaire"}
        if existante is None:
            details = ", ".join(f"{libelles[c]} {_fmt(x)}" for c, x in nouveau.items() if x not in (None, ""))
            ligne.actions.append(("ajout", f"Objectif défini : {details}."))
        else:
            for c in differences:
                ligne.actions.append(("modification", f"{libelles[c]} : {_fmt(getattr(existante, c))} → {_fmt(nouveau[c])}"))
        ligne.operations.append(serializer.save)

    feuille = _trouver(wb, FEUILLE_OBJECTIFS)
    if feuille is None:
        generales.append("Feuille « Objectifs de la période » introuvable : utilisez le canevas de la période.")
    else:
        lignes, manquantes = _lire(feuille, COLONNES_OBJECTIFS)
        if COL_ID in manquantes:
            generales.append("Colonne « Identifiant (ne pas modifier) » introuvable dans la feuille des objectifs.")
        else:
            for numero, valeurs in lignes:
                traiter(FEUILLE_OBJECTIFS, numero, valeurs, SAISIE_OBJECTIFS)
    feuille = _trouver(wb, FEUILLE_INDICATEURS)
    if feuille is not None:
        lignes, manquantes = _lire(feuille, COLONNES_INDICATEURS)
        if COL_ID not in manquantes:
            for numero, valeurs in lignes:
                traiter(FEUILLE_INDICATEURS, numero, valeurs, [COL_CIBLE, COL_COMMENTAIRE])
    return resultat, generales


def _rapport(lignes, generales, mode):
    return {"mode": mode, "totaux": _totaux(lignes), "lignes": [l.en_dict() for l in lignes], "erreurs_generales": generales}


def apercu_canevas_periode(fichier, periode, mode):
    return _rapport(*analyser_canevas_periode(fichier, periode, mode), mode)


def importer_canevas_periode(fichier, periode, mode):
    """Enregistre les lignes valides ; une ligne refusée à l'enregistrement (verrou…) passe en erreur."""
    from django.db import transaction

    lignes, generales = analyser_canevas_periode(fichier, periode, mode)
    for ligne in lignes:
        if ligne.erreurs:
            continue
        try:
            with transaction.atomic():
                for operation in ligne.operations:
                    operation()
        except Exception as exc:  # projet clôturé, saisie fermée…
            ligne.erreur(COL_ID, str(getattr(exc, "detail", exc)))
    return _rapport(lignes, generales, mode)


def rapport_erreurs_periode(fichier, periode, mode) -> bytes:
    """Le fichier reçu, avec les cellules en erreur surlignées et commentées, et une feuille « Erreurs »."""
    lignes, generales = analyser_canevas_periode(fichier, periode, mode)
    fichier.seek(0)
    wb = load_workbook(fichier)
    recap = wb.create_sheet("Erreurs", 0)
    recap.append(["Feuille", "Ligne", "Identifiant", "Colonne", "Erreur"])
    for cellule in recap[1]:
        cellule.font = Font(bold=True)
    for message in generales:
        recap.append(["", "", "", "", message])
    for ligne in lignes:
        if not ligne.erreurs:
            continue
        feuille = _trouver(wb, ligne.feuille)
        entetes = [str(c.value or "") for c in feuille[1]] if feuille is not None else []
        for colonne, message in ligne.erreurs:
            recap.append([ligne.feuille, ligne.numero, ligne.identifiant, colonne, message])
            i = next((i for i, e in enumerate(entetes) if correspond(e, colonne)), None)
            if i is not None:
                cellule = feuille.cell(row=ligne.numero, column=i + 1)
                cellule.fill = PatternFill("solid", fgColor=COULEUR_ERREUR)
                cellule.comment = Comment(message, "Plateforme S&E")
    for lettre, largeur in (("A", 26), ("B", 8), ("C", 14), ("D", 34), ("E", 90)):
        recap.column_dimensions[lettre].width = largeur
    adapter_classeur(wb, feuilles={"Erreurs"})
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
