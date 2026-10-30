"""
Chaîne des documents stratégiques en un seul fichier Excel (modèle, export, import) :

- « Maillons » : les rubriques de la chaîne, de haut en bas (Cadre stratégique, Programme,
  Pilier 1…), chacune devenant une rubrique du menu ;
- « Documents » : un document par ligne, son maillon et son rattachement (document parent et,
  facultativement, code de l'élément du parent) ;
- « Éléments » : la structuration de chaque document (niveau, code, nom, code du parent dans le
  même document) et, pour chaque élément, l'élément d'un document au-dessus auquel il contribue.

Rejouable : réimporter met à jour (maillon et document par nom, élément par code ou par niveau
et nom). Best-effort : une ligne en erreur est ignorée et signalée ; les sauts de maillons sont
acceptés et signalés comme avertissements.
"""
import io

from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.vocabulaire import adapter_classeur

FEUILLE_MAILLONS, FEUILLE_DOCUMENTS, FEUILLE_ELEMENTS = "Maillons", "Documents", "Éléments"
COLONNES_MAILLONS = ["Maillon", "Rubrique du menu"]
COLONNES_DOCUMENTS = ["Document", "Maillon", "Document parent", "Élément parent (code)", "Description"]
# Fiche du document (comme un projet), facultative : un fichier sans ces colonnes reste valable.
COLONNES_FICHE = ["Code", "Statut", "Date de début", "Date de fin", "Budget total", "Fonds propres", "Responsable"]
COLONNES_ELEMENTS = ["Document", "Niveau", "Code", "Nom", "Code parent", "Contribue à (code)"]
COLONNE_CONTRIBUTION = "Contribue à (code)"

EXEMPLE_MAILLONS = [
    ["Cadre stratégique", "Cadres stratégiques"], ["Programme", "Programmes"],
    ["Pilier 1", "Piliers 1"], ["Pilier 2", "Piliers 2"], ["Pilier 3", "Piliers 3"],
]
EXEMPLE_DOCUMENTS = [
    ["Plan national de développement", "Cadre stratégique", "", "", "", "PND", "En cours", "2026-01-01", "2030-12-31", "", "", ""],
    ["Programme capital humain", "Programme", "Plan national de développement", "AXE1", "", "PCH", "En cours",
     "2026-01-01", "2030-12-31", 50000000000, 5000000000, "Direction de la planification"],
    ["Pilier Éducation", "Pilier 1", "Programme capital humain", "", "", "PE", "En préparation",
     "2026-07-01", "2029-12-31", 12000000000, 1000000000, ""],
]
EXEMPLE_ELEMENTS = [
    ["Plan national de développement", "Axe", "AXE1", "Développer le capital humain", "", ""],
    ["Programme capital humain", "Objectif", "OBJ1", "Améliorer l'accès à l'éducation", "", "AXE1"],
    ["Programme capital humain", "Résultat", "R1.1", "Les écoles sont construites", "OBJ1", ""],
    ["Pilier Éducation", "Axe", "PE1", "Infrastructures scolaires", "", "R1.1"],
]
INSTRUCTIONS = [
    "Chaîne des documents stratégiques",
    "- Feuille « Maillons » : les rubriques de la chaîne, de la plus haute à la plus basse (une par ligne).",
    "  Chacune devient une rubrique du menu ; les projets se rattachent au dernier maillon.",
    "- Feuille « Documents » : un document par ligne, avec son maillon et le document au-dessus auquel il est",
    "  rattaché ; « Élément parent (code) » précise l'élément de ce document (vide = le document lui-même) ;",
    "  plusieurs codes séparés par « ; » : le premier compte, les suivants sont pour information.",
    "  Sauter un maillon est permis (ex : un pilier 3 rattaché au programme) : un avertissement le signale.",
    "  Colonnes facultatives de la fiche : Code, Statut (En préparation / En cours / Clôturé), dates",
    "  (AAAA-MM-JJ ou JJ/MM/AAAA), Budget total, Fonds propres (FCFA) et Responsable.",
    "- Feuille « Éléments » : la structuration de chaque document. « Niveau » est le nom du niveau (créé à",
    "  sa première apparition, dans l'ordre du fichier) ; « Code parent » est le code de l'élément parent",
    "  dans le même document ; « Contribue à (code) » est le code d'un élément d'un document au-dessus",
    "  (écrire « Document / CODE » si plusieurs documents ont ce code).",
    "- Réimporter le fichier met à jour ce qui existe déjà au lieu de le dupliquer.",
]

