import datetime

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import EtatApprobation, SaisieApprouvable, TimestampedModel


def duree_en_jours(debut, fin):
    """Nombre de jours de début à fin, bornes comprises (même jour = 1 jour) ; None si fin < début."""
    debut, fin = (datetime.date.fromisoformat(d) if isinstance(d, str) else d for d in (debut, fin))
    jours = (fin - debut).days + 1
    return jours if jours > 0 else None


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


class PerimetreFermeture(models.TextChoices):
    """Ce qui passe en lecture seule quand la saisie est fermée (voir apps.projects.rapportage)."""

    REALISATIONS = "REALISATIONS", "Les réalisations seulement"
    TOUT = "TOUT", "Tout le projet"


class ParametresRapportage(models.Model):
    """
    Réglage de l'organisation (ligne unique, id=1) : contrôle des périodes de rapportage. Quand
    il est actif, la saisie n'est ouverte que pendant les périodes de rapportage (générales ou
    propres au projet) ; le reste du temps, le périmètre choisi est en lecture seule.
    """

    controle_actif = models.BooleanField(default=False)
    perimetre = models.CharField(
        max_length=20, choices=PerimetreFermeture.choices, default=PerimetreFermeture.REALISATIONS
    )

    class Meta:
        verbose_name = "Paramètres des périodes de rapportage"

    @classmethod
    def courants(cls):
        return cls.objects.get_or_create(pk=1)[0]


class FenetreRapportage(TimestampedModel):
    """Période pendant laquelle la saisie est ouverte : pour tous les projets (projet vide) ou un seul."""

    projet = models.ForeignKey(
        "Projet", null=True, blank=True, on_delete=models.CASCADE, related_name="fenetres_rapportage"
    )
    libelle = models.CharField(max_length=100, help_text="Ex : « Rapport du 1er trimestre 2026 ».")
    date_debut = models.DateField()
    date_fin = models.DateField()

    class Meta:
        ordering = ("date_debut", "id")
        verbose_name = "Période de rapportage"

    def __str__(self):
        return self.libelle


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
    elements_strategiques_secondaires = models.ManyToManyField(
        "strategy.ElementStrategique",
        blank=True,
        related_name="projets_secondaires",
        help_text="Autres éléments stratégiques auxquels le projet contribue aussi. Seul element_strategique "
        "compte dans les budgets et les taux (pas de double compte) ; ces liens sont informatifs.",
    )
    structures = models.ManyToManyField(
        "partners.StructureOrganisation", blank=True, related_name="projets",
        help_text="Directions / services de l'organisation chargés du projet.",
    )
    parties_prenantes = models.ManyToManyField("partners.PartiePrenante", blank=True, related_name="projets")
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
    conservation_beneficiaires_mois = models.PositiveIntegerField(
        null=True, blank=True, help_text="Mois après la fin du projet au terme desquels l'identité de ses bénéficiaires "
        "est effacée (apps.core.conservation) ; vide : conservée.",
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_PREPARATION)
    type_mise_en_oeuvre = models.CharField(
        max_length=20, choices=TypeMiseEnOeuvre.choices, default=TypeMiseEnOeuvre.DIRECT
    )
    zones = models.ManyToManyField("geo.Zone", blank=True, related_name="projets")
    class Saisie(models.TextChoices):
        HERITE = "HERITE", "Selon le réglage général"
        OUVERTE = "OUVERTE", "Toujours ouverte"
        FERMEE = "FERMEE", "Fermée, sauf pendant les périodes propres au projet"

    saisie = models.CharField(
        max_length=20,
        choices=Saisie.choices,
        default=Saisie.HERITE,
        help_text="Ouverture de la saisie pour ce projet (voir les périodes de rapportage).",
    )
    perimetre_fermeture = models.CharField(
        max_length=20,
        choices=PerimetreFermeture.choices,
        blank=True,
        help_text="Ce qui est fermé hors période de rapportage ; vide = réglage général.",
    )
    approbation_realisations = models.BooleanField(
        default=False,
        help_text="Les saisies de réalisations (suivis, valeurs d'indicateurs, taux manuels) ne comptent "
        "qu'une fois approuvées (voir apps.projects.approbation).",
    )
    approbation_planification = models.BooleanField(
        default=False,
        help_text="Les ajouts, modifications et suppressions d'éléments de la planification passent par "
        "une demande à approuver.",
    )
    tout_le_pays = models.BooleanField(
        default=False,
        help_text="Intervention sur l'ensemble du territoire du ou des pays d'intervention : aucune zone à "
        "détailler.",
    )
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
    # Ordre des attributs libres de la planification (colonnes du fichier importé, puis ceux ajoutés
    # par la fiche) : les attributs eux-mêmes sont stockés sans ordre (JSON), voir projects.attributs.
    ordre_attributs = models.JSONField(default=list, blank=True)

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

        from apps.partners.models import RallongeFinancement

        initial = self.financements.aggregate(total=Sum("montant_finance"))["total"] or 0
        rallonges = RallongeFinancement.objects.filter(financement__projet=self).aggregate(total=Sum("montant"))["total"] or 0
        return initial + rallonges


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
    masquee_pour = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="activites_masquees",
        help_text="Utilisateurs qui ne voient ni cet élément ni ce qui est en dessous (apps.core.masquage) ; "
        "réglé dans la fiche de l'utilisateur. Les totaux du projet restent complets.",
    )
    libelle = models.CharField(max_length=300)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.NON_REALISEE)
    commentaire = models.TextField(
        blank=True, help_text="Note libre (ex : validation, remarque) — n'affecte ni le suivi ni les calculs."
    )
    # Cadre logique (lot 5) : à n'importe quel niveau de la planification.
    sources_verification = models.TextField(
        blank=True, help_text="Cadre logique : où trouver la preuve (rapports, listes de présence, enquêtes…)."
    )
    hypotheses = models.TextField(
        blank=True, help_text="Cadre logique : hypothèses et risques extérieurs dont dépend la réussite."
    )
    # Attributs libres propres à l'organisation (« Responsable », « Lieu »…) : {nom: texte}.
    # Renseignés par la fiche ou par l'import (colonnes « Attribut : … » de la feuille Planification).
    attributs = models.JSONField(default=dict, blank=True)
    axe_strategique = models.ForeignKey(
        "strategy.ElementStrategique", null=True, blank=True, on_delete=models.SET_NULL, related_name="activites"
    )
    axes_strategiques_secondaires = models.ManyToManyField(
        "strategy.ElementStrategique", blank=True, related_name="activites_secondaires",
        help_text="Autres éléments stratégiques auxquels cet élément contribue aussi (informatif, non compté).",
    )
    structures = models.ManyToManyField(
        "partners.StructureOrganisation", blank=True, related_name="activites",
        help_text="Services de l'organisation chargés de cette partie du projet.",
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
    nb_jours_planifies = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Durée prévue en jours, calculée à l'enregistrement à partir des dates (bornes comprises : "
        "une activité qui commence et se termine le même jour dure 1 jour).",
    )
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

    def save(self, *args, **kwargs):
        if self.date_debut and self.date_fin:
            self.nb_jours_planifies = duree_en_jours(self.date_debut, self.date_fin)
        super().save(*args, **kwargs)

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
    attributs = models.JSONField(default=dict, blank=True, help_text="Attributs libres {nom: texte}, comme Activite.")
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


