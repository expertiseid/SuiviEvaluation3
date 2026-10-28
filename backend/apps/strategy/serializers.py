from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AppreciationStrategique, CadreStrategique, ElementStrategique, TypeNiveau


class CadreStrategiqueSerializer(serializers.ModelSerializer):
    structures_noms = serializers.StringRelatedField(source="structures", many=True, read_only=True)
    parties_prenantes_noms = serializers.StringRelatedField(source="parties_prenantes", many=True, read_only=True)

    class Meta:
        model = CadreStrategique
        fields = (
            "id", "nom", "description", "created_at",
            "structures", "structures_noms", "parties_prenantes", "parties_prenantes_noms",
        )


class TypeNiveauSerializer(serializers.ModelSerializer):
    niveau_parent_nom = serializers.StringRelatedField(source="niveau_parent", read_only=True)

    class Meta:
        model = TypeNiveau
        fields = (
            "id",
            "cadre_strategique",
            "nom_niveau",
            "ordre",
            "niveau_parent",
            "niveau_parent_nom",
            "saut_niveau_autorise",
            "aide_code",
        )


class ElementStrategiqueSerializer(serializers.ModelSerializer):
    type_niveau_nom = serializers.StringRelatedField(source="type_niveau", read_only=True)
    element_parent_nom = serializers.StringRelatedField(source="element_parent", read_only=True)
    parents_secondaires_noms = serializers.StringRelatedField(source="parents_secondaires", many=True, read_only=True)
    structures_noms = serializers.StringRelatedField(source="structures", many=True, read_only=True)
    parties_prenantes_noms = serializers.StringRelatedField(source="parties_prenantes", many=True, read_only=True)

    class Meta:
        model = ElementStrategique
        fields = (
            "id",
            "type_niveau",
            "type_niveau_nom",
            "element_parent",
            "element_parent_nom",
            "code",
            "nom",
            "description",
            "parents_secondaires",
            "parents_secondaires_noms",
            "structures",
            "structures_noms",
            "parties_prenantes",
            "parties_prenantes_noms",
        )

    def validate(self, attrs):
        instance = ElementStrategique(
            id=getattr(self.instance, "id", None),
            type_niveau=attrs.get("type_niveau", getattr(self.instance, "type_niveau", None)),
            element_parent=attrs.get("element_parent", getattr(self.instance, "element_parent", None)),
        )
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        self._valider_parents_secondaires(attrs)
        return attrs

    def _valider_parents_secondaires(self, attrs):
        """Un lien « contribue aussi à » vise un élément d'un niveau supérieur, jamais lui-même ni un de ses descendants."""
        parents = attrs.get("parents_secondaires")
        if not parents:
            return
        type_niveau = attrs.get("type_niveau", getattr(self.instance, "type_niveau", None))
        principal = attrs.get("element_parent", getattr(self.instance, "element_parent", None))
        descendants = set()
        if self.instance is not None:
            a_voir = [self.instance.id]
            while a_voir:
                enfants = list(ElementStrategique.objects.filter(element_parent_id__in=a_voir).values_list("id", flat=True))
                descendants.update(enfants)
                a_voir = enfants
        for parent in parents:
            if self.instance is not None and (parent.id == self.instance.id or parent.id in descendants):
                raise serializers.ValidationError({"parents_secondaires": "Un élément ne peut pas contribuer à lui-même ni à ses descendants."})
            if principal is not None and parent.id == principal.id:
                raise serializers.ValidationError({"parents_secondaires": "Le parent principal n'a pas à être repris dans les autres liens."})
            meme_cadre = parent.type_niveau.cadre_strategique_id == type_niveau.cadre_strategique_id
            if meme_cadre and parent.type_niveau.ordre >= type_niveau.ordre:
                raise serializers.ValidationError(
                    {"parents_secondaires": f"« {parent} » n'est pas d'un niveau supérieur à « {type_niveau.nom_niveau} »."}
                )


class AppreciationStrategiqueSerializer(serializers.ModelSerializer):
    saisi_par_nom = serializers.SerializerMethodField()
    pieces = serializers.SerializerMethodField()

    class Meta:
        model = AppreciationStrategique
        fields = (
            "id", "element", "libelle_periode", "periode_debut", "periode_fin", "etat", "commentaire", "difficultes",
            "recommandations", "saisi_par_nom", "pieces", "created_at",
        )

    def get_saisi_par_nom(self, obj):
        u = obj.saisi_par
        return (u.get_full_name() or u.username) if u else ""

    def get_pieces(self, obj):
        from .suivi import piece_jointe

        return [piece_jointe(p, self.context.get("request")) for p in obj.pieces_justificatives.all()]

    def validate(self, data):
        debut = data.get("periode_debut", getattr(self.instance, "periode_debut", None))
        fin = data.get("periode_fin", getattr(self.instance, "periode_fin", None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"periode_fin": "La fin de la période précède son début."})
        return data
