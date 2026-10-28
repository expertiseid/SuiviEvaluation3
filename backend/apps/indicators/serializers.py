from django.db.models import Sum
from rest_framework import serializers

from apps.core.vocabulaire import v
from apps.strategy.models import ElementStrategique

from .models import Indicateur, PalierAlerte, ParametresAlerte, ValeurIndicateur
from .services import palier_pour_taux, paliers_pour, taux_realisation, valeur_realisee_totale


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

    def get_taux_realisation(self, obj):
        cumule = (
            obj.indicateur.valeurs.filter(periode_fin__lte=obj.periode_fin).aggregate(total=Sum("valeur_realisee"))[
                "total"
            ]
            or 0
        )
        return taux_realisation(cumule, obj.indicateur.valeur_cible)

    def create(self, validated_data):
        validated_data["saisi_par"] = self.context["request"].user
        return super().create(validated_data)


class IndicateurSerializer(serializers.ModelSerializer):
    valeurs = ValeurIndicateurSerializer(many=True, read_only=True)
    taux_realisation_actuel = serializers.SerializerMethodField()
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
        )

    def get_taux_realisation_actuel(self, obj):
        return taux_realisation(valeur_realisee_totale(obj), obj.valeur_cible)

    def get_palier_actuel(self, obj):
        taux = taux_realisation(valeur_realisee_totale(obj), obj.valeur_cible)
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
        return attrs
