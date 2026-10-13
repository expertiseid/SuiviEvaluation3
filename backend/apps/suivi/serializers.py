import datetime

from rest_framework import serializers

from .models import PeriodePlanification, PointSuivi, TranchePlanifiee
from .services import budget_realise_tranche, realise_tranche, statut_tranche, taux_de


class PointSuiviSerializer(serializers.ModelSerializer):
    """
    validators = [] : sans ça, DRF détecte les UniqueConstraint conditionnelles
    du modèle (activite+période, sous_activite+période — chacune valide
    seulement quand son FK est non-nul) et force à tort `activite` ET
    `sous_activite` en `required=True` tous les deux, alors qu'ils sont
    mutuellement exclusifs. La vérification d'unicité est donc refaite à la
    main dans validate() ci-dessous.
    """

    activite_libelle = serializers.StringRelatedField(source="activite", read_only=True)
    sous_activite_libelle = serializers.StringRelatedField(source="sous_activite", read_only=True)
    saisi_par_nom = serializers.StringRelatedField(source="saisi_par", read_only=True)

    class Meta:
        model = PointSuivi
        validators = []
        fields = (
            "id",
            "activite",
            "activite_libelle",
            "sous_activite",
            "sous_activite_libelle",
            "periode_debut",
            "periode_fin",
            "quantite_realisee",
            "budget_realise",
            "statut",
            "commentaire",
            "saisi_par",
            "saisi_par_nom",
            "date_saisie",
        )
        read_only_fields = ("saisi_par", "date_saisie")

    def validate(self, attrs):
        activite = attrs.get("activite") or getattr(self.instance, "activite", None)
        sous_activite = attrs.get("sous_activite") or getattr(self.instance, "sous_activite", None)
        if bool(activite) == bool(sous_activite):
            raise serializers.ValidationError(
                "Un point de suivi doit être rattaché soit à une activité, soit à une sous-activité "
                "(jamais les deux, jamais aucune)."
            )

        periode_debut = attrs.get("periode_debut") or getattr(self.instance, "periode_debut", None)
        periode_fin = attrs.get("periode_fin") or getattr(self.instance, "periode_fin", None)
        doublon = PointSuivi.objects.filter(
            activite=activite, sous_activite=sous_activite, periode_debut=periode_debut, periode_fin=periode_fin
        )
        if self.instance:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError(
                "Un point de suivi existe déjà pour cette période sur cette cible."
            )
        return attrs

    def create(self, validated_data):
        validated_data["saisi_par"] = self.context["request"].user
        return super().create(validated_data)


