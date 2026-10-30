from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .chaine import controler_contribution, controler_rattachement
from .models import AppreciationStrategique, CadreStrategique, ElementStrategique, FinancementDocument, TypeDocument, TypeNiveau


class LigneBailleurSerializer(serializers.Serializer):
    """Bailleur saisi sur la fiche d'un document : son nom (créé s'il est inconnu) et son montant."""
    nom = serializers.CharField(max_length=200)
    montant = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal(0))


class TypeDocumentSerializer(serializers.ModelSerializer):
    """Maillon de la chaîne, avec son nombre de documents (un maillon qui en a ne se supprime pas)."""
    nombre_documents = serializers.SerializerMethodField()

    class Meta:
        model = TypeDocument
        fields = ("id", "nom", "nom_pluriel", "ordre", "icone", "nombre_documents")

    def get_nombre_documents(self, obj):
        return obj.documents.count()


class CadreStrategiqueSerializer(serializers.ModelSerializer):
    """
    Document stratégique : son maillon, son rattachement à un document au-dessus (contrôlé par
    chaine.controler_rattachement : erreur bloquante, saut de maillon signalé dans
    alertes_chaine) et les documents rattachés à lui.
    """
    structures_noms = serializers.StringRelatedField(source="structures", many=True, read_only=True)
    parties_prenantes_noms = serializers.StringRelatedField(source="parties_prenantes", many=True, read_only=True)
    type_document_nom = serializers.SerializerMethodField()
    document_parent_nom = serializers.StringRelatedField(source="document_parent", read_only=True)
    document_parent_type = serializers.SerializerMethodField()
    element_parent_nom = serializers.StringRelatedField(source="element_parent", read_only=True)
    documents_rattaches = serializers.SerializerMethodField()
    # Pas « avertissements » : l'interface notifie ce champ à chaque réponse (saisies à vérifier).
    alertes_chaine = serializers.SerializerMethodField()
    # Fiche du document (comme un projet) : bailleurs en lecture (financements) et en écriture
    # (bailleurs : remplace toute la liste), noms des partenaires et des zones pour l'affichage.
    financements = serializers.SerializerMethodField()
    bailleurs = LigneBailleurSerializer(many=True, write_only=True, required=False)
    partenaire_mise_en_oeuvre_nom = serializers.StringRelatedField(source="partenaire_mise_en_oeuvre", read_only=True)
    partenaires_consortium_noms = serializers.StringRelatedField(source="partenaires_consortium", many=True, read_only=True)
    zones_noms = serializers.StringRelatedField(source="zones", many=True, read_only=True)
    utilisateurs_affectes_noms = serializers.SerializerMethodField()
    elements_parents_secondaires_noms = serializers.StringRelatedField(source="elements_parents_secondaires", many=True, read_only=True)

    class Meta:
        model = CadreStrategique
        fields = (
            "id", "nom", "description", "created_at",
            "structures", "structures_noms", "parties_prenantes", "parties_prenantes_noms",
            "type_document", "type_document_nom", "document_parent", "document_parent_nom", "document_parent_type",
            "element_parent", "element_parent_nom", "elements_parents_secondaires", "elements_parents_secondaires_noms",
            "documents_rattaches", "alertes_chaine",
            "code", "budget_total", "fonds_propres", "date_debut", "date_fin", "statut", "type_mise_en_oeuvre",
            "responsable_nom", "utilisateurs_affectes", "utilisateurs_affectes_noms",
            "partenaire_mise_en_oeuvre", "partenaire_mise_en_oeuvre_nom",
            "partenaires_consortium", "partenaires_consortium_noms", "pays", "tout_le_pays", "zones", "zones_noms",
            "cible_totale", "cible_hommes", "cible_femmes", "cible_jeunes", "cible_pdi", "elements_capitalisation",
            "financements", "bailleurs",
        )

    def get_financements(self, obj):
        return [
            {"id": f.id, "bailleur": f.bailleur_id, "bailleur_nom": f.bailleur.nom, "montant": f.montant}
            for f in obj.financements.select_related("bailleur")
        ]

    def get_utilisateurs_affectes_noms(self, obj):
        return [(f"{u.first_name} {u.last_name}".strip() or u.username) for u in obj.utilisateurs_affectes.all()]

    def get_type_document_nom(self, obj):
        if obj.type_document_id:
            return obj.type_document.nom
        premier = TypeDocument.objects.order_by("ordre", "id").first()
        return premier.nom if premier else None

    def get_document_parent_type(self, obj):
        parent = obj.document_parent
        return parent.type_document.nom if parent and parent.type_document_id else None

    def get_documents_rattaches(self, obj):
        """
        Documents rattachés directement à celui-ci, ou dont un élément contribue à l'un des siens ;
        avec l'élément principal et, pour information, les éléments secondaires de rattachement.
        """
        par_contribution = CadreStrategique.objects.filter(
            types_niveaux__elements__contribue_a__type_niveau__cadre_strategique=obj
        ).exclude(id=obj.id)
        documents = (
            (obj.documents_rattaches.all() | par_contribution).distinct()
            .select_related("type_document", "element_parent").prefetch_related("elements_parents_secondaires")
        )
        return [
            {"id": d.id, "nom": d.nom, "type_document_nom": d.type_document.nom if d.type_document_id else None,
             "element_parent_nom": str(d.element_parent) if d.element_parent_id and d.document_parent_id == obj.id else None,
             "elements_secondaires_noms": [str(e) for e in d.elements_parents_secondaires.all()] if d.document_parent_id == obj.id else []}
            for d in documents.order_by("type_document__ordre", "nom")
        ]

    def get_alertes_chaine(self, obj):
        return controler_rattachement(obj.id, obj.type_document, obj.document_parent, obj.element_parent)[1]

    def validate(self, attrs):
        def valeur(champ):
            return attrs[champ] if champ in attrs else getattr(self.instance, champ, None)

        type_document = valeur("type_document")
        if type_document is None and self.instance is None:
            type_document = attrs["type_document"] = TypeDocument.objects.order_by("ordre", "id").first()
        erreurs, _ = controler_rattachement(
            getattr(self.instance, "id", None), type_document, valeur("document_parent"), valeur("element_parent")
        )
        if erreurs:
            raise serializers.ValidationError({"document_parent": erreurs})
        # Éléments secondaires : du document parent, distincts de l'élément principal.
        if "elements_parents_secondaires" in attrs or "document_parent" in attrs:
            parent = valeur("document_parent")
            secondaires = attrs["elements_parents_secondaires"] if "elements_parents_secondaires" in attrs else (
                list(self.instance.elements_parents_secondaires.all()) if self.instance else [])
            hors_parent = [str(e) for e in secondaires if parent is None or e.type_niveau.cadre_strategique_id != parent.id]
            if hors_parent:
                raise serializers.ValidationError({"elements_parents_secondaires": (
                    f"Élément(s) qui n'appartiennent pas au document de rattachement : {', '.join(hors_parent)}.")})
            principal = valeur("element_parent")
            if principal is not None and "elements_parents_secondaires" in attrs:
                attrs["elements_parents_secondaires"] = [e for e in secondaires if e.id != principal.id]
        debut, fin = valeur("date_debut"), valeur("date_fin")
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"date_fin": "La date de fin précède la date de début."})
        bailleurs = attrs.get("bailleurs") or []
        noms = [b["nom"].strip().lower() for b in bailleurs]
        doublon = next((b["nom"].strip() for i, b in enumerate(bailleurs) if noms.index(noms[i]) != i), None)
        if doublon:
            raise serializers.ValidationError({"bailleurs": f"Le bailleur « {doublon} » est saisi deux fois."})
        return attrs

    def create(self, validated_data):
        bailleurs = validated_data.pop("bailleurs", None)
        document = super().create(validated_data)
        if bailleurs is not None:
            enregistrer_bailleurs(document, bailleurs)
        return document

    def update(self, instance, validated_data):
        bailleurs = validated_data.pop("bailleurs", None)
        document = super().update(instance, validated_data)
        if bailleurs is not None:
            enregistrer_bailleurs(document, bailleurs)
        elif "fonds_propres" in validated_data and document.financements.exists():
            recalculer_budget(document)
        return document


