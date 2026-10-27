from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.constants import ROLES_NOTIFIEES_MODIFICATION_ACTIVITE
from apps.core.permissions import HasGlobalVisibilityOrAssigned, IsAdminOrCreateForAuthenticated, IsAdminOrReadOnly
from apps.indicators.exports import generer_xlsform
from apps.notifications.models import Notification
from apps.notifications.services import notifier, notifier_par_role

from .import_excel import generer_modele_import_projet, importer_projet
from .models import Activite, Equipe, JalonLivrable, NiveauActivite, ParametresCalcul, Projet, SousActivite, TauxManuel
from .queryset_filters import visible_projets_ids
from .serializers import (
    ActiviteSerializer,
    EquipeSerializer,
    JalonLivrableSerializer,
    NiveauActiviteSerializer,
    ParametresCalculSerializer,
    ProjetSerializer,
    ProjetWriteSerializer,
    SousActiviteSerializer,
    TauxManuelSerializer,
)
from .services import (
    supprimer_activite_cascade,
    supprimer_projet_cascade,
    supprimer_sous_activite_cascade,
    synchroniser_projets_associes_activite,
    synchroniser_projets_associes_equipe,
)


class EquipeViewSet(viewsets.ModelViewSet):
    queryset = Equipe.objects.all()
    serializer_class = EquipeSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    search_fields = ("nom",)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        synchroniser_projets_associes_equipe(serializer.instance)


class ProjetViewSet(viewsets.ModelViewSet):
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("statut", "partenaire_bailleur", "partenaire_mise_en_oeuvre")
    search_fields = ("nom", "code")

    def get_queryset(self):
        return (
            Projet.objects.select_related(
                "partenaire_bailleur", "partenaire_mise_en_oeuvre", "element_strategique__type_niveau"
            )
            .filter(id__in=visible_projets_ids(self.request.user))
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProjetWriteSerializer
        return ProjetSerializer

    def perform_destroy(self, instance):
        supprimer_projet_cascade(instance)

    @action(detail=True, methods=["get"], url_path="export/xlsform")
    def export_xlsform(self, request, pk=None):
        projet = self.get_object()
        contenu = generer_xlsform(projet)
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f"attachment; filename=xlsform_{projet.code}.xlsx"
        return response

    @action(detail=False, methods=["get"], url_path="modele-import")
    def modele_import(self, request):
        contenu = generer_modele_import_projet()
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=modele_import_projet.xlsx"
        return response

    @action(detail=False, methods=["post"], url_path="importer", parser_classes=[MultiPartParser, FormParser])
    def importer(self, request):
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
        try:
            resultat = importer_projet(fichier)
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
        return Response(resultat)


class ActiviteViewSet(viewsets.ModelViewSet):
    serializer_class = ActiviteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet", "activite_parent", "responsable")

    CHAMPS_SURVEILLES = ("date_debut", "date_fin", "budget_alloue", "quantite_prevue", "statut")

    def get_queryset(self):
        return Activite.objects.filter(projet__id__in=visible_projets_ids(self.request.user))

    def perform_destroy(self, instance):
        supprimer_activite_cascade(instance)

    @action(detail=False, methods=["get"], url_path="pour-projet")
    def pour_projet(self, request):
        """
        Liste allégée (id, libellé), non paginée, des éléments d'un projet (tous niveaux) —
        alimente le sélecteur de grille d'alerte par activité (potentiellement
        des centaines d'activités, une pagination classique serait inutile ici).
        """
        projet_id = request.query_params.get("projet")
        ids = visible_projets_ids(self.request.user)
        if not projet_id or int(projet_id) not in ids:
            return Response([])
        activites = self.get_queryset().filter(projet__id=projet_id).order_by("libelle")
        return Response([{"id": a.id, "libelle": a.libelle} for a in activites])

    def perform_create(self, serializer):
        super().perform_create(serializer)
        synchroniser_projets_associes_activite(serializer.instance)

    def perform_update(self, serializer):
        instance = serializer.instance
        anciennes_valeurs = {champ: getattr(instance, champ) for champ in self.CHAMPS_SURVEILLES}
        deja_planifiee = anciennes_valeurs["date_debut"] is not None or anciennes_valeurs["date_fin"] is not None

        super().perform_update(serializer)
        synchroniser_projets_associes_activite(serializer.instance)

        activite = serializer.instance
        changements = [
            champ for champ in self.CHAMPS_SURVEILLES if anciennes_valeurs[champ] != getattr(activite, champ)
        ]
        if changements and deja_planifiee:
            projet = activite.projet
            titre = f"Activité modifiée : {activite.libelle}"
            message = f"Projet {projet.nom} — champ(s) modifié(s) : {', '.join(changements)}."
            lien = f"/projets/{projet.id}"
            if projet.utilisateurs_affectes.exists():
                notifier(list(projet.utilisateurs_affectes.all()), Notification.Type.ACTIVITE_MODIFIEE, titre, message, lien)
            notifier_par_role(
                ROLES_NOTIFIEES_MODIFICATION_ACTIVITE,
                Notification.Type.ACTIVITE_MODIFIEE,
                titre,
                message,
                lien,
                exclure=self.request.user,
            )


class NiveauActiviteViewSet(viewsets.ModelViewSet):
    serializer_class = NiveauActiviteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet",)

    def get_queryset(self):
        return NiveauActivite.objects.filter(projet__id__in=visible_projets_ids(self.request.user))


class SousActiviteViewSet(viewsets.ModelViewSet):
    serializer_class = SousActiviteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite", "statut")

    def get_queryset(self):
        return SousActivite.objects.filter(activite__projet__id__in=visible_projets_ids(self.request.user))

    def perform_destroy(self, instance):
        supprimer_sous_activite_cascade(instance)


class JalonLivrableViewSet(viewsets.ModelViewSet):
    """Jalons et livrables d'un élément (méthodes « jalons pondérés » et « livrables »)."""

    serializer_class = JalonLivrableSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite", "type")

    def get_queryset(self):
        return JalonLivrable.objects.filter(activite__projet__id__in=visible_projets_ids(self.request.user))

    def _validation(self, serializer):
        # La validation d'un livrable garde son auteur et sa date ; la retirer les efface.
        valide = serializer.validated_data.get("valide")
        if valide is True and not (serializer.instance and serializer.instance.valide):
            return {"valide_par": self.request.user, "date_validation": timezone.localdate()}
        if valide is False:
            return {"valide_par": None, "date_validation": None}
        return {}

    def perform_create(self, serializer):
        serializer.save(**self._validation(serializer))

    def perform_update(self, serializer):
        serializer.save(**self._validation(serializer))


class TauxManuelViewSet(viewsets.ModelViewSet):
    """Taux saisis à la main (méthode « saisie manuelle »), historisés."""

    serializer_class = TauxManuelSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite",)

    def get_queryset(self):
        return TauxManuel.objects.filter(activite__projet__id__in=visible_projets_ids(self.request.user))

    def perform_create(self, serializer):
        serializer.save(saisi_par=self.request.user)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAdminOrReadOnly])
def parametres_calcul(request):
    """Méthode de calcul et d'agrégation par défaut de l'organisation (modification : Administrateur)."""
    parametres = ParametresCalcul.courants()
    if request.method in ("PUT", "PATCH"):
        serializer = ParametresCalculSerializer(parametres, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(ParametresCalculSerializer(parametres).data)
