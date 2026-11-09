from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class Notification(TimestampedModel):
    class Type(models.TextChoices):
        INDICATEUR_ALERTE = "INDICATEUR_ALERTE", "Indicateur en alerte"
        RAPPORT_SOUMIS = "RAPPORT_SOUMIS", "Rapport soumis pour validation"
        RAPPORT_VALIDE = "RAPPORT_VALIDE", "Rapport validé"
        DOUBLON_SIGNALE = "DOUBLON_SIGNALE", "Doublon bénéficiaire signalé"
        ECHEANCE_ACTIVITE = "ECHEANCE_ACTIVITE", "Échéance d'activité proche"
        ACTIVITE_MODIFIEE = "ACTIVITE_MODIFIEE", "Activité planifiée modifiée"
        PLAINTE = "PLAINTE", "Plaintes et retours"
        STOCKAGE = "STOCKAGE", "Espace de stockage"
        ABONNEMENT = "ABONNEMENT", "Abonnement"

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    lien = models.CharField(max_length=200, blank=True, help_text="Route frontend relative (ex: /rapports)")
    lu = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.titre
