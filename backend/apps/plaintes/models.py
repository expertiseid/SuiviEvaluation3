"""
Mécanisme de gestion des plaintes et retours (MGPR) — lot 1 : paramétrage.

Une installation de la plateforme = une organisation, qui règle elle-même son mécanisme : types
de retours, catégories (dont les catégories sensibles), priorités et délais, circuits de
traitement par étapes avec leurs responsables. Tout est paramétrable, sauf ce qui protège les
personnes (catégories liées à l'exploitation et aux abus sexuels, existence d'un circuit
confidentiel, contrôles d'activation : voir controles.py).

Lot 2 : réception des dossiers (formulaire public et saisie par un agent, voir reception.py).
Lot 3 : traitement (affectation, étapes, décision, communication, clôture, réouverture, recours,
journal, dossiers liés, vues enregistrées ; voir traitement.py). Les délais, le circuit
confidentiel complet et le pilotage arrivent dans les lots suivants.
"""
import uuid

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


class Canal(models.TextChoices):
    """Canal par lequel le retour est arrivé (formulaire public, ou saisi par un agent)."""

    FORMULAIRE = "FORMULAIRE", "Formulaire public"
    TELEPHONE = "TELEPHONE", "Téléphone"
    EN_PERSONNE = "EN_PERSONNE", "En personne, sur le terrain"
    REUNION = "REUNION", "Réunion communautaire"
    BOITE = "BOITE", "Boîte à suggestions"
    COURRIER = "COURRIER", "Courrier"
    COURRIEL = "COURRIEL", "Courriel"
    AUTRE = "AUTRE", "Autre"


class StatutDossier(models.TextChoices):
    """État général, le seul que voit le plaignant sur la page de suivi."""

    RECU = "RECU", "Reçu"
    EN_COURS = "EN_COURS", "En cours de traitement"
    REPONDU = "REPONDU", "Réponse donnée"
    CLOTURE = "CLOTURE", "Clôturé"


class ModeReponse(models.TextChoices):
    AUCUN = "AUCUN", "Pas de réponse souhaitée"
    TELEPHONE = "TELEPHONE", "Par téléphone"
    SMS = "SMS", "Par SMS"
    COURRIEL = "COURRIEL", "Par courriel"
    EN_PERSONNE = "EN_PERSONNE", "En personne"


class IssueDossier(models.TextChoices):
    """Issue d'un dossier clôturé, dont les sorties particulières Référée et Hors périmètre."""

    RESOLU = "RESOLU", "Réponse apportée"
    NON_FONDE = "NON_FONDE", "Non fondé"
    REFERE = "REFERE", "Référé à un acteur externe"
    HORS_PERIMETRE = "HORS_PERIMETRE", "Hors périmètre"
    SANS_SUITE = "SANS_SUITE", "Sans suite (plaignant injoignable, abandon…)"


class CompteurDossiers(models.Model):
    """Séquence des numéros de dossier, par année (verrouillée à chaque réception)."""

    annee = models.PositiveIntegerField(unique=True)
    dernier = models.PositiveIntegerField(default=0)


