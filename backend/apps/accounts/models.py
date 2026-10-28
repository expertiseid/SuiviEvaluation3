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
