"""
Mécanisme de gestion des plaintes et retours (MGPR) — lot 1 : paramétrage.

Une installation de la plateforme = une organisation, qui règle elle-même son mécanisme : types
de retours, catégories (dont les catégories sensibles), priorités et délais, circuits de
traitement par étapes avec leurs responsables. Tout est paramétrable, sauf ce qui protège les
personnes (catégories liées à l'exploitation et aux abus sexuels, existence d'un circuit
confidentiel, contrôles d'activation : voir controles.py).

Lot 2 : réception des dossiers (formulaire public et saisie par un agent, voir reception.py).
Lot 3 : traitement (affectation, étapes, décision, communication, clôture, réouverture, recours,
journal, dossiers liés, vues enregistrées ; voir traitement.py).
Lot 4 : délais et alertes (échéances du dossier et de l'étape, jours ouvrés et jours fériés,
rappels, escalade, prolongation motivée, notifications ; voir delais.py).
Lot 5 : circuit confidentiel complet (marquage manuel et levée motivée, personnes mises en cause
et circuit alternatif, chiffrement des données protégées — chiffrement.py —, assistance et
référencement, export motivé, conservation et suspension légale ; voir confidentiel.py).
Lot 6 : pilotage (indicateurs, tableaux de bord personnalisables, exports, actions correctives,
encart projet ; voir pilotage.py).
Lot 7 : messages au plaignant (modèles multilingues, envoi par courriel et SMS, accusé de réception
automatique ; voir messages.py).
Lot 8 : pièces jointes (chiffrées, type réel contrôlé, métadonnées effacées, liens de 5 minutes) et
compléments du plaignant depuis la page de suivi ; voir pieces.py.
Lot 9 : habilitation confidentielle à double validation (habilitations.py), journal d'audit
(apps.core.audit), demandes des personnes sur leurs données et registre des traitements (droits.py).
"""
import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimestampedModel

from .chiffrement import TexteChiffre


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
    anonymisation_automatique = models.BooleanField(
        default=False, help_text="Anonymiser sans intervention les dossiers dont la durée de conservation est écoulée "
        "(sinon : liste « À anonymiser », confirmation dossier par dossier).",
    )
    texte_consentement = models.TextField(
        blank=True, help_text="Clause de consentement (RGPD) affichée sur le formulaire public ; vide : phrase par défaut.",
    )
    projets = models.ManyToManyField(
        "projects.Projet", blank=True, related_name="mecanismes_plaintes",
        help_text="Projets couverts ; aucun = tous les projets.",
    )
    # Délais et alertes (lot 4).
    delai_defaut_jours = models.PositiveIntegerField(
        default=30, help_text="Délai de traitement quand ni la catégorie ni la priorité n'en fixent.",
    )
    rappel_jours_avant = models.PositiveSmallIntegerField(
        default=2, help_text="Rappel au gestionnaire quand l'échéance approche (jours avant).",
    )
    escalade_active = models.BooleanField(
        default=True, help_text="Un dossier en retard est signalé aussi aux superviseurs.",
    )
    notifications_courriel = models.BooleanField(
        default=True, help_text="Envoyer aussi les notifications par courriel (en plus de l'application).",
    )
    accuse_reception_auto = models.BooleanField(
        default=True, help_text="Envoyer automatiquement un accusé de réception au plaignant joignable.",
    )
    signature_messages = models.CharField(
        max_length=255, blank=True, help_text="Signature ajoutée à la fin des messages (ex : « L'équipe du projet »).",
    )
    seuil_masquage = models.PositiveSmallIntegerField(
        default=5, help_text="Tableaux de bord : une case comptant moins de dossiers confidentiels que ce seuil "
        "est affichée « moins de N ». Jamais en dessous de 5.",
    )
    circuit_alternatif = models.ForeignKey(
        "Circuit", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Circuit confidentiel suivi quand une personne mise en cause est destinataire du circuit "
        "confidentiel habituel (direction, siège, référent extérieur…). Obligatoire pour l'activation.",
    )

    # Protection des données (lot 9) : figurent dans le registre des traitements.
    responsable_traitement = models.CharField(
        max_length=255, blank=True, help_text="Organisation responsable du traitement (nom, adresse).",
    )
    contact_donnees = models.CharField(
        max_length=255, blank=True, help_text="Contact pour les questions et demandes sur les données personnelles.",
    )
    # Pièces jointes (lot 8).
    pieces_formulaire_public = models.BooleanField(
        default=True, help_text="Le plaignant peut joindre des fichiers au formulaire public et à un complément.",
    )
    taille_max_piece_mo = models.PositiveSmallIntegerField(
        default=10, help_text="Taille maximale d'un fichier joint, en Mo (jamais au-dessus du plafond de la plateforme).",
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
    lieu = TexteChiffre(blank=True)
    description = TexteChiffre()
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
    nom = TexteChiffre(blank=True)
    telephone = TexteChiffre(blank=True)
    courriel = TexteChiffre(blank=True)
    mode_reponse = models.CharField(max_length=20, choices=ModeReponse.choices, default=ModeReponse.AUCUN)
    consentement = models.BooleanField(
        default=False, help_text="Accord du plaignant pour l'utilisation de ses informations dans le traitement.",
    )
    consentement_texte = models.TextField(blank=True, help_text="Texte exact accepté par le plaignant (preuve du consentement).")
    consentement_le = models.DateTimeField(null=True, blank=True)
    langue = models.CharField(max_length=5, blank=True)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dossiers_plaintes_saisis",
    )

    # Traitement (lot 3).
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dossiers_plaintes_geres",
        help_text="Gestionnaire du dossier.",
    )
    decision = TexteChiffre(blank=True, help_text="Décision enregistrée (exigée pour clôturer).")
    date_decision = models.DateField(null=True, blank=True)
    date_reponse = models.DateField(null=True, blank=True, help_text="Date à laquelle la décision a été communiquée.")
    issue = models.CharField(max_length=20, choices=IssueDossier.choices, blank=True)
    motif_cloture = TexteChiffre(blank=True)
    retour_donne = models.BooleanField(null=True, blank=True, help_text="Le plaignant a été informé de la réponse.")
    raison_sans_retour = TexteChiffre(blank=True, help_text="Pourquoi le plaignant n'a pas pu être informé.")
    oriente_vers = models.CharField(max_length=255, blank=True, help_text="Sortie « Référée » : acteur externe.")
    consentement_reference = models.BooleanField(default=False)
    date_cloture = models.DateField(null=True, blank=True)
    en_recours = models.BooleanField(default=False, help_text="Le plaignant conteste la réponse : réexamen en cours.")
    gestionnaire_initial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Premier gestionnaire : le recours est réexaminé par une autre personne.",
    )
    dossiers_lies = models.ManyToManyField("self", blank=True, symmetrical=True)

    # Délais (lot 4) : recalculés à chaque changement (delais.recalculer), contrôlés par la tâche planifiée.
    echeance = models.DateField(null=True, blank=True, help_text="Échéance de traitement du dossier.")
    date_entree_etape = models.DateField(null=True, blank=True)
    echeance_etape = models.DateField(null=True, blank=True, help_text="Échéance de l'étape en cours.")
    jours_prolongation = models.PositiveIntegerField(default=0)
    en_retard = models.BooleanField(default=False, help_text="Échéance dépassée (mis à jour par la tâche planifiée).")

    # Circuit confidentiel (lot 5).
    mis_en_cause_utilisateurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="dossiers_plaintes_mis_en_cause",
        help_text="Utilisateurs mis en cause : exclus du dossier, de ses notifications et de son traitement.",
    )
    mis_en_cause_libre = TexteChiffre(blank=True, help_text="Personnes mises en cause qui n'ont pas de compte.")
    suspension_legale = models.BooleanField(default=False, help_text="Lié à une procédure : jamais anonymisé.")
    motif_suspension = TexteChiffre(blank=True)
    anonymise = models.BooleanField(default=False)
    date_anonymisation = models.DateField(null=True, blank=True)

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
        PROLONGATION = "PROLONGATION", "Prolongation du délai"
        RETARD = "RETARD", "Retard"
        MISE_EN_CAUSE = "MISE_EN_CAUSE", "Personnes mises en cause"
        ASSISTANCE = "ASSISTANCE", "Assistance et référencement"
        EXPORT = "EXPORT", "Export de la fiche"
        SUSPENSION = "SUSPENSION", "Suspension légale"
        ANONYMISATION = "ANONYMISATION", "Anonymisation"
        PLAIGNANT = "PLAIGNANT", "Correction du plaignant"
        PIECE_JOINTE = "PIECE_JOINTE", "Pièce jointe"
        TELECHARGEMENT = "TELECHARGEMENT", "Téléchargement d'une pièce jointe"
        COMPLEMENT = "COMPLEMENT", "Complément du plaignant"

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
    texte = TexteChiffre(blank=True)
    # Changement enregistré, lisible tel quel : {"de": …, "a": …} ou valeurs de la clôture.
    details = models.JSONField(default=dict, blank=True)
    # Communication avec le plaignant.
    sens = models.CharField(max_length=10, choices=Sens.choices, blank=True)
    canal = models.CharField(max_length=20, choices=ModeReponse.choices, blank=True)
    objet = models.CharField(max_length=20, choices=Objet.choices, blank=True)

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = "Action sur un dossier"


