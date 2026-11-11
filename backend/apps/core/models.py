from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class TimestampedModel(models.Model):
    """Ajoute created_at/updated_at à tout modèle qui en hérite."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EtatApprobation(models.TextChoices):
    APPROUVEE = "APPROUVEE", "Approuvée"
    EN_ATTENTE = "EN_ATTENTE", "En attente d'approbation"
    REJETEE = "REJETEE", "Rejetée"


class SaisiesApprouveesManager(models.Manager):
    """Gestionnaire par défaut : seules les saisies approuvées comptent (taux, cumuls, exports…)."""

    def get_queryset(self):
        return super().get_queryset().filter(etat_approbation=EtatApprobation.APPROUVEE)


class SaisieApprouvable(models.Model):
    """
    Saisie de réalisation soumise, si le projet l'exige, à approbation (voir
    apps.projects.approbation). `objects` ne renvoie que les saisies approuvées, pour que
    rien d'autre ne compte dans les calculs ; `tous` renvoie aussi celles en attente ou
    rejetées (écran d'approbation, modification, suppression).
    """

    etat_approbation = models.CharField(
        max_length=20, choices=EtatApprobation.choices, default=EtatApprobation.APPROUVEE, db_index=True
    )
    approbation_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approbation_le = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True)

    objects = SaisiesApprouveesManager()
    tous = models.Manager()

    class Meta:
        abstract = True



# Langues de l'interface (le français est la langue source des textes).
LANGUES = (("fr", "Français"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("de", "Deutsch"), ("it", "Italiano"))
CODES_LANGUES = tuple(code for code, _ in LANGUES)


class TraductionCorrigee(TimestampedModel):
    """
    Traduction d'un texte de l'interface corrigée par l'Administrateur : elle remplace celle
    fournie avec l'application (`source` : le texte français tel qu'il est dans le code).
    """

    langue = models.CharField(max_length=5, choices=LANGUES)
    source = models.TextField()
    traduction = models.TextField()
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("langue", "source"), name="traduction_langue_source_unique")]

    def __str__(self):
        return f"[{self.langue}] {self.source[:40]}"


class EvenementAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Le journal d'audit ne se modifie pas.")

    def delete(self):
        raise PermissionError("Le journal d'audit ne se supprime pas.")


class EvenementAudit(models.Model):
    """
    Journal d'audit en ajout uniquement (apps.core.audit) : aucune interface, API ni méthode ne permet de
    modifier ou de supprimer un événement, et la base le refuse aussi (déclencheur, migration 0003).
    Jamais de contenu protégé : l'objet désigne un élément (numéro de dossier, réglage), sans son contenu.
    La personne est gardée par son identifiant et son nom au moment de l'événement (pas de clé
    étrangère : supprimer un compte ne doit rien modifier ici).
    """

    class Action(models.TextChoices):
        CONNEXION = "CONNEXION", "Connexion"
        CONNEXION_ECHOUEE = "CONNEXION_ECHOUEE", "Connexion refusée"
        CONSULTATION_SENSIBLE = "CONSULTATION_SENSIBLE", "Consultation d'un dossier confidentiel"
        DOSSIER = "DOSSIER", "Action sur un dossier"
        TELECHARGEMENT = "TELECHARGEMENT", "Téléchargement d'une pièce jointe"
        EXPORT = "EXPORT", "Export"
        CONFIGURATION = "CONFIGURATION", "Modification de la configuration"
        PERMISSION = "PERMISSION", "Modification des droits d'un compte"
        HABILITATION = "HABILITATION", "Habilitation confidentielle"
        DROITS_PERSONNES = "DROITS_PERSONNES", "Demande d'une personne sur ses données"
        DOUBLE_AUTHENTIFICATION = "DOUBLE_AUTHENTIFICATION", "Double authentification"
        PARTAGE = "PARTAGE", "Partage d'un document par lien"
        MOT_DE_PASSE = "MOT_DE_PASSE", "Mot de passe oublié"
        SUPPRESSION = "SUPPRESSION", "Suppression"

    date = models.DateTimeField(auto_now_add=True, db_index=True)
    utilisateur_id = models.IntegerField(null=True, blank=True, db_index=True)
    utilisateur = models.CharField(max_length=200, blank=True, help_text="Nom et identifiant au moment de l'événement.")
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    module = models.CharField(max_length=40, blank=True)
    objet = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)

    objects = EvenementAuditQuerySet.as_manager()

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = "Événement du journal d'audit"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Le journal d'audit ne se modifie pas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Le journal d'audit ne se supprime pas.")


class IdentiteOrganisation(models.Model):
    """
    Identité de l'organisation qui utilise la plateforme (une seule ligne : IdentiteOrganisation.courante()) :
    nom et logo affichés dans l'en-tête et sur la page de connexion. Réglée par l'Administrateur.
    """

    nom = models.CharField(max_length=200, blank=True, help_text="Nom affiché (ex : ONG Exemple).")
    logo = models.ImageField(upload_to="identite/", blank=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Identité de l'organisation"

    @classmethod
    def courante(cls):
        identite, _ = cls.objects.get_or_create(pk=1)
        return identite
