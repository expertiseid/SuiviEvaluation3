from rest_framework import serializers

from .controles import controler_activation, controler_circuit
from .models import Categorie, Circuit, EtapeCircuit, Mecanisme, Priorite, TypeRetour

LANGUES = {"fr", "en", "ar", "de", "es"}


class MecanismeSerializer(serializers.ModelSerializer):
    """Le mécanisme ; « controles » liste ce qui manque pour l'activer (vide = activable)."""

    controles = serializers.SerializerMethodField()

    class Meta:
        model = Mecanisme
        fields = (
            "id", "nom", "actif", "modele", "anonymat_autorise", "langues", "texte_information", "prefixe_numero",
            "jours_ouvres", "conservation_ordinaire_mois", "conservation_sensible_mois", "projets", "controles",
        )
        read_only_fields = ("actif", "modele")

    def get_controles(self, obj):
        return controler_activation(obj)

    def validate_langues(self, valeur):
        inconnues = [l for l in valeur if l not in LANGUES]
        if inconnues:
            raise serializers.ValidationError(f"Langue(s) non proposée(s) : {', '.join(inconnues)}.")
        return list(dict.fromkeys(valeur))

    def validate_prefixe_numero(self, valeur):
        valeur = valeur.strip().upper()
        if not valeur or not valeur.replace("-", "").isalnum():
            raise serializers.ValidationError("Le préfixe ne contient que des lettres et des chiffres (ex : MGP).")
        return valeur


class TypeRetourSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeRetour
        fields = ("id", "nom", "description", "ordre", "actif")


class PrioriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Priorite
        fields = ("id", "nom", "ordre", "urgente", "delai_jours", "actif")

    def validate(self, attrs):
        # Au moins une priorité urgente active doit rester (non paramétrable).
        if self.instance and self.instance.urgente and self.instance.actif:
            reste_urgente = attrs.get("urgente", True) and attrs.get("actif", True)
            autres = Priorite.objects.filter(urgente=True, actif=True).exclude(pk=self.instance.pk).exists()
            if not reste_urgente and not autres:
                raise serializers.ValidationError("Gardez au moins une priorité urgente active.")
        return attrs


class EtapeCircuitSerializer(serializers.ModelSerializer):
    role_libelle = serializers.CharField(source="role.libelle", read_only=True, default=None)
    responsable_nom = serializers.SerializerMethodField()

    class Meta:
        model = EtapeCircuit
        fields = ("id", "circuit", "nom", "ordre", "delai_jours", "role", "role_libelle", "responsable", "responsable_nom",
                  "est_cloture")

    def get_responsable_nom(self, obj):
        u = obj.responsable
        return (f"{u.first_name} {u.last_name}".strip() or u.username) if u else None

    def validate(self, attrs):
        circuit = attrs.get("circuit") or getattr(self.instance, "circuit", None)
        role = attrs["role"] if "role" in attrs else getattr(self.instance, "role", None)
        if circuit is not None and circuit.sensible and role is not None:
            raise serializers.ValidationError(
                {"role": "Un circuit confidentiel est confié à des personnes nommément désignées, pas à un rôle."}
            )
        return attrs


class CircuitSerializer(serializers.ModelSerializer):
    """Circuit avec ses étapes (lecture) et ce qui empêche de l'utiliser (« erreurs »)."""

    etapes = EtapeCircuitSerializer(many=True, read_only=True)
    erreurs = serializers.SerializerMethodField()
    nb_categories = serializers.IntegerField(source="categories.count", read_only=True)

    class Meta:
        model = Circuit
        fields = ("id", "nom", "description", "sensible", "par_defaut", "actif", "etapes", "erreurs", "nb_categories")

    def get_erreurs(self, obj):
        return controler_circuit(obj)

    def validate(self, attrs):
        if self.instance and "sensible" in attrs and attrs["sensible"] != self.instance.sensible:
            if not attrs["sensible"] and self.instance.categories.filter(sensible=True).exists():
                raise serializers.ValidationError(
                    {"sensible": "Des catégories sensibles utilisent ce circuit : il doit rester confidentiel."}
                )
            if attrs["sensible"] and self.instance.etapes.filter(role__isnull=False).exists():
                raise serializers.ValidationError(
                    {"sensible": "Remplacez d'abord les rôles des étapes par des personnes nommément désignées."}
                )
        return attrs

    def save(self, **kwargs):
        circuit = super().save(**kwargs)
        # Un seul circuit par défaut par nature (ordinaire / confidentiel).
        if circuit.par_defaut:
            Circuit.objects.filter(sensible=circuit.sensible, par_defaut=True).exclude(pk=circuit.pk).update(par_defaut=False)
        return circuit


class CategorieSerializer(serializers.ModelSerializer):
    parent_nom = serializers.CharField(source="parent.nom", read_only=True, default=None)
    circuit_nom = serializers.CharField(source="circuit.nom", read_only=True, default=None)
    sensible_effective = serializers.BooleanField(read_only=True)

    class Meta:
        model = Categorie
        fields = ("id", "nom", "description", "parent", "parent_nom", "sensible", "sensible_effective", "verrouillee",
                  "circuit", "circuit_nom", "delai_jours", "ordre", "actif")
        read_only_fields = ("verrouillee",)
        # Doublons contrôlés dans validate() (parent facultatif : catégorie principale).
        validators = []

    def validate(self, attrs):
        def valeur(champ):
            return attrs[champ] if champ in attrs else getattr(self.instance, champ, None)

        if self.instance and self.instance.verrouillee:
            if not valeur("sensible") or not valeur("actif"):
                raise serializers.ValidationError(
                    "Cette catégorie protège les personnes : elle reste sensible et active."
                )
        parent = valeur("parent")
        if parent is not None:
            if parent.parent_id is not None:
                raise serializers.ValidationError({"parent": "Deux niveaux au plus : choisissez une catégorie principale."})
            if self.instance and parent.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": "Une catégorie ne peut pas être sa propre sous-catégorie."})
            if self.instance and self.instance.sous_categories.exists():
                raise serializers.ValidationError({"parent": "Cette catégorie a des sous-catégories : elle reste principale."})
        circuit = valeur("circuit")
        sensible = valeur("sensible") or bool(parent and parent.sensible)
        if circuit is not None and sensible and not circuit.sensible:
            raise serializers.ValidationError({"circuit": "Une catégorie sensible utilise un circuit confidentiel."})
        nom = (valeur("nom") or "").strip()
        doublon = Categorie.objects.filter(parent=parent, nom__iexact=nom)
        if self.instance:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError({"nom": "Une catégorie porte déjà ce nom à ce niveau."})
        return attrs