class PieceJointe(models.Model):
    """
    Fichier joint à un dossier. Le contenu est toujours chiffré, dans un répertoire privé hors de toute
    racine web (PLAINTES_STOCKAGE_PRIVE) ; il n'est servi que par un lien temporaire, après contrôle
    d'accès (pieces.py). Le nom d'origine est chiffré lui aussi : il peut révéler une identité.
    """

    class Source(models.TextChoices):
        PLAIGNANT = "PLAIGNANT", "Déposée par le plaignant"
        EQUIPE = "EQUIPE", "Ajoutée par l'équipe"

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="pieces")
    nom = TexteChiffre()
    type_mime = models.CharField(max_length=100)
    taille = models.PositiveIntegerField(help_text="Taille du fichier en octets (après effacement des métadonnées).")
    source = models.CharField(max_length=10, choices=Source.choices)
    ajoute_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    date = models.DateTimeField(auto_now_add=True)
    metadonnees_effacees = models.BooleanField(
        default=False, help_text="Métadonnées retirées (photos, documents Office) ; sinon le format n'en permet pas l'effacement.",
    )

    class Meta:
        ordering = ("date", "id")
        verbose_name = "Pièce jointe"

    def __str__(self):
        return f"{self.dossier.numero} — pièce {self.pk}"