class Dossier(TimestampedModel):
    """
    Un retour reçu. Le numéro (préfixe-année-séquence) et l'identifiant interne ne contiennent
    aucune donnée personnelle ; le code de suivi remis au plaignant n'est conservé que sous forme
    d'empreinte et ne donne accès qu'à l'état général (statut).
    """

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    numero = models.CharField(max_length=40, unique=True, editable=False)
    empreinte_code_suivi = models.CharField(max_length=64, unique=True, editable=False)

    canal = models.CharField(max_length=20, choices=Canal.choices)
    date_reception = models.DateField(help_text="Date réelle de réception (saisie par l'agent).")
    recueilli_directement = models.BooleanField(
        null=True, blank=True, help_text="Recueilli directement auprès du plaignant (saisie par un agent).",
    )

    type_retour = models.ForeignKey(TypeRetour, on_delete=models.PROTECT, related_name="dossiers")
    categorie = models.ForeignKey(
        "Categorie", on_delete=models.PROTECT, null=True, blank=True, related_name="dossiers",
        help_text="Vide : à classer.",
    )
    priorite = models.ForeignKey(Priorite, on_delete=models.PROTECT, null=True, blank=True, related_name="dossiers")
    projet = models.ForeignKey(
        "projects.Projet", on_delete=models.SET_NULL, null=True, blank=True, related_name="dossiers_plaintes",
    )
    lieu = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    concerne_personnel = models.BooleanField(
        null=True, blank=True,
        help_text="Question système : le retour concerne-t-il le comportement d'un membre du personnel ou d'un "
        "partenaire ? (oui = sensible ; vide = ne sait pas).",
    )
    sensible = models.BooleanField(default=False)
    circuit = models.ForeignKey(Circuit, on_delete=models.PROTECT, null=True, blank=True, related_name="dossiers")
    etape = models.ForeignKey(EtapeCircuit, on_delete=models.SET_NULL, null=True, blank=True, related_name="dossiers")
    statut = models.CharField(max_length=20, choices=StatutDossier.choices, default=StatutDossier.RECU)

    # Coordonnées : toujours facultatives quand l'anonymat est autorisé ; vides si anonyme.
    anonyme = models.BooleanField(default=False)
    nom = models.CharField(max_length=200, blank=True)
    telephone = models.CharField(max_length=40, blank=True)
    courriel = models.EmailField(blank=True)
    mode_reponse = models.CharField(max_length=20, choices=ModeReponse.choices, default=ModeReponse.AUCUN)
    consentement = models.BooleanField(
        default=False, help_text="Accord du plaignant pour l'utilisation de ses informations dans le traitement.",
    )
    langue = models.CharField(max_length=5, blank=True)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dossiers_plaintes_saisis",
    )

    # Traitement (lot 3).
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dossiers_plaintes_geres",
        help_text="Gestionnaire du dossier.",
    )
    decision = models.TextField(blank=True, help_text="Décision enregistrée (exigée pour clôturer).")
    date_decision = models.DateField(null=True, blank=True)
    date_reponse = models.DateField(null=True, blank=True, help_text="Date à laquelle la décision a été communiquée.")
    issue = models.CharField(max_length=20, choices=IssueDossier.choices, blank=True)
    motif_cloture = models.TextField(blank=True)
    retour_donne = models.BooleanField(null=True, blank=True, help_text="Le plaignant a été informé de la réponse.")
    raison_sans_retour = models.TextField(blank=True, help_text="Pourquoi le plaignant n'a pas pu être informé.")
    oriente_vers = models.CharField(max_length=255, blank=True, help_text="Sortie « Référée » : acteur externe.")
    consentement_reference = models.BooleanField(default=False)
    date_cloture = models.DateField(null=True, blank=True)
    en_recours = models.BooleanField(default=False, help_text="Le plaignant conteste la réponse : réexamen en cours.")
    gestionnaire_initial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Premier gestionnaire : le recours est réexaminé par une autre personne.",
    )
    dossiers_lies = models.ManyToManyField("self", blank=True, symmetrical=True)

    history = HistoricalRecords(excluded_fields=["dossiers_lies"])

    class Meta:
        ordering = ("-date_reception", "-id")
        verbose_name = "Dossier de plainte"

    def __str__(self):
        return self.numero


class ActionDossier(models.Model):
    """Journal du dossier : chaque action y laisse une trace datée et signée (jamais modifiée)."""

    class Type(models.TextChoices):
        RECEPTION = "RECEPTION", "Réception"
        CLASSIFICATION = "CLASSIFICATION", "Classification"
        AFFECTATION = "AFFECTATION", "Affectation"
        RECUSATION = "RECUSATION", "Récusation"
        ETAPE = "ETAPE", "Changement d'étape"
        NOTE = "NOTE", "Note interne"
        ACTION_CORRECTIVE = "ACTION_CORRECTIVE", "Action corrective"
        COMMUNICATION = "COMMUNICATION", "Communication avec le plaignant"
        DECISION = "DECISION", "Décision"
        CLOTURE = "CLOTURE", "Clôture"
        REOUVERTURE = "REOUVERTURE", "Réouverture"
        RECOURS = "RECOURS", "Recours"
        SENSIBILITE = "SENSIBILITE", "Sensibilité"
        LIEN = "LIEN", "Dossiers liés"

    class Sens(models.TextChoices):
        SORTANT = "SORTANT", "Envoyé au plaignant"
        ENTRANT = "ENTRANT", "Reçu du plaignant"

    class Objet(models.TextChoices):
        ACCUSE_RECEPTION = "ACCUSE_RECEPTION", "Accusé de réception"
        PRISE_EN_CHARGE = "PRISE_EN_CHARGE", "Information de prise en charge"
        DEMANDE_COMPLEMENT = "DEMANDE_COMPLEMENT", "Demande de complément"
        DECISION = "DECISION", "Communication de la décision"
        CLOTURE = "CLOTURE", "Confirmation de clôture"
        SATISFACTION = "SATISFACTION", "Enquête de satisfaction"
        AUTRE = "AUTRE", "Autre échange"

    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="actions")
    type = models.CharField(max_length=20, choices=Type.choices)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    date = models.DateTimeField(auto_now_add=True)
    texte = models.TextField(blank=True)
    # Changement enregistré, lisible tel quel : {"de": …, "a": …} ou valeurs de la clôture.
    details = models.JSONField(default=dict, blank=True)
    # Communication avec le plaignant.
    sens = models.CharField(max_length=10, choices=Sens.choices, blank=True)
    canal = models.CharField(max_length=20, choices=ModeReponse.choices, blank=True)
    objet = models.CharField(max_length=20, choices=Objet.choices, blank=True)

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = "Action sur un dossier"


class VueDossiers(models.Model):
    """Filtres enregistrés par un utilisateur pour la liste des dossiers (« Mes vues »)."""

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vues_plaintes")
    nom = models.CharField(max_length=100)
    filtres = models.JSONField(default=dict)

    class Meta:
        ordering = ("nom",)
        constraints = [models.UniqueConstraint(fields=("utilisateur", "nom"), name="vue_plaintes_unique_par_utilisateur")]
