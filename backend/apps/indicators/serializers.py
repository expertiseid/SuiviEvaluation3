from django.db.models import Sum
from rest_framework import serializers

from apps.core.vocabulaire import v
from apps.strategy.models import ElementStrategique

from .models import Enquete, Indicateur, PalierAlerte, ParametresAlerte, ValeurIndicateur
from .services import actualisation, palier_pour_taux, paliers_pour, taux_indicateur, valeur_actuelle, variation


class ParametresAlerteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresAlerte
        fields = ("seuil_echeance_jours",)


class PalierAlerteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PalierAlerte
        fields = ("id", "projet", "indicateur", "activite", "borne_min", "libelle", "couleur")


class ValeurIndicateurSerializer(serializers.ModelSerializer):
    """
    valeur_realisee est ce qui a été réalisé PENDANT cette période précise
    (pas un cumul) — taux_realisation compare donc la somme cumulée
    jusqu'à cette période (elle incluse) à la cible, pas la seule valeur de
    cette ligne.
    """

    saisi_par_nom = serializers.StringRelatedField(source="saisi_par", read_only=True)
    taux_realisation = serializers.SerializerMethodField()

    class Meta:
        model = ValeurIndicateur
        fields = (
            "id",
            "indicateur",
            "periode_debut",
            "periode_fin",
            "valeur_realisee",
            "date_saisie",
            "saisi_par",
            "saisi_par_nom",
            "commentaire",
            "taux_realisation",
        )
        read_only_fields = ("date_saisie", "saisi_par")

    def validate_indicateur(self, indicateur):
        if indicateur.formule:
            raise serializers.ValidationError(v("Cet indicateur est calculé par une formule : aucune valeur n'est à saisir."))
        return indicateur

    def get_taux_realisation(self, obj):
        """Taux à la fin de cette période (cumul des saisies, ou cette valeur, selon l'indicateur)."""
        return taux_indicateur(obj.indicateur, valeur_actuelle(obj.indicateur, jusqu_au=obj.periode_fin))

    def create(self, validated_data):
        validated_data["saisi_par"] = self.context["request"].user
        return super().create(validated_data)