class TauxManuel(TimestampedModel, SaisieApprouvable):
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


class DemandeModification(TimestampedModel):
    """
    Changement de planification en attente d'approbation (projets avec
    approbation_planification, voir apps.projects.approbation) : ajout, modification ou
    suppression d'un élément ou d'une sous-activité, appliqué seulement une fois approuvé.
    """

    class Cible(models.TextChoices):
        ACTIVITE = "activite", "Élément de la planification"
        SOUS_ACTIVITE = "sous_activite", "Sous-activité"

    class Action(models.TextChoices):
        CREATION = "CREATION", "Ajout"
        MODIFICATION = "MODIFICATION", "Modification"
        SUPPRESSION = "SUPPRESSION", "Suppression"

    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name="demandes_modification")
    cible = models.CharField(max_length=20, choices=Cible.choices)
    cible_id = models.PositiveIntegerField(null=True, blank=True, help_text="Vide pour un ajout.")
    action = models.CharField(max_length=20, choices=Action.choices)
    libelle = models.CharField(max_length=300, help_text="Élément concerné, au moment de la demande.")
    donnees = models.JSONField(default=dict, blank=True, help_text="Valeurs demandées (telles que saisies).")
    changements = models.JSONField(
        default=list, blank=True, help_text="[{champ, avant, apres}] pour affichage (modification)."
    )
    etat = models.CharField(max_length=20, choices=EtatApprobation.choices, default=EtatApprobation.EN_ATTENTE)
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    traite_le = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Demande de modification"
        verbose_name_plural = "Demandes de modification"

    def __str__(self):
        return f"{self.get_action_display()} — {self.libelle}"


