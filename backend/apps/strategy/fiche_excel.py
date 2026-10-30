"""
Fiche d'un document de la chaîne (Programme, Pilier…) en Excel, sur le modèle de l'import d'un
projet (apps.projects.import_excel) :

- « Fiche » : une ligne par champ (colonne A = champ, colonne B = valeur), comme la feuille
  « Projet » ;
- « Financements » : un bailleur par ligne avec son montant (même feuille que pour un projet) ;
- « Structuration » : format « plan » (une colonne par niveau, puis « Contribue à (code) »),
  lue par apps.strategy.services.importer_structuration_depuis_feuille.

Le modèle d'un document existant est prérempli avec ses valeurs : on complète, on réimporte.
Une cellule vide ne change rien ; une valeur illisible ou introuvable est ignorée et signalée,
sans bloquer le reste.
"""
from decimal import Decimal

from openpyxl.styles import Font, PatternFill

from apps.core.excel_utils import quadriller

FEUILLE_FICHE = "Fiche"
FEUILLE_FINANCEMENTS = "Financements"

# (libellé de la ligne, clé interne) — l'ordre est celui de la feuille, proche de la fiche projet.
CHAMPS_FICHE = [
    ("Nom du document", "nom"),
    ("Code", "code"),
    ("Description", "description"),
    ("Rattaché à (nom exact du document au-dessus)", "document_parent"),
    ("Éléments de rattachement (codes séparés par ; — le premier compte)", "element_parent"),
    ("Statut (En préparation / En cours / Clôturé)", "statut"),
    ("Date de début (AAAA-MM-JJ)", "date_debut"),
    ("Date de fin (AAAA-MM-JJ)", "date_fin"),
    ("Budget total (FCFA)", "budget_total"),
    ("Fonds propres (FCFA)", "fonds_propres"),
    ("Type de mise en œuvre (Direct / En consortium)", "type_mise_en_oeuvre"),
    ("Partenaire de mise en œuvre", "partenaire_mise_en_oeuvre"),
    ("Partenaires du consortium (séparés par ;)", "partenaires_consortium"),
    ("Responsable", "responsable_nom"),
    ("Utilisateurs affectés — identifiants séparés par ;", "utilisateurs_affectes"),
    ("Pays (codes ISO séparés par ;)", "pays"),
    ("Tout le pays (Oui / Non)", "tout_le_pays"),
    ("Zones d'intervention (séparées par ;)", "zones"),
    ("Services chargés (sigles ou noms séparés par ;)", "structures"),
    ("Parties prenantes (séparées par ;)", "parties_prenantes"),
    ("Cible totale", "cible_totale"),
    ("Cible hommes", "cible_hommes"),
    ("Cible femmes", "cible_femmes"),
    ("Cible jeunes", "cible_jeunes"),
    ("Cible PDI", "cible_pdi"),
    ("Éléments de capitalisation", "elements_capitalisation"),
]
# Anciens libellés encore lus (fichiers téléchargés avant un changement de libellé).
ALIAS_CHAMPS = {"Élément de rattachement (code, facultatif)": "element_parent"}
CIBLES = ("cible_totale", "cible_hommes", "cible_femmes", "cible_jeunes", "cible_pdi")

INSTRUCTIONS_FICHE = [
    "Fiche d'un document de la chaîne (programme, pilier…) — même principe que le modèle d'import d'un projet",
    "",
    "- Feuille « Fiche » : une ligne = un champ (colonne A = nom du champ, colonne B = valeur). Le modèle",
    "  est prérempli avec les valeurs actuelles du document : complétez ou corrigez. Cellule vide = inchangé.",
    "- « Rattaché à » : nom exact d'un document d'un maillon au-dessus ; « Éléments de rattachement » : codes",
    "  de ses éléments séparés par « ; » (vide = le document lui-même). Le PREMIER compte dans les budgets et",
    "  les taux ; les suivants sont affichés pour information (pas de double compte). Sauter un maillon est",
    "  permis (avertissement).",
    "- Listes (partenaires du consortium, utilisateurs, pays, zones, services, parties prenantes) : séparées",
    "  par « ; ». Elles remplacent la liste actuelle. Un nom introuvable est ignoré et signalé.",
    "- Feuille « Financements » : une ligne par bailleur, avec son montant ; elle remplace les bailleurs du",
    "  document. Dès qu'un montant est saisi, budget total = fonds propres + financements.",
    "- Feuille « Structuration » : une colonne par niveau (en jaune), de gauche à droite ; sur chaque ligne,",
    "  écrire l'élément dans UNE SEULE colonne, son parent est le dernier élément écrit dans la colonne de",
    "  gauche au-dessus. « CODE — Nom » renseigne aussi le code. Dernière colonne « Contribue à (code) » :",
    "  code de l'élément du document au-dessus auquel l'élément contribue (le premier niveau suffit).",
    "- Réimporter le fichier met à jour le document sans rien dupliquer. Cette feuille n'est jamais importée.",
]


