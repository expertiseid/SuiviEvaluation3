from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import NIVEAU_ACCES_CHOICES, NIVEAU_ACCES_LECTURE_ECRITURE


class User(AbstractUser):
    """
    Utilisateur custom défini dès le premier commit (AUTH_USER_MODEL).
    Le rattachement aux projets se fait dans l'autre sens, via
    Projet.utilisateurs_affectes (voir apps.projects.models), pour éviter
    toute dépendance circulaire de migration entre accounts et projects.
    """

    # Code d'un Role (référentiel modifiable par l'Administrateur) — gardé en
    # simple texte plutôt qu'en clé étrangère : le code est comparé tel quel
    # partout (permissions, notifications, frontend), voir constants.py.
    role = models.CharField(max_length=32)
    niveau_acces = models.CharField(
        max_length=20,
        choices=NIVEAU_ACCES_CHOICES,
        default=NIVEAU_ACCES_LECTURE_ECRITURE,
        help_text="Lecture seule = consultation uniquement ; Lecture et écriture = peut créer/modifier dans "
        "son périmètre. Un Administrateur a toujours un accès complet, indépendamment de ce champ.",
    )
    telephone = models.CharField(max_length=30, blank=True)
    langue = models.CharField(
        max_length=5, blank=True, help_text="Langue de l'interface pour cet utilisateur (vide : celle de l'organisation)."
    )
    class TypeStructure(models.TextChoices):
        INTERNE = "INTERNE", "Organisation (interne)"
        CONSORTIUM = "CONSORTIUM", "Partenaire de consortium"
        MISE_EN_OEUVRE = "MISE_EN_OEUVRE", "Partenaire de mise en œuvre"
        PARTIE_PRENANTE = "PARTIE_PRENANTE", "Partie prenante"
        BAILLEUR = "BAILLEUR", "Bailleur"

    type_structure = models.CharField(
        max_length=20, choices=TypeStructure.choices, blank=True, help_text="Structure à laquelle appartient l'utilisateur."
    )
    structure_interne = models.ForeignKey(
        "partners.StructureOrganisation", null=True, blank=True, on_delete=models.SET_NULL, related_name="utilisateurs",
        help_text="Direction / service, pour un utilisateur de l'organisation.",
    )
    partenaire = models.ForeignKey(
        "partners.Partenaire", null=True, blank=True, on_delete=models.SET_NULL, related_name="utilisateurs",
        help_text="Partenaire (consortium, mise en œuvre) ou bailleur dont relève l'utilisateur.",
    )
    partie_prenante = models.ForeignKey(
        "partners.PartiePrenante", null=True, blank=True, on_delete=models.SET_NULL, related_name="utilisateurs"
    )
    acces_modules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Droits de cet utilisateur module par module ({clé: MASQUE, LECTURE ou ECRITURE}, voir "
        "apps.core.modules) ; un module absent suit le niveau d'accès. Sans effet pour un Administrateur.",
    )
    zones_affectees = models.ManyToManyField(
        "geo.Zone",
        blank=True,
        related_name="utilisateurs_affectes",
        help_text="Zones auxquelles l'utilisateur (ex: animateur de terrain) est restreint.",
    )

    def __str__(self):
        return self.get_full_name() or self.username


class Role(models.Model):
    """
    Référentiel des rôles, géré par l'Administrateur (écran Utilisateurs >
    Rôles). Les rôles « système » (constants.ROLE_CHOICES, créés par
    migration) sont utilisés tels quels par le code (Administrateur,
    destinataires de notifications...) : renommables, mais ni supprimables
    ni recodables. Un rôle ajouté ne se distingue des autres que par sa
    visibilité — les droits d'écriture dépendent du niveau d'accès de
    chaque utilisateur, pas de son rôle.
    """

    code = models.CharField(max_length=32, unique=True)
    libelle = models.CharField(max_length=100)
    visibilite_globale = models.BooleanField(
        default=False,
        help_text="Voit tous les projets (sinon uniquement les projets/zones auxquels l'utilisateur est affecté).",
    )
    peut_personnaliser_tableau_de_bord = models.BooleanField(
        default=False,
        help_text="Peut choisir les blocs et types de graphiques du tableau de bord, pour tous les utilisateurs "
        "(toujours vrai pour l'Administrateur).",
    )
    peut_approuver = models.BooleanField(
        default=False,
        help_text="Peut approuver ou rejeter les saisies et demandes de modification des projets qui l'exigent "
        "(toujours vrai pour l'Administrateur).",
    )
    systeme = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ("-systeme", "libelle")
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"

    def __str__(self):
        return self.libelle


