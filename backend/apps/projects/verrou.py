"""
Projet clôturé = lecture seule.

Tant qu'un projet est « Clôturé », rien de ce qui lui appartient ne peut être créé, modifié ni
supprimé : planification (tous niveaux, sous-activités, jalons, livrables, taux manuels),
suivi (points de suivi, périodes et objectifs de période), indicateurs et leurs valeurs,
bénéficiaires du projet, financements, documents et dossiers. Le projet lui-même ne peut plus
être modifié, sauf pour le rouvrir (changer son statut), ce qui est réservé à l'administrateur
(voir ProjetViewSet).

Le contrôle est fait au moment de l'enregistrement (signaux pre_save / pre_delete) pour couvrir
toutes les voies : écrans, imports Excel, canevas de suivi. La suppression complète d'un projet
(supprimer_projet_cascade) passe outre via verrou_desactive().
"""
import contextvars
from contextlib import contextmanager

from django.db.models.signals import pre_delete, pre_save
from rest_framework.exceptions import PermissionDenied

_desactive = contextvars.ContextVar("verrou_projet_desactive", default=False)


@contextmanager
def verrou_desactive():
    jeton = _desactive.set(True)
    try:
        yield
    finally:
        _desactive.reset(jeton)


class ProjetClotureError(PermissionDenied):
    def __init__(self, projet):
        super().__init__(
            f"Le projet « {projet.code} » est clôturé : il est en lecture seule. "
            "Un administrateur peut le rouvrir en changeant son statut."
        )


def _projet_id(instance):
    """Projet auquel appartient l'objet, par le premier lien renseigné (None si aucun)."""
    from apps.indicators.models import Indicateur
    from apps.suivi.models import PeriodePlanification

    from .models import Activite, SousActivite

    if getattr(instance, "projet_id", None):
        return instance.projet_id
    liens = (
        ("periode_id", PeriodePlanification, "projet_id"),
        ("activite_id", Activite, "projet_id"),
        ("sous_activite_id", SousActivite, "activite__projet_id"),
    )
    for attribut, modele, chemin in liens:
        cle = getattr(instance, attribut, None)
        if cle:
            return modele.objects.filter(id=cle).values_list(chemin, flat=True).first()
    if getattr(instance, "indicateur_id", None):
        indicateur = Indicateur.objects.filter(id=instance.indicateur_id).first()
        return _projet_id(indicateur) if indicateur else None
    return None


def _verifier(instance):
    from .models import Projet

    if _desactive.get():
        return
    projet_id = _projet_id(instance)
    if projet_id is None:
        return
    projet = Projet.objects.filter(id=projet_id, statut=Projet.Statut.CLOTURE).first()
    if projet is not None:
        raise ProjetClotureError(projet)


def _avant_enregistrement(sender, instance, **kwargs):
    _verifier(instance)


def _avant_enregistrement_projet(sender, instance, **kwargs):
    """Un projet clôturé ne peut être modifié que pour le rouvrir (changement de statut)."""
    if _desactive.get() or instance.pk is None:
        return
    ancien = sender.objects.filter(pk=instance.pk).values_list("statut", flat=True).first()
    if ancien == sender.Statut.CLOTURE and instance.statut == sender.Statut.CLOTURE:
        raise ProjetClotureError(instance)


def connecter():
    from apps.beneficiaries.models import ParticipationProjet
    from apps.documents.models import Document, Dossier
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.partners.models import Financement
    from apps.suivi.models import PeriodePlanification, PointSuivi, TranchePlanifiee

    from .models import Activite, JalonLivrable, NiveauActivite, Projet, SousActivite, TauxManuel

    modeles = (
        Activite, NiveauActivite, SousActivite, JalonLivrable, TauxManuel, PointSuivi, PeriodePlanification,
        TranchePlanifiee, Indicateur, ValeurIndicateur, ParticipationProjet, Financement, Document, Dossier,
    )
    for modele in modeles:
        pre_save.connect(_avant_enregistrement, sender=modele, dispatch_uid=f"verrou_save_{modele.__name__}")
        pre_delete.connect(_avant_enregistrement, sender=modele, dispatch_uid=f"verrou_delete_{modele.__name__}")
    pre_save.connect(_avant_enregistrement_projet, sender=Projet, dispatch_uid="verrou_save_projet")
