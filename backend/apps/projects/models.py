from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimestampedModel


class MethodeCalcul(models.TextChoices):
    """Méthode de calcul du taux d'exécution physique d'un élément (voir apps.projects.taux)."""

    QUANTITE = "QUANTITE", "Par quantité"
    TACHES = "TACHES", "Par tâches pondérées"
    JALONS = "JALONS", "Par jalons pondérés"
    LIVRABLES = "LIVRABLES", "Par livrables"
    BINAIRE = "BINAIRE", "Binaire (achevé / non achevé)"
    MANUELLE = "MANUELLE", "Saisie manuelle"


class MethodeAgregation(models.TextChoices):
    """Calcul du taux d'un élément à partir des éléments placés en dessous (voir apps.projects.taux)."""

    MOYENNE = "MOYENNE", "Moyenne simple"
    PONDEREE_BUDGET = "PONDEREE_BUDGET", "Moyenne pondérée par le budget"
    PONDEREE_POIDS = "PONDEREE_POIDS", "Moyenne pondérée par les poids"


class ParametresCalcul(models.Model):
    """
    Réglage de l'organisation (ligne unique, id=1) : méthode de calcul et méthode
    d'agrégation par défaut, héritées par tous les projets qui ne fixent pas les leurs.
    """

    methode_calcul = models.CharField(max_length=20, choices=MethodeCalcul.choices, default=MethodeCalcul.QUANTITE)
    methode_agregation = models.CharField(
        max_length=20, choices=MethodeAgregation.choices, default=MethodeAgregation.MOYENNE
    )
    plafonner_agregation = models.BooleanField(
        default=True,
        help_text="Dans les agrégations, un taux supérieur à 100 % compte pour 100 % (le taux réel reste affiché).",
    )

    class Meta:
        verbose_name = "Paramètres de calcul des taux"

    @classmethod
    def courants(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Projet(TimestampedModel):
    class Statut(models.TextChoices):
        EN_PREPARATION = "EN_PREPARATION", "En préparation"
        EN_COURS = "EN_COURS", "En cours"
        CLOTURE = "CLOTURE", "Clôturé"

    class TypeMiseEnOeuvre(models.TextChoices):
        DIRECT = "DIRECT", "Direct"
        CONSORTIUM = "CONSORTIUM", "En consortium"

    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    pays = ArrayField(
        models.CharField(max_length=2),
        default=list,
        blank=True,
        help_text="Codes ISO 3166-1 alpha-2 des pays d'intervention (ex : BF, ML, NE).",
    )
    partenaire_bailleur = models.ForeignKey(
        "partners.Partenaire",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projets",
        help_text="Bailleur principal (Partenaire.type=BAILLEUR).",
    )
    partenaire_mise_en_oeuvre = models.ForeignKey(
        "partners.Partenaire",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projets_mise_en_oeuvre",
        help_text="Partenaire de mise en œuvre principal (Partenaire.type=MISE_EN_OEUVRE).",
    )
    partenaires_consortium = models.ManyToManyField(
        "partners.Partenaire",
        blank=True,
        related_name="projets_consortium",
        help_text="Partenaires du consortium — renseigné quand type_mise_en_oeuvre=CONSORTIUM.",
    )
    cadre_strategique = models.ForeignKey(
        "strategy.CadreStrategique",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="projets",
        help_text="Cadre stratégique auquel ce projet est rattaché — borne les éléments stratégiques "
        "proposés pour ses activités. Fortement recommandé mais pas obligatoire.",
    )
    element_strategique = models.ForeignKey(
        "strategy.ElementStrategique",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projets",
        help_text="Élément du cadre stratégique dont relève ce projet (ex : « Programme 2 », « Pilier 3 ») — "
        "n'importe quel niveau du cadre, aucun n'est imposé. Permet de regrouper les projets par élément.",
    )
    budget_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, help_text="Coût total = fonds propres + financements bailleurs."
    )
    fonds_propres = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    date_debut = models.DateField()
    date_fin = models.DateField()
    date_rappel = models.DateField(
        null=True,
        blank=True,
        help_text="Date fixe à laquelle une alerte de rappel est déclenchée pour ce projet, indépendamment "
        "du seuil de jours avant l'échéance (ex : pour un rapport bailleur à une date précise).",
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_PREPARATION)
    type_mise_en_oeuvre = models.CharField(
        max_length=20, choices=TypeMiseEnOeuvre.choices, default=TypeMiseEnOeuvre.DIRECT
    )
    zones = models.ManyToManyField("geo.Zone", blank=True, related_name="projets")
    chef_de_projet_nom = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nom du chef de projet — texte libre, indépendant d'un compte plateforme. Pour donner accès "
        "à la plateforme, ajoute la personne dans « Utilisateurs affectés » ci-dessous.",
    )
    utilisateurs_affectes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="projets_affectes",
        help_text="Utilisateurs (ex: animateurs, chefs de projet) autorisés sur ce projet.",
    )

    # Cible du projet, ventilée par catégorie de bénéficiaires
    cible_totale = models.PositiveIntegerField(null=True, blank=True)
    cible_hommes = models.PositiveIntegerField(null=True, blank=True)
    cible_femmes = models.PositiveIntegerField(null=True, blank=True)
    cible_jeunes = models.PositiveIntegerField(null=True, blank=True)
    cible_pdi = models.PositiveIntegerField(null=True, blank=True, verbose_name="Cible PDI")

    elements_capitalisation = models.TextField(
        blank=True, help_text="Saisi en fin de projet : leçons apprises, bonnes pratiques."
    )

    # Vides = hérités des paramètres de l'organisation (ParametresCalcul).
    methode_calcul = models.CharField(max_length=20, choices=MethodeCalcul.choices, blank=True)
    methode_agregation = models.CharField(max_length=20, choices=MethodeAgregation.choices, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("-date_debut",)

    def __str__(self):
        return f"{self.code} — {self.nom}"

    @property
    def financement_bailleurs_total(self):
        from django.db.models import Sum

        return self.financements.aggregate(total=Sum("montant_finance"))["total"] or 0


class Equipe(TimestampedModel):
    nom = models.CharField(max_length=200, unique=True)
    membres = models.ManyToManyField(
        "intervenants.Intervenant",
        blank=True,
        related_name="equipes",
        help_text="Membres de l'équipe — personnes déjà enregistrées (créées à la volée si besoin).",
    )
    date_debut_contrat = models.DateField(null=True, blank=True)
    date_fin_contrat = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Équipe"
        verbose_name_plural = "Équipes"

    def __str__(self):
        return self.nom


class Activite(TimestampedModel):
    """
    Élément de la planification d'un projet, à n'importe quel niveau — aucun
    niveau n'est imposé : un projet peut être planifié en « Objectif général
    → Objectif spécifique → Activité », un autre en « Résultat → Pilier →
    Activité », un troisième directement en « Activité ». L'arborescence se
    construit avec activite_parent, et le nom affiché de chaque niveau est
    défini par projet dans NiveauActivite. Tous les éléments ont les mêmes
    capacités (budget, quantités, dates, responsables, suivi, indicateurs).
    """

    class Statut(models.TextChoices):
        NON_REALISEE = "NON_REALISEE", "Non réalisée"
        EN_COURS = "EN_COURS", "En cours"
        REALISEE = "REALISEE", "Réalisée"

    projet = models.ForeignKey(Projet, on_delete=models.PROTECT, related_name="activites")
    description = models.TextField(blank=True)
    activite_parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="enfants",
        help_text="Élément parent dans la planification du projet (vide = élément de premier niveau). "
        "La profondeur est libre : chaque projet nomme ses niveaux comme il veut (ex : « Objectif "
        "général » → « Objectif spécifique » → « Activité », ou « Résultat » → « Pilier » → « Activité ») "
        "— voir NiveauActivite. Toujours dans le même projet que son parent (voir clean()).",
    )
    code_activite = models.CharField(
        max_length=30, blank=True, help_text="Codification interne (ex : AI1.1, AI1.1.2)."
    )
    libelle = models.CharField(max_length=300)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.NON_REALISEE)
    commentaire = models.TextField(
        blank=True, help_text="Note libre (ex : validation, remarque) — n'affecte ni le suivi ni les calculs."
    )
    axe_strategique = models.ForeignKey(
        "strategy.ElementStrategique", null=True, blank=True, on_delete=models.SET_NULL, related_name="activites"
    )

    budget_alloue = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_realise = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    valeur_reference = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valeur de base avant le démarrage de l'activité — une activité se suit alors comme un "
        "indicateur (valeur de départ → cible), utile pour tracer la progression attendue dans le temps.",
    )
    quantite_prevue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantite_realisee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unite_quantite = models.CharField(max_length=50, blank=True, help_text="Ex : producteurs, hectares, sessions…")

    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    date_debut_reelle = models.DateField(null=True, blank=True)
    date_fin_reelle = models.DateField(null=True, blank=True)
    nb_jours_planifies = models.PositiveIntegerField(null=True, blank=True)
    date_rappel = models.DateField(
        null=True,
        blank=True,
        help_text="Date fixe à laquelle une alerte de rappel est déclenchée pour cette activité, indépendamment "
        "du seuil de jours avant l'échéance.",
    )

    responsables = models.ManyToManyField(
        "intervenants.Intervenant",
        blank=True,
        related_name="activites_dont_responsable",
        help_text="Responsables de l'activité — personnes déjà enregistrées (créées à la volée si besoin).",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="activites_responsable",
        help_text="Compte plateforme lié (optionnel) — nécessaire pour que le responsable reçoive des "
        "notifications.",
    )
    equipe_responsable = models.ForeignKey(
        Equipe, null=True, blank=True, on_delete=models.SET_NULL, related_name="activites"
    )

    # Calcul du taux d'exécution physique — vides = hérités de l'élément parent, puis
    # du projet, puis de l'organisation (voir apps.projects.taux).
    methode_calcul = models.CharField(max_length=20, choices=MethodeCalcul.choices, blank=True)
    methode_agregation = models.CharField(
        max_length=20,
        choices=MethodeAgregation.choices,
        blank=True,
        help_text="Calcul du taux de cet élément à partir des éléments placés en dessous.",
    )
    poids = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Poids de cet élément quand son parent agrège par « Moyenne pondérée par les poids ».",
    )

    history = HistoricalRecords()

    class Meta:
        # Ordre de création : un import ou une saisie remonte dans l'ordre où il a été fait.
        ordering = ("id",)

    def __str__(self):
        return self.libelle

    def clean(self):
        if self.activite_parent_id:
            if self.activite_parent.projet_id != self.projet_id:
                raise ValidationError("Un élément doit appartenir au même projet que son élément parent.")
            ancetre = self.activite_parent
            while ancetre is not None:
                if ancetre.pk == self.pk:
                    raise ValidationError("Une activité ne peut pas être sa propre ancêtre (boucle détectée).")
                ancetre = ancetre.activite_parent

    @property
    def taux_realisation(self):
        """Taux d'exécution physique selon la méthode de calcul de l'élément (voir apps.projects.taux)."""
        from .taux import taux_element

        return taux_element(self).taux

    @property
    def taux_execution_financiere(self):
        if not self.budget_alloue:
            return None
        return round(float(self.budget_realise or 0) / float(self.budget_alloue) * 100, 1)

    @property
    def alerte_retard(self):
        from django.utils import timezone

        return bool(
            self.date_fin and self.date_fin < timezone.localdate() and self.statut != self.Statut.REALISEE
        )


