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
