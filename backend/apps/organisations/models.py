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
    mode_demo = models.BooleanField(default=False, help_text="Organisation de démonstration : visiteur en lecture seule.")
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


# --- Site vitrine : actualités et partenaires (gérés dans la console Expertise-ID) -----------------

LANGUES_SITE = ("en", "ar", "es", "de")


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
