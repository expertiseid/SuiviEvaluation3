import os

from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned, IsAdminOrCreateForAuthenticated, IsAdminOrReadOnly

from .models import CoucheCarte, CoucheImportee, LimiteAdministrative, Localite, NiveauAdministratif, Zone
from .serializers import CoucheImporteeSerializer, NiveauAdministratifSerializer, ZoneSerializer


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
        "source": "geoBoundaries" if limite.source.startswith("http") else limite.source,
        "geojson": limite.geojson,
    })


@api_view(["GET"])
def couche_carte(request):
    """Couche d'habillage importée (ex. ?pays=BF&cle=routes) ; 404 si elle n'a pas été importée."""
    pays = (request.query_params.get("pays") or "BF").upper()[:2]
    couche = CoucheCarte.objects.filter(pays=pays, cle=request.query_params.get("cle") or "").first()
    if couche is None:
        raise NotFound("Couche non importée.")
    return Response({"cle": couche.cle, "libelle": couche.libelle, "source": couche.source, "geojson": couche.geojson})


LOCALITES_MAX = 3000


@api_view(["GET"])
def localites(request):
    """
    Villes et villages de la partie visible de la carte : ?pays=BF&bbox=sud,ouest,nord,est.
    Au-delà de LOCALITES_MAX, les villes et villages administratifs passent en premier.
    """
    pays = (request.query_params.get("pays") or "BF").upper()[:2]
    try:
        sud, ouest, nord, est = (float(x) for x in request.query_params.get("bbox", "").split(","))
    except ValueError:
        raise NotFound("Paramètre bbox attendu : sud,ouest,nord,est.")
    qs = Localite.objects.filter(pays=pays, latitude__range=(sud, nord), longitude__range=(ouest, est))
    total = qs.count()
    if total > LOCALITES_MAX:
        from django.db.models import Case, IntegerField, Value, When

        rang = Case(When(statut=Localite.VILLE, then=Value(0)), When(statut=Localite.VILLAGE_ADMINISTRATIF, then=Value(1)), default=Value(2), output_field=IntegerField())
        qs = qs.annotate(rang=rang).order_by("rang", "id")
    lignes = qs.values_list("nom", "statut", "commune", "latitude", "longitude")[:LOCALITES_MAX]
    return Response({
        "total": total,
        "localites": [{"nom": n, "statut": s, "commune": c, "lat": la, "lng": lo} for n, s, c, la, lo in lignes],
    })


class CoucheImporteeViewSet(viewsets.ModelViewSet):
    """
    Couches SIG importées pour la carte : création par envoi d'un fichier (champ « fichier » :
    .zip de shapefile, .gpkg, .geojson ou .kml, plus « nom » et « couleur »), puis nom, couleur
    et attribut des étiquettes modifiables.
    """

    queryset = CoucheImportee.objects.select_related("cree_par").defer("geojson")
    serializer_class = CoucheImporteeSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import ValidationError

        from .services.import_sig import ImportSigImpossible, lire_couche

        fichier = request.FILES.get("fichier")
        if fichier is None:
            raise ValidationError({"fichier": "Choisissez un fichier."})
        try:
            lue = lire_couche(fichier)
        except ImportSigImpossible as exc:
            raise ValidationError({"fichier": str(exc)})
        nom = (request.data.get("nom") or os.path.splitext(os.path.basename(fichier.name))[0]).strip()[:150]
        serializer = self.get_serializer(data={"nom": nom, "couleur": request.data.get("couleur") or "#7048e8"})
        serializer.is_valid(raise_exception=True)
        couche = serializer.save(fichier_source=fichier.name[:255], cree_par=request.user, **lue)
        return Response(self.get_serializer(couche).data, status=201)

    @action(detail=True, methods=["get"])
    def geojson(self, request, pk=None):
        couche = CoucheImportee.objects.only("geojson").get(pk=self.get_object().pk)
        return Response(couche.geojson)
