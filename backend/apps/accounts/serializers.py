import re

from django.utils.text import slugify
from rest_framework import serializers

from apps.core.vocabulaire import v
from apps.projects.models import Activite
from apps.strategy.models import ElementStrategique

from .constants import ROLE_ADMIN
from .models import DemandeInscription, Role, User


def _libelle_role(code):
    role = Role.objects.filter(code=code).first()
    return role.libelle if role else code


class RoleSerializer(serializers.ModelSerializer):
    nb_utilisateurs = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id", "code", "libelle", "visibilite_globale", "peut_personnaliser_tableau_de_bord", "peut_approuver",
            "systeme", "nb_utilisateurs",
        )
        read_only_fields = ("id", "systeme", "nb_utilisateurs")
        # Code facultatif à la création (déduit du libellé), jamais modifiable ensuite.
        extra_kwargs = {"code": {"required": False}}

    def get_nb_utilisateurs(self, obj):
        return User.objects.filter(role=obj.code).count()

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("code", None)
            if self.instance.code == ROLE_ADMIN:
                attrs.pop("visibilite_globale", None)  # l'Administrateur voit toujours tout
                attrs.pop("peut_personnaliser_tableau_de_bord", None)  # … et peut toujours tout configurer
                attrs.pop("peut_approuver", None)  # … et approuver
            return attrs

        code = attrs.get("code") or attrs.get("libelle", "")
        code = "".join(c if c.isalnum() else "_" for c in slugify(code)).upper().strip("_")[:32]
        if not code:
            raise serializers.ValidationError({"libelle": "Libellé requis."})
        if Role.objects.filter(code=code).exists():
            raise serializers.ValidationError({"libelle": f"Un rôle avec le code « {code} » existe déjà."})
        attrs["code"] = code
        return attrs



class UserSerializer(serializers.ModelSerializer):
    activites_masquees = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    elements_masques = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    droits_objets = serializers.SerializerMethodField()
    role_libelle = serializers.SerializerMethodField()
    peut_personnaliser_tableau_de_bord = serializers.SerializerMethodField()
    peut_approuver = serializers.SerializerMethodField()

    structure_libelle = serializers.SerializerMethodField()
    est_demo = serializers.SerializerMethodField()
    est_operateur = serializers.SerializerMethodField()
    inactivite_effective = serializers.SerializerMethodField()

    def get_inactivite_effective(self, obj):
        """Durée d'inactivité qui s'applique à ce compte (la sienne, sinon celle de l'organisation) ; 0 : jamais."""
        from apps.core import inactivite

        return inactivite.minutes(obj)

    def get_est_operateur(self, obj):
        """Opérateur Expertise-ID (console de la plateforme multi-organisations, adresse principale)."""
        from apps.organisations import contexte

        return bool(obj.is_superuser and contexte.actif() and contexte.courante() is None)

    def get_est_demo(self, obj):
        """Visiteur de l'installation de démonstration : bandeau « Mode démonstration »."""
        from .demo import IDENTIFIANT, actif

        return actif() and obj.username == IDENTIFIANT
    def get_structure_libelle(self, obj):
        """Structure de l'utilisateur en clair : « Partenaire de consortium — ONG X », « Organisation — Service S&E »…"""
        if not obj.type_structure:
            return ""
        detail = obj.structure_interne or obj.partenaire or obj.partie_prenante
        type_libelle = obj.get_type_structure_display()
        return f"{type_libelle} — {detail}" if detail else type_libelle

    def get_droits_objets(self, obj):
        """Droits précis (apps.projects.droits) : sur un projet, un document stratégique ou un élément."""
        return [
            {"id": d.id, "projet": d.projet_id, "document": d.document_id, "element": d.element_id,
             "libelle": str(d.projet or d.document or d.element), "acces": d.acces, "approuver": d.approuver}
            for d in obj.droits_objets.select_related("projet", "document", "element")
        ]

    def get_peut_approuver(self, obj):
        """Peut approuver quelque part : par son rôle (hors restriction), ou par un droit précis."""
        from apps.core.permissions import peut_approuver
        from apps.projects.droits import a_des_droits_precis

        restreint = obj.hors_droits_precis == obj.HorsDroitsPrecis.LECTURE and obj.role != ROLE_ADMIN
        return (peut_approuver(obj) and not restreint) or a_des_droits_precis(obj, approuver=True)

    def get_role_libelle(self, obj):
        return _libelle_role(obj.role)

    def get_peut_personnaliser_tableau_de_bord(self, obj):
        from apps.core.permissions import peut_personnaliser_tableau_de_bord

        return peut_personnaliser_tableau_de_bord(obj)

    class Meta:
        model = User
        fields = (
            "id",
            "langue",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_libelle",
            "peut_personnaliser_tableau_de_bord",
            "peut_approuver",
            "acces_modules",
            "type_structure",
            "structure_interne",
            "partenaire",
            "partie_prenante",
            "structure_libelle",
            "niveau_acces",
            "telephone",
            "zones_affectees",
            "is_active",
            "est_demo",
            "est_operateur",
            "activites_masquees",
            "elements_masques",
            "droits_objets",
            "hors_droits_precis",
            "saisies_a_approuver",
            "modules_a_approuver",
            "approbateurs",
            "peut_exporter",
            "captures",
            "export_global",
            "import_global",
            "session_inactivite_min",
            "inactivite_effective",
        )
        read_only_fields = ("id",)