_ENTETE = PatternFill("solid", fgColor="FFF2CC")


def _feuille(wb, titre, colonnes, lignes, largeurs):
    """Ajoute une feuille : en-têtes en jaune, lignes données, 20 lignes vides à remplir, quadrillage."""
    feuille = wb.create_sheet(titre) if wb.sheetnames != ["Sheet"] else wb.active
    feuille.title = titre
    feuille.append(colonnes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
        cellule.fill = _ENTETE
    for ligne in lignes:
        feuille.append(ligne)
    for _ in range(20):
        feuille.append([""] * len(colonnes))
    for i, largeur in enumerate(largeurs):
        feuille.column_dimensions[chr(ord("A") + i)].width = largeur
    quadriller(feuille, max_col=len(colonnes))
    figer_entete(feuille)


def _classeur(maillons, documents, elements, adapter=True) -> bytes:
    """Classeur des trois feuilles et des consignes ; `adapter` : traduit / adapte au vocabulaire (modèle seulement)."""
    wb = Workbook()
    _feuille(wb, FEUILLE_MAILLONS, COLONNES_MAILLONS, maillons, [30, 30])
    _feuille(wb, FEUILLE_DOCUMENTS, COLONNES_DOCUMENTS + COLONNES_FICHE, documents, [42, 22, 42, 22, 50, 14, 16, 14, 14, 18, 18, 30])
    _feuille(wb, FEUILLE_ELEMENTS, COLONNES_ELEMENTS, elements, [42, 24, 14, 60, 14, 24])
    instructions = wb.create_sheet("Instructions")
    for ligne in INSTRUCTIONS:
        instructions.append([ligne])
    instructions.column_dimensions["A"].width = 110
    if adapter:
        # Modèle : traduit ou adapté au vocabulaire ; export : données telles quelles (réimportables).
        adapter_classeur(wb)
    else:
        _traduire_structure(wb)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _traduire_structure(wb) -> None:
    """
    Export dans une autre langue : noms de feuilles, en-têtes, statuts et consignes traduits ;
    les données (maillons, documents, codes, noms) restent telles quelles, pour être réimportées.
    """
    from apps.core.langues import langue_active, traduire_classeur

    if langue_active() == "fr":
        return
    feuilles_de_donnees = {FEUILLE_MAILLONS, FEUILLE_DOCUMENTS, FEUILLE_ELEMENTS}
    colonne_statut = (COLONNES_DOCUMENTS + COLONNES_FICHE).index("Statut") + 1

    def garder(feuille, cellule):
        if feuille.title not in feuilles_de_donnees or cellule.row == 1:
            return False
        return not (feuille.title == FEUILLE_DOCUMENTS and cellule.column == colonne_statut)

    traduire_classeur(wb, garder=garder)


def generer_modele_chaine() -> bytes:
    """Modèle à remplir, avec un exemple de chaîne (cadre → programme → pilier)."""
    return _classeur(EXEMPLE_MAILLONS, EXEMPLE_DOCUMENTS, EXEMPLE_ELEMENTS)


def _texte_contribution(cible, documents_meme_code) -> str:
    """Code de l'élément visé, précédé du document quand le code seul est ambigu."""
    document = cible.type_niveau.cadre_strategique
    if not cible.code or documents_meme_code.get(cible.code, 0) > 1:
        return f"{document.nom} / {cible.code or cible.nom}"
    return cible.code


def exporter_chaine() -> bytes:
    """Toute la chaîne actuelle, au format du modèle (réimportable tel quel)."""
    from .models import CadreStrategique, ElementStrategique, TypeDocument

    types = list(TypeDocument.objects.order_by("ordre", "id"))
    premier = types[0] if types else None
    rang = {t.id: i for i, t in enumerate(types)}
    documents = sorted(
        CadreStrategique.objects.select_related("type_document", "document_parent", "element_parent").prefetch_related("elements_parents_secondaires"),
        key=lambda d: (rang.get(d.type_document_id, 0), d.nom),
    )
    elements = list(
        ElementStrategique.objects.select_related("type_niveau__cadre_strategique", "element_parent", "contribue_a__type_niveau__cadre_strategique")
        .order_by("type_niveau__cadre_strategique_id", "type_niveau__ordre", "id")
    )
    codes = {}
    for e in elements:
        if e.code:
            codes[e.code] = codes.get(e.code, 0) + 1
    ordre_documents = {d.id: i for i, d in enumerate(documents)}
    elements.sort(key=lambda e: (ordre_documents.get(e.type_niveau.cadre_strategique_id, 0), e.type_niveau.ordre, e.id))
    return _classeur(
        [[t.nom, t.nom_pluriel] for t in types],
        [
            [d.nom, (d.type_document or premier).nom if (d.type_document or premier) else "",
             d.document_parent.nom if d.document_parent_id else "",
             "; ".join(filter(None, [(d.element_parent.code or d.element_parent.nom) if d.element_parent_id else ""]
                              + [e.code or e.nom for e in d.elements_parents_secondaires.all()])), d.description,
             *_valeurs_fiche(d)]
            for d in documents
        ],
        [
            [e.type_niveau.cadre_strategique.nom, e.type_niveau.nom_niveau, e.code, e.nom,
             (e.element_parent.code or e.element_parent.nom) if e.element_parent_id else "",
             _texte_contribution(e.contribue_a, codes) if e.contribue_a_id else ""]
            for e in elements
        ],
        adapter=False,
    )


def _valeurs_fiche(document) -> list:
    """Colonnes de la fiche d'un document, dans l'ordre de COLONNES_FICHE (export)."""
    return [
        document.code, document.get_statut_display() if document.statut else "",
        document.date_debut.isoformat() if document.date_debut else "",
        document.date_fin.isoformat() if document.date_fin else "",
        float(document.budget_total) if document.budget_total else "",
        float(document.fonds_propres) if document.fonds_propres else "", document.responsable_nom,
    ]


# ----------------------------------------------------------------------------------------- import


def _date(texte):
    """Date d'une cellule : AAAA-MM-JJ (date Excel comprise) ou JJ/MM/AAAA ; None si illisible."""
    import datetime

    texte = str(texte or "").strip()
    for format_, longueur in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10)):
        try:
            return datetime.datetime.strptime(texte[:longueur], format_).date()
        except ValueError:
            continue
    return None


