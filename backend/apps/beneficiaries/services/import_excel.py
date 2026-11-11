"""
Import en masse des bénéficiaires depuis un fichier Excel — évite la saisie
un par un pour de gros effectifs. Best-effort : une ligne en erreur est
ignorée sans bloquer l'import des autres, et tout est rapporté au client.
"""
import datetime
import io

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from apps.core.excel_utils import figer_entete, quadriller
from apps.core.langues import vers_francais
from apps.core.vocabulaire import adapter_classeur, ramener_classeur, v

# Localisation d'abord, puis identité (ordre de collecte sur le terrain). Les colonnes de
# localisation portent le nom des niveaux administratifs du pays (Région, Province, Commune pour
# le Burkina Faso) : voir colonnes(). L'import lit les colonnes par leur nom, et celles de
# localisation dans l'ordre (entre « Pays » et « Nom ») : un fichier à l'ancien ordre reste accepté.
COLONNE_PAYS = "Pays (code ISO, ex : BF)"
LOCALISATION_PAR_DEFAUT = ["Région", "Province", "Commune / Village"]
COLONNES_IDENTITE = [
    "Nom",
    "Prénom",
    "Sexe (F/M)",
    "Date de naissance (AAAA-MM-JJ)",
    "Téléphone",
    "N° pièce d'identité",
    "Type de pièce",
    "Statuts particuliers (séparés par ;)",
    "Types d'activité menée (séparés par ;)",
    "Latitude",
    "Longitude",
    "Consentement (Oui/Non)",
    "Date du consentement (AAAA-MM-JJ)",
]
# Colonnes par défaut (Burkina Faso) : libellés fixes connus du vocabulaire et de l'import combiné.
COLONNES = [COLONNE_PAYS, *LOCALISATION_PAR_DEFAUT, *COLONNES_IDENTITE, "Code projet"]


def niveaux_du_pays(pays: str) -> list[str]:
    """Noms des niveaux administratifs configurés pour le pays, du plus haut au plus bas."""
    from apps.geo.models import NiveauAdministratif

    noms = list(NiveauAdministratif.objects.filter(pays=pays).order_by("ordre").values_list("nom_niveau", flat=True))
    return noms or LOCALISATION_PAR_DEFAUT


def colonnes(pays: str = "BF") -> list[str]:
    """Colonnes du modèle d'import pour un pays : sa localisation (ses niveaux), puis l'identité."""
    return [COLONNE_PAYS, *niveaux_du_pays(pays), *COLONNES_IDENTITE, "Code projet"]


def _exemple(pays, niveaux):
    """Ligne d'exemple : une localité réelle du pays si possible."""
    from apps.geo.models import Zone

    zone = Zone.objects.filter(niveau_administratif__pays=pays).order_by("-niveau_administratif__ordre", "nom").first()
    chemin = []
    while zone is not None:
        chemin.insert(0, zone.nom)
        zone = zone.parent
    chemin = (chemin + [""] * len(niveaux))[: len(niveaux)]
    return [pays, *chemin, "Traoré", "Awa", "F", "1990-05-12", "70000001", "CNIB123456", "CNIB", "Femme;Jeune",
            "Maraîchage", "", "", "Oui", "2026-01-15", ""]


