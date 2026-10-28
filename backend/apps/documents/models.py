from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


def chemin_upload(instance, filename):
    return f"pieces_justificatives/{filename}"


class PieceJustificative(TimestampedModel):
    fichier = models.FileField(upload_to=chemin_upload)
    nom = models.CharField(max_length=200)
    type_document = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents_uploades")
    # Justifie une valeur d'indicateur OU une appréciation d'un élément stratégique.
    valeur_indicateur = models.ForeignKey(
        "indicators.ValeurIndicateur", null=True, blank=True, on_delete=models.CASCADE, related_name="pieces_justificatives"
    )
    appreciation_strategique = models.ForeignKey(
        "strategy.AppreciationStrategique", null=True, blank=True, on_delete=models.CASCADE, related_name="pieces_justificatives"
    )

    class Meta:
        verbose_name = "Pièce justificative"
        verbose_name_plural = "Pièces justificatives"
        constraints = [
            models.CheckConstraint(
                check=models.Q(valeur_indicateur__isnull=False) | models.Q(appreciation_strategique__isnull=False),
                name="piece_rattachee",
            )
        ]

    def __str__(self):
        return self.nom


class Dossier(TimestampedModel):
    """Dossier de la bibliothèque documentaire (GED), organisable en arborescence."""

    nom = models.CharField(max_length=200)
    projet = models.ForeignKey(
        "projects.Projet", null=True, blank=True, on_delete=models.CASCADE, related_name="dossiers"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="sous_dossiers"
    )
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossiers_crees")

    class Meta:
        ordering = ("nom",)

    def __str__(self):
        return self.nom


def chemin_upload_document(instance, filename):
    return f"ged/document_{instance.document_id}/v{instance.version}_{filename}"


class Document(TimestampedModel):
    """Métadonnées d'un document de la GED — le contenu réel est dans ses DocumentVersion."""

    nom = models.CharField(max_length=200)
    dossier = models.ForeignKey(
        Dossier, null=True, blank=True, on_delete=models.CASCADE, related_name="documents"
    )
    projet = models.ForeignKey(
        "projects.Projet", null=True, blank=True, on_delete=models.CASCADE, related_name="documents_ged"
    )
    activite = models.ForeignKey(
        "projects.Activite", null=True, blank=True, on_delete=models.CASCADE, related_name="documents_ged"
    )
    sous_activite = models.ForeignKey(
        "projects.SousActivite", null=True, blank=True, on_delete=models.CASCADE, related_name="documents_ged"
    )
    type_document = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents_ged_crees")

    class Meta:
        ordering = ("nom",)

    def __str__(self):
        return self.nom

    @property
    def derniere_version(self):
        return self.versions.order_by("-version").first()


class DocumentVersion(TimestampedModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    fichier = models.FileField(upload_to=chemin_upload_document)
    version = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="versions_uploadees")
    commentaire = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=("document", "version"), name="document_version_unique"),
        ]

    def __str__(self):
        return f"{self.document.nom} — v{self.version}"