class CodeConnexion(models.Model):
    """
    Code à usage unique envoyé par courriel à chaque connexion (apps.accounts.double_auth). Seule son
    empreinte est gardée ; il expire après quelques minutes et après un nombre limité d'essais.
    """

    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="codes_connexion")
    empreinte = models.CharField(max_length=64)
    cree_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField()
    essais = models.PositiveSmallIntegerField(default=0)
    utilise = models.BooleanField(default=False)

    class Meta:
        ordering = ("-cree_le",)
        verbose_name = "Code de connexion"


class DemandeInscription(models.Model):
    """
    Profil créé par une organisation depuis la page d'accueil (apps.accounts.inscriptions). Il ne donne
    aucun accès : l'organisation doit d'abord s'abonner ; Expertise-ID active ensuite son espace.
    Le mot de passe choisi n'est gardé que sous forme d'empreinte.
    """

    class Offre(models.TextChoices):
        # Standard : projets et utilisateurs illimités, 100 Go, 86 $ par mois. Standard + stockage : la
        # même offre, plus 5 $ par tranche de 10 Go ajoutée. (Avant le 4 nov. 2026 : Essentiel, Standard,
        # Institution, ramenées à Standard par la migration 0013.)
        # Standard 25 Go et Standard 50 Go : l'offre Standard avec moins de stockage, moins chère (5 nov. 2026).
        STANDARD_25 = "STANDARD_25", "Standard 25 Go"
        STANDARD_50 = "STANDARD_50", "Standard 50 Go"
        STANDARD = "STANDARD", "Standard"
        STOCKAGE_PLUS = "STOCKAGE_PLUS", "Standard + stockage"
        # Partenariat : l'offre Standard pour les structures avec lesquelles Expertise-ID collabore,
        # avec une réduction possible jusqu'à la gratuité pendant un an, assistance comprise.
        PARTENARIAT = "PARTENARIAT", "Partenariat"
        # Essai gratuit (10 nov. 2026) : 1 mois, 100 Mo, sans paiement, une seule fois par adresse courriel
        # (EssaiGratuit) ; à la fin, l'espace est bloqué jusqu'au choix d'une offre payante (page Abonnement).
        ESSAI = "ESSAI", "Essai gratuit"

    class Statut(models.TextChoices):
        ABONNEMENT_REQUIS = "ABONNEMENT_REQUIS", "Abonnement requis"
        OFFRE_CHOISIE = "OFFRE_CHOISIE", "Offre choisie, à contacter"
        EN_ACTIVATION = "EN_ACTIVATION", "Espace en cours de création"
        ACTIVEE = "ACTIVEE", "Abonnement activé"
        REFUSEE = "REFUSEE", "Refusée"

    organisation = models.CharField(max_length=200)
    type_organisation = models.CharField(max_length=60)
    pays = models.CharField(max_length=80)
    secteur = models.CharField(max_length=120, blank=True)
    taille = models.CharField(max_length=40, blank=True, help_text="Nombre de personnes ou de projets suivis.")
    contact_nom = models.CharField(max_length=200)
    contact_fonction = models.CharField(max_length=120, blank=True)
    courriel = models.EmailField()
    telephone = models.CharField(max_length=40)
    identifiant = models.CharField(max_length=150, unique=True)
    # Plateforme multi-organisations : adresse souhaitée de l'espace (ong-a.DOMAINE_PLATEFORME).
    sous_domaine = models.CharField(max_length=40, blank=True)
    erreur_activation = models.TextField(blank=True)
    mot_de_passe = models.CharField(max_length=200, help_text="Empreinte du mot de passe choisi.")
    offre = models.CharField(max_length=20, choices=Offre.choices, blank=True)
    message = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ABONNEMENT_REQUIS)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-cree_le",)
        verbose_name = "Demande d'inscription"

    def __str__(self):
        return self.organisation


class EssaiGratuit(models.Model):
    """
    Adresses courriel qui ont déjà eu leur essai gratuit d'un mois (base centrale) : gardées même si l'espace
    ou la demande d'inscription sont supprimés, pour qu'une adresse n'ait droit qu'à un seul essai.
    """

    courriel = models.EmailField(unique=True, help_text="En minuscules.")
    organisation = models.CharField(max_length=200, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Essai gratuit utilisé"
        verbose_name_plural = "Essais gratuits utilisés"

    def __str__(self):
        return self.courriel