def _montant(texte):
    """Montant d'une cellule (espaces et virgule décimale tolérés) ; None si illisible."""
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(texte).replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def appliquer_fiche(document, v, signaler) -> None:
    """
    Renseigne la fiche du document depuis les colonnes facultatives (une cellule vide ne change
    rien) ; une valeur illisible est ignorée et signalée par `signaler(message)`.
    """
    from .models import CadreStrategique

    if v.get("Code"):
        document.code = v["Code"][:50]
    if v.get("Responsable"):
        document.responsable_nom = v["Responsable"][:200]
    if v.get("Statut"):
        from apps.core.langues import correspond

        statut = next((code for code, libelle in CadreStrategique.Statut.choices
                       if correspond(v["Statut"], libelle) or correspond(v["Statut"], code)), None)
        if statut:
            document.statut = statut
        else:
            signaler(f"Statut « {v['Statut']} » inconnu (En préparation, En cours ou Clôturé) — ignoré.")
    for colonne, champ in (("Date de début", "date_debut"), ("Date de fin", "date_fin")):
        if v.get(colonne):
            date = _date(v[colonne])
            if date:
                setattr(document, champ, date)
            else:
                signaler(f"{colonne} « {v[colonne]} » illisible — ignorée.")
    for colonne, champ in (("Budget total", "budget_total"), ("Fonds propres", "fonds_propres")):
        if v.get(colonne):
            montant = _montant(v[colonne])
            if montant is not None and montant >= 0:
                setattr(document, champ, montant)
            else:
                signaler(f"{colonne} « {v[colonne]} » illisible — ignoré.")
    if document.date_debut and document.date_fin and document.date_fin < document.date_debut:
        signaler("La date de fin précède la date de début.")



def _cle(texte) -> str:
    """Forme de comparaison d'un nom : espaces réduits, minuscules."""
    return " ".join(str(texte or "").split()).lower()


def _trouver_feuille(wb, nom):
    """Feuille d'après son nom français (accents facultatifs), même si le modèle a été téléchargé dans une autre langue."""
    from apps.core.langues import correspond

    return next((feuille for feuille in wb.worksheets if correspond(feuille.title, nom)), None)


