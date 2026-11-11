"""
Registre central des organisations (base « central ») : la plateforme accueille plusieurs organisations
sur un même serveur, chacune avec son sous-domaine et sa propre base de données (apps.organisations.contexte).
"""
import re

from django.db import models

# Sous-domaines qui ne peuvent pas désigner une organisation.
RESERVES = {"www", "api", "admin", "app", "console", "mail", "smtp", "ftp", "static", "media", "plateforme",
            "expertise", "expertise-id", "support", "aide", "test", "dev", "staging", "central"}
FORME = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")  # 3 à 40 caractères


class Organisation(models.Model):
    """Une organisation cliente : son sous-domaine (ong-a.domaine), sa base, son état d'abonnement."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente d'activation"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDUE = "SUSPENDUE", "Suspendue"

    nom = models.CharField(max_length=200)
    sous_domaine = models.CharField(max_length=40, unique=True)
    base = models.CharField(max_length=63, unique=True, help_text="Nom de la base PostgreSQL de l'organisation.")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    offre = models.CharField(max_length=20, blank=True)
    stockage_go = models.DecimalField(
        max_digits=9, decimal_places=3, null=True, blank=True,
        help_text="Espace de stockage en Go fixé par Expertise-ID (0,01 = 10 Mo, pour un essai) ; vide : celui de l'offre (apps.organisations.quota).")
    stockage_alerte = models.PositiveSmallIntegerField(
        default=0, help_text="Dernier seuil d'alerte de stockage notifié (0, 90 ou 100 %), pour ne prévenir qu'une fois.")
    abonnement_fin = models.DateField(
        null=True, blank=True, help_text="Fin de la période payée ; ensuite 7 jours de grâce, puis accès bloqué jusqu'au paiement "
                                         "(apps.organisations.abonnement). Vide : sans échéance (partenariat, démonstration).")
    abonnement_prix_mois = models.PositiveIntegerField(
        null=True, blank=True, help_text="Prix d'un mois payé : sert à déduire ce qui reste lors d'un changement d'offre.")
    abonnement_alerte = models.PositiveSmallIntegerField(
        default=0, help_text="Dernière alerte de fin d'abonnement envoyée (1 : 7 jours avant, 2 : terminé, 3 : bloqué).")
    base_vide = models.PositiveBigIntegerField(
        null=True, blank=True,
        help_text="Taille (octets) de la base à la création de l'espace (tables, référentiel des zones) : elle n'est pas "
                  "comptée dans l'espace utilisé (apps.organisations.quota).")
    mode_demo = models.BooleanField(default=False, help_text="Organisation de démonstration : visiteur en lecture seule.")
    suppression_essai = models.JSONField(
        default=dict, blank=True,
        help_text="Essai gratuit non converti (essais.py) : {date de suppression prévue, avertissements envoyés, dernier}.",
    )
    courriel_contact = models.EmailField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    active_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("nom",)
        verbose_name = "Organisation"

    def __str__(self):
        return f"{self.nom} ({self.sous_domaine})"

    @staticmethod
    def nom_de_base(sous_domaine: str) -> str:
        return "org_" + sous_domaine.replace("-", "_")


class CompteOrganisation(models.Model):
    """
    Index de la base centrale : adresse courriel d'un compte → son organisation. La connexion se fait
    par courriel et mot de passe sur l'adresse unique de la plateforme ; cet index dit dans quelle base
    chercher le compte. Tenu à jour à chaque enregistrement d'un utilisateur (comptes.py). Une adresse
    n'appartient qu'à un seul compte de toute la plateforme.
    """

    courriel = models.CharField(max_length=254, unique=True, help_text="En minuscules.")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="comptes")
    utilisateur_id = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organisation", "utilisateur_id"), name="compte_unique_par_organisation")]
        verbose_name = "Compte d'une organisation"

    def __str__(self):
        return f"{self.courriel} → {self.organisation.sous_domaine}"


class PaiementAbonnement(models.Model):
    """
    Paiement en ligne (CinetPay, apps.organisations.paiement) d'un abonnement (payé, il crée aussitôt l'espace
    de l'organisation, sans validation d'Expertise-ID, qui peut ensuite le suspendre) ou de stockage
    supplémentaire (payé, l'espace de stockage de l'organisation est agrandi aussitôt).
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        PAYE = "PAYE", "Payé"
        ECHOUE = "ECHOUE", "Échoué ou abandonné"

    class Nature(models.TextChoices):
        ABONNEMENT = "ABONNEMENT", "Abonnement (inscription)"
        STOCKAGE = "STOCKAGE", "Stockage supplémentaire"
        RENOUVELLEMENT = "RENOUVELLEMENT", "Renouvellement ou changement d'offre"

    nature = models.CharField(max_length=14, choices=Nature.choices, default=Nature.ABONNEMENT)
    # Abonnement : la demande d'inscription ; stockage supplémentaire : l'organisation déjà ouverte.
    demande = models.ForeignKey("accounts.DemandeInscription", on_delete=models.CASCADE, related_name="paiements",
                                null=True, blank=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="paiements_stockage",
                                     null=True, blank=True)
    payeur = models.EmailField(blank=True, help_text="Stockage : adresse du compte qui a payé.")
    reference = models.CharField(max_length=30, unique=True, help_text="Référence envoyée à CinetPay (merchant_transaction_id).")
    offre = models.CharField(max_length=20)
    mois = models.PositiveSmallIntegerField(default=1)
    tranches = models.PositiveSmallIntegerField(default=0, help_text="Tranches de 10 Go de stockage ajoutées.")
    montant = models.PositiveIntegerField()
    deduction = models.PositiveIntegerField(default=0, help_text="Changement d'offre : ce qui restait de l'abonnement, déduit du prix.")
    devise = models.CharField(max_length=3)
    jeton_paiement = models.CharField(max_length=100, blank=True)
    jeton_notification = models.CharField(max_length=64, blank=True, help_text="Comparé à celui de chaque notification de CinetPay.")
    transaction = models.CharField(max_length=100, blank=True, help_text="Identifiant de la transaction chez CinetPay.")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    cree_le = models.DateTimeField(auto_now_add=True)
    paye_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-cree_le",)
        verbose_name = "Paiement d'abonnement"

    def __str__(self):
        return f"{self.reference} : {self.montant} {self.devise} ({self.get_statut_display()})"


