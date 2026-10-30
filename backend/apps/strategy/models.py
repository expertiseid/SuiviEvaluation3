from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimestampedModel


class TypeDocument(TimestampedModel):
    """
    Maillon de la chaîne des documents stratégiques, propre à l'organisation (ex : « Cadre
    stratégique » → « Programme » → « Pilier 1 » → « Pilier 2 » → « Pilier 3 », puis les projets).
    Chaque maillon est une rubrique à part du menu ; ses documents (CadreStrategique) ont leurs
    propres niveaux et éléments, et se rattachent à un document d'un maillon au-dessus.
    """

    nom = models.CharField(max_length=100, help_text="Au singulier : « Programme », « Pilier 1 »…")
    nom_pluriel = models.CharField(max_length=100, help_text="Nom de la rubrique du menu : « Programmes »…")
    ordre = models.PositiveSmallIntegerField(help_text="Position dans la chaîne : 1 = maillon le plus haut.")
    icone = models.CharField(max_length=50, blank=True, help_text="Icône du menu (voir ICONES_MENU de l'interface).")

    class Meta:
        ordering = ("ordre", "id")
        verbose_name = "Type de document stratégique"
        verbose_name_plural = "Types de documents stratégiques"

    def __str__(self):
        return self.nom


class CadreStrategique(TimestampedModel):
    """
    Conteneur racine d'une structuration stratégique complète et
    indépendante — plusieurs cadres peuvent coexister (ex : périodes ou
    programmes différents), chacun avec ses propres niveaux et sa propre
    arborescence, jamais mélangés entre eux.
    """

    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    structures = models.ManyToManyField("partners.StructureOrganisation", blank=True, related_name="cadres_strategiques")
    parties_prenantes = models.ManyToManyField("partners.PartiePrenante", blank=True, related_name="cadres_strategiques")
    # Chaîne des documents (voir TypeDocument) : maillon du document et rattachement à un document
    # d'un maillon au-dessus — au document lui-même, ou à l'un de ses éléments. Sauter un ou
    # plusieurs maillons est permis (avertissement, voir apps.strategy.chaine).
    type_document = models.ForeignKey(
        TypeDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="documents",
        help_text="Maillon de la chaîne ; vide = premier maillon.",
    )
    document_parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="documents_rattaches",
    )
    element_parent = models.ForeignKey(
        "ElementStrategique", null=True, blank=True, on_delete=models.SET_NULL, related_name="documents_rattaches",
        help_text="Élément du document parent auquel ce document est rattaché (vide = le document lui-même).",
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.nom


class TypeNiveau(TimestampedModel):
    """
    Gabarit d'un niveau de la structuration stratégique — libellé et position
    entièrement définis par l'utilisateur (pas de "Plan"/"Orientation"/"Axe"
    en dur : une organisation peut vouloir "Priorité" → "Sous-priorité", une
    autre "Plan" → "Orientation" → "Axe" → "Objectif"...). La chaîne des
    niveaux est linéaire et propre à son cadre stratégique : chaque niveau a
    au plus un niveau_parent, dérivé automatiquement de l'ordre par les
    opérations de réordonnancement de l'écran de configuration (jamais
    choisi manuellement).
    """

    cadre_strategique = models.ForeignKey(
        CadreStrategique, on_delete=models.PROTECT, related_name="types_niveaux"
    )
    nom_niveau = models.CharField(max_length=150, help_text="Ex : 'Orientation stratégique', 'Priorité'...")
    # Pas de unique=True : le réordonnancement échange l'ordre de deux niveaux
    # via deux requêtes PATCH séparées (deux transactions distinctes), ce qui
    # provoquerait une collision transitoire sur une contrainte unique.
    ordre = models.PositiveSmallIntegerField(help_text="Position dans la hiérarchie : 1 = niveau le plus élevé.")
    niveau_parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="niveaux_enfants"
    )
    saut_niveau_autorise = models.BooleanField(
        default=False,
        help_text="Autorise un élément de ce niveau à avoir un parent qui n'est pas du niveau immédiatement supérieur.",
    )
    aide_code = models.CharField(
        max_length=100, blank=True, help_text="Exemple de code affiché comme aide à la saisie (ex : 'Ex : OS1')."
    )

    class Meta:
        ordering = ("cadre_strategique", "ordre")

    def __str__(self):
        return self.nom_niveau

    def clean(self):
        if self.niveau_parent_id and self.niveau_parent.cadre_strategique_id != self.cadre_strategique_id:
            raise ValidationError("Le niveau parent doit appartenir au même cadre stratégique.")

    def niveaux_ancetres(self):
        """Remonte la chaîne niveau_parent, du plus proche au plus lointain."""
        courant = self.niveau_parent
        while courant is not None:
            yield courant
            courant = courant.niveau_parent


