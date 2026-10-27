from django.db import models


class ConfigurationTableauDeBord(models.Model):
    """
    Configuration du tableau de bord, commune à tous les utilisateurs
    (ligne unique, id=1) : blocs masqués et type de chaque graphique.
    Modifiable par l'Administrateur ou un rôle ayant le droit
    « peut_personnaliser_tableau_de_bord » ; les filtres restent propres à
    chaque utilisateur (non enregistrés ici).
    """

    blocs_masques = models.JSONField(default=list, blank=True)
    types_graphiques = models.JSONField(default=dict, blank=True)
    modifie_par = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration du tableau de bord"

    @classmethod
    def courante(cls):
        return cls.objects.get_or_create(pk=1)[0]


class ConfigurationMenu(models.Model):
    """
    Noms et icônes des rubriques du menu latéral, communs à tous les
    utilisateurs (ligne unique, id=1) — libelles : { "/projets": "Programmes" },
    icones : { "/projets": "Briefcase" } (nom d'une icône proposée par le
    frontend). Une rubrique absente garde son nom / son icône par défaut.
    Modifiable par l'Administrateur uniquement.
    """

    libelles = models.JSONField(default=dict, blank=True)
    icones = models.JSONField(default=dict, blank=True)
    # Vocabulaire de l'organisation, appliqué à tous les textes de l'interface et des
    # exports : { "projet": {"singulier": "action", "pluriel": "actions", "feminin": true} }
    # (clés : apps.core.vocabulaire.TERMES).
    vocabulaire = models.JSONField(default=dict, blank=True)
    modifie_par = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration du menu"

    @classmethod
    def courante(cls):
        return cls.objects.get_or_create(pk=1)[0]
