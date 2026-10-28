from rest_framework import serializers

from .models import Document, DocumentVersion, Dossier, PieceJustificative


class PieceJustificativeSerializer(serializers.ModelSerializer):
    uploaded_by_nom = serializers.StringRelatedField(source="uploaded_by", read_only=True)

    class Meta:
        model = PieceJustificative
        fields = (
            "id",
            "fichier",
            "nom",
            "type_document",
            "uploaded_by",
            "uploaded_by_nom",
            "valeur_indicateur",
            "appreciation_strategique",
            "created_at",
        )
        read_only_fields = ("uploaded_by", "created_at")

    def validate(self, data):
        if not (data.get("valeur_indicateur") or data.get("appreciation_strategique")) and self.instance is None:
            raise serializers.ValidationError("Rattachez la pièce à une valeur d'indicateur ou à une appréciation.")
        return data

    def create(self, validated_data):
        validated_data["uploaded_by"] = self.context["request"].user
        return super().create(validated_data)


class DossierSerializer(serializers.ModelSerializer):
    cree_par_nom = serializers.StringRelatedField(source="cree_par", read_only=True)

    class Meta:
        model = Dossier
        fields = ("id", "nom", "projet", "parent", "cree_par", "cree_par_nom")
        read_only_fields = ("cree_par",)

    def create(self, validated_data):
        validated_data["cree_par"] = self.context["request"].user
        return super().create(validated_data)


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by_nom = serializers.StringRelatedField(source="uploaded_by", read_only=True)

    class Meta:
        model = DocumentVersion
        fields = ("id", "document", "fichier", "version", "uploaded_by", "uploaded_by_nom", "commentaire", "created_at")
        read_only_fields = ("version", "uploaded_by", "created_at")


class DocumentSerializer(serializers.ModelSerializer):
    cree_par_nom = serializers.StringRelatedField(source="cree_par", read_only=True)
    activite_nom = serializers.StringRelatedField(source="activite", read_only=True)
    sous_activite_nom = serializers.StringRelatedField(source="sous_activite", read_only=True)
    derniere_version = DocumentVersionSerializer(read_only=True)
    nombre_versions = serializers.IntegerField(source="versions.count", read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "nom",
            "dossier",
            "projet",
            "activite",
            "activite_nom",
            "sous_activite",
            "sous_activite_nom",
            "type_document",
            "description",
            "cree_par",
            "cree_par_nom",
            "derniere_version",
            "nombre_versions",
            "created_at",
        )
        read_only_fields = ("cree_par", "created_at")
