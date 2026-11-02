"""
Journal d'audit de la plateforme, en ajout uniquement (modèle EvenementAudit).

Sont journalisés : connexions (réussies et refusées), consultations de dossiers confidentiels, actions
sur les dossiers de plaintes (créations, changements de statut, affectations…), téléchargements de
pièces jointes, exports, modifications de la configuration, des droits des comptes et des habilitations
confidentielles, demandes des personnes sur leurs données. Jamais de contenu protégé (récit, identité,
décision) : seulement ce qui désigne l'élément concerné.
"""
from .models import EvenementAudit

A = EvenementAudit.Action


def nom_compte(utilisateur) -> str:
    if utilisateur is None or not getattr(utilisateur, "pk", None):
        return ""
    nom = f"{utilisateur.first_name} {utilisateur.last_name}".strip()
    return f"{nom} ({utilisateur.username})" if nom else utilisateur.username


def auditer(utilisateur, action, objet="", module="plaintes", **details):
    return EvenementAudit.objects.create(
        utilisateur_id=getattr(utilisateur, "pk", None), utilisateur=nom_compte(utilisateur), action=action,
        module=module, objet=str(objet)[:255], details=details,
    )


def journal_excel(evenements):
    """Export Excel du journal ; seuls l'en-tête et les libellés d'action se traduisent."""
    import io

    from openpyxl import Workbook
    from openpyxl.styles import Font

    from .langues import traduire_classeur

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Journal d'audit"
    feuille.append(["Date", "Personne", "Action", "Module", "Objet", "Détails"])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    for e in evenements:
        details = "; ".join(f"{cle} : {valeur}" for cle, valeur in e.details.items())
        feuille.append([e.date.astimezone().strftime("%d/%m/%Y %H:%M:%S"), e.utilisateur, e.get_action_display(),
                        e.module, e.objet, details])
    for colonne, largeur in zip("ABCDEF", (20, 32, 34, 12, 40, 60)):
        feuille.column_dimensions[colonne].width = largeur
    traduire_classeur(classeur, garder=lambda _feuille, cellule: cellule.row > 1 and cellule.column != 3)
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()
