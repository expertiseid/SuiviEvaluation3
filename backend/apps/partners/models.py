from django.db import models

from apps.core.models import TimestampedModel


class Partenaire(TimestampedModel):
    class TypePartenaire(models.TextChoices):
        BAILLEUR = "BAILLEUR", "Bailleur"
        MISE_EN_OEUVRE = "MISE_EN_OEUVRE", "Partenaire de mise en œuvre"
        CONSORTIUM = "CONSORTIUM", "Partenaire de consortium"

    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TypePartenaire.choices)
    contact = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Bailleur(TimestampedModel):
    """
    Entité dédiée aux bailleurs (distincte de Partenaire), pour porter le
    montant financé par projet via Financement — Partenaire.type=BAILLEUR
    reste utilisable pour la compatibilité, mais Bailleur est le modèle
    recommandé pour tout nouveau financement multi-bailleurs.
    """

    class TypeBailleur(models.TextChoices):
        INSTITUTIONNEL = "INSTITUTIONNEL", "Institutionnel"
        FONDATION = "FONDATION", "Fondation"
        COOPERATION_BILATERALE = "COOPERATION_BILATERALE", "Coopération bilatérale"
        AUTRE = "AUTRE", "Autre"

    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=30, choices=TypeBailleur.choices, default=TypeBailleur.AUTRE)
    contact = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Financement(TimestampedModel):
    """Table de jonction Projet-Bailleur portant le montant financé."""

    projet = models.ForeignKey("projects.Projet", on_delete=models.CASCADE, related_name="financements")
    bailleur = models.ForeignKey(Bailleur, on_delete=models.PROTECT, related_name="financements")
    montant_finance = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("projet", "bailleur"), name="financement_projet_bailleur_unique")
        ]

    def __str__(self):
        return f"{self.bailleur} → {self.projet} : {self.montant_finance}"


class StructureOrganisation(TimestampedModel):
    """
    Structure interne de l'organisation (direction, service, secteur, cellule…), en arbre de
    profondeur libre : chaque organisation nomme ses niveaux comme elle veut (champ `type`).
    Projets, parties de projet (éléments de planification) et éléments stratégiques peuvent être
    affectés à une ou plusieurs structures.
    """

    nom = models.CharField(max_length=200)
    sigle = models.CharField(max_length=30, blank=True)
    type = models.CharField(max_length=60, blank=True, help_text="Ex : Direction, Service, Secteur, Cellule.")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="enfants")
    responsable = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("nom",)
        verbose_name = "Structure de l'organisation"
        verbose_name_plural = "Structures de l'organisation"

    def __str__(self):
        return f"{self.sigle} — {self.nom}" if self.sigle else self.nom

    def clean(self):
        from django.core.exceptions import ValidationError

        courant = self.parent
        while courant is not None:
            if courant.pk == self.pk:
                raise ValidationError("Une structure ne peut pas être rattachée à elle-même ni à une structure qui en dépend.")
            courant = courant.parent


class CategoriePartiePrenante(TimestampedModel):
    """Catégories de parties prenantes, propres à l'organisation (ex : Ministère, Collectivité, ONG, Communauté)."""

    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class PartiePrenante(TimestampedModel):
    """Partie prenante enregistrée une fois, puis sélectionnée sur les projets et éléments stratégiques."""

    nom = models.CharField(max_length=200)
    categorie = models.ForeignKey(
        CategoriePartiePrenante, null=True, blank=True, on_delete=models.SET_NULL, related_name="parties_prenantes"
    )
    contact = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True, help_text="Intérêt, influence, attentes…")

    class Meta:
        ordering = ("nom",)
        verbose_name = "Partie prenante"
        verbose_name_plural = "Parties prenantes"

    def __str__(self):
        return self.nom
