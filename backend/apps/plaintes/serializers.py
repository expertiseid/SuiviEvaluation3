from rest_framework import serializers

from apps.core.vocabulaire import v

from .controles import controler_activation, controler_circuit
from .models import (
    ActionCorrective, ActionDossier, Categorie, Circuit, Dossier, EtapeCircuit, JourFerie, Mecanisme, ModeleMessage,
    DemandeDroits, HabilitationSensible, PieceJointe, Prestataire, Priorite, TypeRetour, VueDossiers,
)
from .traitement import nom_personne

LANGUES = {"fr", "en", "ar", "de", "es", "it"}


class MecanismeSerializer(serializers.ModelSerializer):
    """Le mécanisme ; « controles » liste ce qui manque pour l'activer (vide = activable)."""

    controles = serializers.SerializerMethodField()
    plafond_piece_mo = serializers.SerializerMethodField()
    pieces_equipe = serializers.SerializerMethodField()

    class Meta:
        model = Mecanisme
        fields = (
            "id", "nom", "actif", "modele", "anonymat_autorise", "langues", "texte_information", "prefixe_numero",
            "jours_ouvres", "conservation_ordinaire_mois", "conservation_sensible_mois", "projets", "controles",
            "delai_defaut_jours", "rappel_jours_avant", "escalade_active", "notifications_courriel",
            "circuit_alternatif", "seuil_masquage", "accuse_reception_auto", "signature_messages",
            "pieces_formulaire_public", "taille_max_piece_mo", "plafond_piece_mo", "pieces_equipe",
            "responsable_traitement", "contact_donnees", "anonymisation_automatique", "texte_consentement",
        )
        read_only_fields = ("actif", "modele")

    def get_controles(self, obj):
        return controler_activation(obj)

    def get_pieces_equipe(self, obj):
        """Formats et limites des fichiers joints par l'équipe (saisie, ajout sur la fiche)."""
        from .pieces import FORMATS_ACCEPTES, PIECES_PAR_AJOUT, taille_max_mo

        return {"formats": FORMATS_ACCEPTES, "taille_max_mo": taille_max_mo(obj), "nombre_max": PIECES_PAR_AJOUT}

    def get_plafond_piece_mo(self, obj):
        from .pieces import plafond_mo

        return plafond_mo()

    def validate_taille_max_piece_mo(self, valeur):
        from .pieces import plafond_mo

        if not 1 <= valeur <= plafond_mo():
            raise serializers.ValidationError(f"Entre 1 et {plafond_mo()} Mo (plafond de la plateforme).")
        return valeur

    def validate_langues(self, valeur):
        inconnues = [l for l in valeur if l not in LANGUES]
        if inconnues:
            raise serializers.ValidationError(f"Langue(s) non proposée(s) : {', '.join(inconnues)}.")
        return list(dict.fromkeys(valeur))

    def validate_seuil_masquage(self, valeur):
        if valeur < 5:
            raise serializers.ValidationError("Le seuil de masquage ne descend jamais en dessous de 5.")
        return valeur

    def validate_circuit_alternatif(self, valeur):
        if valeur is not None and not valeur.sensible:
            raise serializers.ValidationError("Le circuit alternatif doit être un circuit confidentiel.")
        return valeur

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
        responsable = attrs.get("responsable") if "responsable" in attrs else None
        if circuit is not None and circuit.sensible and responsable is not None:
            from .habilitations import est_habilite

            if not est_habilite(responsable):
                raise serializers.ValidationError({"responsable": v(
                    "Cette personne n'a pas d'habilitation confidentielle : demandez-la d'abord "
                    "(Paramétrage › Habilitations), puis faites-la valider par une deuxième personne.")})
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


