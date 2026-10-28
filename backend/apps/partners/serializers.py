from rest_framework import serializers

from .models import Bailleur, CategoriePartiePrenante, Financement, Partenaire, PartiePrenante, StructureOrganisation


class PartenaireSerializer(serializers.ModelSerializer):
    projets_mise_en_oeuvre_codes = serializers.SerializerMethodField()
    projets_consortium_codes = serializers.SerializerMethodField()
    projets_bailleur_codes = serializers.SerializerMethodField()

    def get_projets_bailleur_codes(self, obj):
        return sorted(obj.projets.values_list("code", flat=True))

    class Meta:
        model = Partenaire
        fields = (
            "id", "nom", "type", "contact", "email", "telephone",
            "projets_mise_en_oeuvre_codes", "projets_consortium_codes", "projets_bailleur_codes",
        )

    def _projets(self, obj, nature):
        """Projets où le partenaire tient ce rôle : champ du projet, ou rôle précisé dans l'onglet Partenaires."""
        from apps.projects.models import Projet

        if nature == "MISE_EN_OEUVRE":
            projets = Projet.objects.filter(partenaire_mise_en_oeuvre=obj)
        else:
            projets = Projet.objects.filter(partenaires_consortium=obj)
        roles = Projet.objects.filter(roles_partenaires__partenaire=obj, roles_partenaires__nature=nature)
        return sorted(set(projets.values_list("code", flat=True)) | set(roles.values_list("code", flat=True)))

    def get_projets_mise_en_oeuvre_codes(self, obj):
        return self._projets(obj, "MISE_EN_OEUVRE")

    def get_projets_consortium_codes(self, obj):
        return self._projets(obj, "CONSORTIUM")


class BailleurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bailleur
        fields = ("id", "nom", "type", "contact")


class FinancementSerializer(serializers.ModelSerializer):
    bailleur_nom = serializers.StringRelatedField(source="bailleur", read_only=True)

    class Meta:
        model = Financement
        fields = ("id", "projet", "bailleur", "bailleur_nom", "montant_finance")


class StructureOrganisationSerializer(serializers.ModelSerializer):
    nb_projets = serializers.IntegerField(source="projets.count", read_only=True)
    nb_utilisateurs = serializers.IntegerField(source="utilisateurs.count", read_only=True)
    projets_resume = serializers.SerializerMethodField()
    utilisateurs_resume = serializers.SerializerMethodField()

    class Meta:
        model = StructureOrganisation
        fields = (
            "id", "nom", "sigle", "type", "parent", "responsable", "nb_projets", "nb_utilisateurs",
            "projets_resume", "utilisateurs_resume",
        )

    def get_projets_resume(self, obj):
        """Projets de la structure, pour l'organigramme (écran Organisation)."""
        return [{"id": p.id, "code": p.code, "nom": p.nom, "statut": p.statut} for p in obj.projets.order_by("code")]

    def get_utilisateurs_resume(self, obj):
        return [{"id": u.id, "nom": u.get_full_name() or u.username, "role": u.role} for u in obj.utilisateurs.order_by("first_name", "username")]

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        courant = parent
        while courant is not None and self.instance is not None:
            if courant.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": "Une structure ne peut pas dépendre d'elle-même ni d'une structure qui en dépend."})
            courant = courant.parent
        return attrs


class CategoriePartiePrenanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriePartiePrenante
        fields = ("id", "nom")


class PartiePrenanteSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.StringRelatedField(source="categorie", read_only=True)
    nb_projets = serializers.IntegerField(source="projets.count", read_only=True)

    class Meta:
        model = PartiePrenante
        fields = ("id", "nom", "categorie", "categorie_nom", "contact", "email", "telephone", "description", "nb_projets")
