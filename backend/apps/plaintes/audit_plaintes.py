"""
Journal d'audit du mécanisme (apps.core.audit) : chaque entrée du journal d'un dossier y est reportée,
sans son texte (numéro du dossier et nature de l'action seulement) ; consultations des dossiers
confidentiels, une fois par personne et par dossier toutes les 10 minutes.
"""
from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.audit import A, auditer
from apps.core.models import EvenementAudit

from .models import ActionDossier

PARTICULIERES = {ActionDossier.Type.EXPORT: A.EXPORT, ActionDossier.Type.TELECHARGEMENT: A.TELECHARGEMENT}


@receiver(post_save, sender=ActionDossier)
def _reporter_action(sender, instance, created, **kwargs):
    if created:
        auditer(instance.auteur, PARTICULIERES.get(instance.type, A.DOSSIER), instance.dossier.numero,
                type=instance.type, sensible=instance.dossier.sensible)


def consultation(dossier, utilisateur):
    if not dossier.sensible:
        return
    recente = EvenementAudit.objects.filter(
        action=A.CONSULTATION_SENSIBLE, utilisateur_id=utilisateur.pk, objet=dossier.numero,
        date__gte=timezone.now() - timedelta(minutes=10),
    ).exists()
    if not recente:
        auditer(utilisateur, A.CONSULTATION_SENSIBLE, dossier.numero)


def configuration(utilisateur, element, operation, **details):
    auditer(utilisateur, A.CONFIGURATION, element, operation=operation, **details)