def generer_modele_import(pays: str = "BF", projet=None) -> bytes:
    """`projet` : le modèle propose les variables personnalisées de ce projet (sinon toutes)."""
    from .variables import variables_concernant

    from ..models import VariableBeneficiaire

    niveaux = niveaux_du_pays(pays)
    variables = variables_concernant([projet.id]) if projet else list(VariableBeneficiaire.objects.all())
    entetes = colonnes(pays) + [variable.libelle for variable in variables]
    wb = Workbook()
    feuille = wb.active
    feuille.title = "Bénéficiaires"
    feuille.append(entetes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    feuille.append(_exemple(pays, niveaux))
    for _ in range(20):
        feuille.append([""] * len(entetes))
    quadriller(feuille, max_col=len(entetes))
    figer_entete(feuille)

    instructions = wb.create_sheet("Instructions")
    instructions.append(["Consignes"])
    instructions.append(["- Ne pas modifier l'ordre ou le nom des colonnes de la feuille 'Bénéficiaires'."])
    instructions.append(["- Nom, Prénom et Sexe sont obligatoires ; les autres colonnes sont facultatives."])
    instructions.append(["- Sexe : F ou M."])
    instructions.append(["- Pays : code ISO 3166-1 alpha-2 (ex : BF). Par défaut BF si laissé vide."])
    instructions.append([
        f"- Localisation : une colonne par niveau administratif du pays ({' › '.join(niveaux)}), du plus haut au "
        "plus bas, à remplir avec les noms connus de la plateforme (menu « Zones administratives »)."
    ])
    instructions.append([f"- {niveaux[-1]} : créé(e) automatiquement s'il (elle) n'existe pas encore."])
    instructions.append(["- Latitude / Longitude (facultatif) : position GPS en degrés décimaux (ex : 12.3714 / -1.5197)."])
    instructions.append(["- Consentement (facultatif) : Oui si la personne a donné son accord pour l'enregistrement de ses données, Non sinon ; vide si non renseigné. Date du consentement : AAAA-MM-JJ."])
    instructions.append(["- Plusieurs statuts particuliers : séparer par un point-virgule (ex : Femme;Jeune)."])
    instructions.append([
        "- Types d'activité menée (ex : Maraîchage, Élevage) : séparer par un point-virgule — un type inconnu "
        "est ignoré (avertissement), il doit d'abord être créé (fiche bénéficiaire ou admin)."
    ])
    instructions.append(["- Les doublons potentiels seront signalés automatiquement après l'import."])
    for variable in variables:
        detail = {
            "NOMBRE": f"nombre{f' ({variable.unite})' if variable.unite else ''}",
            "DATE": "date (AAAA-MM-JJ)",
            "OUI_NON": "Oui ou Non",
            "CHOIX": f"une valeur parmi : {', '.join(variable.choix)}",
            "CHOIX_MULTIPLE": f"une ou plusieurs valeurs (séparées par ;) parmi : {', '.join(variable.choix)}",
        }.get(variable.type, "texte")
        instructions.append([f"- {variable.libelle} : {detail}. « NA » si sans objet."])
    instructions.append([
        "- Code projet (facultatif) : code exact d'un projet déjà créé sur la plateforme — le bénéficiaire "
        "est alors automatiquement inscrit à ce projet (participation datée du jour de l'import). Laisser "
        "vide si le bénéficiaire ne doit être rattaché à aucun projet pour l'instant."
    ])

    buffer = io.BytesIO()
    adapter_classeur(wb)
    wb.save(buffer)
    return buffer.getvalue()


def _normaliser_sexe(valeur) -> str | None:
    if not valeur:
        return None
    # Saisie dans une autre langue (« Female », « Weiblich »…) : ramenée au français.
    v = vers_francais(str(valeur).strip()).lower()
    if v in ("f", "féminin", "feminin", "femme"):
        return "F"
    if v in ("m", "masculin", "homme"):
        return "M"
    return None


def _oui_non(valeur):
    """True / False ; None si vide ; « ? » si la valeur n'est ni oui ni non (dans l'une des langues)."""
    from apps.core.langues import vers_francais

    from .variables import NON, OUI

    if valeur is None or str(valeur).strip() == "":
        return None
    if isinstance(valeur, bool):
        return valeur
    texte = vers_francais(str(valeur).strip()).lower()
    return True if texte in OUI else False if texte in NON else "?"


def _normaliser_date(valeur):
    if not valeur:
        return None
    if isinstance(valeur, (datetime.date, datetime.datetime)):
        return valeur.date() if isinstance(valeur, datetime.datetime) else valeur
    try:
        return datetime.datetime.strptime(str(valeur).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _resoudre_zone(pays, noms):
    """
    Zone à partir des noms de localisation, du niveau le plus haut au plus bas (un par niveau
    administratif configuré pour le pays ; une case vide est sautée). Le dernier niveau est créé
    s'il n'existe pas encore. Renvoie (zone, message d'avertissement ou "").
    """
    from apps.geo.models import NiveauAdministratif, Zone

    niveaux = list(NiveauAdministratif.objects.filter(pays=pays).order_by("ordre"))
    zone = None
    for niveau, nom in zip(niveaux, noms):
        nom = str(nom or "").strip()
        if not nom:
            continue
        qs = Zone.objects.filter(niveau_administratif=niveau, nom__iexact=nom)
        if zone is not None:
            qs = qs.filter(parent=zone)
        trouvee = qs.first()
        if trouvee is None:
            if niveau == niveaux[-1]:
                trouvee = Zone.objects.create(nom=nom, niveau_administratif=niveau, parent=zone)
            else:
                return zone, f"{niveau.nom_niveau} « {nom} » non trouvé(e) — localisation arrêtée au niveau au-dessus."
        zone = trouvee
    return zone, ""


def _colonnes_localisation(entetes):
    """Colonnes de localisation : celles entre « Pays » et « Nom » (ou, ancien format, Région/Province/Commune)."""
    if COLONNE_PAYS in entetes and "Nom" in entetes and entetes.index(COLONNE_PAYS) < entetes.index("Nom"):
        return entetes[entetes.index(COLONNE_PAYS) + 1 : entetes.index("Nom")]
    return [c for c in LOCALISATION_PAR_DEFAUT if c in entetes]


def _decimal(valeur):
    from decimal import Decimal, InvalidOperation

    if valeur in (None, ""):
        return None
    try:
        return Decimal(str(valeur).replace(",", ".").strip()).quantize(Decimal("0.000001"))
    except InvalidOperation:
        return None


def _resoudre_statuts(valeur):
    from ..models import StatutParticulier

    if not valeur:
        return [], []

    noms = [n.strip() for n in str(valeur).split(";") if n.strip()]
    trouves = []
    inconnus = []
    for nom in noms:
        # Saisi dans une autre langue (« Woman ») : nom français du catalogue en second essai.
        statut = (
            StatutParticulier.objects.filter(libelle__iexact=nom).first()
            or StatutParticulier.objects.filter(code__iexact=nom).first()
            or StatutParticulier.objects.filter(libelle__iexact=vers_francais(nom)).first()
        )
        if statut:
            trouves.append(statut)
        else:
            inconnus.append(nom)
    return trouves, inconnus


def _resoudre_types_activite(valeur):
    from ..models import TypeActiviteBeneficiaire

    if not valeur:
        return [], []

    noms = [n.strip() for n in str(valeur).split(";") if n.strip()]
    trouves = []
    inconnus = []
    for nom in noms:
        type_activite = (
            TypeActiviteBeneficiaire.objects.filter(libelle__iexact=nom).first()
            or TypeActiviteBeneficiaire.objects.filter(code__iexact=nom).first()
            or TypeActiviteBeneficiaire.objects.filter(libelle__iexact=vers_francais(nom)).first()
        )
        if type_activite:
            trouves.append(type_activite)
        else:
            inconnus.append(nom)
    return trouves, inconnus


def _resoudre_projet(code):
    from apps.projects.models import Projet

    if not code:
        return None
    return Projet.objects.filter(code__iexact=str(code).strip()).first()


def importer_beneficiaires(fichier, utilisateur, projet=None) -> dict:
    wb = ramener_classeur(load_workbook(fichier, data_only=True))
    feuille = wb["Bénéficiaires"] if "Bénéficiaires" in wb.sheetnames else wb.worksheets[0]
    return importer_beneficiaires_depuis_feuille(feuille, utilisateur, projet=projet)


def importer_beneficiaires_depuis_feuille(feuille, utilisateur, projet=None) -> dict:
    """
    `projet` : si fourni (import combiné), chaque bénéficiaire créé est
    aussi inscrit à ce projet (ParticipationProjet, date du jour).
    """
    from ..models import Beneficiaire, VariableBeneficiaire
    from .duplicate_detection import enregistrer_signalements
    from .variables import normaliser

    lignes = list(feuille.iter_rows(min_row=1, values_only=True))
    if not lignes:
        return {"crees": 0, "erreurs": [], "avertissements": [], "doublons_detectes": 0}

    entetes = [str(c).strip() if c else "" for c in lignes[0]]

    def valeur(ligne, nom_colonne):
        if nom_colonne not in entetes:
            return None
        return ligne[entetes.index(nom_colonne)]

    colonnes_localisation = _colonnes_localisation(entetes)
    # Variables personnalisées présentes dans le fichier (colonnes à leur libellé).
    variables = [variable for variable in VariableBeneficiaire.objects.all() if variable.libelle in entetes]

    crees = 0
    erreurs = []
    avertissements = []
    doublons_detectes = 0

    for numero, ligne in enumerate(lignes[1:], start=2):
        if not any(ligne):
            continue

        nom = valeur(ligne, "Nom")
        prenom = valeur(ligne, "Prénom")
        sexe = _normaliser_sexe(valeur(ligne, "Sexe (F/M)"))

        if not nom or not prenom:
            erreurs.append({"ligne": numero, "message": "Nom et prénom obligatoires — ligne ignorée."})
            continue
        if not sexe:
            erreurs.append({"ligne": numero, "message": "Sexe invalide (attendu F ou M) — ligne ignorée."})
            continue

        pays = str(valeur(ligne, COLONNE_PAYS) or "BF").strip().upper() or "BF"
        zone, probleme = _resoudre_zone(pays, [valeur(ligne, c) for c in colonnes_localisation])
        if probleme:
            avertissements.append({"ligne": numero, "message": probleme})
        latitude, longitude = _decimal(valeur(ligne, "Latitude")), _decimal(valeur(ligne, "Longitude"))
        if (latitude is not None and not -90 <= latitude <= 90) or (longitude is not None and not -180 <= longitude <= 180):
            avertissements.append({"ligne": numero, "message": "Position GPS invalide — ignorée."})
            latitude = longitude = None

        consentement = _oui_non(valeur(ligne, "Consentement (Oui/Non)"))
        if consentement == "?":
            avertissements.append({"ligne": numero, "message": "Consentement : Oui ou Non attendu — ignoré."})
            consentement = None

        statuts, inconnus = _resoudre_statuts(valeur(ligne, "Statuts particuliers (séparés par ;)"))
        for nom_inconnu in inconnus:
            avertissements.append({"ligne": numero, "message": f"Statut particulier inconnu ignoré : « {nom_inconnu} »."})

        types_activite, types_inconnus = _resoudre_types_activite(valeur(ligne, "Types d'activité menée (séparés par ;)"))
        for nom_inconnu in types_inconnus:
            avertissements.append({"ligne": numero, "message": f"Type d'activité inconnu ignoré : « {nom_inconnu} »."})

        beneficiaire = Beneficiaire.objects.create(
            nom=str(nom).strip(),
            prenom=str(prenom).strip(),
            sexe=sexe,
            date_naissance=_normaliser_date(valeur(ligne, "Date de naissance (AAAA-MM-JJ)")),
            telephone=str(valeur(ligne, "Téléphone") or "").strip(),
            numero_piece_identite=str(valeur(ligne, "N° pièce d'identité") or "").strip(),
            type_piece=str(valeur(ligne, "Type de pièce") or "").strip(),
            pays=pays,
            zone=zone,
            latitude=latitude,
            longitude=longitude,
            consentement=consentement,
            date_consentement=_normaliser_date(valeur(ligne, "Date du consentement (AAAA-MM-JJ)")) if consentement is not None else None,
        )
        reponses = {}
        for variable in variables:
            brute = valeur(ligne, variable.libelle)
            try:
                propre = normaliser(variable, brute)
            except ValueError as exc:
                avertissements.append({"ligne": numero, "message": f"{exc} Réponse ignorée."})
                continue
            if propre is not None:
                reponses[str(variable.id)] = propre
        if reponses:
            Beneficiaire.objects.filter(pk=beneficiaire.pk).update(reponses=reponses)
        if statuts:
            beneficiaire.statuts_particuliers.set(statuts)
        if types_activite:
            beneficiaire.types_activite.set(types_activite)

        code_projet = valeur(ligne, "Code projet")
        projet_ligne = _resoudre_projet(code_projet) if code_projet else None
        if code_projet and projet_ligne is None:
            avertissements.append({"ligne": numero, "message": f"{v('Code projet inconnu ignoré : « ')}{code_projet} »."})

        projet_a_rattacher = projet_ligne or projet
        if projet_a_rattacher is not None:
            from ..models import ParticipationProjet

            ParticipationProjet.objects.create(
                beneficiaire=beneficiaire, projet=projet_a_rattacher, date_inscription=datetime.date.today()
            )

        doublons_detectes += sum(1 for _, cree in enregistrer_signalements(beneficiaire) if cree)

        crees += 1

    return {
        "crees": crees,
        "erreurs": erreurs,
        "avertissements": avertissements,
        "doublons_detectes": doublons_detectes,
    }
