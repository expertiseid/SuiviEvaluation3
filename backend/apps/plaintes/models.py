"""
Mécanisme de gestion des plaintes et retours (MGPR) — lot 1 : paramétrage.

Une installation de la plateforme = une organisation, qui règle elle-même son mécanisme : types
de retours, catégories (dont les catégories sensibles), priorités et délais, circuits de
traitement par étapes avec leurs responsables. Tout est paramétrable, sauf ce qui protège les
personnes (catégories liées à l'exploitation et aux abus sexuels, existence d'un circuit
confidentiel, contrôles d'activation : voir controles.py).

Les dossiers eux-mêmes (réception, traitement, délais, circuit confidentiel, pilotage) arrivent
dans les lots suivants et s'appuient sur ce paramétrage.
"""
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimestampedModel


class Mecanisme(TimestampedModel):
    """Le mécanisme de l'organisation (une seule ligne : Mecanisme.courant())."""

    nom = models.CharField(max_length=200, default="Mécanisme de gestion des plaintes et retours")
    actif = models.BooleanField(
        default=False, help_text="Mécanisme en service (réception ouverte) ; activable seulement si les contrôles passent.",
    )
    modele = models.CharField(max_length=30, blank=True, help_text="Dernier modèle appliqué (voir modeles_mecanisme).")
    anonymat_autorise = models.BooleanField(
        default=True, help_text="Plaintes anonymes acceptées : aucune coordonnée ne peut alors être exigée.",
    )
    langues = ArrayField(
        models.CharField(max_length=5), default=list, blank=True,
        help_text="Langues du formulaire public (codes : fr, en, ar, de, es).",
    )
    texte_information = models.TextField(
        blank=True,
        help_text="Texte affiché aux plaignants : à quoi sert le mécanisme, ce qui va se passer, comment les "
        "données sont protégées, gratuité.",
    )
    prefixe_numero = models.CharField(
        max_length=12, default="MGP", help_text="Préfixe des numéros de dossier (ex : MGP-2026-00412).",
    )
    jours_ouvres = models.BooleanField(
        default=False, help_text="Délais comptés en jours ouvrés (sinon en jours calendaires).",
    )
    # Conservation : aucune valeur par défaut imposée, l'organisation la fixe avant l'activation.
    conservation_ordinaire_mois = models.PositiveIntegerField(null=True, blank=True)
    conservation_sensible_mois = models.PositiveIntegerField(null=True, blank=True)
    projets = models.ManyToManyField(
        "projects.Projet", blank=True, related_name="mecanismes_plaintes",
        help_text="Projets couverts ; aucun = tous les projets.",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Mécanisme de plaintes"

    def __str__(self):
        return self.nom

    @classmethod
    def courant(cls):
        """Le mécanisme de l'installation, créé à la première demande."""
        mecanisme, _ = cls.objects.get_or_create(pk=1)
        return mecanisme


class TypeRetour(TimestampedModel):
    """Plainte, suggestion, question, remerciement, signalement… (liste libre)."""

    nom = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=300, blank=True)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("ordre", "id")

    def __str__(self):
        return self.nom


class Priorite(TimestampedModel):
    """Niveau de priorité et délai total de traitement associé ; au moins un niveau urgent."""

    nom = models.CharField(max_length=60, unique=True)
    ordre = models.PositiveIntegerField(default=0)
    urgente = models.BooleanField(default=False, help_text="Priorité urgente : notification immédiate, circuit accéléré.")
    delai_jours = models.PositiveIntegerField(
        null=True, blank=True, help_text="Délai de traitement total (jours) ; vide = délais des étapes du circuit.",
    )
    actif = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("ordre", "id")

    def __str__(self):
        return self.nom


class Circuit(TimestampedModel):
    """
    Circuit de traitement : suite ordonnée d'étapes (EtapeCircuit) avec responsables et délais.
    Un circuit « sensible » (confidentiel) traite les catégories sensibles ; ses étapes sont
    confiées à des personnes nommément désignées, jamais à un rôle entier.
    """

    nom = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=300, blank=True)
    sensible = models.BooleanField(default=False, help_text="Circuit confidentiel (exploitation et abus sexuels, fraude…).")
    par_defaut = models.BooleanField(
        default=False, help_text="Circuit utilisé quand la catégorie n'en désigne pas (un par défaut pour chaque nature).",
    )
    actif = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("sensible", "nom")

    def __str__(self):
        return self.nom


class EtapeCircuit(TimestampedModel):
    """Étape d'un circuit : son responsable (un rôle ou une personne), son délai, clôture ou non."""

    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE, related_name="etapes")
    nom = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    delai_jours = models.PositiveIntegerField(null=True, blank=True, help_text="Délai de l'étape (jours).")
    role = models.ForeignKey(
        "accounts.Role", null=True, blank=True, on_delete=models.SET_NULL, related_name="etapes_plaintes",
        help_text="Rôle responsable (circuit ordinaire uniquement).",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="etapes_plaintes",
        help_text="Personne responsable (obligatoire dans un circuit sensible).",
    )
    est_cloture = models.BooleanField(default=False, help_text="Étape de clôture du dossier.")

    history = HistoricalRecords()

    class Meta:
        ordering = ("circuit", "ordre", "id")

    def __str__(self):
        return f"{self.circuit} — {self.nom}"


class Categorie(TimestampedModel):
    """
    Catégorie de retour, sur deux niveaux (catégorie, sous-catégorie). Une catégorie sensible
    fait passer le dossier dans le circuit confidentiel. Les catégories « verrouillées »
    (exploitation et abus sexuels) restent sensibles et ne se suppriment ni ne se désactivent.
    """

    nom = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="sous_categories")
    sensible = models.BooleanField(default=False)
    verrouillee = models.BooleanField(
        default=False, help_text="Protège les personnes : reste sensible, ne peut être ni supprimée ni désactivée.",
    )
    circuit = models.ForeignKey(
        Circuit, null=True, blank=True, on_delete=models.SET_NULL, related_name="categories",
        help_text="Circuit propre à la catégorie ; vide = circuit par défaut (sensible ou ordinaire).",
    )
    delai_jours = models.PositiveIntegerField(null=True, blank=True, help_text="Délai propre à la catégorie (jours).")
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("ordre", "nom")
        constraints = [
            models.UniqueConstraint(fields=("parent", "nom"), name="categorie_plainte_nom_unique"),
            models.UniqueConstraint(
                fields=("nom",), condition=models.Q(parent__isnull=True), name="categorie_plainte_racine_unique",
            ),
        ]

    def __str__(self):
        return f"{self.parent.nom} › {self.nom}" if self.parent_id else self.nom

    @property
    def sensible_effective(self) -> bool:
        """Une sous-catégorie d'une catégorie sensible est sensible."""
        return self.sensible or bool(self.parent_id and self.parent.sensible)
