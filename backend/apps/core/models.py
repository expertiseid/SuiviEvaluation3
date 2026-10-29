from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


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



# Langues de l'interface (le français est la langue source des textes).
LANGUES = (("fr", "Français"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("de", "Deutsch"))
CODES_LANGUES = tuple(code for code, _ in LANGUES)


class TraductionCorrigee(TimestampedModel):
    """
    Traduction d'un texte de l'interface corrigée par l'Administrateur : elle remplace celle
    fournie avec l'application (`source` : le texte français tel qu'il est dans le code).
    """

    langue = models.CharField(max_length=5, choices=LANGUES)
    source = models.TextField()
    traduction = models.TextField()
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("langue", "source"), name="traduction_langue_source_unique")]

    def __str__(self):
        return f"[{self.langue}] {self.source[:40]}"
