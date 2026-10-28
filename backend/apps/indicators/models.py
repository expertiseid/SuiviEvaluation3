from django.conf import settings
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from apps.core.models import SaisieApprouvable, TimestampedModel


class Indicateur(TimestampedModel):
    class Frequence(models.TextChoices):
        MENSUELLE = "MENSUELLE", "Mensuelle"
        TRIMESTRIELLE = "TRIMESTRIELLE", "Trimestrielle"
        SEMESTRIELLE = "SEMESTRIELLE", "Semestrielle"
        ANNUELLE = "ANNUELLE", "Annuelle"

    libelle = models.TextField(
        help_text="Énoncé complet de l'indicateur — sans limite de longueur : un indicateur de cadre logique "
        "formel est souvent une phrase complète dépassant largement 300 caractères."
    )
    unite = models.CharField(max_length=50)
    valeur_reference = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    valeur_reference_date = models.DateField(null=True, blank=True)
    valeur_cible = models.DecimalField(max_digits=14, decimal_places=2)
    frequence_collecte = models.CharField(max_length=20, choices=Frequence.choices)

    # Rattachement au projet lui-même OU à un élément de sa planification, à
    # n'importe quel niveau (Activite couvre tous les niveaux librement nommés :
    # objectif, résultat, pilier, activité...) — au plus un des deux
    # (contrainte ci-dessous). Un indicateur peut n'avoir aucun de ces
    # rattachements : c'est alors un indicateur purement stratégique, relié
    # uniquement via elements_strategiques ci-dessous.
    projet = models.ForeignKey(
        "projects.Projet", null=True, blank=True, on_delete=models.PROTECT, related_name="indicateurs"
    )
    activite = models.ForeignKey(
        "projects.Activite", null=True, blank=True, on_delete=models.PROTECT, related_name="indicateurs"
    )

    # Rattachement (0..N, indépendant du rattachement projet ci-dessus) à
    # n'importe quel niveau de la structuration stratégique paramétrable —
    # une organisation peut suivre ses indicateurs au niveau "axe" pendant
    # qu'une autre les suit au niveau "produit", sans changement de schéma.
    elements_strategiques = models.ManyToManyField(
        "strategy.ElementStrategique",
        through="IndicateurElement",
        blank=True,
        related_name="indicateurs",
    )

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~Q(projet__isnull=False, activite__isnull=False),
                name="indicateur_rattachement_au_plus_un",
            )
        ]

    def __str__(self):
        return self.libelle

    @property
    def projet_rattache(self):
        if self.projet_id:
            return self.projet
        if self.activite_id:
            return self.activite.projet
        return None


class ValeurIndicateur(TimestampedModel, SaisieApprouvable):
    indicateur = models.ForeignKey(Indicateur, on_delete=models.PROTECT, related_name="valeurs")
    periode_debut = models.DateField()
    periode_fin = models.DateField()
    valeur_realisee = models.DecimalField(max_digits=14, decimal_places=2)
    date_saisie = models.DateTimeField(auto_now_add=True)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="valeurs_indicateurs_saisies"
    )
    commentaire = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Valeur d'indicateur"
        verbose_name_plural = "Valeurs d'indicateur"
        constraints = [
            models.UniqueConstraint(
                fields=("indicateur", "periode_debut", "periode_fin"),
                name="valeur_indicateur_periode_unique",
            )
        ]
        ordering = ("-periode_fin",)

    def __str__(self):
        return f"{self.indicateur} — {self.periode_debut} au {self.periode_fin}"


class IndicateurElement(TimestampedModel):
    """Table de jonction Indicateur ↔ ElementStrategique (rattachement à n'importe quel niveau de la structuration)."""

    indicateur = models.ForeignKey(Indicateur, on_delete=models.CASCADE, related_name="indicateur_elements")
    element_strategique = models.ForeignKey(
        "strategy.ElementStrategique", on_delete=models.CASCADE, related_name="indicateur_elements"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("indicateur", "element_strategique"), name="indicateur_element_unique")
        ]

    def __str__(self):
        return f"{self.indicateur} ↔ {self.element_strategique}"


class ParametresAlerte(TimestampedModel):
    """
    Réglage unique (singleton, id=1) — ne porte plus que les rappels
    d'échéance : la grille d'interprétation des taux de réalisation
    (paliers/libellés/couleurs) est désormais portée par PalierAlerte,
    paramétrable projet par projet (voir plus bas).
    """

    seuil_echeance_jours = models.PositiveSmallIntegerField(
        default=7,
        help_text="Nombre de jours avant une échéance (activité, sous-activité, projet) à partir duquel une "
        "alerte de rappel est envoyée — l'échéance déjà dépassée alerte toujours, quel que soit ce seuil.",
    )

    class Meta:
        verbose_name = "Paramètres d'alerte"
        verbose_name_plural = "Paramètres d'alerte"

    def __str__(self):
        return "Paramètres d'alerte"

    @classmethod
    def instance(cls) -> "ParametresAlerte":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PalierAlerte(TimestampedModel):
    """
    Un palier de la grille d'interprétation des taux de réalisation : à
    partir de `borne_min` (%), l'élément concerné affiche `libelle` dans la
    couleur `couleur`. Une organisation définit autant de paliers qu'elle
    veut (pas figé à 3), à l'un de ces 4 niveaux de portée (exactement un des
    quatre, ou aucun pour la grille globale) :

      Indicateur > Activité > Projet > Global

    Un indicateur/une activité sans grille propre hérite de celle de son
    projet ; un projet sans grille propre hérite de la grille globale par
    défaut — avec potentiellement 1000 indicateurs (ou activités) ayant
    chacun sa propre grille, indépendamment les uns des autres.
    """

    projet = models.ForeignKey(
        "projects.Projet",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="paliers_alerte",
        help_text="Grille propre à ce projet (utilisée par ses indicateurs/activités sans grille propre).",
    )
    indicateur = models.ForeignKey(
        "Indicateur",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="paliers_alerte",
        help_text="Grille propre à cet indicateur précis, prioritaire sur celle de son projet.",
    )
    activite = models.ForeignKey(
        "projects.Activite",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="paliers_alerte",
        help_text="Grille propre à cette activité précise, prioritaire sur celle de son projet.",
    )
    borne_min = models.PositiveSmallIntegerField(
        help_text="Taux de réalisation (%) à partir duquel ce palier s'applique."
    )
    libelle = models.CharField(max_length=50)
    couleur = models.CharField(max_length=7, help_text="Couleur hexadécimale (ex : #0ca30c).")

    class Meta:
        verbose_name = "Palier d'alerte"
        verbose_name_plural = "Paliers d'alerte"
        ordering = ("projet_id", "indicateur_id", "activite_id", "borne_min")
        constraints = [
            models.UniqueConstraint(
                fields=("projet", "indicateur", "activite", "borne_min"), name="palier_alerte_portee_borne_unique"
            ),
            models.CheckConstraint(
                check=(
                    models.Q(projet__isnull=False, indicateur__isnull=True, activite__isnull=True)
                    | models.Q(projet__isnull=True, indicateur__isnull=False, activite__isnull=True)
                    | models.Q(projet__isnull=True, indicateur__isnull=True, activite__isnull=False)
                    | models.Q(projet__isnull=True, indicateur__isnull=True, activite__isnull=True)
                ),
                name="palier_alerte_une_seule_portee",
            ),
        ]

    def __str__(self):
        portee = self.indicateur or self.activite or self.projet or "Global"
        return f"{portee} — ≥ {self.borne_min}% : {self.libelle}"
