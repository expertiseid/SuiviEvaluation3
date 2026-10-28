from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import NiveauAdministratif, Zone


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