class TranchePlanifieeSerializer(serializers.ModelSerializer):
    """
    validators = [] : même raison que PointSuiviSerializer — la contrainte
    exactement-un-des-trois (activite/sous_activite/indicateur) et l'unicité
    par période sont vérifiées à la main dans validate(), pas via les
    contraintes du modèle (DRF ne sait pas les traduire automatiquement).

    Rattachée à une PeriodePlanification, la tranche en reprend
    automatiquement le libellé et les dates (inutile de les envoyer).
    """

    activite_libelle = serializers.StringRelatedField(source="activite", read_only=True)
    sous_activite_libelle = serializers.StringRelatedField(source="sous_activite", read_only=True)
    indicateur_libelle = serializers.StringRelatedField(source="indicateur", read_only=True)
    realise = serializers.SerializerMethodField()
    taux = serializers.SerializerMethodField()
    budget_realise = serializers.SerializerMethodField()
    taux_financier = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()

    class Meta:
        model = TranchePlanifiee
        validators = []
        fields = (
            "id",
            "periode",
            "activite",
            "activite_libelle",
            "sous_activite",
            "sous_activite_libelle",
            "indicateur",
            "indicateur_libelle",
            "libelle",
            "periode_debut",
            "periode_fin",
            "cible",
            "budget",
            "date_debut_prevue",
            "date_fin_prevue",
            "commentaire",
            "realise",
            "taux",
            "budget_realise",
            "taux_financier",
            "statut",
        )
        extra_kwargs = {
            "libelle": {"required": False},
            "periode_debut": {"required": False},
            "periode_fin": {"required": False},
        }

    def get_realise(self, obj):
        return realise_tranche(obj)

    def get_taux(self, obj):
        return taux_de(self.get_realise(obj), obj.cible)

    def get_budget_realise(self, obj):
        return budget_realise_tranche(obj)

    def get_taux_financier(self, obj):
        return taux_de(self.get_budget_realise(obj), obj.budget)

    def get_statut(self, obj):
        return statut_tranche(obj, self.get_realise(obj), datetime.date.today())

    def validate(self, attrs):
        def valeur(champ):
            return attrs[champ] if champ in attrs else getattr(self.instance, champ, None)

        activite, sous_activite, indicateur = valeur("activite"), valeur("sous_activite"), valeur("indicateur")
        if sum(bool(x) for x in (activite, sous_activite, indicateur)) != 1:
            raise serializers.ValidationError(
                "Une tranche doit être rattachée à une seule cible : une activité, une sous-activité ou un indicateur."
            )

        periode = valeur("periode")
        if periode is not None:
            if activite:
                dans_le_projet = activite.objectif_specifique.objectif_general.projet_id == periode.projet_id
            elif sous_activite:
                dans_le_projet = sous_activite.activite.objectif_specifique.objectif_general.projet_id == periode.projet_id
            else:
                from apps.indicators.services import indicateurs_pour_projet

                dans_le_projet = indicateurs_pour_projet(periode.projet_id).filter(id=indicateur.id).exists()
            if not dans_le_projet:
                raise serializers.ValidationError("Cet élément n'appartient pas au projet de la période.")
            doublon = TranchePlanifiee.objects.filter(
                periode=periode, activite=activite, sous_activite=sous_activite, indicateur=indicateur
            )
            if self.instance:
                doublon = doublon.exclude(pk=self.instance.pk)
            if doublon.exists():
                raise serializers.ValidationError("Cet élément a déjà ses valeurs pour cette période.")
            attrs["libelle"] = periode.libelle
            attrs["periode_debut"] = periode.date_debut
            attrs["periode_fin"] = periode.date_fin
        elif not valeur("libelle") or valeur("cible") is None:
            raise serializers.ValidationError("Libellé et cible sont requis.")

        periode_debut, periode_fin = valeur("periode_debut"), valeur("periode_fin")
        if not periode_debut or not periode_fin:
            raise serializers.ValidationError("Les dates de la période sont requises.")
        if periode_fin < periode_debut:
            raise serializers.ValidationError("La période de fin doit être postérieure à la période de début.")

        debut_prevu, fin_prevue = valeur("date_debut_prevue"), valeur("date_fin_prevue")
        for date_prevue in (debut_prevu, fin_prevue):
            if date_prevue and not (periode_debut <= date_prevue <= periode_fin):
                raise serializers.ValidationError(
                    f"Les dates prévues doivent rester dans la période ({periode_debut} → {periode_fin})."
                )
        if debut_prevu and fin_prevue and fin_prevue < debut_prevu:
            raise serializers.ValidationError("La date de fin prévue doit être postérieure à la date de début prévue.")
        if not activite and valeur("budget") is not None:
            attrs["budget"] = None  # budget propre aux activités uniquement
        if indicateur:
            attrs["date_debut_prevue"] = attrs["date_fin_prevue"] = None
        return attrs


class PeriodePlanificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodePlanification
        fields = ("id", "projet", "libelle", "date_debut", "date_fin")

    def validate(self, attrs):
        debut = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        fin = attrs.get("date_fin", getattr(self.instance, "date_fin", None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError("La date de fin doit être postérieure à la date de début.")
        return attrs
