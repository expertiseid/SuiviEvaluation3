from django.utils.text import slugify
from rest_framework import serializers

from apps.core.vocabulaire import v
from apps.projects.models import Activite
from apps.strategy.models import ElementStrategique

from .constants import ROLE_ADMIN
from .models import DemandeInscription, Role, User


def _libelle_role(code):
    role = Role.objects.filter(code=code).first()
    return role.libelle if role else code


class RoleSerializer(serializers.ModelSerializer):
    nb_utilisateurs = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id", "code", "libelle", "visibilite_globale", "peut_personnaliser_tableau_de_bord", "peut_approuver",
            "systeme", "nb_utilisateurs",
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
                attrs.pop("peut_approuver", None)  # … et approuver
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
    activites_masquees = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    elements_masques = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    role_libelle = serializers.SerializerMethodField()
    peut_personnaliser_tableau_de_bord = serializers.SerializerMethodField()
    peut_approuver = serializers.SerializerMethodField()

    structure_libelle = serializers.SerializerMethodField()
    est_demo = serializers.SerializerMethodField()
    est_operateur = serializers.SerializerMethodField()

    def get_est_operateur(self, obj):
        """Opérateur Expertise-ID (console de la plateforme multi-organisations, adresse principale)."""
        from apps.organisations import contexte

        return bool(obj.is_superuser and contexte.actif() and contexte.courante() is None)

    def get_est_demo(self, obj):
        """Visiteur de l'installation de démonstration : bandeau « Mode démonstration »."""
        from .demo import IDENTIFIANT, actif

        return actif() and obj.username == IDENTIFIANT
    def get_structure_libelle(self, obj):
        """Structure de l'utilisateur en clair : « Partenaire de consortium — ONG X », « Organisation — Service S&E »…"""
        if not obj.type_structure:
            return ""
        detail = obj.structure_interne or obj.partenaire or obj.partie_prenante
        type_libelle = obj.get_type_structure_display()
        return f"{type_libelle} — {detail}" if detail else type_libelle

    def get_peut_approuver(self, obj):
        from apps.core.permissions import peut_approuver

        return peut_approuver(obj)

    def get_role_libelle(self, obj):
        return _libelle_role(obj.role)

    def get_peut_personnaliser_tableau_de_bord(self, obj):
        from apps.core.permissions import peut_personnaliser_tableau_de_bord

        return peut_personnaliser_tableau_de_bord(obj)

    class Meta:
        model = User
        fields = (
            "id",
            "langue",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_libelle",
            "peut_personnaliser_tableau_de_bord",
            "peut_approuver",
            "acces_modules",
            "type_structure",
            "structure_interne",
            "partenaire",
            "partie_prenante",
            "structure_libelle",
            "niveau_acces",
            "telephone",
            "zones_affectees",
            "is_active",
            "est_demo",
            "est_operateur",
            "activites_masquees",
            "elements_masques",
        )
        read_only_fields = ("id",)


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    # Éléments masqués à cet utilisateur (apps.core.masquage) : masquer un élément masque ce qui est en dessous.
    activites_masquees = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=Activite.objects.all())
    elements_masques = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=ElementStrategique.objects.all())

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
            "acces_modules",
            "type_structure",
            "structure_interne",
            "partenaire",
            "partie_prenante",
            "is_active",
            "password",
            "activites_masquees",
            "elements_masques",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        """Seul le lien correspondant au type de structure est gardé (les autres sont vidés)."""
        attrs = super().validate(attrs)
        from apps.organisations import contexte

        # Plateforme multi-organisations : l'adresse courriel sert à se connecter, elle est obligatoire.
        courriel = attrs.get("email", getattr(self.instance, "email", ""))
        if contexte.actif() and contexte.courante() is not None and not (courriel or "").strip():
            raise serializers.ValidationError({"email": v("L'adresse courriel est obligatoire : elle sert à se connecter.")})
        type_structure = attrs.get("type_structure", getattr(self.instance, "type_structure", ""))
        garde = {
            "INTERNE": "structure_interne",
            "CONSORTIUM": "partenaire",
            "MISE_EN_OEUVRE": "partenaire",
            "BAILLEUR": "partenaire",
            "PARTIE_PRENANTE": "partie_prenante",
        }.get(type_structure)
        if "type_structure" in attrs or any(c in attrs for c in ("structure_interne", "partenaire", "partie_prenante")):
            for champ in ("structure_interne", "partenaire", "partie_prenante"):
                if champ != garde:
                    attrs[champ] = None
        return attrs

    def validate_email(self, value):
        """Plateforme multi-organisations : l'adresse sert à se connecter, elle n'appartient qu'à un compte."""
        from apps.organisations import comptes, contexte

        org = contexte.courante()
        if contexte.actif() and org is not None and comptes.courriel_pris(value, org, getattr(self.instance, "pk", None)):
            raise serializers.ValidationError("Cette adresse courriel est déjà utilisée par un autre compte de la plateforme.")
        return value

    def validate_acces_modules(self, value):
        from apps.core.modules import NIVEAUX

        if not isinstance(value, dict) or any(niveau not in NIVEAUX for niveau in value.values()):
            raise serializers.ValidationError("Droits par module invalides.")
        return value

    def validate_role(self, value):
        if not Role.objects.filter(code=value).exists():
            raise serializers.ValidationError(f"Rôle « {value} » inconnu.")
        return value

    MASQUAGES = ("activites_masquees", "elements_masques")  # côté inverse des relations : .set() après l'enregistrement

    def _masquages(self, user, masquages):
        for champ, valeurs in masquages.items():
            if valeurs is not None:
                getattr(user, champ).set(valeurs)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        zones_affectees = validated_data.pop("zones_affectees", None)
        masquages = {c: validated_data.pop(c, None) for c in self.MASQUAGES}
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if zones_affectees is not None:
            user.zones_affectees.set(zones_affectees)
        self._masquages(user, masquages)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        zones_affectees = validated_data.pop("zones_affectees", None)
        masquages = {c: validated_data.pop(c, None) for c in self.MASQUAGES}
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if zones_affectees is not None:
            instance.zones_affectees.set(zones_affectees)
        self._masquages(instance, masquages)
        return instance


class DemandeInscriptionSerializer(serializers.ModelSerializer):
    offre_libelle = serializers.CharField(source="get_offre_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = DemandeInscription
        exclude = ("mot_de_passe",)
        read_only_fields = ("cree_le",)