class NiveauActivite(TimestampedModel):
    """
    Nom affiché pour chaque niveau de la planification d'un projet (ex :
    profondeur 0 = « Résultat », profondeur 1 = « Pilier », profondeur 2 =
    « Activité ») — purement d'affichage, n'affecte ni le modèle Activite ni
    son comportement. Profondeur 0 = un élément sans activite_parent
    (premier niveau sous le projet) ; chaque profondeur suivante = un niveau
    d'imbrication en plus, sans limite. Sans ligne définie pour une
    profondeur donnée, l'affichage retombe sur « Activité ».
    """

    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name="niveaux_activite")
    profondeur = models.PositiveIntegerField()
    nom_niveau = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Niveau d'activité"
        verbose_name_plural = "Niveaux d'activité"
        ordering = ("profondeur",)
        constraints = [
            models.UniqueConstraint(fields=("projet", "profondeur"), name="niveau_activite_profondeur_unique")
        ]

    def __str__(self):
        return f"{self.projet} — niveau {self.profondeur} : {self.nom_niveau}"


class SousActivite(TimestampedModel):
    class Statut(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiée"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminée"

    activite = models.ForeignKey(Activite, on_delete=models.PROTECT, related_name="sous_activites")
    libelle = models.CharField(max_length=300)
    axe_strategique = models.ForeignKey(
        "strategy.ElementStrategique", null=True, blank=True, on_delete=models.SET_NULL, related_name="sous_activites"
    )
    quantite_prevue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantite_realisee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unite_quantite = models.CharField(max_length=50, blank=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)
    # Méthode « tâches pondérées » de l'activité : chaque sous-activité est une tâche.
    poids = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, help_text="Poids de la tâche (les poids totalisent 100)."
    )
    avancement = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Niveau d'achèvement saisi (0 à 100 %). Vide : déduit des quantités, sinon du statut.",
    )

    history = HistoricalRecords()

    class Meta:
        # Ordre de création, comme les éléments de la planification.
        ordering = ("id",)
        verbose_name = "Sous-activité"

    def __str__(self):
        return self.libelle


