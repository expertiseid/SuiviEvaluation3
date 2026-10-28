from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimestampedModel


class NiveauAdministratif(TimestampedModel):
    """
    Gabarit d'un niveau administratif, paramétrable par pays — un pays peut
    définir « Région » → « Province » → « Commune » → « Village », un autre
    « Région » → « Département » → « Commune »... Même logique que TypeNiveau
    pour le Plan stratégique, mais scopée par pays plutôt que par cadre
    stratégique.
    """

    pays = models.CharField(max_length=2, help_text="Code ISO 3166-1 alpha-2 du pays (ex : BF, ML, NE).")
    nom_niveau = models.CharField(max_length=150, help_text="Ex : 'Région', 'Province', 'Commune', 'Village'...")
    ordre = models.PositiveSmallIntegerField(help_text="Position dans la hiérarchie : 1 = niveau le plus élevé.")
    niveau_parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="niveaux_enfants"
    )
    saut_niveau_autorise = models.BooleanField(
        default=True,
        help_text="Autorise une zone de ce niveau à avoir une zone parente qui n'est pas du niveau immédiatement "
        "supérieur — utile car la précision des données de terrain varie (parfois seule la région est connue).",
    )
    aide_code = models.CharField(
        max_length=100, blank=True, help_text="Exemple affiché comme aide à la saisie (ex : 'Ex : Kadiogo')."
    )

    class Meta:
        ordering = ("pays", "ordre")
        verbose_name = "Niveau administratif"
        verbose_name_plural = "Niveaux administratifs"

    def __str__(self):
        return f"{self.pays} — {self.nom_niveau}"

    def clean(self):
        if self.niveau_parent_id and self.niveau_parent.pays != self.pays:
            raise ValidationError("Le niveau parent doit appartenir au même pays.")

    def niveaux_ancetres(self):
        """Remonte la chaîne niveau_parent, du plus proche au plus lointain."""
        courant = self.niveau_parent
        while courant is not None:
            yield courant
            courant = courant.niveau_parent


class Zone(TimestampedModel):
    """
    Donnée réelle saisie par l'utilisateur (sa région, sa province, son
    village...), rattachée à un NiveauAdministratif et, sauf racine, à une
    zone parente. Pas de FK directe vers un pays : l'isolement par pays est
    garanti transitivement via niveau_administratif.pays.
    """

    niveau_administratif = models.ForeignKey(NiveauAdministratif, on_delete=models.PROTECT, related_name="zones")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="enfants")
    code = models.CharField(max_length=20, blank=True, db_index=True, help_text="Code administratif (pcode), si connu.")
    nom = models.CharField(max_length=150)
    # Centre de la zone (carte des bénéficiaires) : calculé depuis les limites administratives
    # chargées (geo.limites), ou saisi à la main.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "Zone d'intervention"
        verbose_name_plural = "Zones d'intervention"
        ordering = ("niveau_administratif__ordre", "nom")

    def __str__(self):
        return self.nom

    @property
    def pays(self):
        return self.niveau_administratif.pays

    def clean(self):
        niveau_attendu = self.niveau_administratif.niveau_parent
        if niveau_attendu is None:
            if self.parent is not None:
                raise ValidationError(
                    f"Une zone de niveau « {self.niveau_administratif.nom_niveau} » (niveau racine) ne peut pas "
                    "avoir de zone parente."
                )
            return

        if self.parent is None:
            if self.niveau_administratif.saut_niveau_autorise:
                return
            raise ValidationError(
                f"Une zone de niveau « {self.niveau_administratif.nom_niveau} » doit avoir une zone parente de "
                f"niveau « {niveau_attendu.nom_niveau} »."
            )

        if self.parent.niveau_administratif_id == niveau_attendu.id:
            return

        if self.niveau_administratif.saut_niveau_autorise and self.parent.niveau_administratif in list(
            self.niveau_administratif.niveaux_ancetres()
        ):
            return

        raise ValidationError(
            f"Le parent d'une zone de niveau « {self.niveau_administratif.nom_niveau} » doit être de niveau "
            f"« {niveau_attendu.nom_niveau} »"
            + (" (ou d'un niveau supérieur, saut de niveau autorisé)." if self.niveau_administratif.saut_niveau_autorise else ".")
        )


class LimiteAdministrative(TimestampedModel):
    """
    Contours des zones d'un niveau administratif d'un pays (GeoJSON simplifié, source
    geoBoundaries, licence ouverte), gardés en cache après le premier téléchargement.
    Niveau 1 = premier découpage (régions), 2 = le suivant (provinces)…
    """

    pays = models.CharField(max_length=2)
    niveau = models.PositiveSmallIntegerField()
    nom_niveau = models.CharField(max_length=60, blank=True, help_text="Nom donné par la source (Region, Province…).")
    annee = models.CharField(max_length=10, blank=True)
    source = models.URLField(max_length=500, blank=True)
    geojson = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("pays", "niveau"), name="limite_pays_niveau_unique")]

    def __str__(self):
        return f"{self.pays} niveau {self.niveau}"