class ElementStrategique(TimestampedModel):
    """
    Donnée réelle saisie par l'utilisateur (son plan stratégique effectif,
    ses axes effectifs...), rattachée à un TypeNiveau et, sauf racine, à un
    élément parent du niveau immédiatement supérieur. Pas de FK directe vers
    CadreStrategique : l'isolement par cadre est garanti transitivement via
    type_niveau.cadre_strategique (TypeNiveau.clean() interdit un
    niveau_parent d'un autre cadre).
    """

    type_niveau = models.ForeignKey(TypeNiveau, on_delete=models.PROTECT, related_name="elements")
    element_parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="enfants"
    )
    code = models.CharField(max_length=50, blank=True)
    nom = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    parents_secondaires = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="enfants_secondaires",
        help_text="Autres éléments du niveau supérieur auxquels celui-ci contribue aussi. Seul element_parent "
        "structure l'arbre et compte dans les totaux ; ces liens sont informatifs.",
    )
    structures = models.ManyToManyField("partners.StructureOrganisation", blank=True, related_name="elements_strategiques")
    parties_prenantes = models.ManyToManyField("partners.PartiePrenante", blank=True, related_name="elements_strategiques")
    contribue_a = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="contributions",
        help_text="Élément d'un document d'un maillon au-dessus auquel celui-ci (et ce qui est en dessous) "
        "contribue ; vide = le rattachement du document.",
    )

    class Meta:
        # Tri par id (= ordre de création) et non par code/nom : un import
        # Excel doit remonter dans l'ordre de saisie du fichier, pas réordonné
        # alphabétiquement — ce que "code, nom" faisait involontairement dès
        # que plusieurs éléments partageaient un code vide ou similaire.
        ordering = ("type_niveau__ordre", "id")

    def __str__(self):
        return f"{self.code} — {self.nom}" if self.code else self.nom

    def clean(self):
        niveau_attendu = self.type_niveau.niveau_parent
        if niveau_attendu is None:
            if self.element_parent is not None:
                raise ValidationError(
                    f"Un élément de niveau « {self.type_niveau.nom_niveau} » (niveau racine) ne peut pas avoir de parent."
                )
            return

        if self.element_parent is None:
            raise ValidationError(
                f"Un élément de niveau « {self.type_niveau.nom_niveau} » doit avoir un parent "
                f"de niveau « {niveau_attendu.nom_niveau} »."
            )

        if self.element_parent.type_niveau_id == niveau_attendu.id:
            return

        if self.type_niveau.saut_niveau_autorise and self.element_parent.type_niveau in list(
            self.type_niveau.niveaux_ancetres()
        ):
            return

        raise ValidationError(
            f"Le parent d'un élément de niveau « {self.type_niveau.nom_niveau} » doit être de niveau "
            f"« {niveau_attendu.nom_niveau} »"
            + (" (ou d'un niveau supérieur, saut de niveau autorisé)." if self.type_niveau.saut_niveau_autorise else ".")
        )


class AppreciationStrategique(TimestampedModel):
    """
    Renseignement propre à un élément d'un document stratégique pour une période, en plus du
    calcul automatique à partir des projets : appréciation de l'avancement, analyse,
    difficultés, recommandations (pièces jointes : documents.PieceJustificative).
    """

    class Etat(models.TextChoices):
        BON = "BON", "Bonne progression"
        MOYEN = "MOYEN", "Progression moyenne"
        INSUFFISANT = "INSUFFISANT", "Progression insuffisante"

    element = models.ForeignKey(ElementStrategique, on_delete=models.CASCADE, related_name="appreciations")
    libelle_periode = models.CharField(max_length=100, blank=True, help_text="Ex : « Année 2026 », « 1er semestre 2027 ».")
    periode_debut = models.DateField()
    periode_fin = models.DateField()
    etat = models.CharField(max_length=12, choices=Etat.choices)
    commentaire = models.TextField(blank=True, help_text="Analyse de l'avancement sur la période.")
    difficultes = models.TextField(blank=True)
    recommandations = models.TextField(blank=True)
    saisi_par = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="appreciations_strategiques"
    )

    class Meta:
        ordering = ("-periode_fin", "-id")
        constraints = [
            models.CheckConstraint(check=models.Q(periode_fin__gte=models.F("periode_debut")), name="appreciation_periode_valide")
        ]

    def __str__(self):
        return f"{self.element} — {self.libelle_periode or self.periode_fin}"