class PartenaireProjet(TimestampedModel):
    """
    Rôle d'un partenaire (consortium ou mise en œuvre) dans un projet et éléments de la
    planification (objectifs, résultats, activités…) qu'il doit réaliser.
    """

    class Nature(models.TextChoices):
        MISE_EN_OEUVRE = "MISE_EN_OEUVRE", "Mise en œuvre"
        CONSORTIUM = "CONSORTIUM", "Consortium"

    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name="roles_partenaires")
    partenaire = models.ForeignKey("partners.Partenaire", on_delete=models.PROTECT, related_name="roles_projets")
    nature = models.CharField(max_length=20, choices=Nature.choices, default=Nature.CONSORTIUM)
    chef_de_file = models.BooleanField(default=False)
    role = models.TextField(blank=True, help_text="Rôle et responsabilités du partenaire dans le projet.")
    elements = models.ManyToManyField(
        Activite, blank=True, related_name="partenaires_charges",
        help_text="Éléments de la planification que ce partenaire réalise (tout ce qui est en dessous en fait partie).",
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ("-chef_de_file", "partenaire__nom")
        constraints = [models.UniqueConstraint(fields=("projet", "partenaire"), name="partenaire_projet_unique")]

    def __str__(self):
        return f"{self.partenaire} — {self.projet.code}"


class Risque(TimestampedModel):
    """
    Risque (interne ou externe) de la mise en œuvre d'un projet : identifié et coté (probabilité
    × impact, de 1 à 5), avec ses mesures, puis suivi par des réévaluations successives
    (EvaluationRisque) — la dernière donne son état courant.
    """

    class Nature(models.TextChoices):
        INTERNE = "INTERNE", "Interne"
        EXTERNE = "EXTERNE", "Externe"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif (à surveiller)"
        SURVENU = "SURVENU", "Survenu"
        MAITRISE = "MAITRISE", "Maîtrisé"
        CLOS = "CLOS", "Clos"

    CATEGORIES = (
        "Financier", "Opérationnel", "Sécuritaire", "Politique et institutionnel", "Climatique et environnemental",
        "Social et communautaire", "Sanitaire", "Juridique", "Fiduciaire", "Autre",
    )

    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name="risques")
    code = models.CharField(max_length=20, blank=True)
    libelle = models.CharField(max_length=300)
    description = models.TextField(blank=True, help_text="Causes et conséquences possibles.")
    nature = models.CharField(max_length=10, choices=Nature.choices, default=Nature.EXTERNE)
    categorie = models.CharField(max_length=60, blank=True)
    element = models.ForeignKey(
        Activite, null=True, blank=True, on_delete=models.SET_NULL, related_name="risques",
        help_text="Élément de la planification le plus exposé (facultatif).",
    )
    probabilite = models.PositiveSmallIntegerField(default=3, help_text="1 (rare) à 5 (quasi certain).")
    impact = models.PositiveSmallIntegerField(default=3, help_text="1 (négligeable) à 5 (majeur).")
    mesures_attenuation = models.TextField(blank=True, help_text="Ce qui est prévu pour réduire la probabilité ou l'impact.")
    plan_contingence = models.TextField(blank=True, help_text="Ce qui sera fait si le risque survient.")
    responsable = models.ForeignKey(
        "intervenants.Intervenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="risques_suivis",
        help_text="Personne chargée de surveiller le risque (comme les responsables d'activités).",
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    date_identification = models.DateField(default=datetime.date.today)
    date_prochaine_revue = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("projet", "code", "id")
        constraints = [
            models.CheckConstraint(check=models.Q(probabilite__gte=1, probabilite__lte=5), name="risque_probabilite_1_5"),
            models.CheckConstraint(check=models.Q(impact__gte=1, impact__lte=5), name="risque_impact_1_5"),
        ]

    def __str__(self):
        return f"{self.code} {self.libelle}".strip()

    @property
    def criticite(self) -> int:
        return self.probabilite * self.impact

    @staticmethod
    def niveau_pour(criticite: int) -> str:
        """FAIBLE (1-4), MOYEN (5-9), ELEVE (10-15), CRITIQUE (16-25)."""
        if criticite >= 16:
            return "CRITIQUE"
        if criticite >= 10:
            return "ELEVE"
        if criticite >= 5:
            return "MOYEN"
        return "FAIBLE"

    @property
    def niveau(self) -> str:
        return self.niveau_pour(self.criticite)

    def save(self, *args, **kwargs):
        if not self.code and self.projet_id:
            # R1, R2… : le numéro suit le plus grand existant (pas de doublon après une suppression au milieu).
            numeros = [
                int(c[1:]) for c in Risque.objects.filter(projet_id=self.projet_id).values_list("code", flat=True)
                if c[:1] == "R" and c[1:].isdigit()
            ]
            self.code = f"R{max(numeros, default=0) + 1}"
        super().save(*args, **kwargs)


class EvaluationRisque(TimestampedModel):
    """Réévaluation d'un risque à une date : sa cotation, son statut et les actions menées."""

    risque = models.ForeignKey(Risque, on_delete=models.CASCADE, related_name="evaluations")
    date = models.DateField(default=datetime.date.today)
    probabilite = models.PositiveSmallIntegerField()
    impact = models.PositiveSmallIntegerField()
    statut = models.CharField(max_length=10, choices=Risque.Statut.choices)
    actions_menees = models.TextField(blank=True)
    commentaire = models.TextField(blank=True)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="evaluations_risques"
    )

    class Meta:
        ordering = ("-date", "-id")
        constraints = [
            models.CheckConstraint(check=models.Q(probabilite__gte=1, probabilite__lte=5), name="evaluation_probabilite_1_5"),
            models.CheckConstraint(check=models.Q(impact__gte=1, impact__lte=5), name="evaluation_impact_1_5"),
        ]

    def __str__(self):
        return f"{self.risque} au {self.date}"
