"""
Variables personnalisées des bénéficiaires (VariableBeneficiaire) : contrôle des réponses,
affichage, et « NA » pour une variable qui ne concerne pas le projet (exports, import).
"""
import datetime
from decimal import Decimal, InvalidOperation

from apps.core.langues import vers_francais

NA = "NA"
OUI = ("oui", "o", "yes", "y", "1", "true", "vrai")
NON = ("non", "n", "no", "0", "false", "faux")


def variables_concernant(projet_ids):
    """Variables qui concernent au moins un de ces projets (ou tous les projets)."""
    from django.db.models import Q

    from ..models import VariableBeneficiaire

    filtre = Q(tous_les_projets=True)
    if projet_ids:
        filtre |= Q(projets__id__in=list(projet_ids))
    return list(VariableBeneficiaire.objects.filter(filtre).distinct().prefetch_related("projets"))


def normaliser(variable, valeur):
    """
    Réponse contrôlée et mise au format de stockage, ou None si vide / « NA ».
    Lève ValueError avec un message lisible si la réponse ne convient pas.
    """
    if valeur is None or (isinstance(valeur, str) and valeur.strip() in ("", NA)) or valeur == []:
        return None
    T = variable.Type
    if variable.type == T.NOMBRE:
        try:
            nombre = Decimal(str(valeur).replace(",", ".").replace(" ", ""))
        except InvalidOperation:
            raise ValueError(f"« {variable.libelle} » : un nombre est attendu.")
        return float(nombre)
    if variable.type == T.DATE:
        if isinstance(valeur, datetime.datetime):
            return valeur.date().isoformat()
        if isinstance(valeur, datetime.date):
            return valeur.isoformat()
        for format_date in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(str(valeur).strip(), format_date).date().isoformat()
            except ValueError:
                continue
        raise ValueError(f"« {variable.libelle} » : date attendue (AAAA-MM-JJ ou JJ/MM/AAAA).")
    if variable.type == T.OUI_NON:
        if isinstance(valeur, bool):
            return valeur
        texte = vers_francais(str(valeur).strip()).lower()
        if texte in OUI:
            return True
        if texte in NON:
            return False
        raise ValueError(f"« {variable.libelle} » : oui ou non attendu.")
    if variable.type in (T.CHOIX, T.CHOIX_MULTIPLE):
        proposes = {c.lower(): c for c in variable.choix}
        elements = valeur if isinstance(valeur, list) else str(valeur).split(";")
        retenus = []
        for element in elements:
            texte = str(element).strip()
            if not texte:
                continue
            if texte.lower() not in proposes:
                raise ValueError(f"« {variable.libelle} » : « {texte} » ne fait pas partie des choix ({', '.join(variable.choix)}).")
            retenus.append(proposes[texte.lower()])
        if not retenus:
            return None
        if variable.type == T.CHOIX:
            if len(retenus) > 1:
                raise ValueError(f"« {variable.libelle} » : un seul choix possible.")
            return retenus[0]
        return retenus
    return str(valeur).strip()


def normaliser_reponses(reponses: dict) -> dict:
    """Toutes les réponses d'un bénéficiaire ({id: valeur}) ; ValueError si l'une ne convient pas."""
    from ..models import VariableBeneficiaire

    variables = {str(v.id): v for v in VariableBeneficiaire.objects.filter(id__in=[k for k in reponses if str(k).isdigit()])}
    propres = {}
    for cle, valeur in (reponses or {}).items():
        variable = variables.get(str(cle))
        if variable is None:
            continue  # variable supprimée entre-temps : réponse ignorée
        valeur = normaliser(variable, valeur)
        if valeur is not None:
            propres[str(variable.id)] = valeur
    return propres


def affichage(variable, valeur) -> str:
    if valeur is None or valeur == "":
        return ""
    if variable.type == variable.Type.OUI_NON:
        return "Oui" if valeur else "Non"
    if variable.type == variable.Type.CHOIX_MULTIPLE and isinstance(valeur, list):
        return "; ".join(valeur)
    if variable.type == variable.Type.NOMBRE:
        texte = f"{valeur:g}" if isinstance(valeur, (int, float)) else str(valeur)
        return f"{texte} {variable.unite}".strip() if variable.unite else texte
    if variable.type == variable.Type.DATE:
        try:
            return datetime.date.fromisoformat(valeur).strftime("%d/%m/%Y")
        except ValueError:
            return str(valeur)
    return str(valeur)


def cellule(variable, beneficiaire, projet_ids):
    """Valeur d'export : « NA » si la variable ne concerne aucun de ces projets."""
    if not variable.concerne(projet_ids):
        return NA
    valeur = (beneficiaire.reponses or {}).get(str(variable.id))
    if valeur is None:
        return ""
    if variable.type == variable.Type.NOMBRE:
        return valeur  # nombre dans Excel
    if variable.type == variable.Type.DATE:
        return datetime.date.fromisoformat(valeur)
    if variable.type == variable.Type.OUI_NON:
        return "Oui" if valeur else "Non"
    if variable.type == variable.Type.CHOIX_MULTIPLE:
        return "; ".join(valeur)
    return valeur