class IndicateurSerializer(serializers.ModelSerializer):
    valeurs = ValeurIndicateurSerializer(many=True, read_only=True)
    taux_realisation_actuel = serializers.SerializerMethodField()
    valeur_actuelle = serializers.SerializerMethodField()
    actualisation = serializers.SerializerMethodField()
    variation = serializers.SerializerMethodField()
    ecart_cible = serializers.SerializerMethodField()
    palier_actuel = serializers.SerializerMethodField()
    # Lien par table intermédiaire (IndicateurElement) : DRF le rendrait en lecture seule, le
    # rattachement envoyé par le formulaire était alors ignoré sans message.
    elements_strategiques = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=ElementStrategique.objects.all()
    )
    elements_strategiques_libelles = serializers.StringRelatedField(
        source="elements_strategiques", many=True, read_only=True
    )
    projet_nom = serializers.StringRelatedField(source="projet", read_only=True)
    projet_rattache_nom = serializers.SerializerMethodField()
    activite_libelle = serializers.StringRelatedField(source="activite", read_only=True)
    formule_explication = serializers.SerializerMethodField()

    class Meta:
        model = Indicateur
        fields = (
            "id",
            "libelle",
            "unite",
            "valeur_reference",
            "valeur_reference_date",
            "valeur_cible",
            "frequence_collecte",
            "projet",
            "projet_nom",
            "projet_rattache_nom",
            "activite",
            "activite_libelle",
            "elements_strategiques",
            "elements_strategiques_libelles",
            "valeurs",
            "taux_realisation_actuel",
            "palier_actuel",
            "sens",
            "calcul_taux",
            "agregation",
            "poids",
            "valeur_actuelle",
            "actualisation",
            "variation",
            "ecart_cible",
            "formule",
            "formule_explication",
        )

    def get_taux_realisation_actuel(self, obj):
        return taux_indicateur(obj)

    def get_formule_explication(self, obj):
        """La formule d'un indicateur calculé, en français (une ligne par terme, puis le calcul)."""
        from .formules import explication

        return explication(obj.formule) if obj.formule else None

    def validate_poids(self, poids):
        if poids is not None and poids <= 0:
            raise serializers.ValidationError("Le poids doit être supérieur à 0 (vide : poids 1).")
        return poids

    def validate_formule(self, formule):
        from .formules import FormuleInvalide, valider

        if formule in (None, {}):
            return None
        try:
            return valider(formule)
        except FormuleInvalide as exc:
            raise serializers.ValidationError(str(exc))

    def get_actualisation(self, obj):
        """À jour ou non selon la fréquence de collecte (dernière saisie, nouvelle valeur attendue le…)."""
        return actualisation(obj)

    def get_variation(self, obj):
        """Écart entre les deux dernières périodes saisies."""
        return variation(obj)

    def get_ecart_cible(self, obj):
        """Ce qu'il reste à faire pour atteindre la cible (négatif : dépassée), dans le sens de l'indicateur."""
        from apps.dashboard.performance import ecart_a_la_cible

        return ecart_a_la_cible(obj, valeur_actuelle(obj))

    def get_valeur_actuelle(self, obj):
        """Valeur retenue pour le taux : somme des saisies, ou dernière valeur saisie."""
        return valeur_actuelle(obj)

    def get_palier_actuel(self, obj):
        taux = taux_indicateur(obj)
        palier = palier_pour_taux(taux, paliers_pour(indicateur=obj, projet=obj.projet_rattache))
        if palier is None:
            return None
        return {"id": palier.id, "libelle": palier.libelle, "couleur": palier.couleur, "borne_min": palier.borne_min}

    def get_projet_rattache_nom(self, obj):
        """
        Nom du projet auquel l'indicateur se rattache, quel que soit le
        niveau de rattachement (projet direct ou élément de sa planification,
        à n'importe quel niveau) — None seulement pour un indicateur purement stratégique,
        sans aucun rattachement à la hiérarchie projet.
        """
        projet = obj.projet_rattache
        return projet.nom if projet else None

    RATTACHEMENT_FIELDS = ("projet", "activite")

    def create(self, validated_data):
        elements = validated_data.pop("elements_strategiques", None)
        indicateur = super().create(validated_data)
        if elements is not None:
            indicateur.elements_strategiques.set(elements)
        return indicateur

    def update(self, instance, validated_data):
        elements = validated_data.pop("elements_strategiques", None)
        indicateur = super().update(instance, validated_data)
        if elements is not None:
            indicateur.elements_strategiques.set(elements)
        return indicateur

    def validate(self, attrs):
        valeurs = [
            attrs.get(champ, getattr(self.instance, champ, None)) for champ in self.RATTACHEMENT_FIELDS
        ]
        if sum(bool(v) for v in valeurs) > 1:
            raise serializers.ValidationError(
                v("Un indicateur se rattache soit au projet, soit à un élément de sa planification (ou à aucun des deux, s'il est purement stratégique).")
            )
        if attrs.get("formule"):
            # Calculé : la formule donne un niveau à chaque instant, pas des quantités à additionner.
            attrs["agregation"] = Indicateur.Agregation.DERNIERE
            if self.instance is not None and self.instance.valeurs.exists():
                raise serializers.ValidationError(
                    {"formule": v("Cet indicateur a déjà des valeurs saisies : créez plutôt un nouvel indicateur calculé.")})
        return attrs


class EnqueteSerializer(serializers.ModelSerializer):
    """Description d'une enquête (sans ses données) ; le plan de sondage se règle ici."""

    projet_code = serializers.CharField(source="projet.code", read_only=True, default="")
    cree_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Enquete
        fields = (
            "id", "titre", "projet", "projet_code", "date_debut", "date_fin", "fichier_source", "colonnes", "colonnes_ecartees",
            "nombre_reponses", "colonne_poids", "colonne_strate", "colonne_grappe", "cree_par_nom", "created_at",
        )
        read_only_fields = ("fichier_source", "colonnes", "colonnes_ecartees", "nombre_reponses")

    def get_cree_par_nom(self, obj):
        u = obj.cree_par
        return (u.get_full_name() or u.username) if u else ""

    def validate(self, attrs):
        colonnes = {c["nom"]: c["type"] for c in (self.instance.colonnes if self.instance else attrs.get("colonnes", []))}
        for champ in ("colonne_poids", "colonne_strate", "colonne_grappe"):
            nom = attrs.get(champ)
            if nom and nom not in colonnes:
                raise serializers.ValidationError({champ: v("Colonne inconnue : « {0} ».").format(nom)})
        if attrs.get("colonne_poids") and colonnes.get(attrs["colonne_poids"]) != "NOMBRE":
            raise serializers.ValidationError({"colonne_poids": v("Les poids doivent être des nombres.")})
        return attrs
