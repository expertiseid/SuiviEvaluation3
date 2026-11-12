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
    source = models.CharField(max_length=500, blank=True, help_text="geoBoundaries (adresse) ou base nationale importée (BNDT…).")
    geojson = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("pays", "niveau"), name="limite_pays_niveau_unique")]

    def __str__(self):
        return f"{self.pays} niveau {self.niveau}"


class CoucheCarte(TimestampedModel):
    """Couche d'habillage de la carte des bénéficiaires (ex. réseau routier), GeoJSON simplifié."""

    pays = models.CharField(max_length=2)
    cle = models.SlugField(max_length=30, help_text="Ex : routes.")
    libelle = models.CharField(max_length=100)
    source = models.CharField(max_length=500, blank=True)
    geojson = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("pays", "cle"), name="couche_pays_cle_unique")]

    def __str__(self):
        return f"{self.pays} {self.libelle}"


class Localite(models.Model):
    """
    Localité nommée (ville, village) d'une base topographique nationale : affichée sur la carte
    à fort zoom, par zone visible (plusieurs dizaines de milliers par pays).
    """

    VILLE = "VILLE"
    VILLAGE_ADMINISTRATIF = "VILLAGE_ADMIN"
    VILLAGE = "VILLAGE"

    pays = models.CharField(max_length=2)
    nom = models.CharField(max_length=150)
    statut = models.CharField(max_length=20)
    commune = models.CharField(max_length=150, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=("pays", "latitude", "longitude"), name="localite_position_idx")]

    def __str__(self):
        return self.nom


class CoucheImportee(TimestampedModel):
    """
    Couche SIG importée par un utilisateur (shapefile en .zip, GeoPackage, GeoJSON) pour la carte
    des bénéficiaires et ses cartes imprimables : reprojetée en WGS 84 et simplifiée à l'import.
    """

    class Geometrie(models.TextChoices):
        POINT = "POINT", "Points"
        LIGNE = "LIGNE", "Lignes"
        POLYGONE = "POLYGONE", "Polygones"

    nom = models.CharField(max_length=150)
    couleur = models.CharField(max_length=7, default="#7048e8")
    geometrie = models.CharField(max_length=10, choices=Geometrie.choices)
    fichier_source = models.CharField(max_length=255, blank=True)
    projection_source = models.CharField(max_length=200, blank=True)
    colonnes = models.JSONField(default=list, blank=True, help_text="Attributs conservés (affichés au survol).")
    champ_etiquette = models.CharField(max_length=100, blank=True, help_text="Attribut écrit sur la carte (nom…).")
    nombre_objets = models.PositiveIntegerField(default=0)
    emprise = models.JSONField(default=list, blank=True, help_text="[ouest, sud, est, nord] en degrés.")
    geojson = models.JSONField()
    cree_par = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="couches_importees")

    class Meta:
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class InstallationZones(models.Model):
    """
    Zones administratives d'un pays installées automatiquement (apps.geo.services.installation) : une ligne par
    pays, pour suivre l'installation (en cours, terminée, échec) et l'afficher sur la plateforme.
    """

    class Statut(models.TextChoices):
        EN_COURS = "EN_COURS", "En cours"
        TERMINE = "TERMINE", "Terminée"
        ECHEC = "ECHEC", "Échec"

    pays = models.CharField(max_length=2, unique=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    zones = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    source = models.CharField(max_length=40, blank=True, help_text="« geoBoundaries » ou « référentiel national ».")
    maj = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("pays",)
