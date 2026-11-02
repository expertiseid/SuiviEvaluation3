import re

from django.db import transaction
from django.http import HttpResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.constants import ROLE_ADMIN

from .audit import A, auditer
from .langues import dans_la_langue_demandee
from .models import CODES_LANGUES, LANGUES, EvenementAudit, TraductionCorrigee
from .permissions import IsAdmin, IsAdminOrReadOnly

REPERE = re.compile(r"\{\d+\}")


def reperes_incoherents(source, traduction):
    """
    Les emplacements {0}, {1}… du texte français, que l'interface remplace par une valeur (un nom,
    un nombre) : la traduction doit garder exactement les mêmes. Renvoie le message d'erreur, ou None.
    """
    attendus, presents = set(REPERE.findall(source)), set(REPERE.findall(traduction))
    if attendus == presents:
        return None
    manquants, en_trop = sorted(attendus - presents), sorted(presents - attendus)
    morceaux = []
    if manquants:
        morceaux.append(f"il manque {', '.join(manquants)}")
    if en_trop:
        morceaux.append(f"{', '.join(en_trop)} n'existe pas dans le texte français")
    return "Emplacements à conserver tels quels : " + " ; ".join(morceaux) + "."


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def traductions(request):
    """
    Au démarrage de l'interface (même avant connexion) : langues proposées, langue par défaut
    de l'organisation et, pour ?langue=xx, les traductions corrigées par l'Administrateur.
    """
    from apps.dashboard.models import ConfigurationMenu

    langue = request.query_params.get("langue", "")
    corrections = {}
    if langue in CODES_LANGUES:
        corrections = dict(TraductionCorrigee.objects.filter(langue=langue).values_list("source", "traduction"))
    return Response({
        "langue_defaut": ConfigurationMenu.courante().langue_defaut or "fr",
        "langues": [{"code": code, "nom": nom} for code, nom in LANGUES],
        "corrections": corrections,
    })


class TraductionCorrigeeSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = TraductionCorrigee
        fields = ("id", "langue", "source", "traduction", "updated_at", "modifie_par_nom")
        validators = []  # une nouvelle saisie remplace la précédente (voir create)

    def get_modifie_par_nom(self, obj):
        return str(obj.modifie_par) if obj.modifie_par else None

    def validate_langue(self, valeur):
        if valeur == "fr":
            raise serializers.ValidationError("Le français est la langue source : modifiez plutôt le vocabulaire.")
        return valeur

    def validate(self, attrs):
        erreur = reperes_incoherents(attrs["source"], attrs["traduction"])
        if erreur:
            raise serializers.ValidationError({"traduction": erreur})
        return attrs

    def create(self, validated_data):
        # Une correction par texte et par langue : une nouvelle saisie remplace l'ancienne.
        correction, _ = TraductionCorrigee.objects.update_or_create(
            langue=validated_data["langue"], source=validated_data["source"],
            defaults={"traduction": validated_data["traduction"], "modifie_par": self.context["request"].user},
        )
        return correction