def identifiant_libre(courriel: str) -> str:
    """Identifiant interne tiré d'une adresse courriel (awa.kabore@exemple.org → awa.kabore, puis awa.kabore2…)."""
    base = re.sub(r"[^\w.+-]", "", courriel.split("@")[0].strip().lower())[:140] or "utilisateur"
    identifiant, numero = base, 1
    while User.objects.filter(username__iexact=identifiant).exists():
        numero += 1
        identifiant = f"{base}{numero}"
    return identifiant


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    # Éléments masqués à cet utilisateur (apps.core.masquage) : masquer un élément masque ce qui est en dessous.
    activites_masquees = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=Activite.objects.all())
    elements_masques = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=ElementStrategique.objects.all())
    # Droits précis : la liste envoyée remplace la précédente ([{projet | document | element, acces, approuver}]).
    droits_objets = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "niveau_acces",
            "telephone",
            "zones_affectees",
            "acces_modules",
            "type_structure",
            "structure_interne",
            "partenaire",
            "partie_prenante",
            "is_active",
            "password",
            "activites_masquees",
            "elements_masques",
            "droits_objets",
            "hors_droits_precis",
            "saisies_a_approuver",
            "modules_a_approuver",
            "approbateurs",
            "peut_exporter",
            "captures",
            "export_global",
            "import_global",
            "session_inactivite_min",
        )
        read_only_fields = ("id",)
        # Identifiant interne : tiré de l'adresse courriel s'il n'est pas donné (voir validate).
        extra_kwargs = {"username": {"required": False}}

    def validate_droits_objets(self, valeurs):
        from apps.projects.models import DroitObjet, Projet
        from apps.strategy.models import CadreStrategique

        modeles = {"projet": Projet, "document": CadreStrategique, "element": ElementStrategique}
        propres, vus = [], set()
        for valeur in valeurs:
            cibles = [(cle, valeur.get(cle)) for cle in modeles if valeur.get(cle) not in (None, "")]
            if len(cibles) != 1:
                raise serializers.ValidationError(v("Chaque droit porte sur un seul projet, document ou élément."))
            cle, identifiant = cibles[0]
            if not modeles[cle].objects.filter(pk=identifiant).exists():
                raise serializers.ValidationError(v("Projet, document ou élément introuvable."))
            if (cle, str(identifiant)) in vus:
                raise serializers.ValidationError(v("Le même projet, document ou élément figure deux fois."))
            vus.add((cle, str(identifiant)))
            acces = valeur.get("acces") or DroitObjet.Acces.LECTURE
            if acces not in DroitObjet.Acces.values:
                raise serializers.ValidationError(v("Accès inconnu : lecture seule, ou lecture et écriture."))
            propres.append({f"{cle}_id": int(identifiant), "acces": acces, "approuver": bool(valeur.get("approuver"))})
        return propres

    def validate_modules_a_approuver(self, modules):
        from apps.core.modules import API_PAR_MODULE

        if not isinstance(modules, list) or any(m not in API_PAR_MODULE for m in modules):
            raise serializers.ValidationError("Onglets inconnus.")
        return modules

    def validate_approbateurs(self, approbateurs):
        if self.instance is not None and any(a.pk == self.instance.pk for a in approbateurs):
            raise serializers.ValidationError(v("Une personne ne peut pas approuver ses propres saisies."))
        return approbateurs

    def _droits(self, user, droits):
        from apps.projects.models import DroitObjet

        if droits is None:
            return
        user.droits_objets.all().delete()
        DroitObjet.objects.bulk_create([DroitObjet(utilisateur=user, **d) for d in droits])
        user.__dict__.pop("_droits_objets", None)

    def validate_session_inactivite_min(self, valeur):
        from apps.core import inactivite

        if valeur is not None and not inactivite.DUREE_MIN <= valeur <= inactivite.DUREE_MAX:
            raise serializers.ValidationError(v("Indiquez une durée entre 5 et 480 minutes."))
        return valeur

    def validate(self, attrs):
        """Seul le lien correspondant au type de structure est gardé (les autres sont vidés)."""
        attrs = super().validate(attrs)
        from apps.organisations import contexte

        # Plateforme multi-organisations : l'adresse courriel sert à se connecter, elle est obligatoire.
        courriel = attrs.get("email", getattr(self.instance, "email", ""))
        if contexte.actif() and contexte.courante() is not None and not (courriel or "").strip():
            raise serializers.ValidationError({"email": v("L'adresse courriel est obligatoire : elle sert à se connecter.")})
        if self.instance is None and not (attrs.get("username") or "").strip():
            if not (courriel or "").strip():
                raise serializers.ValidationError({"email": v("Indiquez l'adresse courriel (ou un identifiant).")})
            attrs["username"] = identifiant_libre(courriel)
        type_structure = attrs.get("type_structure", getattr(self.instance, "type_structure", ""))
        garde = {
            "INTERNE": "structure_interne",
            "CONSORTIUM": "partenaire",
            "MISE_EN_OEUVRE": "partenaire",
            "BAILLEUR": "partenaire",
            "PARTIE_PRENANTE": "partie_prenante",
        }.get(type_structure)
        if "type_structure" in attrs or any(c in attrs for c in ("structure_interne", "partenaire", "partie_prenante")):
            for champ in ("structure_interne", "partenaire", "partie_prenante"):
                if champ != garde:
                    attrs[champ] = None
        return attrs

    def validate_email(self, value):
        """Plateforme multi-organisations : l'adresse sert à se connecter, elle n'appartient qu'à un compte."""
        from apps.organisations import comptes, contexte

        org = contexte.courante()
        if contexte.actif() and org is not None and comptes.courriel_pris(value, org, getattr(self.instance, "pk", None)):
            raise serializers.ValidationError("Cette adresse courriel est déjà utilisée par un autre compte de la plateforme.")
        return value

    def validate_acces_modules(self, value):
        from apps.core.modules import NIVEAUX

        if not isinstance(value, dict) or any(niveau not in NIVEAUX for niveau in value.values()):
            raise serializers.ValidationError("Droits par module invalides.")
        return value

    def validate_role(self, value):
        if not Role.objects.filter(code=value).exists():
            raise serializers.ValidationError(f"Rôle « {value} » inconnu.")
        return value

    MASQUAGES = ("activites_masquees", "elements_masques")  # côté inverse des relations : .set() après l'enregistrement

    def _masquages(self, user, masquages):
        for champ, valeurs in masquages.items():
            if valeurs is not None:
                getattr(user, champ).set(valeurs)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        zones_affectees = validated_data.pop("zones_affectees", None)
        masquages = {c: validated_data.pop(c, None) for c in self.MASQUAGES}
        droits = validated_data.pop("droits_objets", None)
        approbateurs = validated_data.pop("approbateurs", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if zones_affectees is not None:
            user.zones_affectees.set(zones_affectees)
        self._masquages(user, masquages)
        self._droits(user, droits)
        if approbateurs is not None:
            user.approbateurs.set(approbateurs)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        zones_affectees = validated_data.pop("zones_affectees", None)
        masquages = {c: validated_data.pop(c, None) for c in self.MASQUAGES}
        droits = validated_data.pop("droits_objets", None)
        approbateurs = validated_data.pop("approbateurs", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if zones_affectees is not None:
            instance.zones_affectees.set(zones_affectees)
        self._masquages(instance, masquages)
        self._droits(instance, droits)
        if approbateurs is not None:
            instance.approbateurs.set(approbateurs)
        return instance


class DemandeInscriptionSerializer(serializers.ModelSerializer):
    offre_libelle = serializers.CharField(source="get_offre_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = DemandeInscription
        exclude = ("mot_de_passe",)
        read_only_fields = ("cree_le",)
