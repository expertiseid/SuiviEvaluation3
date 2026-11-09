import django_filters
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.core.vocabulaire import v
from apps.organisations import quota
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
    # Explorateur : documents hors de tout dossier (racine), et bibliothèque libre (sans projet).
    sans_dossier = django_filters.BooleanFilter(field_name="dossier", lookup_expr="isnull")
    libres = django_filters.BooleanFilter(method="filtrer_libres")

    class Meta:
        model = Document
        fields = ["dossier", "projet", "activite", "sous_activite", "type_document"]

    def filtrer_libres(self, queryset, name, value):
        libres = Q(projet__isnull=True, activite__isnull=True, sous_activite__isnull=True)
        return queryset.filter(libres) if value else queryset.exclude(libres)

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


class DossierFilter(django_filters.FilterSet):
    """`libres=true` : dossiers de la bibliothèque libre (sans projet)."""

    libres = django_filters.BooleanFilter(field_name="projet", lookup_expr="isnull")

    class Meta:
        model = Dossier
        fields = ["projet", "parent"]


class DossierViewSet(viewsets.ModelViewSet):
    serializer_class = DossierSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_class = DossierFilter
    # L'explorateur construit l'arborescence entière : tous les dossiers du projet (ou de la
    # bibliothèque libre) d'un coup, sans pagination.
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Count, Q

        ids = visible_projets_ids(self.request.user)
        return Dossier.objects.filter(Q(projet__isnull=True) | Q(projet__id__in=ids)).annotate(
            nombre_documents=Count("documents", distinct=True, filter=Q(documents__supprime_le__isnull=True)),
            nombre_sous_dossiers=Count("sous_dossiers", distinct=True, filter=Q(sous_dossiers__supprime_le__isnull=True)),
        )

    def perform_destroy(self, instance):
        """À la corbeille, avec son contenu (corbeille.py)."""
        from . import corbeille

        corbeille.jeter(self.request.user, dossiers=[instance])


def _selection(request, donnees, tous=False):
    """Dossiers et documents désignés ({"dossiers": [...], "documents": [...]}), parmi ceux visibles."""
    from . import corbeille

    def ids(cle):
        valeur = donnees.get(cle) or []
        if isinstance(valeur, str):
            valeur = valeur.split(",")
        try:
            return {int(x) for x in valeur if str(x).strip()}
        except (TypeError, ValueError):
            raise ValidationError({cle: v("Sélection invalide.")})

    dossiers = list(corbeille._visibles(request.user, Dossier, tous=tous).filter(pk__in=ids("dossiers")))
    documents = list(corbeille._visibles(request.user, Document, tous=tous).filter(pk__in=ids("documents")))
    if not dossiers and not documents:
        raise ValidationError({"detail": v("Aucun élément sélectionné.")})
    return dossiers, documents


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    # JSON : renommer un document ou le déplacer dans un autre dossier (explorateur).
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    filterset_class = DocumentFilter
    search_fields = ("nom", "description")

    def get_queryset(self):
        from .liens import documents_visibles

        return documents_visibles(self.request.user).select_related("cree_par").prefetch_related("versions")

    def perform_destroy(self, instance):
        from . import corbeille

        corbeille.jeter(self.request.user, documents=[instance])

    @action(detail=False, methods=["post"], url_path="supprimer-selection")
    def supprimer_selection(self, request):
        """Plusieurs dossiers et documents à la corbeille d'un coup."""
        from . import corbeille

        dossiers, documents = _selection(request, request.data)
        return Response({"nombre": corbeille.jeter(request.user, dossiers, documents)})

    @action(detail=False, methods=["get"], url_path="telecharger-selection")
    def telecharger_selection(self, request):
        """Archive zip de la sélection (?dossiers=1,2&documents=3,4), dossiers avec leur contenu."""
        from django.http import FileResponse

        from . import corbeille

        dossiers, documents = _selection(request, request.query_params)
        try:
            fichier = corbeille.archive(dossiers, documents)
        except ValueError:
            raise ValidationError({"detail": v("Sélection trop volumineuse (plus de 500 Mo) : téléchargez-la en plusieurs fois.")})
        return FileResponse(fichier, as_attachment=True, filename="documents.zip", content_type="application/zip")

    @action(detail=False, methods=["get"])
    def corbeille(self, request):
        from datetime import timedelta

        from . import corbeille

        dossiers, documents = corbeille.elements(request.user)
        def projet(e):
            if isinstance(e, Document) and not e.projet:
                return (e.activite and e.activite.projet) or (e.sous_activite and e.sous_activite.activite.projet)
            return e.projet

        def ligne(e, type_):
            p = projet(e)
            return {"type": type_, "id": e.pk, "nom": e.nom, "projet": p.pk if p else None, "projet_nom": p.nom if p else "",
                    "supprime_le": e.supprime_le, "supprime_par_nom": str(e.supprime_par or ""),
                    "supprime_definitivement_le": e.supprime_le + timedelta(days=corbeille.DUREE_CONSERVATION_JOURS)}

        return Response({
            "duree_conservation_jours": corbeille.DUREE_CONSERVATION_JOURS,
            "dossiers": [{**ligne(d, "dossier"), "nombre_elements": Document.tous.filter(supprime_avec=d).count()
                          + Dossier.tous.filter(supprime_avec=d).count()} for d in dossiers],
            "documents": [ligne(d, "document") for d in documents],
        })

    @action(detail=False, methods=["post"], url_path="corbeille/restaurer")
    def corbeille_restaurer(self, request):
        from . import corbeille

        dossiers, documents = _selection(request, request.data, tous=True)
        en_corbeille = lambda e: e.supprime_le and not e.supprime_avec_id
        return Response({"nombre": corbeille.restaurer([d for d in dossiers if en_corbeille(d)],
                                                       [d for d in documents if en_corbeille(d)])})

    @action(detail=False, methods=["post"], url_path="corbeille/vider")
    def corbeille_vider(self, request):
        """Suppression définitive : la sélection, ou toute la corbeille ({"tout": true})."""
        from . import corbeille

        if request.data.get("tout"):
            dossiers, documents = (list(q) for q in corbeille.elements(request.user))
        else:
            dossiers, documents = _selection(request, request.data, tous=True)
            dossiers = [d for d in dossiers if d.supprime_le and not d.supprime_avec_id]
            documents = [d for d in documents if d.supprime_le and not d.supprime_avec_id]
        return Response({"nombre": corbeille.vider(dossiers, documents)})

    def create(self, request, *args, **kwargs):
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": v('Un fichier est requis pour créer un document.')})
        # Espace de stockage plein : refus avant de créer le document (sinon il resterait sans fichier).
        quota.verifier(getattr(fichier, "size", 0))

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(cree_par=request.user)

        DocumentVersion.objects.create(
            document=document, fichier=fichier, version=1, uploaded_by=request.user
        )
        return Response(self.get_serializer(document).data, status=201)

    @action(detail=True, methods=["get", "post"])
    def liens(self, request, pk=None):
        """Liens de partage du document (personnes sans compte) : liste, ou création."""
        from .partage import liens_du_document

        return liens_du_document(self, request, self.get_object())

    @action(detail=True, methods=["post"], url_path=r"liens/(?P<lien_id>\d+)/revoquer")
    def revoquer_lien(self, request, pk=None, lien_id=None):
        from .partage import revoquer

        return revoquer(request, self.get_object(), lien_id)

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        document = self.get_object()
        serializer = DocumentVersionSerializer(document.versions.all(), many=True, context=self.get_serializer_context())
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
