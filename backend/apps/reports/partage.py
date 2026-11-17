"""
Liens de partage : création et révocation (comptes connectés), et pages publiques en lecture
seule servies par le jeton du lien, sans authentification. Les données sont celles des écrans
habituels (mêmes fonctions), limitées aux projets que le créateur du lien peut voir.

Mot de passe facultatif : la page demande d'abord le mot de passe (POST …/acces/, essais limités) ;
l'accès accordé est un jeton signé, envoyé ensuite dans l'en-tête X-Acces-Partage. Changer ou retirer
le mot de passe rend caducs les accès déjà accordés.
"""
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.accounts.constants import ROLE_ADMIN
from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.projects.queryset_filters import visible_projets_ids

from .models import LienPartage


SEL_ACCES = "partage.acces"
DUREE_ACCES = 12 * 3600  # un accès accordé vaut 12 heures, puis le mot de passe est redemandé
LONGUEUR_MIN = 4


class LienPartageSerializer(serializers.ModelSerializer):
    cree_par_nom = serializers.SerializerMethodField()
    # Écrit seulement : « » retire le mot de passe ; absent, il reste tel quel.
    mot_de_passe = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    protege = serializers.SerializerMethodField()
    projet_code = serializers.CharField(source="projet.code", read_only=True, default="")
    valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = LienPartage
        fields = (
            "id", "jeton", "type", "contenu", "projet", "projet_code", "filtres", "libelle", "cree_par_nom", "expire_le",
            "actif", "valide", "nombre_consultations", "derniere_consultation", "created_at", "mot_de_passe", "protege",
        )
        read_only_fields = ("jeton", "nombre_consultations", "derniere_consultation")

    def get_cree_par_nom(self, obj):
        return obj.cree_par.get_full_name() or obj.cree_par.username

    def get_protege(self, obj):
        return bool(obj.mot_de_passe)

    def validate_mot_de_passe(self, valeur):
        if valeur and len(valeur) < LONGUEUR_MIN:
            raise serializers.ValidationError(f"Le mot de passe doit compter au moins {LONGUEUR_MIN} caractères.")
        return make_password(valeur) if valeur else ""

    def validate(self, data):
        type_ = data.get("type", getattr(self.instance, "type", None))
        projet = data.get("projet", getattr(self.instance, "projet", None))
        if type_ == LienPartage.Type.SUIVI_PROJET and projet is None:
            raise serializers.ValidationError({"projet": "Choisissez le projet à partager."})
        if type_ == LienPartage.Type.TABLEAU_DE_BORD:
            data["projet"] = None
        return data


class LienPartageViewSet(viewsets.ModelViewSet):
    """Liens créés par l'utilisateur (tous pour l'administrateur) ; ?type=&projet= pour filtrer."""

    serializer_class = LienPartageSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("type", "projet")

    def get_queryset(self):
        qs = LienPartage.objects.select_related("cree_par", "projet")
        if self.request.user.role != ROLE_ADMIN:
            qs = qs.filter(cree_par=self.request.user)
        return qs

    def perform_create(self, serializer):
        projet = serializer.validated_data.get("projet")
        if projet is not None and projet.id not in set(visible_projets_ids(self.request.user)):
            raise PermissionDenied("Projet non accessible.")
        serializer.save(cree_par=self.request.user)


# --- Pages publiques ------------------------------------------------------------------


def _lien(jeton) -> LienPartage:
    lien = LienPartage.objects.select_related("cree_par", "projet").filter(jeton=jeton).first()
    if lien is None or not lien.valide:
        raise NotFound("Ce lien de partage n'existe pas, a expiré ou a été désactivé.")
    return lien


def _marque(lien) -> str:
    """Fin de l'empreinte du mot de passe : un nouveau mot de passe rend caducs les accès accordés."""
    return lien.mot_de_passe[-16:]


def _acces_accorde(request, lien) -> bool:
    if not lien.mot_de_passe:
        return True
    try:
        acces = signing.loads(request.headers.get("X-Acces-Partage", ""), salt=SEL_ACCES, max_age=DUREE_ACCES)
    except signing.BadSignature:
        return False
    return acces.get("l") == lien.id and acces.get("m") == _marque(lien)


