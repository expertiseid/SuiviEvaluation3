from django.utils.text import slugify
from rest_framework import serializers

from .constants import ROLE_ADMIN
from .models import Role, User


def _libelle_role(code):
    role = Role.objects.filter(code=code).first()
    return role.libelle if role else code


class RoleSerializer(serializers.ModelSerializer):
    nb_utilisateurs = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id", "code", "libelle", "visibilite_globale", "peut_personnaliser_tableau_de_bord", "systeme", "nb_utilisateurs",
        )
        read_only_fields = ("id", "systeme", "nb_utilisateurs")
        # Code facultatif à la création (déduit du libellé), jamais modifiable ensuite.
        extra_kwargs = {"code": {"required": False}}

    def get_nb_utilisateurs(self, obj):
        return User.objects.filter(role=obj.code).count()

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("code", None)
            if self.instance.code == ROLE_ADMIN:
                attrs.pop("visibilite_globale", None)  # l'Administrateur voit toujours tout
                attrs.pop("peut_personnaliser_tableau_de_bord", None)  # … et peut toujours tout configurer
            return attrs

        code = attrs.get("code") or attrs.get("libelle", "")
        code = "".join(c if c.isalnum() else "_" for c in slugify(code)).upper().strip("_")[:32]
        if not code:
            raise serializers.ValidationError({"libelle": "Libellé requis."})
        if Role.objects.filter(code=code).exists():
            raise serializers.ValidationError({"libelle": f"Un rôle avec le code « {code} » existe déjà."})
        attrs["code"] = code
        return attrs



class UserSerializer(serializers.ModelSerializer):
    role_libelle = serializers.SerializerMethodField()
    peut_personnaliser_tableau_de_bord = serializers.SerializerMethodField()

    def get_role_libelle(self, obj):
        return _libelle_role(obj.role)

    def get_peut_personnaliser_tableau_de_bord(self, obj):
        from apps.core.permissions import peut_personnaliser_tableau_de_bord

        return peut_personnaliser_tableau_de_bord(obj)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_libelle",
            "peut_personnaliser_tableau_de_bord",
            "niveau_acces",
            "telephone",
            "zones_affectees",
            "is_active",
        )
        read_only_fields = ("id",)


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "niveau_acces",
            "telephone",
            "zones_affectees",
            "is_active",
            "password",
        )
        read_only_fields = ("id",)

    def validate_role(self, value):
        if not Role.objects.filter(code=value).exists():
            raise serializers.ValidationError(f"Rôle « {value} » inconnu.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        zones_affectees = validated_data.pop("zones_affectees", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if zones_affectees is not None:
            user.zones_affectees.set(zones_affectees)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        zones_affectees = validated_data.pop("zones_affectees", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if zones_affectees is not None:
            instance.zones_affectees.set(zones_affectees)
        return instance
