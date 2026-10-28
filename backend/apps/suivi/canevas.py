"""
Canevas de suivi d'un projet : un classeur Excel prérempli (éléments de la planification,
sous-activités, jalons et livrables, indicateurs) à compléter hors ligne puis à réimporter
pour saisir le suivi en masse.

Import en deux temps :
1. analyser_canevas() vérifie tout le fichier sans rien enregistrer et décrit, ligne par
   ligne, ce qui sera fait (ajout, modification) ou pourquoi la ligne est refusée
   (erreurs rattachées à une cellule précise) — c'est l'aperçu montré avant validation ;
2. importer_canevas() rejoue la même analyse puis enregistre les lignes valides, dans une
   transaction.

Règles :
- Rien n'est jamais écrasé silencieusement. Mode « ajouter » : une saisie qui existe déjà
  (même élément, même période) ou une valeur déjà renseignée est ignorée et signalée.
  Mode « mettre à jour » : elle est remplacée, l'aperçu montre l'ancienne et la nouvelle
  valeur, et l'historique des modifications garde la trace (django-simple-history).
- Les taux automatiques sont recalculés à partir des données importées (ils ne sont jamais
  stockés) ; un taux manuel n'est enregistré que pour un élément en « Saisie manuelle ».
- Identifiants inconnus, d'un autre projet, ou en double dans le fichier : refusés.
- Les droits sont ceux de la saisie à l'écran (projet visible, droit d'écriture).
"""
import datetime
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.vocabulaire import adapter_classeur, ramener_classeur

COULEUR_LECTURE = "EDEDED"  # colonnes informatives (ne pas modifier)
COULEUR_SAISIE = "DDEBF7"  # colonnes à compléter
COULEUR_ERREUR = "F8CBAD"

FEUILLE_SUIVI = "Suivi"
FEUILLE_JALONS = "Jalons et livrables"
FEUILLE_INDICATEURS = "Indicateurs"

COL_ID = "Identifiant (ne pas modifier)"
COL_DEBUT = "Période début (AAAA-MM-JJ)"
COL_FIN = "Période fin (AAAA-MM-JJ)"
COL_QTE = "Quantité réalisée sur la période"
COL_BUDGET = "Budget réalisé sur la période (FCFA)"
COL_STATUT = "Statut"
COL_TAUX = "Taux manuel (%)"
COL_AVANCEMENT = "Avancement (%)"
COL_POIDS = "Poids (%)"
COL_COMMENTAIRE = "Commentaire"
COL_ELEMENT = "Identifiant de l'élément"
COL_TYPE = "Type (Jalon / Livrable)"
COL_LIBELLE = "Libellé"
COL_ACHEVEMENT = "Achèvement (%)"
COL_VALIDE = "Validé (Oui / Non)"
COL_VALEUR = "Valeur réalisée sur la période"

LECTURE_SUIVI = ["Niveau", "Code", "Libellé", "Méthode de calcul", "Unité", "Quantité prévue", "Réalisé cumulé", "Taux actuel (%)"]
SAISIE_SUIVI = [COL_DEBUT, COL_FIN, COL_QTE, COL_BUDGET, COL_STATUT, COL_TAUX, COL_AVANCEMENT, COL_POIDS, COL_COMMENTAIRE]
COLONNES_SUIVI = [COL_ID, *LECTURE_SUIVI, *SAISIE_SUIVI]
COLONNES_JALONS = [COL_ID, COL_ELEMENT, "Élément", COL_TYPE, COL_LIBELLE, COL_POIDS, COL_ACHEVEMENT, COL_VALIDE]
LECTURE_JALONS = {"Élément"}
COLONNES_INDICATEURS = [COL_ID, "Libellé", "Unité", "Valeur cible", "Réalisé cumulé", COL_DEBUT, COL_FIN, COL_VALEUR, COL_COMMENTAIRE]
LECTURE_INDICATEURS = {"Libellé", "Unité", "Valeur cible", "Réalisé cumulé"}

