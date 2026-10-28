import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel


def nouveau_jeton():
    return secrets.token_urlsafe(32)


class LienPartage(TimestampedModel):
    """
    Lien secret donnant accès, sans compte et en lecture seule, à une page : le tableau de bord
    (avec les projets visibles par son créateur et ses filtres) ou le suivi d'un projet (tout, les
    activités seulement, ou les indicateurs seulement). Révocable, avec expiration facultative.
    """

    class Type(models.TextChoices):
        TABLEAU_DE_BORD = "TABLEAU_DE_BORD", "Tableau de bord"
        SUIVI_PROJET = "SUIVI_PROJET", "Suivi d'un projet"

    class Contenu(models.TextChoices):
        TOUT = "TOUT", "Activités et indicateurs"
        ACTIVITES = "ACTIVITES", "Réalisation des activités"
        INDICATEURS = "INDICATEURS", "Suivi des indicateurs"

    jeton = models.CharField(max_length=64, unique=True, default=nouveau_jeton, editable=False)
    type = models.CharField(max_length=20, choices=Type.choices)
    contenu = models.CharField(max_length=12, choices=Contenu.choices, default=Contenu.TOUT)
    projet = models.ForeignKey("projects.Projet", null=True, blank=True, on_delete=models.CASCADE, related_name="liens_partage")
    filtres = models.JSONField(default=dict, blank=True, help_text="Filtres du tableau de bord au moment du partage.")
    libelle = models.CharField(max_length=150, blank=True, help_text="Pour qui ou pourquoi (ex : « Comité de pilotage »).")
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liens_partage")
    expire_le = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    nombre_consultations = models.PositiveIntegerField(default=0)
    derniere_consultation = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.libelle or self.get_type_display()

    @property
    def valide(self) -> bool:
        return self.actif and (self.expire_le is None or self.expire_le >= timezone.localdate())
