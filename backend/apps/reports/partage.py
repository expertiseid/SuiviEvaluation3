"""
Liens de partage : création et révocation (comptes connectés), et pages publiques en lecture
seule servies par le jeton du lien, sans authentification. Les données sont celles des écrans
habituels (mêmes fonctions), limitées aux projets que le créateur du lien peut voir.
"""
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.constants import ROLE_ADMIN
from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.projects.queryset_filters import visible_projets_ids

from .models import LienPartage


class LienPartageSerializer(serializers.ModelSerializer):
    cree_par_nom = serializers.SerializerMethodField()
    projet_code = serializers.CharField(source="projet.code", read_only=True, default="")
    valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = LienPartage
        fields = (
            "id", "jeton", "type", "contenu", "projet", "projet_code", "filtres", "libelle", "cree_par_nom", "expire_le",
            "actif", "valide", "nombre_consultations", "derniere_consultation", "created_at",
        )
        read_only_fields = ("jeton", "nombre_consultations", "derniere_consultation")

    def get_cree_par_nom(self, obj):
        return obj.cree_par.get_full_name() or obj.cree_par.username

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