def _lignes(feuille, colonnes):
    """[(numéro, {colonne: valeur})] d'une feuille, colonnes repérées par leur en-tête (même traduit)."""
    lignes = list(feuille.iter_rows(values_only=True))
    if not lignes:
        return []
    from apps.core.langues import correspond

    # En-têtes reconnus dans toutes les langues, accents et casse indifférents.
    index = {}
    for nom in colonnes:
        trouve = next((i for i, c in enumerate(lignes[0]) if c is not None and correspond(str(c), nom)), None)
        if trouve is not None:
            index[nom] = trouve
    resultat = []
    for numero, ligne in enumerate(lignes[1:], start=2):
        valeurs = {nom: (str(ligne[i]).strip() if i < len(ligne) and ligne[i] is not None else "") for nom, i in index.items()}
        if any(valeurs.values()):
            resultat.append((numero, valeurs))
    return resultat


def resoudre_contribution(document, texte):
    """
    Élément visé par « CODE » ou « Document / CODE » : d'abord dans les documents au-dessus de
    `document` (sa chaîne de rattachement), sinon dans tout document d'un maillon au-dessus.
    Renvoie (élément, message d'erreur).
    """
    from .chaine import documents_au_dessus, ordre_du_type, types_ordonnes
    from .models import ElementStrategique

    texte = str(texte or "").strip()
    if not texte:
        return None, None
    nom_document, _, code = texte.rpartition("/")
    nom_document, code = nom_document.strip(), code.strip()
    candidats = ElementStrategique.objects.select_related("type_niveau__cadre_strategique__type_document").filter(code__iexact=code)
    if nom_document:
        candidats = candidats.filter(type_niveau__cadre_strategique__nom__iexact=nom_document)
    candidats = [c for c in candidats if c.type_niveau.cadre_strategique_id != document.id]
    if not candidats:
        return None, f"Élément « {texte} » introuvable dans un autre document."
    au_dessus = {d.id for d in documents_au_dessus(document)}
    dans_la_chaine = [c for c in candidats if c.type_niveau.cadre_strategique_id in au_dessus]
    if len(dans_la_chaine) == 1:
        return dans_la_chaine[0], None
    types = types_ordonnes()
    rang = ordre_du_type(document.type_document, types)
    plus_haut = [c for c in (dans_la_chaine or candidats) if ordre_du_type(c.type_niveau.cadre_strategique.type_document, types) < rang]
    if len(plus_haut) == 1:
        return plus_haut[0], None
    if not plus_haut:
        return None, f"« {texte} » n'est pas un élément d'un document d'un maillon au-dessus."
    return None, f"Code « {texte} » présent dans plusieurs documents : écrire « Document / {code} »."