# --- Site vitrine : actualités et partenaires (gérés dans la console Expertise-ID) -----------------

LANGUES_SITE = ("en", "ar", "es", "de", "it")


def chemin_site(instance, nom):
    """Fichiers du site, hors de tout espace d'organisation : MEDIA_ROOT/site/<type>/<nom>."""
    return f"site/{instance._meta.model_name}/{nom}"


class Actualite(models.Model):
    """
    Actualité du site vitrine (page « Notre actualité »). Rédigée en français ; traductions facultatives
    {langue: {titre, resume, contenu}} : une langue sans traduction affiche le français.
    """

    titre = models.CharField(max_length=200)
    resume = models.CharField(max_length=400, blank=True, help_text="Une ou deux phrases, affichées dans la liste.")
    contenu = models.TextField(blank=True, help_text="Paragraphes séparés par une ligne vide.")
    image = models.ImageField(upload_to=chemin_site, blank=True)
    lien = models.URLField(blank=True, help_text="Facultatif : « En savoir plus ».")
    date_publication = models.DateField()
    publiee = models.BooleanField(default=False, help_text="Brouillon tant que non publiée.")
    traductions = models.JSONField(default=dict, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date_publication", "-id")
        verbose_name = "Actualité du site"

    def __str__(self):
        return self.titre


class PartenaireSite(models.Model):
    """Partenaire affiché sur le site vitrine (page « Nos partenaires »)."""

    class Categorie(models.TextChoices):
        FINANCIER = "FINANCIER", "Partenaire financier"
        TECHNIQUE = "TECHNIQUE", "Partenaire technique"
        INSTITUTION = "INSTITUTION", "Institution"
        CLIENT = "CLIENT", "Organisation utilisatrice"

    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=12, choices=Categorie.choices, default=Categorie.TECHNIQUE)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to=chemin_site, blank=True)
    site_web = models.URLField(blank=True)
    ordre = models.PositiveIntegerField(default=0)
    visible = models.BooleanField(default=True)
    traductions = models.JSONField(default=dict, blank=True, help_text="{langue: {description}}")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ordre", "nom")
        verbose_name = "Partenaire du site"

    def __str__(self):
        return self.nom


class AbonneNewsletter(models.Model):
    """
    Abonné à la newsletter du site vitrine (apps.organisations.newsletter). Inscrit depuis le site, il ne
    reçoit rien tant qu'il n'a pas confirmé par le lien envoyé par courriel ; chaque envoi porte un lien
    de désinscription (le même jeton).
    """

    courriel = models.EmailField(unique=True, help_text="En minuscules.")
    langue = models.CharField(max_length=5, default="fr")
    jeton = models.CharField(max_length=64, unique=True, help_text="Lien de confirmation et de désinscription.")
    cree_le = models.DateTimeField(auto_now_add=True)
    confirme_le = models.DateTimeField(null=True, blank=True)
    desinscrit_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-cree_le",)
        verbose_name = "Abonné à la newsletter"

    def __str__(self):
        return self.courriel

    @property
    def statut(self) -> str:
        if self.desinscrit_le:
            return "DESINSCRIT"
        return "ACTIF" if self.confirme_le else "EN_ATTENTE"


class EnvoiNewsletter(models.Model):
    """
    Newsletter rédigée dans la console : en français, traductions facultatives {langue: {sujet, contenu}} ;
    chaque abonné la reçoit dans sa langue (le français si la traduction manque). Envoyée une seule fois.
    """

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        EN_COURS = "EN_COURS", "Envoi en cours"
        ENVOYE = "ENVOYE", "Envoyée"

    sujet = models.CharField(max_length=200)
    contenu = models.TextField(help_text="Paragraphes séparés par une ligne vide.")
    traductions = models.JSONField(default=dict, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    destinataires = models.PositiveIntegerField(default=0)
    envoyes = models.PositiveIntegerField(default=0)
    echecs = models.PositiveIntegerField(default=0)
    envoye_par = models.CharField(max_length=254, blank=True)
    envoye_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-cree_le",)
        verbose_name = "Envoi de la newsletter"

    def __str__(self):
        return self.sujet