class JalonLivrable(TimestampedModel):
    """
    Jalon ou livrable d'un élément de la planification, pour les méthodes de
    calcul « jalons pondérés » (achèvement de chaque jalon) et « livrables »
    (seuls les livrables validés comptent).
    """

    class Type(models.TextChoices):
        JALON = "JALON", "Jalon"
        LIVRABLE = "LIVRABLE", "Livrable"

    activite = models.ForeignKey(Activite, on_delete=models.PROTECT, related_name="jalons_livrables")
    type = models.CharField(max_length=10, choices=Type.choices)
    libelle = models.CharField(max_length=300)
    poids = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    date_prevue = models.DateField(null=True, blank=True)
    achevement = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Jalon : niveau d'achèvement (0 à 100 %)."
    )
    valide = models.BooleanField(default=False, help_text="Livrable : validé.")
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_validation = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("id",)
        verbose_name = "Jalon ou livrable"
        verbose_name_plural = "Jalons et livrables"

    def __str__(self):
        return self.libelle


class TauxManuel(TimestampedModel):
    """
    Taux d'exécution saisi à la main (méthode « saisie manuelle ») — historisé :
    le taux en vigueur est la saisie la plus récente, jamais recalculé.
    """

    activite = models.ForeignKey(Activite, on_delete=models.PROTECT, related_name="taux_manuels")
    taux = models.DecimalField(max_digits=5, decimal_places=2)
    date = models.DateField()
    saisi_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    commentaire = models.TextField(blank=True)

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = "Taux saisi manuellement"
        verbose_name_plural = "Taux saisis manuellement"
        constraints = [
            models.CheckConstraint(check=models.Q(taux__gte=0, taux__lte=100), name="taux_manuel_entre_0_et_100")
        ]

    def __str__(self):
        return f"{self.activite} — {self.taux} % au {self.date}"
