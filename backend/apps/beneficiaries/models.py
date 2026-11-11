from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimestampedModel


class StatutParticulier(TimestampedModel):
    """Référentiel extensible (PDI, Jeune, Femme, Personne handicapée, ...)."""

    code = models.CharField(max_length=50, unique=True)
    libelle = models.CharField(max_length=100)

    def __str__(self):
        return self.libelle


class TypeActiviteBeneficiaire(TimestampedModel):
    """
    Référentiel extensible de l'activité économique menée par le
    bénéficiaire (maraîchage, élevage, petit commerce...) — créable à la
    volée depuis la fiche bénéficiaire si l'activité voulue n'y figure pas
    encore, même logique que StatutParticulier.
    """

    code = models.CharField(max_length=50, unique=True)
    libelle = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Type d'activité du bénéficiaire"
        verbose_name_plural = "Types d'activité des bénéficiaires"
        ordering = ("libelle",)

    def __str__(self):
        return self.libelle


class VariableBeneficiaire(TimestampedModel):
    """
    Information à collecter sur les bénéficiaires (taille du ménage, superficie cultivée…),
    pour tous les projets ou seulement certains. La réponse est gardée une fois par bénéficiaire
    (Beneficiaire.reponses) ; pour un projet que la variable ne concerne pas, elle vaut « NA »
    (exports) et n'est pas demandée (formulaire).
    """

    class Type(models.TextChoices):
        TEXTE = "TEXTE", "Texte"
        NOMBRE = "NOMBRE", "Nombre"
        DATE = "DATE", "Date"
        OUI_NON = "OUI_NON", "Oui / non"
        CHOIX = "CHOIX", "Choix unique"
        CHOIX_MULTIPLE = "CHOIX_MULTIPLE", "Choix multiple"

    libelle = models.CharField(max_length=200, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.TEXTE)
    choix = models.JSONField(default=list, blank=True, help_text="Réponses proposées (choix unique ou multiple).")
    unite = models.CharField(max_length=30, blank=True, help_text="Pour un nombre (ex : ha, personnes).")
    aide = models.CharField(max_length=300, blank=True)
    tous_les_projets = models.BooleanField(default=True)
    projets = models.ManyToManyField(
        "projects.Projet", blank=True, related_name="variables_beneficiaires",
        help_text="Projets concernés, si la variable ne concerne pas tous les projets.",
    )
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("ordre", "libelle")

    def __str__(self):
        return self.libelle

    def concerne(self, projet_ids) -> bool:
        """La variable concerne-t-elle au moins un de ces projets ?"""
        return self.tous_les_projets or bool(set(projet_ids) & {p.id for p in self.projets.all()})


class Beneficiaire(TimestampedModel):
    class Sexe(models.TextChoices):
        FEMININ = "F", "Féminin"
        MASCULIN = "M", "Masculin"

    identifiant = models.CharField(
        max_length=20, unique=True, null=True, blank=True, editable=False,
        help_text="Identifiant unique attribué automatiquement (BEN-000123), repris dans le QR code de sa carte.",
    )
    nom = models.CharField(max_length=150)
    prenom = models.CharField(max_length=150)
    sexe = models.CharField(max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField(null=True, blank=True)
    telephone = models.CharField(max_length=30, blank=True, db_index=True)
    numero_piece_identite = models.CharField(max_length=50, blank=True, db_index=True)
    type_piece = models.CharField(max_length=50, blank=True)
    pays = models.CharField(
        max_length=2, blank=True, help_text="Code ISO 3166-1 alpha-2 du pays (ex : BF, ML, NE)."
    )
    zone = models.ForeignKey("geo.Zone", null=True, blank=True, on_delete=models.PROTECT, related_name="beneficiaires")
    reponses = models.JSONField(
        default=dict, blank=True, help_text="Réponses aux variables personnalisées : {id de la variable: valeur}."
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    consentement = models.BooleanField(
        null=True, blank=True, help_text="Accord de la personne pour l'enregistrement de ses données ; vide : non renseigné.",
    )
    date_consentement = models.DateField(null=True, blank=True)
    date_anonymisation = models.DateField(
        null=True, blank=True, help_text="Identité effacée à l'échéance de conservation de ses projets (apps.core.conservation).",
    )
    statuts_particuliers = models.ManyToManyField(StatutParticulier, blank=True, related_name="beneficiaires")
    types_activite = models.ManyToManyField(
        TypeActiviteBeneficiaire,
        blank=True,
        related_name="beneficiaires",
        help_text="Activité(s) économique(s) menée(s) par le bénéficiaire (maraîchage, élevage...).",
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ("nom", "prenom")

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.identifiant:
            self.identifiant = f"BEN-{self.pk:06d}"
            Beneficiaire.objects.filter(pk=self.pk).update(identifiant=self.identifiant)


class ParticipationProjet(TimestampedModel):
    """
    Table de jonction explicite (plutôt qu'un simple M2M implicite) : c'est
    elle qui permet de suivre un même bénéficiaire à travers plusieurs
    projets/cycles dans la durée.
    """

    beneficiaire = models.ForeignKey(Beneficiaire, on_delete=models.PROTECT, related_name="participations")
    projet = models.ForeignKey("projects.Projet", on_delete=models.PROTECT, related_name="participations")
    activite = models.ForeignKey(
        "projects.Activite", null=True, blank=True, on_delete=models.CASCADE, related_name="participations"
    )
    sous_activite = models.ForeignKey(
        "projects.SousActivite", null=True, blank=True, on_delete=models.CASCADE, related_name="participations"
    )
    date_inscription = models.DateField()
    role_dans_projet = models.CharField(max_length=150, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Participation à un projet"
        verbose_name_plural = "Participations aux projets"
        ordering = ("-date_inscription",)

    def __str__(self):
        return f"{self.beneficiaire} — {self.projet}"


class SignalementDoublon(TimestampedModel):
    class Statut(models.TextChoices):
        SIGNALE = "SIGNALE", "Signalé"
        ECARTE = "ECARTE", "Écarté (faux positif)"
        FUSIONNE = "FUSIONNE", "Fusionné"

    class Methode(models.TextChoices):
        PIECE_IDENTITE = "PIECE_IDENTITE", "Correspondance exacte pièce d'identité"
        SIMILARITE = "SIMILARITE", "Nom proche et confirmation (téléphone, naissance ou localité)"

    beneficiaire_1 = models.ForeignKey(
        Beneficiaire, on_delete=models.PROTECT, related_name="signalements_comme_beneficiaire_1"
    )
    beneficiaire_2 = models.ForeignKey(
        Beneficiaire, on_delete=models.PROTECT, related_name="signalements_comme_beneficiaire_2"
    )
    score = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    methode = models.CharField(max_length=20, choices=Methode.choices)
    motifs = models.JSONField(default=list, blank=True, help_text="Pourquoi la paire est signalée (« Même téléphone »…).")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.SIGNALE)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="doublons_traites"
    )
    date_traitement = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Doublon potentiel : {self.beneficiaire_1} / {self.beneficiaire_2}"
