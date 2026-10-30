from django.db import models
from rest_framework import serializers

from apps.core.vocabulaire import v

from .attributs import nettoyer as nettoyer_attributs
from .attributs import ordonner as ordonner_attributs
from .attributs import retenir_ordre as retenir_ordre_attributs


def attributs_dans_l_ordre(serializer, attributs, projet_id):
    """Attributs dans l'ordre du projet (colonnes du fichier importé) ; ordre lu une fois par projet."""
    ordres = serializer.context.setdefault("ordres_attributs", {})
    if projet_id not in ordres:
        ordres[projet_id] = Projet.objects.filter(id=projet_id).values_list("ordre_attributs", flat=True).first() or []
    attributs = attributs or {}
    return {nom: attributs[nom] for nom in ordonner_attributs(attributs, ordres[projet_id])}
from .budgets import avertissements_budget
from .models import (
    Activite,
    Equipe,
    EvaluationRisque,
    FenetreRapportage,
    JalonLivrable,
    NiveauActivite,
    ParametresCalcul,
    ParametresRapportage,
    PartenaireProjet,
    Projet,
    Risque,
    SousActivite,
    TauxManuel,
)
from .rapportage import etat_saisie
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
            "attributs",
        )
        read_only_fields = ("quantite_realisee", "statut")

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        retenir_ordre_attributs(instance.activite.projet, instance.attributs or {})
        return instance

    def to_representation(self, instance):
        donnees = super().to_representation(instance)
        donnees["attributs"] = attributs_dans_l_ordre(self, instance.attributs, instance.activite.projet_id)
        return donnees
        extra_kwargs = {"avancement": {"min_value": 0, "max_value": 100}, "poids": {"min_value": 0}}

    def validate_attributs(self, valeur):
        return nettoyer_attributs(valeur)

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
    axes_strategiques_secondaires_noms = serializers.StringRelatedField(
        source="axes_strategiques_secondaires", many=True, read_only=True
    )
    structures_noms = serializers.StringRelatedField(source="structures", many=True, read_only=True)
    partenaires_charges_noms = serializers.SerializerMethodField()
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
            "sources_verification",
            "hypotheses",
            "attributs",
            "axe_strategique",
            "axe_strategique_libelle",
            "axes_strategiques_secondaires",
            "axes_strategiques_secondaires_noms",
            "structures",
            "structures_noms",
            "partenaires_charges_noms",
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

    def validate_attributs(self, valeur):
        return nettoyer_attributs(valeur)

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        retenir_ordre_attributs(instance.projet, instance.attributs or {})
        return instance

    def to_representation(self, instance):
        donnees = super().to_representation(instance)
        donnees["attributs"] = attributs_dans_l_ordre(self, instance.attributs, instance.projet_id)
        return donnees

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
        relations = {champ: validated_data.pop(champ, None) for champ in self.RELATIONS_MULTIPLES}
        instance = Activite(**validated_data)
        instance.clean()
        instance.save()
        self._enregistrer_relations(instance, relations)
        return instance

    def update(self, instance, validated_data):
        relations = {champ: validated_data.pop(champ, None) for champ in self.RELATIONS_MULTIPLES}
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()
        instance.save()
        self._enregistrer_relations(instance, relations)
        return instance

    RELATIONS_MULTIPLES = ("responsables", "axes_strategiques_secondaires", "structures")

    @staticmethod
    def _enregistrer_relations(instance, relations):
        for champ, valeurs in relations.items():
            if valeurs is not None:
                getattr(instance, champ).set(valeurs)

    def get_partenaires_charges_noms(self, obj):
        """Partenaires chargés de cet élément (rôle des partenaires dans le projet)."""
        return [r.partenaire.nom for r in obj.partenaires_charges.select_related("partenaire")]


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


class ParametresRapportageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresRapportage
        fields = ("controle_actif", "perimetre")


