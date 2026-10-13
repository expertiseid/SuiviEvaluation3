from django.db.models import Q
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.projects.models import Projet
from apps.projects.queryset_filters import visible_projets_ids

from .export_excel import exporter_suivi_excel
from .export_periode import (
    exporter_periode_excel,
    exporter_periode_pdf,
    exporter_suivi_periode_excel,
    exporter_suivi_periode_pdf,
)
from .export_pdf import exporter_suivi_pdf
from .models import PeriodePlanification, PointSuivi, TranchePlanifiee
from .serializers import PeriodePlanificationSerializer, PointSuiviSerializer, TranchePlanifieeSerializer
from .services import construire_dashboard_suivi, construire_planification_periode, synchroniser_activite_depuis_suivi, synchroniser_sous_activite_depuis_suivi


class PointSuiviViewSet(viewsets.ModelViewSet):
    serializer_class = PointSuiviSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite", "sous_activite")

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)
        return (
            PointSuivi.objects.filter(
                Q(activite__objectif_specifique__objectif_general__projet__id__in=ids)
                | Q(sous_activite__activite__objectif_specifique__objectif_general__projet__id__in=ids)
            )
            .select_related("activite", "sous_activite", "saisi_par")
        )

    def _synchroniser(self, instance):
        if instance.activite_id:
            synchroniser_activite_depuis_suivi(instance.activite)
        else:
            synchroniser_sous_activite_depuis_suivi(instance.sous_activite)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._synchroniser(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._synchroniser(serializer.instance)

    def perform_destroy(self, instance):
        activite, sous_activite = instance.activite, instance.sous_activite
        super().perform_destroy(instance)
        if activite:
            synchroniser_activite_depuis_suivi(activite)
        else:
            synchroniser_sous_activite_depuis_suivi(sous_activite)


class TranchePlanifieeViewSet(viewsets.ModelViewSet):
    serializer_class = TranchePlanifieeSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("periode", "activite", "sous_activite", "indicateur")

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)
        return TranchePlanifiee.objects.filter(
            Q(activite__objectif_specifique__objectif_general__projet__id__in=ids)
            | Q(sous_activite__activite__objectif_specifique__objectif_general__projet__id__in=ids)
            | Q(
                indicateur__isnull=False,
                indicateur__projet__isnull=True,
                indicateur__objectif_general__isnull=True,
                indicateur__objectif_specifique__isnull=True,
                indicateur__activite__isnull=True,
            )
            | Q(indicateur__projet__id__in=ids)
            | Q(indicateur__objectif_general__projet__id__in=ids)
            | Q(indicateur__objectif_specifique__objectif_general__projet__id__in=ids)
            | Q(indicateur__activite__objectif_specifique__objectif_general__projet__id__in=ids)
        ).select_related("activite", "sous_activite", "indicateur")


class PeriodePlanificationViewSet(viewsets.ModelViewSet):
    """Périodes de l'onglet « Planification par période » d'un projet."""

    serializer_class = PeriodePlanificationSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet",)
    pagination_class = None

    def get_queryset(self):
        return PeriodePlanification.objects.filter(projet__id__in=visible_projets_ids(self.request.user))

    @action(detail=True, methods=["get"])
    def valeurs(self, request, pk=None):
        """Valeurs de chaque élément sur la période (saisies, sinon calculées au prorata) — onglet et exports."""
        return Response(construire_planification_periode(self.get_object()))

    @action(detail=True, methods=["get"], url_path="exporter/excel")
    def exporter_excel(self, request, pk=None):
        periode = self.get_object()
        response = HttpResponse(
            exporter_periode_excel(periode),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={self._nom_fichier(periode)}.xlsx"
        return response

    @action(detail=True, methods=["get"], url_path="exporter/pdf")
    def exporter_pdf(self, request, pk=None):
        periode = self.get_object()
        response = HttpResponse(exporter_periode_pdf(periode), content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={self._nom_fichier(periode)}.pdf"
        return response

    @action(detail=True, methods=["get"], url_path="exporter-suivi/excel")
    def exporter_suivi_excel(self, request, pk=None):
        """Export du suivi par période (module Suivi) — même présentation que l'export du suivi global."""
        periode = self.get_object()
        response = HttpResponse(
            exporter_suivi_periode_excel(periode),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={self._nom_fichier(periode, 'suivi')}.xlsx"
        return response

    @action(detail=True, methods=["get"], url_path="exporter-suivi/pdf")
    def exporter_suivi_pdf(self, request, pk=None):
        periode = self.get_object()
        response = HttpResponse(exporter_suivi_periode_pdf(periode), content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={self._nom_fichier(periode, 'suivi')}.pdf"
        return response

    @staticmethod
    def _nom_fichier(periode, prefixe="planification"):
        libelle = "".join(c if c.isalnum() else "_" for c in periode.libelle).strip("_")
        return f"{prefixe}_{periode.projet.code}_{libelle}"

    def perform_create(self, serializer):
        if serializer.validated_data["projet"].id not in set(visible_projets_ids(self.request.user)):
            raise PermissionDenied("Projet non accessible.")
        serializer.save()

    def perform_update(self, serializer):
        periode = serializer.save()
        # Les valeurs de la période suivent ses nouvelles dates/libellé ; une
        # date prévue qui sortirait de la période est simplement effacée.
        for tranche in periode.tranches.all():
            tranche.libelle = periode.libelle
            tranche.periode_debut = periode.date_debut
            tranche.periode_fin = periode.date_fin
            if tranche.date_debut_prevue and not (periode.date_debut <= tranche.date_debut_prevue <= periode.date_fin):
                tranche.date_debut_prevue = None
            if tranche.date_fin_prevue and not (periode.date_debut <= tranche.date_fin_prevue <= periode.date_fin):
                tranche.date_fin_prevue = None
            tranche.save()


def _projet_visible_ou_404(request, projet_id):
    ids = list(visible_projets_ids(request.user))
    return Projet.objects.filter(id__in=ids, id=projet_id).first()


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def suivi_dashboard_projet(request, projet_id):
    projet = _projet_visible_ou_404(request, projet_id)
    if projet is None:
        return Response({"detail": "Projet introuvable ou non accessible."}, status=404)
    return Response(construire_dashboard_suivi(projet))


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def suivi_exporter_excel(request, projet_id):
    projet = _projet_visible_ou_404(request, projet_id)
    if projet is None:
        return Response({"detail": "Projet introuvable ou non accessible."}, status=404)

    contenu = exporter_suivi_excel(projet)
    response = HttpResponse(
        contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f"attachment; filename=suivi_{projet.code}.xlsx"
    return response


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def suivi_exporter_pdf(request, projet_id):
    projet = _projet_visible_ou_404(request, projet_id)
    if projet is None:
        return Response({"detail": "Projet introuvable ou non accessible."}, status=404)

    contenu = exporter_suivi_pdf(projet)
    response = HttpResponse(contenu, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=suivi_{projet.code}.pdf"
    return response