class TraductionCorrigeeViewSet(viewsets.ModelViewSet):
    """Traductions corrigées (?langue=) : lecture pour tous, correction par l'Administrateur."""

    queryset = TraductionCorrigee.objects.all().order_by("source")
    serializer_class = TraductionCorrigeeSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("langue",)
    pagination_class = None

    @action(detail=False, methods=["post"])
    def importer(self, request):
        """
        Import d'un fichier de traductions : {langue, lignes: [{source, traduction}]}, où une
        traduction nulle retire la correction. Tout ou rien : la moindre ligne invalide annule l'import.
        """
        langue = request.data.get("langue")
        lignes = request.data.get("lignes")
        if langue not in CODES_LANGUES or langue == "fr":
            raise serializers.ValidationError({"langue": "Langue inconnue ou langue source."})
        if not isinstance(lignes, list):
            raise serializers.ValidationError({"lignes": "Liste attendue."})
        erreurs = []
        for i, ligne in enumerate(lignes):
            source, traduction = (ligne or {}).get("source"), (ligne or {}).get("traduction")
            if not isinstance(source, str) or not source.strip() or not (traduction is None or isinstance(traduction, str)):
                erreurs.append({"source": source, "erreur": "Ligne illisible."})
            elif traduction is not None and not traduction.strip():
                erreurs.append({"source": source, "erreur": "Traduction vide."})
            elif traduction is not None and (erreur := reperes_incoherents(source, traduction)):
                erreurs.append({"source": source, "erreur": erreur})
        if erreurs:
            raise serializers.ValidationError({"lignes": erreurs})
        corrigees = retirees = 0
        with transaction.atomic():
            for ligne in lignes:
                if ligne["traduction"] is None:
                    # Supprimer objet par objet pour que l'historique garde la trace du retrait.
                    for correction in TraductionCorrigee.objects.filter(langue=langue, source=ligne["source"]):
                        correction.delete()
                        retirees += 1
                else:
                    TraductionCorrigee.objects.update_or_create(
                        langue=langue, source=ligne["source"],
                        defaults={"traduction": ligne["traduction"], "modifie_par": request.user},
                    )
                    corrigees += 1
        return Response({"corrigees": corrigees, "retirees": retirees})

    @action(detail=False)
    def journal(self, request):
        """Les 200 dernières modifications des traductions d'une langue (?langue=) : qui, quand, quoi."""
        if request.user.role != ROLE_ADMIN:
            raise PermissionDenied()
        historique = TraductionCorrigee.history.select_related("history_user").order_by("-history_date")
        if request.query_params.get("langue"):
            historique = historique.filter(langue=request.query_params["langue"])
        return Response([
            {
                "date": h.history_date,
                "utilisateur": str(h.history_user) if h.history_user else None,
                "type": {"+": "correction", "~": "correction", "-": "retrait"}[h.history_type],
                "source": h.source,
                "traduction": h.traduction,
            }
            for h in historique[:200]
        ])


# --- Journal d'audit ---------------------------------------------------------------------------------

class ConnexionAuditee(TokenObtainPairView):
    """Connexion (jeton JWT), inscrite au journal d'audit, réussie ou refusée (identifiant tenté seulement)."""

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import User

        try:
            reponse = super().post(request, *args, **kwargs)
        except Exception:
            auditer(None, A.CONNEXION_ECHOUEE, module="comptes", identifiant=str(request.data.get("username", ""))[:150])
            raise
        auditer(User.objects.filter(username=request.data.get("username")).first(), A.CONNEXION, module="comptes")
        return reponse


class EvenementAuditSerializer(serializers.ModelSerializer):
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = EvenementAudit
        fields = ("id", "date", "utilisateur_id", "utilisateur", "action", "action_libelle", "module", "objet", "details")
        read_only_fields = fields


def filtrer_audit(params):
    qs = EvenementAudit.objects.all()
    if params.get("action"):
        qs = qs.filter(action=params["action"])
    if params.get("utilisateur"):
        qs = qs.filter(utilisateur__icontains=params["utilisateur"])
    if params.get("objet"):
        qs = qs.filter(objet__icontains=params["objet"])
    if params.get("du"):
        qs = qs.filter(date__date__gte=params["du"])
    if params.get("au"):
        qs = qs.filter(date__date__lte=params["au"])
    return qs


class JournalAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Journal d'audit (Administrateur) : consultation filtrée (?action=&utilisateur=&objet=&du=&au=) et export
    Excel. Lecture seule : aucune route ne modifie ni ne supprime un événement.
    """

    serializer_class = EvenementAuditSerializer
    permission_classes = (IsAdmin,)

    def get_queryset(self):
        return filtrer_audit(self.request.query_params)

    @action(detail=False, methods=["get"])
    @dans_la_langue_demandee
    def exporter(self, request):
        from .audit import journal_excel

        evenements = list(self.get_queryset()[:50000])
        contenu = journal_excel(evenements)
        auditer(request.user, A.EXPORT, "Journal d'audit", module="comptes", nombre=len(evenements))
        reponse = HttpResponse(contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        reponse["Content-Disposition"] = "attachment; filename=journal_audit.xlsx"
        return reponse