def recalculer_budget(document):
    """Avec des bailleurs, le coût total = fonds propres + leurs financements (comme un projet)."""
    total = sum((f.montant for f in document.financements.all()), 0)
    if total:
        document.budget_total = document.fonds_propres + total
        document.save(update_fields=["budget_total", "updated_at"])


def enregistrer_bailleurs(document, lignes):
    """Remplace les bailleurs du document ; un nom inconnu crée le bailleur (comme sur un projet)."""
    from apps.partners.models import Bailleur

    gardes = []
    for ligne in lignes:
        nom = ligne["nom"].strip()
        bailleur = Bailleur.objects.filter(nom__iexact=nom).first() or Bailleur.objects.create(nom=nom)
        financement, _ = FinancementDocument.objects.update_or_create(
            document=document, bailleur=bailleur, defaults={"montant": ligne["montant"]},
        )
        gardes.append(financement.id)
    document.financements.exclude(id__in=gardes).delete()
    recalculer_budget(document)


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
    contribue_a_nom = serializers.SerializerMethodField()
    alertes_chaine = serializers.SerializerMethodField()
    cadre_strategique = serializers.IntegerField(source="type_niveau.cadre_strategique_id", read_only=True)

    class Meta:
        model = ElementStrategique
        fields = (
            "cadre_strategique",
            "contribue_a",
            "contribue_a_nom",
            "alertes_chaine",
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
        if "contribue_a" in attrs and attrs["contribue_a"] is not None:
            element = ElementStrategique(id=getattr(self.instance, "id", None), type_niveau=instance.type_niveau)
            erreurs, _ = controler_contribution(element, attrs["contribue_a"])
            if erreurs:
                raise serializers.ValidationError({"contribue_a": erreurs})
        return attrs

    def get_contribue_a_nom(self, obj):
        """« Document › élément » auquel l'élément contribue."""
        cible = obj.contribue_a
        return f"{cible.type_niveau.cadre_strategique} › {cible}" if cible else None

    def get_alertes_chaine(self, obj):
        return controler_contribution(obj, obj.contribue_a)[1] if obj.contribue_a_id else []

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