class HabilitationSensible(models.Model):
    """
    Habilitation aux dossiers confidentiels (habilitations.py) : distincte des rôles, demandée par une
    personne et validée par une deuxième déjà habilitée (ou Administrateur) ; jamais par soi-même. Pour
    la toute première habilitation de l'organisation (aucun valideur possible), confirmation par un code
    envoyé par courriel à la personne qui la demande, puis délai de sécurité de 24 heures.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        EN_DELAI = "EN_DELAI", "Confirmée, active après le délai de sécurité"
        ACTIVE = "ACTIVE", "Active"
        REFUSEE = "REFUSEE", "Refusée"
        RETIREE = "RETIREE", "Retirée"

    EN_COURS = (Statut.EN_ATTENTE, Statut.EN_DELAI, Statut.ACTIVE)

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habilitations_sensibles")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    motif = models.TextField(help_text="Pourquoi cette personne doit accéder aux dossiers confidentiels.")
    demandee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    date_demande = models.DateTimeField(auto_now_add=True)
    premiere = models.BooleanField(default=False, help_text="Première habilitation : confirmation par courriel et délai.")
    empreinte_code = models.CharField(max_length=64, blank=True, help_text="Empreinte du code de confirmation envoyé.")
    validee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    date_validation = models.DateTimeField(null=True, blank=True)
    active_le = models.DateTimeField(null=True, blank=True, help_text="Début d'effet (après le délai pour une première).")
    commentaire_validation = models.TextField(blank=True)
    retiree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    date_retrait = models.DateTimeField(null=True, blank=True)
    motif_retrait = models.TextField(blank=True)

    class Meta:
        ordering = ("-date_demande", "-id")
        verbose_name = "Habilitation confidentielle"
        constraints = [
            models.UniqueConstraint(fields=["utilisateur"], condition=models.Q(statut__in=["EN_ATTENTE", "EN_DELAI", "ACTIVE"]),
                                    name="une_habilitation_en_cours_par_personne"),
        ]

    def __str__(self):
        return f"{self.utilisateur} — {self.get_statut_display()}"


class DemandeDroits(models.Model):
    """
    Demande d'une personne sur ses données (accès, rectification, effacement, opposition) : procédure
    tracée (droits.py), réponse attendue sous un mois. Les coordonnées et le contenu sont chiffrés.
    """

    class Type(models.TextChoices):
        ACCES = "ACCES", "Accès à ses données"
        RECTIFICATION = "RECTIFICATION", "Rectification"
        EFFACEMENT = "EFFACEMENT", "Effacement"
        OPPOSITION = "OPPOSITION", "Opposition au traitement"

    class Statut(models.TextChoices):
        RECUE = "RECUE", "Reçue"
        EN_COURS = "EN_COURS", "En cours"
        SATISFAITE = "SATISFAITE", "Satisfaite"
        REFUSEE = "REFUSEE", "Refusée (motivée)"

    type = models.CharField(max_length=15, choices=Type.choices)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.RECUE)
    date_reception = models.DateField()
    echeance = models.DateField(help_text="Réponse attendue au plus tard (un mois après la réception).")
    demandeur = TexteChiffre(help_text="Nom de la personne qui exerce son droit.")
    contact = TexteChiffre(blank=True)
    description = TexteChiffre(blank=True)
    dossier = models.ForeignKey(Dossier, on_delete=models.SET_NULL, null=True, blank=True, related_name="demandes_droits")
    numero_dossier = models.CharField(max_length=40, blank=True, help_text="Gardé si le dossier est supprimé.")
    reponse = TexteChiffre(blank=True)
    date_reponse = models.DateField(null=True, blank=True)
    enregistree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    traitee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date_reception", "-id")
        verbose_name = "Demande sur les données personnelles"


class VueDossiers(models.Model):
    """Filtres enregistrés par un utilisateur pour la liste des dossiers (« Mes vues »)."""

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vues_plaintes")
    nom = models.CharField(max_length=100)
    filtres = models.JSONField(default=dict)

    class Meta:
        ordering = ("nom",)
        constraints = [models.UniqueConstraint(fields=("utilisateur", "nom"), name="vue_plaintes_unique_par_utilisateur")]


class JourFerie(models.Model):
    """Jours fériés de l'organisation : exclus du calcul des délais en jours ouvrés."""

    date = models.DateField(unique=True)
    libelle = models.CharField(max_length=150)

    class Meta:
        ordering = ("date",)
        verbose_name = "Jour férié"

    def __str__(self):
        return f"{self.date} — {self.libelle}"