class DossierSerializer(serializers.ModelSerializer):
    """Dossier en lecture ; il se modifie par les actions de traitement (traitement.py), jamais directement."""

    type_retour_nom = serializers.CharField(source="type_retour.nom", read_only=True)
    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True, default=None)
    categorie_parent_nom = serializers.CharField(source="categorie.parent.nom", read_only=True, default=None)
    priorite_nom = serializers.CharField(source="priorite.nom", read_only=True, default=None)
    priorite_urgente = serializers.BooleanField(source="priorite.urgente", read_only=True, default=False)
    projet_nom = serializers.CharField(source="projet.nom", read_only=True, default=None)
    projet_code = serializers.CharField(source="projet.code", read_only=True, default=None)
    circuit_nom = serializers.CharField(source="circuit.nom", read_only=True, default=None)
    etape_nom = serializers.CharField(source="etape.nom", read_only=True, default=None)
    saisi_par_nom = serializers.SerializerMethodField()
    responsable_nom = serializers.SerializerMethodField()
    gestionnaire_initial_nom = serializers.SerializerMethodField()
    mis_en_cause_noms = serializers.SerializerMethodField()

    class Meta:
        model = Dossier
        fields = (
            "id", "numero", "canal", "date_reception", "recueilli_directement", "type_retour", "type_retour_nom",
            "categorie", "categorie_nom", "categorie_parent_nom", "priorite", "priorite_nom", "priorite_urgente",
            "projet", "projet_nom", "projet_code", "lieu", "description", "concerne_personnel", "sensible", "circuit",
            "circuit_nom", "etape", "etape_nom", "statut", "anonyme", "nom", "telephone", "courriel", "mode_reponse",
            "consentement", "consentement_texte", "consentement_le", "langue", "saisi_par", "saisi_par_nom", "created_at",
            "responsable", "responsable_nom", "decision", "date_decision", "date_reponse", "issue", "motif_cloture",
            "retour_donne", "raison_sans_retour", "oriente_vers", "consentement_reference", "date_cloture", "en_recours",
            "gestionnaire_initial", "gestionnaire_initial_nom",
            "echeance", "echeance_etape", "date_entree_etape", "jours_prolongation", "en_retard",
            "mis_en_cause_utilisateurs", "mis_en_cause_noms", "mis_en_cause_libre", "suspension_legale", "motif_suspension",
            "anonymise", "date_anonymisation",
        )
        read_only_fields = fields

    def get_saisi_par_nom(self, obj):
        return nom_personne(obj.saisi_par) or None

    def get_responsable_nom(self, obj):
        return nom_personne(obj.responsable) or None

    def get_gestionnaire_initial_nom(self, obj):
        return nom_personne(obj.gestionnaire_initial) or None

    def get_mis_en_cause_noms(self, obj):
        return [nom_personne(u) for u in obj.mis_en_cause_utilisateurs.all()]


class ActionDossierSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ActionDossier
        fields = ("id", "type", "auteur", "auteur_nom", "date", "texte", "details", "sens", "canal", "objet")
        read_only_fields = fields

    def get_auteur_nom(self, obj):
        return nom_personne(obj.auteur) or None


class HabilitationSerializer(serializers.ModelSerializer):
    """Habilitation confidentielle ; « peut_* » : ce que la personne connectée peut en faire."""

    utilisateur_nom = serializers.SerializerMethodField()
    utilisateur_role = serializers.CharField(source="utilisateur.role", read_only=True)
    demandee_par_nom = serializers.SerializerMethodField()
    validee_par_nom = serializers.SerializerMethodField()
    retiree_par_nom = serializers.SerializerMethodField()
    en_vigueur = serializers.SerializerMethodField()
    peut_valider = serializers.SerializerMethodField()
    peut_confirmer = serializers.SerializerMethodField()

    class Meta:
        model = HabilitationSensible
        fields = ("id", "utilisateur", "utilisateur_nom", "utilisateur_role", "statut", "motif", "demandee_par",
                  "demandee_par_nom", "date_demande", "premiere", "validee_par_nom", "date_validation", "active_le",
                  "commentaire_validation", "retiree_par_nom", "date_retrait", "motif_retrait", "en_vigueur",
                  "peut_valider", "peut_confirmer")
        read_only_fields = fields

    def get_utilisateur_nom(self, obj):
        return nom_personne(obj.utilisateur)

    def get_demandee_par_nom(self, obj):
        return nom_personne(obj.demandee_par) or None

    def get_validee_par_nom(self, obj):
        return nom_personne(obj.validee_par) or None

    def get_retiree_par_nom(self, obj):
        return nom_personne(obj.retiree_par) or None

    def get_en_vigueur(self, obj):
        from django.utils import timezone

        return obj.statut == "ACTIVE" or (obj.statut == "EN_DELAI" and obj.active_le and obj.active_le <= timezone.now())

    def _moi(self):
        return self.context["request"].user

    def get_peut_valider(self, obj):
        from .habilitations import valideurs_possibles

        return obj.statut == "EN_ATTENTE" and not obj.premiere and valideurs_possibles(obj).filter(pk=self._moi().pk).exists()

    def get_peut_confirmer(self, obj):
        return obj.statut == "EN_ATTENTE" and obj.premiere and obj.demandee_par_id == self._moi().pk


class DemandeDroitsSerializer(serializers.ModelSerializer):
    """Demande sur les données personnelles (lecture) ; créée et traitée par droits.py."""

    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    traitee_par_nom = serializers.SerializerMethodField()
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = DemandeDroits
        fields = ("id", "type", "type_libelle", "statut", "statut_libelle", "date_reception", "echeance", "demandeur",
                  "contact", "description", "dossier", "numero_dossier", "reponse", "date_reponse", "traitee_par_nom",
                  "en_retard", "created_at")
        read_only_fields = fields

    def get_traitee_par_nom(self, obj):
        return nom_personne(obj.traitee_par) or None

    def get_en_retard(self, obj):
        from django.utils import timezone

        return obj.statut in ("RECUE", "EN_COURS") and obj.echeance < timezone.localdate()