# Lignes de la Fiche dont la valeur est un choix (traduit avec le reste) et non une donnée libre.
CHAMPS_A_CHOIX = {"statut", "type_mise_en_oeuvre", "tout_le_pays"}


def traduire_classeur_document(wb) -> None:
    """
    Classeur d'un document (modèle ou export) dans une autre langue que le français : noms de
    feuilles, libellés de la Fiche, valeurs à choix (statut, type…), en-têtes, légende, consignes
    et « Contribue à (code) » sont traduits ; les données (noms, codes, montants, niveaux du
    document) restent telles quelles. L'import ramène tout au français (vers_francais).
    """
    from apps.core.langues import correspond, langue_active, traduire_classeur, vers_francais

    if langue_active() == "fr":
        return
    from .import_chaine import COLONNE_CONTRIBUTION
    from .services import DEBUT_LEGENDE

    libelles_a_choix = {libelle for libelle, cle in CHAMPS_FICHE if cle in CHAMPS_A_CHOIX}

    def garder(feuille, cellule):
        titre = str(vers_francais(feuille.title))
        if titre == FEUILLE_FICHE:
            if cellule.column == 1:
                return False
            # La colonne A est déjà traduite quand on arrive à la B : comparer à ses traductions.
            libelle = str(feuille.cell(row=cellule.row, column=1).value or "")
            return not any(correspond(libelle, l) for l in libelles_a_choix)
        if titre == FEUILLE_FINANCEMENTS:
            return cellule.row > 1 and cellule.column != 2  # en-têtes et type de bailleur traduits
        if titre == "Structuration":
            valeur = str(cellule.value or "")
            return not (valeur.startswith(DEBUT_LEGENDE) or valeur == COLONNE_CONTRIBUTION)
        return False  # Instructions

    traduire_classeur(wb, garder=garder)


def avec_fiche(document) -> bool:
    """Les documents des maillons après le premier (Programme, Pilier…) ont une fiche."""
    from .chaine import ordre_du_type

    return ordre_du_type(document.type_document) > 1


def _liste(valeurs) -> str:
    return "; ".join(str(v) for v in valeurs if v)


def valeurs_fiche(document) -> dict:
    """Valeurs actuelles du document, telles qu'écrites dans la feuille « Fiche »."""
    d = document
    return {
        "nom": d.nom, "code": d.code, "description": d.description,
        "document_parent": d.document_parent.nom if d.document_parent_id else "",
        "element_parent": _liste(
            [(d.element_parent.code or d.element_parent.nom) if d.element_parent_id else ""]
            + [e.code or e.nom for e in d.elements_parents_secondaires.all()]
        ),
        "statut": d.get_statut_display() if d.statut else "",
        "date_debut": d.date_debut.isoformat() if d.date_debut else "",
        "date_fin": d.date_fin.isoformat() if d.date_fin else "",
        "budget_total": float(d.budget_total) if d.budget_total else "",
        "fonds_propres": float(d.fonds_propres) if d.fonds_propres else "",
        "type_mise_en_oeuvre": d.get_type_mise_en_oeuvre_display(),
        "partenaire_mise_en_oeuvre": d.partenaire_mise_en_oeuvre.nom if d.partenaire_mise_en_oeuvre_id else "",
        "partenaires_consortium": _liste(p.nom for p in d.partenaires_consortium.all()),
        "responsable_nom": d.responsable_nom,
        "utilisateurs_affectes": _liste(u.username for u in d.utilisateurs_affectes.all()),
        "pays": _liste(d.pays),
        "tout_le_pays": "Oui" if d.tout_le_pays else "Non",
        "zones": _liste(z.nom for z in d.zones.all()),
        "structures": _liste(s.sigle or s.nom for s in d.structures.all()),
        "parties_prenantes": _liste(p.nom for p in d.parties_prenantes.all()),
        **{c: getattr(d, c) if getattr(d, c) is not None else "" for c in CIBLES},
        "elements_capitalisation": d.elements_capitalisation,
    }


