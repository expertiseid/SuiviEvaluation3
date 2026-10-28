from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    """Ajoute created_at/updated_at à tout modèle qui en hérite."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EtatApprobation(models.TextChoices):
    APPROUVEE = "APPROUVEE", "Approuvée"
    EN_ATTENTE = "EN_ATTENTE", "En attente d'approbation"
    REJETEE = "REJETEE", "Rejetée"


class SaisiesApprouveesManager(models.Manager):
    """Gestionnaire par défaut : seules les saisies approuvées comptent (taux, cumuls, exports…)."""

    def get_queryset(self):
        return super().get_queryset().filter(etat_approbation=EtatApprobation.APPROUVEE)


class SaisieApprouvable(models.Model):
    """
    Saisie de réalisation soumise, si le projet l'exige, à approbation (voir
    apps.projects.approbation). `objects` ne renvoie que les saisies approuvées, pour que
    rien d'autre ne compte dans les calculs ; `tous` renvoie aussi celles en attente ou
    rejetées (écran d'approbation, modification, suppression).
    """

    etat_approbation = models.CharField(
        max_length=20, choices=EtatApprobation.choices, default=EtatApprobation.APPROUVEE, db_index=True
    )
    approbation_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approbation_le = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True)

    objects = SaisiesApprouveesManager()
    tous = models.Manager()

    class Meta:
        abstract = True

