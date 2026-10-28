from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import CoucheImportee, NiveauAdministratif, Zone


class NiveauAdministratifSerializer(serializers.ModelSerializer):
    niveau_parent_nom = serializers.StringRelatedField(source="niveau_parent", read_only=True)

    class Meta:
        model = NiveauAdministratif
        fields = (
            "id",
            "pays",
            "nom_niveau",
            "ordre",
            "niveau_parent",
            "niveau_parent_nom",
            "saut_niveau_autorise",
            "aide_code",
        )


class ZoneSerializer(serializers.ModelSerializer):
    niveau_administratif_nom = serializers.StringRelatedField(source="niveau_administratif", read_only=True)
    pays = serializers.CharField(source="niveau_administratif.pays", read_only=True)
    parent_nom = serializers.StringRelatedField(source="parent", read_only=True)

    class Meta:
        model = Zone
        fields = (
            "id",
            "niveau_administratif",
            "niveau_administratif_nom",
            "pays",
            "parent",
            "parent_nom",
            "code",
            "nom",
            "latitude",
            "longitude",
        )

    def validate(self, attrs):
        instance = Zone(
            id=getattr(self.instance, "id", None),
            niveau_administratif=attrs.get(
                "niveau_administratif", getattr(self.instance, "niveau_administratif", None)
            ),
            parent=attrs.get("parent", getattr(self.instance, "parent", None)),
        )
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return attrs


class CoucheImporteeSerializer(serializers.ModelSerializer):
    """Description d'une couche importée (le GeoJSON se lit à part : couches-importees/{id}/geojson/)."""

    cree_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = CoucheImportee
        fields = (
            "id", "nom", "couleur", "geometrie", "fichier_source", "projection_source", "colonnes", "champ_etiquette",
            "nombre_objets", "emprise", "cree_par_nom", "created_at",
        )
        read_only_fields = ("geometrie", "fichier_source", "projection_source", "colonnes", "nombre_objets", "emprise")

    def get_cree_par_nom(self, obj):
        u = obj.cree_par
        return (u.get_full_name() or u.username) if u else ""

    def validate_couleur(self, valeur):
        import re

        if not re.fullmatch(r"#[0-9a-fA-F]{6}", valeur):
            raise serializers.ValidationError("Couleur attendue au format #RRGGBB.")
        return valeur

    def validate_champ_etiquette(self, valeur):
        if valeur and self.instance is not None and valeur not in self.instance.colonnes:
            raise serializers.ValidationError("Attribut inconnu dans cette couche.")
        return valeur