class RappelDossier(models.Model):
    """Rappel envoyé pour un dossier : au plus un par dossier et par jour (pas de rappel en double)."""

    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="rappels")
    date = models.DateField()
    motif = models.CharField(max_length=20)  # PROCHE, RETARD

    class Meta:
        constraints = [models.UniqueConstraint(fields=("dossier", "date"), name="un_rappel_par_dossier_et_par_jour")]


class Prestataire(TimestampedModel):
    """Annuaire des prestataires d'assistance tenu par l'organisation (référencement des victimes)."""

    class Type(models.TextChoices):
        MEDICAL = "MEDICAL", "Médical"
        PSYCHOSOCIAL = "PSYCHOSOCIAL", "Psychosocial"
        JURIDIQUE = "JURIDIQUE", "Juridique"
        SECURITE = "SECURITE", "Sécurité et hébergement"
        AUTRE = "AUTRE", "Autre"

    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices)
    contact = models.CharField(max_length=255, blank=True)
    zone = models.CharField(max_length=200, blank=True, help_text="Zone couverte.")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ("type", "nom")

    def __str__(self):
        return self.nom


class Referencement(models.Model):
    """
    Orientation vers une assistance (médicale, psychosociale, juridique, sécurité), avec le
    consentement de la personne. On enregistre le consentement, la date et le prestataire — jamais
    le contenu des échanges avec lui.
    """

    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="referencements")
    prestataire = models.ForeignKey(Prestataire, on_delete=models.PROTECT, related_name="referencements")
    type = models.CharField(max_length=20, choices=Prestataire.Type.choices)
    consentement = models.BooleanField()
    date = models.DateField()
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        ordering = ("-date", "-id")


class ActionCorrective(TimestampedModel):
    """Action corrective décidée à la suite de plaintes : suivie (responsable, échéance, statut), reliée à plusieurs dossiers."""

    class Statut(models.TextChoices):
        A_FAIRE = "A_FAIRE", "À faire"
        EN_COURS = "EN_COURS", "En cours"
        REALISEE = "REALISEE", "Réalisée"
        ABANDONNEE = "ABANDONNEE", "Abandonnée"

    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    projet = models.ForeignKey("projects.Projet", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="actions_correctives_plaintes")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="actions_correctives_plaintes")
    echeance = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.A_FAIRE)
    date_realisation = models.DateField(null=True, blank=True)
    dossiers = models.ManyToManyField(Dossier, blank=True, related_name="actions_correctives")
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        ordering = ("statut", "echeance", "-id")

    def __str__(self):
        return self.titre


class TableauPlaintes(models.Model):
    """
    Composition d'une vue du tableau de bord (éléments et types de graphiques). Utilisateur vide :
    vue de l'organisation ; sinon copie personnelle, qui ne change rien pour les autres.
    """

    vue = models.CharField(max_length=30)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name="tableaux_plaintes")
    elements = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("vue", "utilisateur"), name="tableau_plaintes_unique",
                                               nulls_distinct=False)]


class ModeleMessage(TimestampedModel):
    """
    Modèle de message au plaignant, par objet et par langue, avec une version courriel et une version
    SMS. Variables : {numero}, {nom}, {mecanisme}, {date_reception}, {lien_suivi}, {decision}, {signature}.
    Pour un dossier confidentiel, {decision} n'est jamais remplacée par la décision (aucun détail).
    """

    OBJETS = [c for c in ActionDossier.Objet.choices if c[0] != "AUTRE"]

    objet = models.CharField(max_length=20, choices=OBJETS)
    langue = models.CharField(max_length=5, default="fr")
    sujet = models.CharField(max_length=200, blank=True, help_text="Objet du courriel.")
    texte_courriel = models.TextField(blank=True)
    texte_sms = models.CharField(max_length=480, blank=True, help_text="Court : 160 caractères par SMS.")
    actif = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("objet", "langue")
        constraints = [models.UniqueConstraint(fields=("objet", "langue"), name="modele_message_unique")]

    def __str__(self):
        return f"{self.get_objet_display()} ({self.langue})"