def ajouter_feuilles_fiche(wb, document) -> None:
    """Feuilles « Fiche » (préremplie) et « Financements » (bailleurs actuels) en tête du classeur."""
    from apps.projects.import_excel import generer_feuille_financements

    fiche = wb.create_sheet(FEUILLE_FICHE, 0)
    valeurs = valeurs_fiche(document)
    for libelle, cle in CHAMPS_FICHE:
        fiche.append([libelle, valeurs[cle]])
    for ligne in fiche.iter_rows(min_col=1, max_col=1):
        ligne[0].font = Font(bold=True)
        ligne[0].fill = PatternFill("solid", fgColor="FFF2CC")
    quadriller(fiche, max_col=2)
    fiche.column_dimensions["A"].width = 50
    fiche.column_dimensions["B"].width = 70

    financements = generer_feuille_financements(wb, avec_exemple=False)
    lignes = [[f.bailleur.nom, f.bailleur.get_type_display(), float(f.montant)] for f in document.financements.select_related("bailleur")]
    for i, ligne in enumerate(lignes, start=2):
        for j, valeur in enumerate(ligne, start=1):
            financements.cell(row=i, column=j, value=valeur)
    wb.move_sheet(financements, offset=1 - wb.sheetnames.index(FEUILLE_FINANCEMENTS))


# ------------------------------------------------------------------------------------- import


def _cle(texte) -> str:
    from apps.projects.import_excel import _normaliser_entete

    return _normaliser_entete(str(texte or ""))


def _elements_liste(texte) -> list:
    return [x.strip() for x in str(texte or "").split(";") if x.strip()]


