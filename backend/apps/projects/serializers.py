from rest_framework import serializers

from apps.core.vocabulaire import v

from .budgets import avertissements_budget
from .models import Activite, Equipe, JalonLivrable, NiveauActivite, ParametresCalcul, Projet, SousActivite, TauxManuel
from .taux import ArbreTaux


class NiveauActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NiveauActivite
        fields = ("id", "projet", "profondeur", "nom_niveau")


class EquipeSerializer(serializers.ModelSerializer):
    membres_noms = serializers.StringRelatedField(source="membres", many=True, read_only=True)

    class Meta:
        model = Equipe
        fields = ("id", "nom", "membres", "membres_noms", "date_debut_contrat", "date_fin_contrat")


class SousActiviteSerializer(serializers.ModelSerializer):
    """
    quantite_realisee/statut sont en lecture seule ici : ce sont des valeurs
    dérivées, synchronisées automatiquement depuis le dernier PointSuivi
    (apps.suivi) — la planification (ce formulaire) ne fixe que la cible, la
    saisie du réel se fait exclusivement depuis le module Suivi.
    """

    axe_strategique_libelle = serializers.StringRelatedField(source="axe_strategique", read_only=True)

    class Meta:
        model = SousActivite
        fields = (
            "id",
            "activite",
            "libelle",
            "axe_strategique",
            "axe_strategique_libelle",
            "quantite_prevue",
            "quantite_realisee",
            "unite_quantite",
            "date_debut",
            "date_fin",
            "statut",
            "poids",
            "avancement",
        )
        read_only_fields = ("quantite_realisee", "statut")
        extra_kwargs = {"avancement": {"min_value": 0, "max_value": 100}, "poids": {"min_value": 0}}

    def validate(self, attrs):
        if "axe_strategique" in attrs and attrs["axe_strategique"] is not None:
            axe = attrs["axe_strategique"]
            activite = attrs.get("activite") or getattr(self.instance, "activite", None)
            cadre_projet = activite.projet.cadre_strategique_id
            # Projet sans cadre stratégique choisi : rien à quoi comparer, pas de restriction.
            if cadre_projet is not None and axe.type_niveau.cadre_strategique_id != cadre_projet:
                raise serializers.ValidationError(
                    {"axe_strategique": v("Cet élément stratégique n'appartient pas au cadre stratégique du projet.")}
                )
        return attrs