class EssaisMotDePasse(AnonRateThrottle):
    """Mot de passe d'un lien : 10 essais par minute et par adresse, contre les essais en série."""

    scope = "partage_mot_de_passe"
    rate = "10/min"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([EssaisMotDePasse])
def acces_partage(request, jeton):
    """{mot_de_passe} : accès à un lien protégé ({acces} : à renvoyer dans l'en-tête X-Acces-Partage)."""
    lien = _lien(jeton)
    if lien.mot_de_passe and not check_password(str(request.data.get("mot_de_passe", "")), lien.mot_de_passe):
        return Response({"detail": "Mot de passe incorrect.", "code": "mot_de_passe_incorrect"}, status=403)
    return Response({"acces": signing.dumps({"l": lien.id, "m": _marque(lien)}, salt=SEL_ACCES)})


def _ids_visibles(lien):
    ids = list(visible_projets_ids(lien.cree_par))
    if lien.type == LienPartage.Type.SUIVI_PROJET:
        return [lien.projet_id] if lien.projet_id in ids else []
    return ids


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def partage_public(request, jeton, ressource=""):
    """
    Données d'une page partagée : sans `ressource`, la description du lien (compte une
    consultation) ; sinon celles qu'attend l'écran : dashboard, configuration, menu, suivi,
    parametres-alerte.
    """
    lien = _lien(jeton)
    if not _acces_accorde(request, lien):
        return Response({
            "detail": "Ce lien est protégé par un mot de passe.", "code": "mot_de_passe_requis",
            "libelle": lien.libelle, "partage_par": lien.cree_par.get_full_name() or lien.cree_par.username,
        }, status=403)
    if not ressource:
        LienPartage.objects.filter(id=lien.id).update(
            nombre_consultations=F("nombre_consultations") + 1, derniere_consultation=timezone.now()
        )
        return Response({
            "type": lien.type, "contenu": lien.contenu, "libelle": lien.libelle, "expire_le": lien.expire_le,
            "projet": {"id": lien.projet.id, "code": lien.projet.code, "nom": lien.projet.nom} if lien.projet else None,
            "filtres": lien.filtres, "partage_par": lien.cree_par.get_full_name() or lien.cree_par.username,
        })

    if ressource == "menu":
        from apps.dashboard.models import ConfigurationMenu

        configuration = ConfigurationMenu.courante()
        return Response({
            "libelles": configuration.libelles, "icones": configuration.icones,
            "vocabulaire": configuration.vocabulaire, "peut_modifier": False,
        })
    if ressource == "parametres-alerte":
        from apps.indicators.models import ParametresAlerte
        from apps.indicators.serializers import ParametresAlerteSerializer

        return Response(ParametresAlerteSerializer(ParametresAlerte.instance()).data)

    if lien.type == LienPartage.Type.TABLEAU_DE_BORD:
        if ressource == "dashboard":
            from apps.dashboard.views import donnees_consolidees

            return Response(donnees_consolidees(_ids_visibles(lien), request.query_params))
        if ressource == "configuration":
            from apps.dashboard.models import ConfigurationTableauDeBord

            configuration = ConfigurationTableauDeBord.courante()
            return Response({
                "blocs_masques": configuration.blocs_masques, "types_graphiques": configuration.types_graphiques,
                "peut_modifier": False,
            })

    if lien.type == LienPartage.Type.SUIVI_PROJET and ressource == "suivi":
        from apps.suivi.services import construire_dashboard_suivi

        if not _ids_visibles(lien):
            raise NotFound("Ce projet n'est plus accessible.")
        donnees = construire_dashboard_suivi(lien.projet)
        if lien.contenu == LienPartage.Contenu.ACTIVITES:
            donnees["indicateurs"] = []
        elif lien.contenu == LienPartage.Contenu.INDICATEURS:
            donnees["activites"] = []
        return Response(donnees)

    raise NotFound("Rien à afficher ici.")