def importer_fiche(wb, document) -> tuple[list, list]:
    """
    Applique les feuilles « Fiche » et « Financements » au document (celui de la page d'où
    l'import est lancé). Renvoie (erreurs, avertissements) ; rien ne bloque le reste de l'import.
    """
    from apps.accounts.models import User
    from apps.core.langues import correspond
    from apps.geo.models import Zone
    from apps.partners.models import Partenaire, PartiePrenante, StructureOrganisation

    from .chaine import controler_rattachement
    from .import_chaine import _date, _montant, _trouver_feuille
    from .models import CadreStrategique, ElementStrategique

    erreurs, avertissements = [], []
    feuille = _trouver_feuille(wb, FEUILLE_FICHE)
    # Libellés reconnus dans toutes les langues (comparés aux traductions de chaque libellé attendu).
    champs = [*CHAMPS_FICHE, *ALIAS_CHAMPS.items()]
    valeurs, numeros = {}, {}
    for numero, ligne in enumerate(feuille.iter_rows(values_only=True), start=1):
        if not ligne or ligne[0] in (None, ""):
            continue
        cle = next((c for libelle, c in champs if correspond(str(ligne[0]), libelle)), None)
        valeur = ligne[1] if len(ligne) > 1 else None
        if cle and valeur not in (None, ""):
            valeurs[cle] = valeur.strip() if isinstance(valeur, str) else valeur
            numeros[cle] = numero

    def signaler(cle, message):
        avertissements.append({"ligne": numeros.get(cle, 0), "message": f"[Fiche] {message}"})

    d = document
    for cle in ("nom", "code", "description", "responsable_nom", "elements_capitalisation"):
        if cle in valeurs:
            setattr(d, cle, str(valeurs[cle])[:200] if cle in ("nom", "responsable_nom") else str(valeurs[cle]))
    for cle, modele in (("statut", CadreStrategique.Statut), ("type_mise_en_oeuvre", CadreStrategique.TypeMiseEnOeuvre)):
        if cle in valeurs:
            saisie = str(valeurs[cle])
            code = next((code for code, libelle in modele.choices if correspond(saisie, libelle) or correspond(saisie, code)), None)
            if code:
                setattr(d, cle, code)
            else:
                signaler(cle, f"Valeur « {valeurs[cle]} » inconnue — ignorée.")
    for cle in ("date_debut", "date_fin"):
        if cle in valeurs:
            date = valeurs[cle].date() if hasattr(valeurs[cle], "date") else _date(valeurs[cle])
            if date:
                setattr(d, cle, date)
            else:
                signaler(cle, f"Date « {valeurs[cle]} » illisible — ignorée.")
    for cle in ("budget_total", "fonds_propres"):
        if cle in valeurs:
            montant = _montant(valeurs[cle])
            if montant is not None and montant >= 0:
                setattr(d, cle, montant)
            else:
                signaler(cle, f"Montant « {valeurs[cle]} » illisible — ignoré.")
    for cle in CIBLES:
        if cle in valeurs:
            try:
                setattr(d, cle, max(0, int(float(valeurs[cle]))))
            except (TypeError, ValueError):
                signaler(cle, f"Nombre « {valeurs[cle]} » illisible — ignoré.")
    if "tout_le_pays" in valeurs:
        saisie = str(valeurs["tout_le_pays"])
        d.tout_le_pays = correspond(saisie, "Oui") or _cle(saisie) in ("yes", "1", "true", "vrai")
    if "pays" in valeurs:
        d.pays = [p.upper()[:2] for p in _elements_liste(valeurs["pays"])]
    if "partenaire_mise_en_oeuvre" in valeurs:
        nom = str(valeurs["partenaire_mise_en_oeuvre"])
        d.partenaire_mise_en_oeuvre = (
            Partenaire.objects.filter(nom__iexact=nom).first()
            or Partenaire.objects.create(nom=nom, type=Partenaire.TypePartenaire.MISE_EN_OEUVRE)
        )

    # Rattachement : contrôlé comme dans le formulaire (erreur : ignoré ; saut : avertissement).
    secondaires = None  # None : inchangés
    if "document_parent" in valeurs or "element_parent" in valeurs:
        parent, element = d.document_parent, d.element_parent
        if "document_parent" in valeurs:
            parent = CadreStrategique.objects.filter(nom__iexact=str(valeurs["document_parent"])).first()
            element, secondaires = None, []
            if parent is None:
                erreurs.append({"ligne": numeros["document_parent"],
                                "message": f"[Fiche] Document « {valeurs['document_parent']} » introuvable — rattachement inchangé."})
        if parent is not None and "element_parent" in valeurs:
            # « P3-K1; P3-K2 » : le premier est l'élément principal, les suivants pour information.
            elements = ElementStrategique.objects.filter(type_niveau__cadre_strategique=parent)
            trouves = []
            for texte in _elements_liste(valeurs["element_parent"]):
                trouve = elements.filter(code__iexact=texte).first() or elements.filter(nom__iexact=texte).first()
                if trouve is None:
                    signaler("element_parent", f"Élément « {texte} » introuvable dans « {parent} » — ignoré.")
                elif trouve not in trouves:
                    trouves.append(trouve)
            element, secondaires = (trouves[0] if trouves else None), trouves[1:]
        if parent is not None:
            refus, alertes = controler_rattachement(d.id, d.type_document, parent, element)
            if refus:
                secondaires = None
                erreurs.extend({"ligne": numeros.get("document_parent", 0), "message": f"[Fiche] {m}"} for m in refus)
            else:
                d.document_parent, d.element_parent = parent, element
                avertissements.extend({"ligne": numeros.get("document_parent", 0), "message": f"[Fiche] {m}"} for m in alertes)
    if d.date_debut and d.date_fin and d.date_fin < d.date_debut:
        signaler("date_fin", "La date de fin précède la date de début.")
    d.save()
    if secondaires is not None:
        d.elements_parents_secondaires.set(secondaires)

    def retrouver(cle, chercher):
        """Objets d'une liste « ; » ; les noms introuvables sont signalés."""
        trouves = []
        for texte in _elements_liste(valeurs[cle]):
            objet = chercher(texte)
            if objet is None:
                signaler(cle, f"« {texte} » introuvable — ignoré.")
            else:
                trouves.append(objet)
        return trouves

    if "partenaires_consortium" in valeurs:
        d.partenaires_consortium.set(retrouver("partenaires_consortium", lambda t: (
            Partenaire.objects.filter(nom__iexact=t).first() or Partenaire.objects.create(nom=t, type=Partenaire.TypePartenaire.CONSORTIUM))))
    if "utilisateurs_affectes" in valeurs:
        d.utilisateurs_affectes.set(retrouver("utilisateurs_affectes", lambda t: User.objects.filter(username__iexact=t).first()))
    if "zones" in valeurs:
        d.zones.set(retrouver("zones", lambda t: Zone.objects.filter(nom__iexact=t).order_by("niveau_administratif__ordre").first()))
    if "structures" in valeurs:
        d.structures.set(retrouver("structures", lambda t: (
            StructureOrganisation.objects.filter(sigle__iexact=t).first() or StructureOrganisation.objects.filter(nom__iexact=t).first())))
    if "parties_prenantes" in valeurs:
        d.parties_prenantes.set(retrouver("parties_prenantes", lambda t: PartiePrenante.objects.filter(nom__iexact=t).first()))

    financements = _trouver_feuille(wb, FEUILLE_FINANCEMENTS)
    if financements is not None:
        erreurs.extend(_importer_financements(financements, d))
    return erreurs, avertissements