STATUTS_ACTIVITE = {"non realisee": "NON_REALISEE", "en cours": "EN_COURS", "realisee": "REALISEE"}
STATUTS_SOUS_ACTIVITE = {"planifiee": "PLANIFIEE", "en cours": "EN_COURS", "terminee": "TERMINEE"}

MODE_AJOUT = "ajout"
MODE_MISE_A_JOUR = "mise_a_jour"


def libelles_canevas() -> set:
    """Libellés fixes du canevas (pour ramener_classeur, quand le vocabulaire est personnalisé)."""
    return {FEUILLE_SUIVI, FEUILLE_JALONS, FEUILLE_INDICATEURS, *COLONNES_SUIVI, *COLONNES_JALONS, *COLONNES_INDICATEURS}


# --- Génération ---------------------------------------------------------------------------

def _feuille(wb, titre, colonnes, lecture, lignes, premiere=False):
    feuille = wb.active if premiere else wb.create_sheet()
    feuille.title = titre
    feuille.append(colonnes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
        nom = cellule.value
        couleur = COULEUR_LECTURE if nom == COL_ID or nom in lecture else COULEUR_SAISIE
        cellule.fill = PatternFill("solid", fgColor=couleur)
    for ligne in lignes:
        feuille.append(ligne)
    quadriller(feuille, max_col=len(colonnes))
    figer_entete(feuille)
    for i, nom in enumerate(colonnes, start=1):
        feuille.column_dimensions[feuille.cell(row=1, column=i).column_letter].width = 42 if nom in ("Libellé", "Élément", COL_LIBELLE) else 18
    return feuille


def generer_canevas_suivi(projet) -> bytes:
    from apps.indicators.services import indicateurs_pour_projet, valeur_realisee_totale
    from apps.projects.models import JalonLivrable, MethodeCalcul, NiveauActivite
    from apps.projects.taux import ArbreTaux

    arbre = ArbreTaux(projet)
    noms_niveaux = dict(NiveauActivite.objects.filter(projet=projet).values_list("profondeur", "nom_niveau"))
    lignes, jalons = [], []

    def parcourir(elements, profondeur):
        for e in elements:
            resultat = arbre.resultat(e.id)
            methode = "Agrégé" if resultat.methode == "AGREGATION" else MethodeCalcul(resultat.methode).label
            lignes.append(
                [f"E{e.id}", noms_niveaux.get(profondeur, "Activité"), e.code_activite, "  " * profondeur + e.libelle,
                 methode, e.unite_quantite, e.quantite_prevue, e.quantite_realisee, resultat.taux]
                + [""] * (len(SAISIE_SUIVI) - 2) + [e.poids, ""]
            )
            for sa in e.sous_activites.all():
                lignes.append(
                    [f"S{sa.id}", "Sous-activité", "", "  " * (profondeur + 1) + sa.libelle, "", sa.unite_quantite,
                     sa.quantite_prevue, sa.quantite_realisee, None]
                    + [""] * (len(SAISIE_SUIVI) - 3) + [sa.avancement, sa.poids, ""]
                )
            for j in e.jalons_livrables.all():
                jalons.append(
                    [f"J{j.id}", f"E{e.id}", e.libelle, j.get_type_display(), j.libelle, j.poids, j.achevement,
                     ("Oui" if j.valide else "Non") if j.type == JalonLivrable.Type.LIVRABLE else ""]
                )
            parcourir(arbre.enfants[e.id], profondeur + 1)

    parcourir(arbre.racines, 0)
    indicateurs = [
        [f"I{i.id}", i.libelle, i.unite, i.valeur_cible, valeur_realisee_totale(i), "", "", "", ""]
        for i in indicateurs_pour_projet(projet.id).order_by("libelle")
    ]

    wb = Workbook()
    _feuille(wb, FEUILLE_SUIVI, COLONNES_SUIVI, set(LECTURE_SUIVI), lignes, premiere=True)
    _feuille(wb, FEUILLE_JALONS, COLONNES_JALONS, LECTURE_JALONS, jalons)
    _feuille(wb, FEUILLE_INDICATEURS, COLONNES_INDICATEURS, LECTURE_INDICATEURS, indicateurs)
    instructions = wb.create_sheet("Instructions")
    for texte in [
        f"Canevas de suivi — {projet.code} — {projet.nom}",
        "- Colonnes grises : informations, à ne pas modifier (l'identifiant relie chaque ligne à la plateforme).",
        "- Colonnes bleues : à compléter. Une ligne sans saisie est ignorée.",
        "- Feuille « Suivi » : pour une saisie de période, indique la période (début et fin) puis la quantité "
        "réalisée PENDANT cette période (pas un cumul), le budget réalisé (éléments uniquement) et le statut.",
        "- Taux manuel (%) : seulement pour un élément en « Saisie manuelle » (0 à 100) ; daté de la fin de période, "
        "sinon du jour de l'import.",
        "- Avancement (%) et Poids (%) des sous-activités : méthode « tâches pondérées ». Poids d'un élément : "
        "agrégation « pondérée par les poids » du niveau au-dessus.",
        "- Feuille « Jalons et livrables » : modifie poids, achèvement ou validation ; pour en ajouter un, laisse "
        "l'identifiant vide et indique l'identifiant de l'élément (Exx), le type et le libellé.",
        "- Feuille « Indicateurs » : valeur réalisée PENDANT la période indiquée.",
        "- À l'import, un aperçu montre ce qui sera ajouté ou modifié, et les cellules en erreur, avant validation.",
        "- Mode « ajouter » : une saisie déjà existante (même période) ou une valeur déjà renseignée n'est jamais "
        "remplacée. Mode « mettre à jour » : elle est remplacée, avec trace dans l'historique.",
    ]:
        instructions.append([texte])
    instructions.column_dimensions["A"].width = 130
    adapter_classeur(wb)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# --- Analyse ------------------------------------------------------------------------------

@dataclass
class Ligne:
    feuille: str
    numero: int
    identifiant: str
    libelle: str = ""
    actions: list = field(default_factory=list)  # (type « ajout » | « modification » | « ignoree », texte)
    erreurs: list = field(default_factory=list)  # (colonne, message)
    operations: list = field(default_factory=list)  # fonctions à exécuter à l'import

    def erreur(self, colonne, message):
        self.erreurs.append((colonne, message))

    def statut(self):
        if self.erreurs:
            return "erreur"
        types = {t for t, _ in self.actions}
        if "modification" in types:
            return "modification"
        if "ajout" in types:
            return "ajout"
        return "ignoree"

    def en_dict(self):
        return {
            "feuille": self.feuille,
            "ligne": self.numero,
            "identifiant": self.identifiant,
            "libelle": self.libelle,
            "statut": self.statut(),
            "actions": [texte for _, texte in self.actions],
            "erreurs": [{"colonne": c, "message": m} for c, m in self.erreurs],
        }


def _vide(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _nombre(ligne, colonne, valeur, minimum=0, maximum=None):
    if _vide(valeur):
        return None
    try:
        nombre = Decimal(str(valeur).replace(",", ".").replace(" ", "").replace(" ", ""))
    except InvalidOperation:
        ligne.erreur(colonne, f"« {valeur} » n'est pas un nombre.")
        return None
    if nombre < minimum or (maximum is not None and nombre > maximum):
        ligne.erreur(colonne, f"Valeur attendue entre {minimum} et {maximum}." if maximum is not None else f"Valeur négative interdite.")
        return None
    return nombre


def _date(ligne, colonne, valeur):
    if _vide(valeur):
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    try:
        return datetime.datetime.strptime(str(valeur).strip(), "%Y-%m-%d").date()
    except ValueError:
        ligne.erreur(colonne, f"Date « {valeur} » invalide (format AAAA-MM-JJ).")
        return None


def _normaliser(texte):
    import unicodedata

    t = "".join(c for c in unicodedata.normalize("NFD", str(texte)) if unicodedata.category(c) != "Mn")
    return " ".join(t.replace("_", " ").lower().split())


def _periode(ligne, valeurs):
    debut, fin = _date(ligne, COL_DEBUT, valeurs.get(COL_DEBUT)), _date(ligne, COL_FIN, valeurs.get(COL_FIN))
    if debut is None and not ligne.erreurs:
        ligne.erreur(COL_DEBUT, "Période début obligatoire pour cette saisie.")
    if fin is None and not ligne.erreurs:
        ligne.erreur(COL_FIN, "Période fin obligatoire pour cette saisie.")
    if debut and fin and debut > fin:
        ligne.erreur(COL_FIN, "La fin de période précède son début.")
        return None, None
    return debut, fin


def _fmt(v):
    if v is None or v == "":
        return "vide"
    if isinstance(v, Decimal):
        return f"{v.normalize():f}"
    return str(v)


def _valeur_simple(ligne, mode, objet, champ, nouveau, libelle, enregistrer):
    """Champ simple (poids, avancement...) : remplir une valeur vide = ajout ; la changer = modification."""
    ancien = getattr(objet, champ)
    if nouveau is None or (ancien is not None and Decimal(str(ancien)) == Decimal(str(nouveau))):
        return
    if ancien is None:
        ligne.actions.append(("ajout", f"{libelle} : {_fmt(nouveau)}"))
    elif mode == MODE_AJOUT:
        ligne.actions.append(("ignoree", f"{libelle} déjà renseigné ({_fmt(ancien)}) — conservé (mode ajouter)"))
        return
    else:
        ligne.actions.append(("modification", f"{libelle} : {_fmt(ancien)} → {_fmt(nouveau)}"))
    ligne.operations.append(enregistrer)


def _lire(feuille, colonnes_attendues):
    """[(numéro de ligne, {colonne: valeur})] pour les lignes non vides ; en-têtes manquants signalés."""
    lignes = list(feuille.iter_rows(min_row=1, values_only=True))
    if not lignes:
        return [], []
    entetes = [str(c).strip() if c else "" for c in lignes[0]]
    manquantes = [c for c in colonnes_attendues if c not in entetes]
    resultat = []
    for numero, valeurs in enumerate(lignes[1:], start=2):
        dico = {entetes[i]: v for i, v in enumerate(valeurs) if i < len(entetes) and entetes[i]}
        resultat.append((numero, dico))
    return resultat, manquantes


def analyser_canevas(fichier, projet, mode=MODE_AJOUT, utilisateur=None):
    """Analyse complète du fichier, sans rien enregistrer. Renvoie (lignes, erreurs_generales)."""
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.indicators.services import indicateurs_pour_projet
    from apps.projects.models import Activite, JalonLivrable, MethodeCalcul, SousActivite, TauxManuel
    from apps.projects.taux import ArbreTaux

    from .models import PointSuivi
    from .services import synchroniser_activite_depuis_suivi, synchroniser_sous_activite_depuis_suivi

    wb = ramener_classeur(load_workbook(fichier, data_only=True))
    arbre = ArbreTaux(projet)
    elements = {f"E{e.id}": e for e in Activite.objects.filter(projet=projet)}
    sous_activites = {f"S{s.id}": s for s in SousActivite.objects.filter(activite__projet=projet)}
    jalons_existants = {f"J{j.id}": j for j in JalonLivrable.objects.filter(activite__projet=projet)}
    indicateurs = {f"I{i.id}": i for i in indicateurs_pour_projet(projet.id)}
    resultat, generales, deja_vus = [], [], {}
    aujourdhui = datetime.date.today()

    def identifiant_unique(ligne, cle):
        if cle in deja_vus:
            ligne.erreur(COL_ID, f"Doublon : même saisie qu'à la ligne {deja_vus[cle]} — ligne ignorée.")
            return False
        deja_vus[cle] = ligne.numero
        return True

    # ---- Feuille « Suivi » ----
    if FEUILLE_SUIVI in wb.sheetnames:
        lignes, manquantes = _lire(wb[FEUILLE_SUIVI], [COL_ID])
        if manquantes:
            generales.append(f"Feuille « {FEUILLE_SUIVI} » : colonne « {COL_ID} » introuvable.")
        for numero, v in lignes:
            if all(_vide(v.get(c)) for c in SAISIE_SUIVI):
                continue
            identifiant = str(v.get(COL_ID) or "").strip()
            ligne = Ligne(FEUILLE_SUIVI, numero, identifiant, str(v.get("Libellé") or "").strip())
            resultat.append(ligne)
            cible = elements.get(identifiant) or sous_activites.get(identifiant)
            if cible is None:
                ligne.erreur(COL_ID, "Identifiant inconnu ou d'un autre projet." if identifiant else "Identifiant manquant.")
                continue
            est_element = identifiant.startswith("E")
            ligne.libelle = cible.libelle
            qte = _nombre(ligne, COL_QTE, v.get(COL_QTE))
            budget = _nombre(ligne, COL_BUDGET, v.get(COL_BUDGET))
            taux = _nombre(ligne, COL_TAUX, v.get(COL_TAUX), 0, 100)
            avancement = _nombre(ligne, COL_AVANCEMENT, v.get(COL_AVANCEMENT), 0, 100)
            poids = _nombre(ligne, COL_POIDS, v.get(COL_POIDS))
            commentaire = str(v.get(COL_COMMENTAIRE) or "").strip()
            statut = None
            if not _vide(v.get(COL_STATUT)):
                table = STATUTS_ACTIVITE if est_element else STATUTS_SOUS_ACTIVITE
                statut = table.get(_normaliser(v[COL_STATUT])) or (
                    str(v[COL_STATUT]).strip().upper() if str(v[COL_STATUT]).strip().upper() in table.values() else None
                )
                if statut is None:
                    ligne.erreur(COL_STATUT, f"Statut inconnu « {v[COL_STATUT]} » (attendu : {', '.join(table)}).")
            if budget is not None and not est_element:
                ligne.erreur(COL_BUDGET, "Une sous-activité n'a pas de budget propre.")
            if avancement is not None and est_element:
                ligne.erreur(COL_AVANCEMENT, "L'avancement se saisit sur les sous-activités (tâches).")
            if taux is not None and (not est_element or arbre.resultat(cible.id).methode != MethodeCalcul.MANUELLE):
                ligne.erreur(COL_TAUX, "Taux manuel réservé aux éléments en « Saisie manuelle » ; les autres taux sont calculés.")

            point_demande = any(x is not None for x in (qte, budget, statut)) or bool(commentaire)
            debut = fin = None
            if point_demande:
                debut, fin = _periode(ligne, v)
            elif taux is not None:
                fin = _date(ligne, COL_FIN, v.get(COL_FIN))  # date du taux ; vide = jour de l'import
            if ligne.erreurs:
                continue

            if point_demande:
                if not identifiant_unique(ligne, ("point", identifiant, debut, fin)):
                    continue
                filtre = {"activite": cible} if est_element else {"sous_activite": cible}
                existant = PointSuivi.tous.filter(**filtre, periode_debut=debut, periode_fin=fin).first()
                periode = f"{debut:%d/%m/%Y} → {fin:%d/%m/%Y}"
                champs = {"quantite_realisee": qte, "budget_realise": budget, "statut": statut or "", "commentaire": commentaire}

                def enregistrer_point(cible=cible, filtre=filtre, existant=existant, champs=champs, debut=debut, fin=fin):
                    point = existant or PointSuivi(**filtre, periode_debut=debut, periode_fin=fin, saisi_par=utilisateur)
                    for cle, val in champs.items():
                        setattr(point, cle, val)
                    point.save()
                    (synchroniser_activite_depuis_suivi if isinstance(cible, Activite) else synchroniser_sous_activite_depuis_suivi)(cible)

                if existant is None:
                    ligne.actions.append(("ajout", f"Saisie de suivi {periode} : quantité {_fmt(qte)}"
                                          + (f", budget {_fmt(budget)}" if budget is not None else "")
                                          + (f", statut {statut}" if statut else "")))
                    ligne.operations.append(enregistrer_point)
                elif mode == MODE_AJOUT:
                    ligne.actions.append(("ignoree", f"Saisie {periode} déjà existante — conservée (mode ajouter)"))
                else:
                    changements = [
                        f"{nom} {_fmt(getattr(existant, cle))} → {_fmt(champs[cle])}"
                        for cle, nom in (("quantite_realisee", "quantité"), ("budget_realise", "budget"), ("statut", "statut"))
                        if _fmt(getattr(existant, cle)) != _fmt(champs[cle])
                    ]
                    ligne.actions.append(("modification", f"Saisie {periode} : " + (", ".join(changements) or "commentaire")))
                    ligne.operations.append(enregistrer_point)

            if taux is not None:
                date_taux = fin or aujourdhui
                existant = TauxManuel.tous.filter(activite=cible, date=date_taux).first()

                def enregistrer_taux(cible=cible, existant=existant, taux=taux, date_taux=date_taux, commentaire=commentaire):
                    objet = existant or TauxManuel(activite=cible, date=date_taux, saisi_par=utilisateur)
                    objet.taux, objet.commentaire = taux, commentaire
                    objet.save()

                if existant is None:
                    ligne.actions.append(("ajout", f"Taux manuel {_fmt(taux)} % au {date_taux:%d/%m/%Y}"))
                    ligne.operations.append(enregistrer_taux)
                elif mode == MODE_AJOUT:
                    ligne.actions.append(("ignoree", f"Taux manuel du {date_taux:%d/%m/%Y} déjà saisi — conservé (mode ajouter)"))
                else:
                    ligne.actions.append(("modification", f"Taux manuel du {date_taux:%d/%m/%Y} : {_fmt(existant.taux)} → {_fmt(taux)} %"))
                    ligne.operations.append(enregistrer_taux)

            for champ, valeur, nom in (("avancement", avancement, "Avancement (%)"), ("poids", poids, "Poids (%)")):
                if valeur is None:
                    continue

                def enregistrer_champ(cible=cible, champ=champ, valeur=valeur):
                    setattr(cible, champ, valeur)
                    cible.save(update_fields=[champ])

                _valeur_simple(ligne, mode, cible, champ, valeur, nom, enregistrer_champ)

    # ---- Feuille « Jalons et livrables » ----
    if FEUILLE_JALONS in wb.sheetnames:
        lignes, _ = _lire(wb[FEUILLE_JALONS], [COL_ID])
        for numero, v in lignes:
            if all(_vide(v.get(c)) for c in (COL_ID, COL_ELEMENT, COL_LIBELLE, COL_POIDS, COL_ACHEVEMENT, COL_VALIDE)):
                continue
            identifiant = str(v.get(COL_ID) or "").strip()
            ligne = Ligne(FEUILLE_JALONS, numero, identifiant, str(v.get(COL_LIBELLE) or "").strip())
            poids = _nombre(ligne, COL_POIDS, v.get(COL_POIDS))
            achevement = _nombre(ligne, COL_ACHEVEMENT, v.get(COL_ACHEVEMENT), 0, 100)
            valide = None
            if not _vide(v.get(COL_VALIDE)):
                valide = {"oui": True, "non": False}.get(_normaliser(v[COL_VALIDE]))
                if valide is None:
                    ligne.erreur(COL_VALIDE, "Attendu : Oui ou Non.")
            if identifiant:
                jalon = jalons_existants.get(identifiant)
                if jalon is None:
                    ligne.erreur(COL_ID, "Identifiant inconnu ou d'un autre projet.")
                if ligne.erreurs:
                    resultat.append(ligne)
                    continue
                if not identifiant_unique(ligne, ("jalon", identifiant)):
                    resultat.append(ligne)
                    continue
                ligne.libelle = jalon.libelle

                def enregistrer_jalon(jalon=jalon, champ=None, valeur=None):
                    setattr(jalon, champ, valeur)
                    if champ == "valide":
                        jalon.valide_par = utilisateur if valeur else None
                        jalon.date_validation = aujourdhui if valeur else None
                    jalon.save()

                for champ, valeur, nom in (("poids", poids, "Poids (%)"), ("achevement", achevement, "Achèvement (%)")):
                    if valeur is not None:
                        _valeur_simple(ligne, mode, jalon, champ, valeur, nom,
                                       lambda jalon=jalon, champ=champ, valeur=valeur: enregistrer_jalon(jalon, champ, valeur))
                if valide is not None and valide != jalon.valide:
                    if valide:
                        ligne.actions.append(("ajout", "Livrable validé"))
                        ligne.operations.append(lambda jalon=jalon: enregistrer_jalon(jalon, "valide", True))
                    elif mode == MODE_AJOUT:
                        ligne.actions.append(("ignoree", "Validation déjà enregistrée — conservée (mode ajouter)"))
                    else:
                        ligne.actions.append(("modification", "Validation retirée"))
                        ligne.operations.append(lambda jalon=jalon: enregistrer_jalon(jalon, "valide", False))
            else:
                element = elements.get(str(v.get(COL_ELEMENT) or "").strip())
                type_ = {"jalon": "JALON", "livrable": "LIVRABLE"}.get(_normaliser(v.get(COL_TYPE) or ""))
                if element is None:
                    ligne.erreur(COL_ELEMENT, "Identifiant d'élément (Exx) inconnu ou manquant.")
                if type_ is None:
                    ligne.erreur(COL_TYPE, "Type attendu : Jalon ou Livrable.")
                if not ligne.libelle:
                    ligne.erreur(COL_LIBELLE, "Libellé obligatoire pour un nouveau jalon ou livrable.")
                if not ligne.erreurs and identifiant_unique(ligne, ("nouveau-jalon", element.id, type_, ligne.libelle.lower())):
                    ligne.actions.append(("ajout", f"Nouveau {type_.lower()} « {ligne.libelle} » sur « {element.libelle} »"))
                    ligne.operations.append(
                        lambda element=element, type_=type_, libelle=ligne.libelle, poids=poids, achevement=achevement, valide=valide:
                        JalonLivrable.objects.create(
                            activite=element, type=type_, libelle=libelle, poids=poids, achevement=achevement or 0,
                            valide=bool(valide), valide_par=utilisateur if valide else None,
                            date_validation=aujourdhui if valide else None,
                        )
                    )
            resultat.append(ligne)

    # ---- Feuille « Indicateurs » ----
    if FEUILLE_INDICATEURS in wb.sheetnames:
        lignes, _ = _lire(wb[FEUILLE_INDICATEURS], [COL_ID])
        for numero, v in lignes:
            if all(_vide(v.get(c)) for c in (COL_DEBUT, COL_FIN, COL_VALEUR, COL_COMMENTAIRE)):
                continue
            identifiant = str(v.get(COL_ID) or "").strip()
            ligne = Ligne(FEUILLE_INDICATEURS, numero, identifiant, str(v.get("Libellé") or "").strip())
            resultat.append(ligne)
            indicateur = indicateurs.get(identifiant)
            if indicateur is None:
                ligne.erreur(COL_ID, "Identifiant inconnu ou d'un autre projet.")
                continue
            valeur = _nombre(ligne, COL_VALEUR, v.get(COL_VALEUR), minimum=Decimal("-1e12"))
            if valeur is None and not ligne.erreurs:
                ligne.erreur(COL_VALEUR, "Valeur réalisée obligatoire.")
            debut, fin = _periode(ligne, v)
            if ligne.erreurs or not identifiant_unique(ligne, ("indicateur", identifiant, debut, fin)):
                continue
            ligne.libelle = indicateur.libelle
            existant = ValeurIndicateur.tous.filter(indicateur=indicateur, periode_debut=debut, periode_fin=fin).first()
            commentaire = str(v.get(COL_COMMENTAIRE) or "").strip()

            def enregistrer_valeur(indicateur=indicateur, existant=existant, debut=debut, fin=fin, valeur=valeur, commentaire=commentaire):
                objet = existant or ValeurIndicateur(indicateur=indicateur, periode_debut=debut, periode_fin=fin, saisi_par=utilisateur)
                objet.valeur_realisee, objet.commentaire = valeur, commentaire
                objet.save()

            periode = f"{debut:%d/%m/%Y} → {fin:%d/%m/%Y}"
            if existant is None:
                ligne.actions.append(("ajout", f"Valeur {periode} : {_fmt(valeur)}"))
                ligne.operations.append(enregistrer_valeur)
            elif mode == MODE_AJOUT:
                ligne.actions.append(("ignoree", f"Valeur {periode} déjà saisie — conservée (mode ajouter)"))
            else:
                ligne.actions.append(("modification", f"Valeur {periode} : {_fmt(existant.valeur_realisee)} → {_fmt(valeur)}"))
                ligne.operations.append(enregistrer_valeur)

    if not any(n in wb.sheetnames for n in (FEUILLE_SUIVI, FEUILLE_JALONS, FEUILLE_INDICATEURS)):
        generales.append("Aucune feuille du canevas de suivi trouvée (Suivi, Jalons et livrables, Indicateurs).")
    # Lignes préremplies inchangées (ex : poids déjà en place) : rien à montrer.
    return [l for l in resultat if l.actions or l.erreurs], generales


def _totaux(lignes):
    totaux = {"ajout": 0, "modification": 0, "ignoree": 0, "erreur": 0}
    for ligne in lignes:
        totaux[ligne.statut()] += 1
    return totaux


def apercu_canevas(fichier, projet, mode, utilisateur):
    lignes, generales = analyser_canevas(fichier, projet, mode, utilisateur)
    return {"mode": mode, "totaux": _totaux(lignes), "lignes": [l.en_dict() for l in lignes], "erreurs_generales": generales}


def importer_canevas(fichier, projet, mode, utilisateur):
    """Enregistre les lignes valides (les lignes en erreur sont ignorées), dans une transaction."""
    from django.db import transaction

    lignes, generales = analyser_canevas(fichier, projet, mode, utilisateur)
    with transaction.atomic():
        for ligne in lignes:
            if not ligne.erreurs:
                for operation in ligne.operations:
                    operation()
    return {"mode": mode, "totaux": _totaux(lignes), "lignes": [l.en_dict() for l in lignes], "erreurs_generales": generales}


def rapport_erreurs(fichier, projet, mode, utilisateur) -> bytes:
    """Le fichier reçu, avec les cellules en erreur surlignées et commentées, et une feuille « Erreurs »."""
    lignes, generales = analyser_canevas(fichier, projet, mode, utilisateur)
    fichier.seek(0)
    wb = ramener_classeur(load_workbook(fichier))
    recap = wb.create_sheet("Erreurs", 0)
    recap.append(["Feuille", "Ligne", "Identifiant", "Colonne", "Erreur"])
    for cellule in recap[1]:
        cellule.font = Font(bold=True)
    for message in generales:
        recap.append(["", "", "", "", message])
    for ligne in lignes:
        if not ligne.erreurs or ligne.feuille not in wb.sheetnames:
            continue
        feuille = wb[ligne.feuille]
        entetes = [c.value for c in feuille[1]]
        for colonne, message in ligne.erreurs:
            recap.append([ligne.feuille, ligne.numero, ligne.identifiant, colonne, message])
            if colonne in entetes:
                cellule = feuille.cell(row=ligne.numero, column=entetes.index(colonne) + 1)
                cellule.fill = PatternFill("solid", fgColor=COULEUR_ERREUR)
                cellule.comment = Comment(message, "Plateforme S&E")
    for lettre, largeur in (("A", 22), ("B", 8), ("C", 14), ("D", 34), ("E", 90)):
        recap.column_dimensions[lettre].width = largeur
    adapter_classeur(wb)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
