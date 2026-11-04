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
    nombre_documents = serializers.IntegerField(read_only=True, default=0)
    nombre_sous_dossiers = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Dossier
        fields = ("id", "nom", "projet", "parent", "cree_par", "cree_par_nom", "nombre_documents", "nombre_sous_dossiers")
        read_only_fields = ("cree_par",)

    def validate(self, attrs):
        """Un sous-dossier appartient au même projet que son parent ; un dossier ne se range pas en lui-même."""
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        projet = attrs.get("projet", getattr(self.instance, "projet", None))
        if parent is not None:
            if parent.projet_id != (projet.pk if projet else None):
                raise serializers.ValidationError({"parent": "Le dossier parent appartient à un autre projet."})
            courant = parent
            while courant is not None:
                if self.instance and courant.pk == self.instance.pk:
                    raise serializers.ValidationError({"parent": "Un dossier ne peut pas être rangé dans lui-même."})
                courant = courant.parent
        return attrs

    def create(self, validated_data):
        validated_data["cree_par"] = self.context["request"].user
        return super().create(validated_data)


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by_nom = serializers.StringRelatedField(source="uploaded_by", read_only=True)

    def to_representation(self, instance):
        """« fichier » : adresse signée valable une heure (liens.py), jamais l'adresse /media/ publique."""
        donnees = super().to_representation(instance)
        requete = self.context.get("request")
        if requete is not None and instance.fichier:
            from .liens import adresse

            donnees["fichier"] = adresse(requete, instance)
        return donnees

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

    def validate(self, attrs):
        """Un document ne se range que dans un dossier du même projet (ou de la bibliothèque libre)."""
        dossier = attrs.get("dossier", getattr(self.instance, "dossier", None))
        projet = attrs.get("projet", getattr(self.instance, "projet", None))
        if dossier is not None and dossier.projet_id != (projet.pk if projet else None):
            raise serializers.ValidationError({"dossier": "Ce dossier appartient à un autre projet."})
        return attrs
