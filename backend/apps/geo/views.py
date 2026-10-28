from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrCreateForAuthenticated, IsAdminOrReadOnly

from .models import LimiteAdministrative, NiveauAdministratif, Zone
from .serializers import NiveauAdministratifSerializer, ZoneSerializer


class NiveauAdministratifViewSet(viewsets.ModelViewSet):
    queryset = NiveauAdministratif.objects.select_related("niveau_parent").all()
    serializer_class = NiveauAdministratifSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("pays",)


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.select_related("niveau_administratif", "parent").all()
    serializer_class = ZoneSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    filterset_fields = ("niveau_administratif", "parent")
    search_fields = ("nom",)

    def get_queryset(self):
        qs = super().get_queryset()
        pays = self.request.query_params.get("pays")
        if pays:
            qs = qs.filter(niveau_administratif__pays=pays)
        return qs


@api_view(["GET"])
def limites_administratives(request):
    """
    Contours d'un niveau administratif (GeoJSON) pour la carte : ?pays=BF&niveau=2. Téléchargés
    depuis geoBoundaries au premier appel, puis servis depuis le cache.
    """
    from .services.limites import LimitesIndisponibles, completer_par_les_enfants, placer_zones, telecharger

    pays = (request.query_params.get("pays") or "BF").upper()[:2]
    niveau = int(request.query_params.get("niveau") or 1)
    try:
        nouvelle = not LimiteAdministrative.objects.filter(pays=pays, niveau=niveau).exists()
        limite = telecharger(pays, niveau)
        if nouvelle:
            placer_zones(limite)
            completer_par_les_enfants(pays)
    except LimitesIndisponibles as exc:
        raise NotFound(str(exc))
    return Response({
        "pays": limite.pays, "niveau": limite.niveau, "nom_niveau": limite.nom_niveau, "annee": limite.annee,
        "geojson": limite.geojson,
    })