@transaction.atomic
def importer_chaine(fichier) -> dict:
    """
    Importe les trois feuilles dans l'ordre : maillons (et leur ordre), documents (créés, puis
    rattachés), éléments, puis les rattachements à un élément et les contributions — qui
    supposent que les éléments visés existent. Tout ou rien en cas d'erreur inattendue
    (transaction) ; les lignes en erreur sont seulement ignorées et signalées.
    """
    from .chaine import controler_contribution, controler_rattachement
    from .models import CadreStrategique, ElementStrategique, TypeDocument, TypeNiveau

    wb = load_workbook(fichier, data_only=True)
    rapport = {"maillons_crees": 0, "documents_crees": 0, "documents_mis_a_jour": 0,
               "elements_crees": 0, "elements_mis_a_jour": 0, "erreurs": [], "avertissements": []}

    def erreur(feuille, ligne, message):
        """Ligne ignorée, signalée avec sa feuille."""
        rapport["erreurs"].append({"ligne": ligne, "message": f"[{feuille}] {message}"})

    def avertir(feuille, ligne, message):
        """Ligne acceptée mais à vérifier (saut de maillon…)."""
        rapport["avertissements"].append({"ligne": ligne, "message": f"[{feuille}] {message}"})

    # Maillons : dans l'ordre du fichier, avant ceux qui n'y figurent pas.
    feuille = _trouver_feuille(wb, FEUILLE_MAILLONS)
    if feuille is not None:
        existants = {_cle(t.nom): t for t in TypeDocument.objects.all()}
        vus = []
        for numero, v in _lignes(feuille, COLONNES_MAILLONS):
            nom = v.get("Maillon", "")
            if not nom:
                erreur(FEUILLE_MAILLONS, numero, "Nom du maillon manquant — ligne ignorée.")
                continue
            maillon = existants.get(_cle(nom))
            if maillon is None:
                maillon = TypeDocument.objects.create(nom=nom, nom_pluriel=v.get("Rubrique du menu") or nom, ordre=0)
                existants[_cle(nom)] = maillon
                rapport["maillons_crees"] += 1
            elif v.get("Rubrique du menu"):
                maillon.nom_pluriel = v["Rubrique du menu"]
            if maillon not in vus:
                vus.append(maillon)
        autres = [t for t in TypeDocument.objects.order_by("ordre", "id") if t not in vus]
        for rang, maillon in enumerate(vus + autres, start=1):
            maillon.ordre = rang
            maillon.save()

    maillons = {_cle(t.nom): t for t in TypeDocument.objects.all()}
    premier = TypeDocument.objects.order_by("ordre", "id").first()
    documents = {_cle(d.nom): d for d in CadreStrategique.objects.select_related("type_document")}

    # Documents : créés d'abord (un parent peut figurer plus bas), rattachés ensuite.
    feuille = _trouver_feuille(wb, FEUILLE_DOCUMENTS)
    lignes_documents = _lignes(feuille, COLONNES_DOCUMENTS + COLONNES_FICHE) if feuille is not None else []
    a_rattacher = []
    for numero, v in lignes_documents:
        nom = v.get("Document", "")
        if not nom:
            erreur(FEUILLE_DOCUMENTS, numero, "Nom du document manquant — ligne ignorée.")
            continue
        document = documents.get(_cle(nom))
        # Maillon vide : celui du document s'il existe déjà (sinon le premier maillon).
        if v.get("Maillon"):
            maillon = maillons.get(_cle(v["Maillon"]))
        else:
            maillon = (document.type_document if document is not None else None) or premier
        if maillon is None:
            connus = ", ".join(t.nom for t in TypeDocument.objects.order_by("ordre", "id"))
            erreur(FEUILLE_DOCUMENTS, numero, f"Maillon « {v.get('Maillon')} » inconnu — maillons existants : {connus}. Ligne ignorée.")
            continue
        if document is None:
            document = CadreStrategique(nom=nom, description=v.get("Description", ""), type_document=maillon)
            rapport["documents_crees"] += 1
        else:
            document.type_document = maillon
            if v.get("Description"):
                document.description = v["Description"]
            rapport["documents_mis_a_jour"] += 1
        appliquer_fiche(document, v, lambda message: avertir(FEUILLE_DOCUMENTS, numero, f"{nom} : {message}"))
        document.save()
        documents[_cle(nom)] = document
        a_rattacher.append((numero, document, v))

    def rattacher_documents(seulement_sans_element):
        """
        Rattache les documents de la feuille. Deux passages : d'abord les rattachements au
        document lui-même (avant les éléments), puis ceux à un élément du parent (après).
        """
        for numero, document, v in a_rattacher:
            code_element = v.get("Élément parent (code)", "")
            if seulement_sans_element == bool(code_element):
                continue
            parent = None
            if v.get("Document parent"):
                parent = documents.get(_cle(v["Document parent"]))
                if parent is None:
                    erreur(FEUILLE_DOCUMENTS, numero, f"Document parent « {v['Document parent']} » inconnu — rattachement ignoré.")
                    continue
            element, secondaires = None, []
            if code_element:
                if parent is None:
                    erreur(FEUILLE_DOCUMENTS, numero, "Élément parent sans document parent — rattachement ignoré.")
                    continue
                # « P3-K1; P3-K2 » : le premier est l'élément principal, les suivants pour information.
                trouves, introuvable = [], None
                for code in [c.strip() for c in code_element.split(";") if c.strip()]:
                    trouve = ElementStrategique.objects.filter(type_niveau__cadre_strategique=parent).filter(code__iexact=code).first() \
                        or ElementStrategique.objects.filter(type_niveau__cadre_strategique=parent, nom__iexact=code).first()
                    if trouve is None:
                        introuvable = code
                        break
                    trouves.append(trouve)
                if introuvable is not None:
                    erreur(FEUILLE_DOCUMENTS, numero, f"Élément « {introuvable} » introuvable dans « {parent} » — rattachement ignoré.")
                    continue
                element, secondaires = trouves[0], [e for e in trouves[1:] if e != trouves[0]]
            erreurs, avertissements = controler_rattachement(document.id, document.type_document, parent, element)
            if erreurs:
                for message in erreurs:
                    erreur(FEUILLE_DOCUMENTS, numero, message)
                continue
            for message in avertissements:
                avertir(FEUILLE_DOCUMENTS, numero, f"{document.nom} : {message}")
            document.document_parent, document.element_parent = parent, element
            document.save(update_fields=["document_parent", "element_parent", "updated_at"])
            document.elements_parents_secondaires.set(secondaires)

    # Rattachements au document lui-même tout de suite (pour résoudre la chaîne des contributions),
    # rattachements à un élément après la création des éléments.
    rattacher_documents(seulement_sans_element=True)

    # Éléments : niveaux créés à leur première apparition, dans l'ordre du fichier.
    feuille = _trouver_feuille(wb, FEUILLE_ELEMENTS)
    lignes_elements = _lignes(feuille, COLONNES_ELEMENTS) if feuille is not None else []
    contributions = []
    niveaux = {}
    for numero, v in lignes_elements:
        document = documents.get(_cle(v.get("Document")))
        if document is None:
            erreur(FEUILLE_ELEMENTS, numero, f"Document « {v.get('Document')} » inconnu (feuille « Documents ») — ligne ignorée.")
            continue
        nom, code, nom_niveau = v.get("Nom", ""), v.get("Code", ""), v.get("Niveau", "")
        if not nom or not nom_niveau:
            erreur(FEUILLE_ELEMENTS, numero, "Niveau ou nom manquant — ligne ignorée.")
            continue
        if document.id not in niveaux:
            niveaux[document.id] = {_cle(n.nom_niveau): n for n in TypeNiveau.objects.filter(cadre_strategique=document)}
        niveau = niveaux[document.id].get(_cle(nom_niveau))
        if niveau is None:
            dernier = TypeNiveau.objects.filter(cadre_strategique=document).order_by("-ordre").first()
            niveau = TypeNiveau.objects.create(
                cadre_strategique=document, nom_niveau=nom_niveau, ordre=(dernier.ordre + 1) if dernier else 1, niveau_parent=dernier,
            )
            niveaux[document.id][_cle(nom_niveau)] = niveau
        parent = None
        if v.get("Code parent"):
            parent = ElementStrategique.objects.filter(type_niveau__cadre_strategique=document, code__iexact=v["Code parent"]).first()
            if parent is None:
                erreur(FEUILLE_ELEMENTS, numero, f"Code parent « {v['Code parent']} » introuvable dans « {document} » — ligne ignorée.")
                continue
        existant = None
        if code:
            existant = ElementStrategique.objects.filter(type_niveau__cadre_strategique=document, code__iexact=code).first()
        if existant is None:
            existant = ElementStrategique.objects.filter(type_niveau=niveau, nom__iexact=nom, element_parent=parent).first()
        element = existant or ElementStrategique(type_niveau=niveau)
        element.type_niveau, element.element_parent, element.nom = niveau, parent, nom
        if code:
            element.code = code
        if parent is not None and niveau.niveau_parent_id != parent.type_niveau_id and not niveau.saut_niveau_autorise:
            # Niveaux libres : le saut de niveau est accepté dans ce fichier.
            niveau.saut_niveau_autorise = True
            niveau.save(update_fields=["saut_niveau_autorise"])
        try:
            element.clean()
        except Exception as exc:  # message de validation du modèle
            erreur(FEUILLE_ELEMENTS, numero, " ".join(getattr(exc, "messages", [str(exc)])))
            continue
        element.save()
        rapport["elements_mis_a_jour" if existant else "elements_crees"] += 1
        if v.get(COLONNE_CONTRIBUTION):
            contributions.append((numero, element, document, v[COLONNE_CONTRIBUTION]))

    rattacher_documents(seulement_sans_element=False)

    for numero, element, document, texte in contributions:
        cible, message = resoudre_contribution(document, texte)
        if cible is None:
            erreur(FEUILLE_ELEMENTS, numero, f"{element} : {message}")
            continue
        erreurs, avertissements = controler_contribution(element, cible)
        if erreurs:
            for m in erreurs:
                erreur(FEUILLE_ELEMENTS, numero, f"{element} : {m}")
            continue
        for m in avertissements:
            avertir(FEUILLE_ELEMENTS, numero, f"{element} : {m}")
        element.contribue_a = cible
        element.save(update_fields=["contribue_a", "updated_at"])
    return rapport
