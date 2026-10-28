import django_filters
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.core.vocabulaire import v
from apps.projects.queryset_filters import visible_projets_ids

from .models import Document, DocumentVersion, Dossier, PieceJustificative
from .serializers import (
    DocumentSerializer,
    DocumentVersionSerializer,
    DossierSerializer,
    PieceJustificativeSerializer,
)


class DocumentFilter(django_filters.FilterSet):
    """
    `projet=<id>` élargi : retrouve aussi les documents rattachés à une
    activité ou une sous-activité de ce projet, pas seulement ceux rattachés
    directement au projet — pour que l'onglet « Documents » d'un projet
    centralise tout ce qui le concerne, quel que soit le niveau auquel un
    document a été ajouté.
    """

    projet = django_filters.NumberFilter(method="filtrer_projet")

    class Meta:
        model = Document
        fields = ["dossier", "projet", "activite", "sous_activite", "type_document"]

    def filtrer_projet(self, queryset, name, value):
        return queryset.filter(
            Q(projet_id=value)
            | Q(activite__projet_id=value)
            | Q(sous_activite__activite__projet_id=value)
        )


class PieceJustificativeViewSet(viewsets.ModelViewSet):
    queryset = PieceJustificative.objects.select_related("uploaded_by")
    serializer_class = PieceJustificativeSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    parser_classes = (MultiPartParser, FormParser)
    filterset_fields = ("valeur_indicateur", "appreciation_strategique", "type_document")

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        """Fichier de la pièce, servi aux seuls comptes connectés (sans dépendre du serveur web)."""
        import os

        from django.http import FileResponse

        piece = self.get_object()
        extension = os.path.splitext(piece.fichier.name)[1]
        nom = piece.nom if piece.nom.lower().endswith(extension.lower()) else f"{piece.nom}{extension}"
        return FileResponse(piece.fichier.open("rb"), as_attachment=True, filename=nom)


class DossierViewSet(viewsets.ModelViewSet):
    serializer_class = DossierSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet", "parent")

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)
        from django.db.models import Q

        return Dossier.objects.filter(Q(projet__isnull=True) | Q(projet__id__in=ids))


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    parser_classes = (MultiPartParser, FormParser)
    filterset_class = DocumentFilter
    search_fields = ("nom", "description")

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)

        return Document.objects.select_related("cree_par").prefetch_related("versions").filter(
            Q(projet__isnull=True, activite__isnull=True, sous_activite__isnull=True)
            | Q(projet__id__in=ids)
            | Q(activite__projet__id__in=ids)
            | Q(sous_activite__activite__projet__id__in=ids)
        )

    def create(self, request, *args, **kwargs):
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": v('Un fichier est requis pour créer un document.')})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(cree_par=request.user)

        DocumentVersion.objects.create(
            document=document, fichier=fichier, version=1, uploaded_by=request.user
        )
        return Response(self.get_serializer(document).data, status=201)

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        document = self.get_object()
        serializer = DocumentVersionSerializer(document.versions.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="nouvelle-version")
    def nouvelle_version(self, request, pk=None):
        document = self.get_object()
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": "Un fichier est requis."})

        derniere = document.derniere_version
        nouvelle_version_num = (derniere.version + 1) if derniere else 1
        version = DocumentVersion.objects.create(
            document=document,
            fichier=fichier,
            version=nouvelle_version_num,
            uploaded_by=request.user,
            commentaire=request.data.get("commentaire", ""),
        )
        return Response(DocumentVersionSerializer(version).data, status=201)
