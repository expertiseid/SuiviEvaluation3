from django.utils import timezone
from rest_framework import serializers

from .models import (
    Beneficiaire,
    ParticipationProjet,
    SignalementDoublon,
    StatutParticulier,
    TypeActiviteBeneficiaire,
    VariableBeneficiaire,
)


class StatutParticulierSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutParticulier
        fields = ("id", "code", "libelle")


class TypeActiviteBeneficiaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeActiviteBeneficiaire
        fields = ("id", "code", "libelle")


def calculer_age(date_naissance):
    if not date_naissance:
        return None
    aujourdhui = timezone.localdate()
    age = aujourdhui.year - date_naissance.year
    if (aujourdhui.month, aujourdhui.day) < (date_naissance.month, date_naissance.day):
        age -= 1
    return age


def tranche_age_de(age):
    """
    Tranches alignées sur la convention déjà utilisée dans l'app pour le
    statut particulier « Jeune » (moins de 35 ans) : 0-17 / 18-35 / 36-59 / 60+.
    """
    if age is None:
        return None
    if age < 18:
        return "0-17 ans"
    if age <= 35:
        return "18-35 ans"
    if age <= 59:
        return "36-59 ans"
    return "60 ans et plus"


class ParticipationProjetSerializer(serializers.ModelSerializer):
    projet_nom = serializers.StringRelatedField(source="projet", read_only=True)
    beneficiaire_nom = serializers.StringRelatedField(source="beneficiaire", read_only=True)
    activite_nom = serializers.StringRelatedField(source="activite", read_only=True)
    sous_activite_nom = serializers.StringRelatedField(source="sous_activite", read_only=True)

    class Meta:
        model = ParticipationProjet
        fields = (
            "id",
            "beneficiaire",
            "beneficiaire_nom",
            "projet",
            "projet_nom",
            "activite",
            "activite_nom",
            "sous_activite",
            "sous_activite_nom",
            "date_inscription",
            "role_dans_projet",
        )


class VariableBeneficiaireSerializer(serializers.ModelSerializer):
    projets_codes = serializers.SerializerMethodField()
    nb_reponses = serializers.SerializerMethodField()

    class Meta:
        model = VariableBeneficiaire
        fields = (
            "id", "libelle", "type", "choix", "unite", "aide", "tous_les_projets", "projets", "projets_codes",
            "ordre", "nb_reponses",
        )

    def get_projets_codes(self, obj):
        return sorted(p.code for p in obj.projets.all())

    def get_nb_reponses(self, obj):
        return Beneficiaire.objects.filter(reponses__has_key=str(obj.id)).count()

    def validate(self, attrs):
        type_variable = attrs.get("type", getattr(self.instance, "type", None))
        choix = [str(c).strip() for c in attrs.get("choix", getattr(self.instance, "choix", [])) if str(c).strip()]
        if type_variable in (VariableBeneficiaire.Type.CHOIX, VariableBeneficiaire.Type.CHOIX_MULTIPLE) and len(choix) < 2:
            raise serializers.ValidationError({"choix": "Indiquer au moins deux réponses possibles."})
        if "choix" in attrs:
            attrs["choix"] = list(dict.fromkeys(choix))
        tous = attrs.get("tous_les_projets", getattr(self.instance, "tous_les_projets", True))
        projets = attrs.get("projets", None if self.instance is None else list(self.instance.projets.all()))
        if not tous and not projets:
            raise serializers.ValidationError({"projets": "Choisir les projets concernés, ou « tous les projets »."})
        return attrs


class BeneficiaireSerializer(serializers.ModelSerializer):
    zone_nom = serializers.StringRelatedField(source="zone", read_only=True)
    participations = ParticipationProjetSerializer(many=True, read_only=True)
    age = serializers.SerializerMethodField()
    tranche_age = serializers.SerializerMethodField()

    class Meta:
        model = Beneficiaire
        fields = (
            "id",
            "identifiant",
            "nom",
            "prenom",
            "sexe",
            "date_naissance",
            "age",
            "tranche_age",
            "telephone",
            "numero_piece_identite",
            "type_piece",
            "pays",
            "zone",
            "zone_nom",
            "latitude",
            "longitude",
            "consentement",
            "date_consentement",
            "date_anonymisation",
            "reponses",
            "statuts_particuliers",
            "types_activite",
            "participations",
        )
        read_only_fields = ("date_anonymisation",)

    def validate_reponses(self, valeur):
        from .services.variables import normaliser_reponses

        if not isinstance(valeur, dict):
            raise serializers.ValidationError("Réponses invalides.")
        try:
            return normaliser_reponses(valeur)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_latitude(self, valeur):
        if valeur is not None and not -90 <= valeur <= 90:
            raise serializers.ValidationError("La latitude doit être comprise entre -90 et 90.")
        return valeur

    def validate_longitude(self, valeur):
        if valeur is not None and not -180 <= valeur <= 180:
            raise serializers.ValidationError("La longitude doit être comprise entre -180 et 180.")
        return valeur

    def get_age(self, obj):
        return calculer_age(obj.date_naissance)

    def get_tranche_age(self, obj):
        return tranche_age_de(calculer_age(obj.date_naissance))


class SignalementDoublonSerializer(serializers.ModelSerializer):
    beneficiaire_1_nom = serializers.StringRelatedField(source="beneficiaire_1", read_only=True)
    beneficiaire_2_nom = serializers.StringRelatedField(source="beneficiaire_2", read_only=True)

    class Meta:
        model = SignalementDoublon
        fields = (
            "id",
            "beneficiaire_1",
            "beneficiaire_1_nom",
            "beneficiaire_2",
            "beneficiaire_2_nom",
            "score",
            "motifs",
            "methode",
            "statut",
            "traite_par",
            "date_traitement",
        )
        read_only_fields = ("traite_par", "date_traitement")