def _importer_financements(feuille, document) -> list:
    """Remplace les bailleurs du document par ceux de la feuille (lignes vides ignorées)."""
    from apps.core.langues import correspond
    from apps.partners.models import Bailleur
    from apps.projects.import_excel import COLONNES_FINANCEMENTS

    from .import_chaine import _montant
    from .serializers import enregistrer_bailleurs

    lignes = list(feuille.iter_rows(values_only=True))
    if not lignes:
        return []
    # En-têtes et types de bailleur reconnus dans toutes les langues (modèle rempli traduit).
    def colonne(nom):
        return next((i for i, c in enumerate(lignes[0]) if c not in (None, "") and correspond(str(c), nom)), None)

    i_nom, i_type, i_montant = (colonne(c) for c in COLONNES_FINANCEMENTS)
    if i_nom is None or i_montant is None:
        return [{"ligne": 1, "message": "[Financements] Colonnes « Bailleur » et « Montant financé (FCFA) » introuvables."}]
    erreurs, retenus = [], []
    for numero, ligne in enumerate(lignes[1:], start=2):
        nom = str(ligne[i_nom] or "").strip() if i_nom < len(ligne) else ""
        brut = ligne[i_montant] if i_montant < len(ligne) else None
        if not nom and brut in (None, ""):
            continue
        montant = _montant(brut) if brut not in (None, "") else Decimal(0)
        if not nom or montant is None or montant < 0:
            erreurs.append({"ligne": numero, "message": f"[Financements] Bailleur ou montant invalide (« {nom} ») — ligne ignorée."})
            continue
        if nom.lower() in {r["nom"].lower() for r in retenus}:
            erreurs.append({"ligne": numero, "message": f"[Financements] Bailleur « {nom} » déjà présent plus haut — ligne ignorée."})
            continue
        if not Bailleur.objects.filter(nom__iexact=nom).exists() and i_type is not None and i_type < len(ligne):
            saisie = str(ligne[i_type] or "")
            type_ = next((code for code, libelle in Bailleur.TypeBailleur.choices if correspond(saisie, libelle)), Bailleur.TypeBailleur.AUTRE)
            Bailleur.objects.create(nom=nom, type=type_)
        retenus.append({"nom": nom, "montant": montant})
    enregistrer_bailleurs(document, retenus)
    return erreurs
