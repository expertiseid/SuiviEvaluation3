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


class NonSupprimes(models.Manager):
    """Gestionnaire par défaut : sans ce qui est à la corbeille (corbeille.py). `tous` : y compris la corbeille."""

    def get_queryset(self):
        return super().get_queryset().filter(supprime_le__isnull=True)


class EnCorbeille(models.Model):
    """Mis à la corbeille le … par … ; `supprime_avec` : parti avec ce dossier (restauré ou vidé avec lui)."""

    supprime_le = models.DateTimeField(null=True, blank=True, db_index=True)
    supprime_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    supprime_avec = models.ForeignKey("documents.Dossier", null=True, blank=True, on_delete=models.CASCADE, related_name="+")

    objects = NonSupprimes()
    tous = models.Manager()

    class Meta:
        abstract = True


class Dossier(EnCorbeille, TimestampedModel):
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


class Document(EnCorbeille, TimestampedModel):
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


def nouveau_jeton_document():
    import secrets

    return secrets.token_urlsafe(32)


class LienDocument(TimestampedModel):
    """
    Lien secret pour montrer un document à une personne qui n'a pas de compte (bailleur, partenaire…) :
    consultation seule ou consultation et téléchargement, date et heure d'expiration obligatoires, mot
    de passe et nombre d'ouvertures facultatifs, révocable à tout moment. Chaque ouverture est comptée.
    Sans version fixée, le lien donne toujours la dernière version du document.
    """

    class Droit(models.TextChoices):
        CONSULTER = "CONSULTER", "Consulter seulement"
        TELECHARGER = "TELECHARGER", "Consulter et télécharger"

    jeton = models.CharField(max_length=64, unique=True, default=nouveau_jeton_document, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="liens")
    version = models.ForeignKey(DocumentVersion, null=True, blank=True, on_delete=models.CASCADE, related_name="liens",
                                help_text="Vide : toujours la dernière version.")
    droit = models.CharField(max_length=12, choices=Droit.choices, default=Droit.CONSULTER)
    libelle = models.CharField(max_length=150, blank=True, help_text="Pour qui ou pourquoi (ex : « Bailleur — rapport annuel »).")
    expire_le = models.DateTimeField()
    mot_de_passe = models.CharField(max_length=128, blank=True, help_text="Empreinte ; vide : pas de mot de passe.")
    ouvertures_max = models.PositiveIntegerField(null=True, blank=True, help_text="Vide : sans limite.")
    nombre_ouvertures = models.PositiveIntegerField(default=0)
    derniere_ouverture = models.DateTimeField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    revoque_le = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liens_documents")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.libelle or f"Lien vers {self.document}"

    @property
    def etat(self) -> str:
        """ACTIF, EXPIRE, EPUISE (ouvertures atteintes) ou REVOQUE."""
        from django.utils import timezone

        if not self.actif:
            return "REVOQUE"
        if self.expire_le <= timezone.now():
            return "EXPIRE"
        if self.ouvertures_max is not None and self.nombre_ouvertures >= self.ouvertures_max:
            return "EPUISE"
        return "ACTIF"
