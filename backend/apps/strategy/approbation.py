"""
Approbation des modifications d'une stratégie (CadreStrategique.approbation_modifications) : pour qui peut
modifier sans pouvoir approuver, une modification du document, ou l'ajout, la modification ou la suppression
d'un élément (pilier, axe…) ou d'une appréciation devient une demande (DemandeModification), appliquée une
fois approuvée — comme la planification des projets (apps.projects.approbation).

Peut approuver : l'Administrateur, la personne qui a le droit d'approuver l'élément concerné (ou celui sous
lequel on ajoute), sinon le document, par un droit précis ou par son rôle (apps.projects.droits).
"""
from rest_framework.response import Response

from apps.projects.approbation import creer_demande, doit_faire_approuver, peut_approuver_auteur
from apps.projects.droits import droits_document, droits_element
from apps.projects.models import DemandeModification

from .models import AppreciationStrategique, CadreStrategique, ElementStrategique


def peut_approuver_strategie(utilisateur, document_id, element_id=None) -> bool:
    if element_id:
        return droits_element(utilisateur, element_id).approuver
    return droits_document(utilisateur, document_id).approuver


def exige_demande(document, utilisateur, element_id=None) -> bool:
    if document and doit_faire_approuver(utilisateur):  # tout ce qu'il saisit doit être approuvé
        return True
    return bool(document and document.approbation_modifications
                and not peut_approuver_strategie(utilisateur, document.id, element_id))


def peut_traiter(utilisateur, demande) -> bool:
    return peut_approuver_auteur(utilisateur, demande.demandeur,
                                 peut_approuver_strategie(utilisateur, demande.document_id, demande.element_id))


class DemandeStrategieMixin:
    """
    Vues des documents, éléments et appréciations : si la stratégie exige une approbation et que l'utilisateur
    ne peut pas approuver, la création, la modification ou la suppression devient une demande (réponse 202).
    Les données sont validées tout de suite, pour ne pas laisser passer une demande impossible à appliquer.
    """

    cible_demande = None
    creation_par_demande = True

    def _contexte(self, instance=None, validated=None):
        """(document, élément concerné) de l'objet ou des données validées."""
        if isinstance(instance, CadreStrategique):
            return instance, None
        if isinstance(instance, ElementStrategique):
            return instance.type_niveau.cadre_strategique, instance.id
        if isinstance(instance, AppreciationStrategique):
            return instance.element.type_niveau.cadre_strategique, instance.element_id
        validated = validated or {}
        if "element" in validated:  # appréciation
            element = validated["element"]
            return element.type_niveau.cadre_strategique, element.id
        if "type_niveau" in validated:  # nouvel élément : sous son parent, ou dans le document
            parent = validated.get("element_parent")
            return validated["type_niveau"].cadre_strategique, parent.id if parent else None
        return None, None

    def _demande(self, document, element_id, action, instance=None, donnees=None):
        demande = creer_demande(
            projet=None, document=document, element_id=element_id, cible=self.cible_demande, action=action,
            utilisateur=self.request.user, instance=instance, donnees=donnees,
            libelle=getattr(instance, "nom", "") or (donnees or {}).get("nom", "") or str(instance or ""),
        )
        return Response({
            "demande_approbation": demande.id,
            "message": f"{demande.get_action_display()} envoyée pour approbation : elle sera appliquée une fois approuvée.",
        }, status=202)

    def create(self, request, *args, **kwargs):
        if not self.creation_par_demande:
            return super().create(request, *args, **kwargs)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document, element_id = self._contexte(validated=serializer.validated_data)
        if exige_demande(document, request.user, element_id):
            return self._demande(document, element_id, DemandeModification.Action.CREATION, donnees=_donnees(request))
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        document, element_id = self._contexte(instance)
        if exige_demande(document, request.user, element_id):
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
            serializer.is_valid(raise_exception=True)
            return self._demande(document, element_id, DemandeModification.Action.MODIFICATION, instance, _donnees(request))
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        document, element_id = self._contexte(instance)
        if exige_demande(document, request.user, element_id):
            return self._demande(document, element_id, DemandeModification.Action.SUPPRESSION, instance)
        return super().destroy(request, *args, **kwargs)


def _donnees(request):
    """Données de la requête en dictionnaire simple (JSON), pour les rejouer à l'approbation."""
    donnees = request.data
    if hasattr(donnees, "lists"):  # formulaire : listes gardées pour les champs multiples
        return {cle: (valeurs if len(valeurs) > 1 else valeurs[0]) for cle, valeurs in donnees.lists()}
    return dict(donnees)


def appliquer(demande):
    """Applique une demande approuvée sur la stratégie (avec les contrôles habituels du sérialiseur)."""
    from rest_framework.exceptions import PermissionDenied

    from .serializers import AppreciationStrategiqueSerializer, CadreStrategiqueSerializer, ElementStrategiqueSerializer
    from .services import supprimer_cadre_strategique_cascade

    classes = {
        DemandeModification.Cible.DOCUMENT: (CadreStrategiqueSerializer, CadreStrategique),
        DemandeModification.Cible.ELEMENT: (ElementStrategiqueSerializer, ElementStrategique),
        DemandeModification.Cible.APPRECIATION: (AppreciationStrategiqueSerializer, AppreciationStrategique),
    }
    classe_serialiseur, modele = classes[demande.cible]
    instance = modele.objects.filter(pk=demande.cible_id).first() if demande.cible_id else None
    if demande.action != DemandeModification.Action.CREATION and instance is None:
        raise PermissionDenied("L'élément concerné n'existe plus.")
    if demande.action == DemandeModification.Action.SUPPRESSION:
        if modele is CadreStrategique:
            supprimer_cadre_strategique_cascade(instance)
        else:
            instance.delete()
        return
    serialiseur = classe_serialiseur(instance, data=demande.donnees, partial=instance is not None)
    serialiseur.is_valid(raise_exception=True)
    creation = demande.action == DemandeModification.Action.CREATION
    objet = serialiseur.save(**({"saisi_par": demande.demandeur} if creation and modele is AppreciationStrategique else {}))
    if creation:
        demande.cible_id = objet.pk