class PieceJointeSerializer(serializers.ModelSerializer):
    ajoute_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = PieceJointe
        fields = ("id", "nom", "type_mime", "taille", "source", "ajoute_par", "ajoute_par_nom", "date", "metadonnees_effacees")
        read_only_fields = fields

    def get_ajoute_par_nom(self, obj):
        return nom_personne(obj.ajoute_par) or None


class DossierDetailSerializer(DossierSerializer):
    """Fiche complète : journal, dossiers liés (seulement ceux que l'utilisateur peut voir)."""

    actions = ActionDossierSerializer(many=True, read_only=True)
    pieces = PieceJointeSerializer(many=True, read_only=True)
    dossiers_lies = serializers.SerializerMethodField()
    referencements = serializers.SerializerMethodField()
    habilite = serializers.SerializerMethodField()
    fin_conservation = serializers.SerializerMethodField()

    class Meta(DossierSerializer.Meta):
        fields = DossierSerializer.Meta.fields + ("actions", "pieces", "dossiers_lies", "referencements", "habilite", "fin_conservation")
        read_only_fields = fields

    def get_referencements(self, obj):
        return [{"id": r.id, "prestataire": r.prestataire.nom, "type": r.type, "date": r.date, "auteur": nom_personne(r.auteur)}
                for r in obj.referencements.select_related("prestataire", "auteur")]

    def get_habilite(self, obj):
        """L'utilisateur peut-il lever la sensibilité (point focal du circuit, Administrateur) ?"""
        from .confidentiel import est_habilite

        requete = self.context.get("request")
        return bool(requete and est_habilite(obj, requete.user))

    def get_fin_conservation(self, obj):
        from .confidentiel import fin_de_conservation

        return fin_de_conservation(obj)

    def get_dossiers_lies(self, obj):
        visibles = self.context.get("visibles")
        lies = obj.dossiers_lies.all() if visibles is None else visibles.filter(pk__in=obj.dossiers_lies.values("pk"))
        return [{"id": d.id, "numero": d.numero, "statut": d.statut} for d in lies.order_by("numero")]


class VueDossiersSerializer(serializers.ModelSerializer):
    class Meta:
        model = VueDossiers
        fields = ("id", "nom", "filtres")

    def validate_nom(self, valeur):
        valeur = valeur.strip()
        doublon = VueDossiers.objects.filter(utilisateur=self.context["request"].user, nom__iexact=valeur)
        if self.instance:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Vous avez déjà une vue de ce nom.")
        return valeur


class JourFerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = JourFerie
        fields = ("id", "date", "libelle")


class PrestataireSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prestataire
        fields = ("id", "nom", "type", "contact", "zone", "actif")


class ActionCorrectiveSerializer(serializers.ModelSerializer):
    """Action corrective ; seuls les dossiers que l'utilisateur peut voir sont montrés et peuvent être liés."""

    responsable_nom = serializers.SerializerMethodField()
    projet_code = serializers.CharField(source="projet.code", read_only=True, default=None)
    dossiers_lies = serializers.SerializerMethodField()

    class Meta:
        model = ActionCorrective
        fields = ("id", "titre", "description", "projet", "projet_code", "responsable", "responsable_nom", "echeance",
                  "statut", "date_realisation", "dossiers", "dossiers_lies", "created_at")
        read_only_fields = ("date_realisation", "created_at")
        extra_kwargs = {"dossiers": {"required": False}}

    def get_responsable_nom(self, obj):
        return nom_personne(obj.responsable) or None

    def _visibles(self):
        from .reception import dossiers_visibles

        return dossiers_visibles(self.context["request"].user)

    def get_dossiers_lies(self, obj):
        return [{"id": d.id, "numero": d.numero} for d in self._visibles().filter(pk__in=obj.dossiers.values("pk")).order_by("numero")]

    def validate_dossiers(self, dossiers):
        visibles = set(self._visibles().filter(pk__in=[d.pk for d in dossiers]).values_list("pk", flat=True))
        if any(d.pk not in visibles for d in dossiers):
            raise serializers.ValidationError("Certains dossiers ne vous sont pas accessibles.")
        return dossiers


class ModeleMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeleMessage
        fields = ("id", "objet", "langue", "sujet", "texte_courriel", "texte_sms", "actif")

    def validate_langue(self, valeur):
        if valeur not in LANGUES:
            raise serializers.ValidationError("Langue non proposée.")
        return valeur