class FenetreRapportageSerializer(serializers.ModelSerializer):
    projet_code = serializers.CharField(source="projet.code", read_only=True, default=None)

    class Meta:
        model = FenetreRapportage
        fields = ("id", "projet", "projet_code", "libelle", "date_debut", "date_fin")

    def validate(self, attrs):
        debut = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        fin = attrs.get("date_fin", getattr(self.instance, "date_fin", None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"date_fin": "La fin doit être après le début."})
        return attrs


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
    elements_strategiques_secondaires_noms = serializers.StringRelatedField(
        source="elements_strategiques_secondaires", many=True, read_only=True
    )
    structures_noms = serializers.StringRelatedField(source="structures", many=True, read_only=True)
    parties_prenantes_noms = serializers.StringRelatedField(source="parties_prenantes", many=True, read_only=True)
    services_detail = serializers.SerializerMethodField()
    activites = serializers.SerializerMethodField()

    # Champs lourds (planification complète, services et leurs membres) : retirés de la liste
    # des projets, sauf demande explicite (?planification=1) — voir ProjetViewSet.
    CHAMPS_DETAIL = ("activites", "services_detail")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("sans_detail"):
            for champ in self.CHAMPS_DETAIL:
                self.fields.pop(champ, None)

    def get_services_detail(self, obj):
        """
        Services qui travaillent sur le projet (affectés au projet ou à une de ses parties), avec
        leurs membres : qui participe au projet.
        """
        from apps.partners.models import StructureOrganisation

        sur_le_projet = set(obj.structures.values_list("id", flat=True))
        services = StructureOrganisation.objects.filter(
            models.Q(projets=obj) | models.Q(activites__projet=obj)
        ).distinct().prefetch_related("utilisateurs")
        resultat = []
        for s in services:
            parties = list(obj.activites.filter(structures=s).values_list("libelle", flat=True))
            resultat.append({
                "id": s.id,
                "nom": str(s),
                "type": s.type,
                "tout_le_projet": s.id in sur_le_projet,
                "parties": parties,
                "membres": [u.get_full_name() or u.username for u in s.utilisateurs.all()],
            })
        return sorted(resultat, key=lambda x: (not x["tout_le_projet"], x["nom"]))
    financement_bailleurs_total = serializers.ReadOnlyField()

    etat_saisie = serializers.SerializerMethodField()

    def get_etat_saisie(self, obj):
        """Saisie ouverte ou fermée aujourd'hui (périodes de rapportage, voir apps.projects.rapportage)."""
        etat = etat_saisie(obj)
        return {"ouverte": etat.ouverte, "perimetre": etat.perimetre, "message": etat.message}

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
            "tout_le_pays",
            "etat_saisie",
            "saisie",
            "perimetre_fermeture",
            "approbation_realisations",
            "approbation_planification",
            "cadre_strategique",
            "cadre_strategique_nom",
            "element_strategique",
            "element_strategique_libelle",
            "elements_strategiques_secondaires",
            "elements_strategiques_secondaires_noms",
            "structures",
            "structures_noms",
            "parties_prenantes",
            "parties_prenantes_noms",
            "services_detail",
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
            "ordre_attributs",
            "activites",
        )
        read_only_fields = ("ordre_attributs",)

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
            "tout_le_pays",
            "saisie",
            "perimetre_fermeture",
            "approbation_realisations",
            "approbation_planification",
            "cadre_strategique",
            "element_strategique",
            "elements_strategiques_secondaires",
            "structures",
            "parties_prenantes",
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
        if element is not None and element in attrs.get("elements_strategiques_secondaires", []):
            raise serializers.ValidationError(
                {"elements_strategiques_secondaires": "L'élément principal n'a pas à être repris dans les autres liens."}
            )
        return attrs


class PartenaireProjetSerializer(serializers.ModelSerializer):
    partenaire_nom = serializers.StringRelatedField(source="partenaire", read_only=True)
    elements_libelles = serializers.SerializerMethodField()

    class Meta:
        model = PartenaireProjet
        fields = (
            "id", "projet", "partenaire", "partenaire_nom", "nature", "chef_de_file", "role",
            "elements", "elements_libelles",
        )

    def get_elements_libelles(self, obj):
        return [f"{a.code_activite} {a.libelle}".strip() for a in obj.elements.all()]

    def validate(self, attrs):
        projet = attrs.get("projet", getattr(self.instance, "projet", None))
        etrangers = [a for a in attrs.get("elements", []) if a.projet_id != projet.id]
        if etrangers:
            raise serializers.ValidationError({"elements": v("Ces éléments n'appartiennent pas à ce projet.")})
        return attrs


class EvaluationRisqueSerializer(serializers.ModelSerializer):
    saisi_par_nom = serializers.SerializerMethodField()
    niveau = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationRisque
        fields = (
            "id", "risque", "date", "probabilite", "impact", "niveau", "statut", "actions_menees", "commentaire",
            "saisi_par_nom", "created_at",
        )

    def get_saisi_par_nom(self, obj):
        u = obj.saisi_par
        return (u.get_full_name() or u.username) if u else ""

    def get_niveau(self, obj):
        return Risque.niveau_pour(obj.probabilite * obj.impact)

    def validate(self, data):
        for champ in ("probabilite", "impact"):
            if champ in data and not 1 <= data[champ] <= 5:
                raise serializers.ValidationError({champ: "Valeur de 1 à 5."})
        return data


class RisqueSerializer(serializers.ModelSerializer):
    criticite = serializers.IntegerField(read_only=True)
    niveau = serializers.CharField(read_only=True)
    responsable_nom = serializers.SerializerMethodField()
    element_libelle = serializers.SerializerMethodField()
    evaluations = EvaluationRisqueSerializer(many=True, read_only=True)

    class Meta:
        model = Risque
        fields = (
            "id", "projet", "code", "libelle", "description", "nature", "categorie", "element", "element_libelle",
            "probabilite", "impact", "criticite", "niveau", "mesures_attenuation", "plan_contingence", "responsable",
            "responsable_nom", "statut", "date_identification", "date_prochaine_revue", "evaluations",
        )
        read_only_fields = ("code",)

    def get_responsable_nom(self, obj):
        return str(obj.responsable) if obj.responsable else ""

    def get_element_libelle(self, obj):
        e = obj.element
        return f"{e.code_activite} {e.libelle}".strip() if e else ""

    def validate(self, data):
        for champ in ("probabilite", "impact"):
            if champ in data and not 1 <= data[champ] <= 5:
                raise serializers.ValidationError({champ: "Valeur de 1 à 5."})
        projet = data.get("projet") or getattr(self.instance, "projet", None)
        element = data.get("element")
        if element is not None and projet is not None and element.projet_id != projet.id:
            raise serializers.ValidationError({"element": "Cet élément n'appartient pas au projet."})
        return data