class ActiviteSerializer(serializers.ModelSerializer):
    """
    statut/quantite_realisee/budget_realise sont en lecture seule ici : ce
    sont des valeurs dérivées, synchronisées automatiquement depuis le
    dernier PointSuivi (apps.suivi) — la planification (ce formulaire/API)
    ne fixe que la cible, la saisie du réel se fait exclusivement depuis le
    module Suivi (qui, lui, écrit directement sur le modèle, hors de ce
    serializer). date_debut_reelle/date_fin_reelle restent écrivables ici :
    ce sont de simples dates jalons (pas un historique périodique), éditées
    depuis le module Suivi via une requête PATCH ciblée.
    """

    responsable_compte_nom = serializers.StringRelatedField(source="responsable", read_only=True)
    responsables_noms = serializers.StringRelatedField(source="responsables", many=True, read_only=True)
    equipe_responsable_nom = serializers.StringRelatedField(source="equipe_responsable", read_only=True)
    axe_strategique_libelle = serializers.StringRelatedField(source="axe_strategique", read_only=True)
    sous_activites = SousActiviteSerializer(many=True, read_only=True)
    jalons_livrables = serializers.SerializerMethodField()
    enfants = serializers.SerializerMethodField()
    taux_realisation = serializers.SerializerMethodField()
    methode_calcul_effective = serializers.SerializerMethodField()
    taux_avertissements = serializers.SerializerMethodField()
    budget_avertissements = serializers.SerializerMethodField()
    taux_execution_financiere = serializers.ReadOnlyField()
    alerte_retard = serializers.ReadOnlyField()

    class Meta:
        model = Activite
        fields = (
            "id",
            "projet",
            "activite_parent",
            "code_activite",
            "libelle",
            "description",
            "statut",
            "commentaire",
            "axe_strategique",
            "axe_strategique_libelle",
            "budget_alloue",
            "budget_realise",
            "valeur_reference",
            "quantite_prevue",
            "quantite_realisee",
            "unite_quantite",
            "date_debut",
            "date_fin",
            "date_debut_reelle",
            "date_fin_reelle",
            "nb_jours_planifies",
            "date_rappel",
            "responsables",
            "responsables_noms",
            "responsable",
            "responsable_compte_nom",
            "equipe_responsable",
            "equipe_responsable_nom",
            "sous_activites",
            "enfants",
            "taux_realisation",
            "methode_calcul",
            "methode_agregation",
            "poids",
            "methode_calcul_effective",
            "taux_avertissements",
            "budget_avertissements",
            "jalons_livrables",
            "taux_execution_financiere",
            "alerte_retard",
        )
        read_only_fields = ("statut", "quantite_realisee", "budget_realise")
        # Le projet peut être omis à la création d'un élément enfant : il est
        # alors repris de l'élément parent (voir validate()).
        extra_kwargs = {"projet": {"required": False}}

    def _resultat_taux(self, obj):
        # Un seul calcul pour tout l'arbre du projet, partagé par tous ses éléments.
        arbres = self.context.setdefault("arbres_taux", {})
        if obj.projet_id not in arbres:
            arbres[obj.projet_id] = ArbreTaux(obj.projet)
        return arbres[obj.projet_id].resultat(obj.id)

    def get_taux_realisation(self, obj):
        return self._resultat_taux(obj).taux

    def get_methode_calcul_effective(self, obj):
        """Méthode réellement appliquée (héritée si l'élément n'en fixe pas), ou AGREGATION."""
        return self._resultat_taux(obj).methode

    def get_taux_avertissements(self, obj):
        return self._resultat_taux(obj).avertissements

    def get_budget_avertissements(self, obj):
        """Contrôle du budget d'un niveau dont le détail est saisi en dessous (apps.projects.budgets)."""
        controles = self.context.setdefault("controles_budget", {})
        if obj.projet_id not in controles:
            controles[obj.projet_id] = avertissements_budget(
                Activite.objects.filter(projet_id=obj.projet_id).only("id", "activite_parent_id", "budget_alloue")
            )
        return controles[obj.projet_id].get(obj.id, [])

    def get_jalons_livrables(self, obj):
        return JalonLivrableSerializer(obj.jalons_livrables.all(), many=True).data

    def get_enfants(self, obj):
        # Activités imbriquées sous celle-ci (voir Activite.activite_parent) —
        # même sérialiseur, récursif : chaque enfant peut lui-même avoir des
        # enfants (profondeur illimitée).
        return ActiviteSerializer(obj.enfants.all(), many=True, context=self.context).data

    def validate(self, attrs):
        activite_parent = attrs.get("activite_parent") or getattr(self.instance, "activite_parent", None)
        projet = attrs.get("projet") or getattr(self.instance, "projet", None)
        if projet is None and activite_parent is not None:
            projet = attrs["projet"] = activite_parent.projet
        if projet is None:
            raise serializers.ValidationError({"projet": v("Indique le projet ou l'élément parent.")})
        if activite_parent and activite_parent.projet_id != projet.id:
            raise serializers.ValidationError(
                {"activite_parent": v("L'élément parent doit appartenir au même projet.")}
            )

        if "axe_strategique" in attrs and attrs["axe_strategique"] is not None:
            axe = attrs["axe_strategique"]
            cadre_projet = projet.cadre_strategique_id
            # Projet sans cadre stratégique choisi : rien à quoi comparer, pas de restriction.
            if cadre_projet is not None and axe.type_niveau.cadre_strategique_id != cadre_projet:
                raise serializers.ValidationError(
                    {"axe_strategique": v("Cet élément stratégique n'appartient pas au cadre stratégique du projet.")}
                )
        return attrs

    def create(self, validated_data):
        # responsables (M2M) doit être retiré avant la création de l'instance
        # (comme le fait ModelSerializer.create() par défaut) — on reproduit
        # ce comportement à la main puisqu'on a besoin d'appeler clean() juste
        # avant le save() pour valider activite_parent.
        responsables = validated_data.pop("responsables", None)
        instance = Activite(**validated_data)
        instance.clean()
        instance.save()
        if responsables is not None:
            instance.responsables.set(responsables)
        return instance

    def update(self, instance, validated_data):
        responsables = validated_data.pop("responsables", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()
        instance.save()
        if responsables is not None:
            instance.responsables.set(responsables)
        return instance


class JalonLivrableSerializer(serializers.ModelSerializer):
    valide_par_nom = serializers.StringRelatedField(source="valide_par", read_only=True)

    class Meta:
        model = JalonLivrable
        fields = (
            "id", "activite", "type", "libelle", "poids", "date_prevue", "achevement",
            "valide", "valide_par", "valide_par_nom", "date_validation",
        )
        read_only_fields = ("valide_par", "date_validation")
        extra_kwargs = {"achevement": {"min_value": 0, "max_value": 100}, "poids": {"min_value": 0}}


class TauxManuelSerializer(serializers.ModelSerializer):
    saisi_par_nom = serializers.StringRelatedField(source="saisi_par", read_only=True)

    class Meta:
        model = TauxManuel
        fields = ("id", "activite", "taux", "date", "saisi_par", "saisi_par_nom", "commentaire")
        read_only_fields = ("saisi_par",)
        extra_kwargs = {"taux": {"min_value": 0, "max_value": 100}}


class ParametresCalculSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresCalcul
        fields = ("methode_calcul", "methode_agregation", "plafonner_agregation")


class ProjetSerializer(serializers.ModelSerializer):
    """
    Lecture : FK affichées en clair + planification imbriquée (`activites` :
    les éléments de premier niveau, chacun avec ses `enfants`, sur autant de
    niveaux que le projet en définit).
    """

    partenaire_bailleur_nom = serializers.StringRelatedField(source="partenaire_bailleur", read_only=True)
    partenaire_mise_en_oeuvre_nom = serializers.StringRelatedField(source="partenaire_mise_en_oeuvre", read_only=True)
    partenaires_consortium_noms = serializers.StringRelatedField(source="partenaires_consortium", many=True, read_only=True)
    cadre_strategique_nom = serializers.StringRelatedField(source="cadre_strategique", read_only=True)
    element_strategique_libelle = serializers.SerializerMethodField()
    activites = serializers.SerializerMethodField()
    financement_bailleurs_total = serializers.ReadOnlyField()

    class Meta:
        model = Projet
        fields = (
            "id",
            "nom",
            "code",
            "pays",
            "partenaire_bailleur",
            "partenaire_bailleur_nom",
            "partenaire_mise_en_oeuvre",
            "partenaire_mise_en_oeuvre_nom",
            "partenaires_consortium",
            "partenaires_consortium_noms",
            "budget_total",
            "fonds_propres",
            "financement_bailleurs_total",
            "date_debut",
            "date_fin",
            "date_rappel",
            "statut",
            "type_mise_en_oeuvre",
            "zones",
            "cadre_strategique",
            "cadre_strategique_nom",
            "element_strategique",
            "element_strategique_libelle",
            "chef_de_projet_nom",
            "utilisateurs_affectes",
            "cible_totale",
            "cible_hommes",
            "cible_femmes",
            "cible_jeunes",
            "cible_pdi",
            "elements_capitalisation",
            "methode_calcul",
            "methode_agregation",
            "activites",
        )

    def get_element_strategique_libelle(self, obj):
        element = obj.element_strategique
        if element is None:
            return None
        return f"{element.type_niveau.nom_niveau} : {element}"

    def get_activites(self, obj):
        racines = obj.activites.filter(activite_parent__isnull=True)
        return ActiviteSerializer(racines, many=True, context=self.context).data


class ProjetWriteSerializer(serializers.ModelSerializer):
    """Écriture : uniquement les IDs en FK/M2M, pas de hiérarchie imbriquée."""

    class Meta:
        model = Projet
        fields = (
            "id",
            "nom",
            "code",
            "pays",
            "partenaire_bailleur",
            "partenaire_mise_en_oeuvre",
            "partenaires_consortium",
            "budget_total",
            "fonds_propres",
            "date_debut",
            "date_fin",
            "date_rappel",
            "statut",
            "type_mise_en_oeuvre",
            "zones",
            "cadre_strategique",
            "element_strategique",
            "chef_de_projet_nom",
            "utilisateurs_affectes",
            "cible_totale",
            "cible_hommes",
            "cible_femmes",
            "cible_jeunes",
            "cible_pdi",
            "elements_capitalisation",
            "methode_calcul",
            "methode_agregation",
        )

    def validate(self, attrs):
        element = attrs.get("element_strategique", getattr(self.instance, "element_strategique", None))
        cadre = attrs.get("cadre_strategique", getattr(self.instance, "cadre_strategique", None))
        if element is not None:
            if cadre is None:
                # Choisir un élément suffit : le cadre est celui de l'élément.
                attrs["cadre_strategique"] = element.type_niveau.cadre_strategique
            elif element.type_niveau.cadre_strategique_id != cadre.id:
                raise serializers.ValidationError(
                    {"element_strategique": v("Cet élément n'appartient pas au cadre stratégique du projet.")}
                )
        return attrs
