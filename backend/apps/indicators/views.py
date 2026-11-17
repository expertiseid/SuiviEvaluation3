from django.db.models import Q
from django.http import HttpResponse
from rest_framework import generics, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.constants import ROLE_CHARGE_SE
from apps.core.langues import dans_la_langue_demandee
from apps.core.masquage import activites_masquees, elements_masques
from apps.core.permissions import AvertissementsSaisieMixin, HasGlobalVisibilityOrAssigned, IsAdminOrReadOnly, SuppressionAtomiqueMixin
from apps.core.vocabulaire import v
from apps.notifications.models import Notification
from apps.notifications.services import notifier, notifier_par_role
from apps.projects.models import Activite, Projet
from apps.projects.queryset_filters import visible_projets_ids

from .import_excel import generer_modele_import_indicateurs, importer_indicateurs
from .models import Enquete, Indicateur, PalierAlerte, ParametresAlerte, ValeurIndicateur
from .serializers import (
    EnqueteSerializer, IndicateurSerializer, PalierAlerteSerializer, ParametresAlerteSerializer, ValeurIndicateurSerializer,
)
from .services import palier_pour_taux, paliers_pour, supprimer_indicateur_cascade, taux_indicateur


class ParametresAlerteView(generics.RetrieveUpdateAPIView):
    """
    Réglage unique (singleton) : GET pour tout utilisateur authentifié,
    PATCH réservé à l'Administrateur — ne porte plus que le seuil de rappel
    d'échéance (la grille d'alerte est désormais dans PalierAlerte, voir
    paliers_alerte ci-dessous).
    """

    serializer_class = ParametresAlerteSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def get_object(self):
        return ParametresAlerte.instance()


def _resoudre_portee(params):
    """
    Résout la portée demandée (indicateur, activité, projet ou — si aucun
    des trois n'est fourni — la grille globale) à partir de query params
    (GET) ou du body (PUT), mêmes clés dans les deux cas. Retourne un dict
    à au plus une entrée, utilisable tel quel comme filtre/kwargs PalierAlerte.
    """
    indicateur_id = params.get("indicateur")
    activite_id = params.get("activite")
    projet_id = params.get("projet")
    if len([v for v in (indicateur_id, activite_id, projet_id) if v]) > 1:
        raise ValidationError({"portee": v('Précise au plus un seul parmi projet/indicateur/activité.')})

    if indicateur_id:
        indicateur = Indicateur.objects.filter(id=indicateur_id).first()
        if indicateur is None:
            raise ValidationError({"indicateur": v('Indicateur introuvable.')})
        return {"indicateur": indicateur}
    if activite_id:
        activite = Activite.objects.filter(id=activite_id).first()
        if activite is None:
            raise ValidationError({"activite": "Activité introuvable."})
        return {"activite": activite}
    if projet_id:
        projet = Projet.objects.filter(id=projet_id).first()
        if projet is None:
            raise ValidationError({"projet": v('Projet introuvable.')})
        return {"projet": projet}
    return {}


def _projet_de_la_portee(portee):
    """Le projet dont hérite cette portée (None pour la grille globale elle-même)."""
    if "indicateur" in portee:
        return portee["indicateur"].projet_rattache
    if "activite" in portee:
        return portee["activite"].projet
    if "projet" in portee:
        return portee["projet"]
    return None


def _paliers_herites(portee):
    """Grille dont hériterait cette portée si elle n'avait pas (ou plus) de grille propre."""
    return paliers_pour(
        indicateur=portee.get("indicateur"), activite=portee.get("activite"), projet=_projet_de_la_portee(portee)
    )


@api_view(["GET", "PUT"])
@permission_classes([IsAdminOrReadOnly])
def paliers_alerte(request):
    """
    Portée au choix — au plus un de ces trois paramètres (aucun = grille
    globale) :
      ?indicateur=<id> | ?activite=<id> | ?projet=<id>

    GET : grille effective de cette portée (la sienne si définie, sinon
    celle héritée du niveau supérieur — indicateur/activité > projet >
    globale — avec `personnalise` disant si CETTE portée précise a sa
    propre grille).

    PUT { "indicateur"|"activite"|"projet": <id>, "paliers": [...] } :
    remplace intégralement la grille propre à cette portée — réservé à
    l'Administrateur. Une liste vide revient à hériter de nouveau du niveau
    supérieur (sauf pour la grille globale, qui doit toujours en contenir
    au moins un).
    """
    if request.method == "GET":
        portee = _resoudre_portee(request.query_params)
        paliers_propres = list(PalierAlerte.objects.filter(**portee).order_by("borne_min")) if portee else []
        personnalise = bool(portee) and bool(paliers_propres)
        paliers = paliers_propres if personnalise else _paliers_herites(portee)
        return Response({"personnalise": personnalise, "paliers": PalierAlerteSerializer(paliers, many=True).data})

    portee = _resoudre_portee(request.data)
    filtre_portee = portee or {"projet__isnull": True, "indicateur__isnull": True, "activite__isnull": True}
    lignes = request.data.get("paliers", [])
    if not portee and not lignes:
        raise ValidationError({"paliers": "La grille globale doit contenir au moins un palier."})

    noms_vus = set()
    for ligne in lignes:
        borne = ligne.get("borne_min")
        if borne is None or not (0 <= int(borne) <= 100):
            raise ValidationError({"paliers": "Chaque borne doit être un pourcentage entre 0 et 100."})
        if borne in noms_vus:
            raise ValidationError({"paliers": f"Le seuil {borne}% est défini plusieurs fois."})
        noms_vus.add(borne)
        if not str(ligne.get("libelle") or "").strip():
            raise ValidationError({"paliers": "Chaque palier doit avoir un libellé."})

    PalierAlerte.objects.filter(**filtre_portee).delete()
    PalierAlerte.objects.bulk_create(
        [
            PalierAlerte(
                **portee,
                borne_min=int(ligne["borne_min"]),
                libelle=str(ligne["libelle"]).strip(),
                couleur=ligne.get("couleur") or "#495057",
            )
            for ligne in lignes
        ]
    )
    paliers = list(PalierAlerte.objects.filter(**filtre_portee).order_by("borne_min"))
    if not paliers:
        paliers = _paliers_herites(portee)
    return Response(
        {"personnalise": bool(portee) and bool(lignes), "paliers": PalierAlerteSerializer(paliers, many=True).data}
    )


class IndicateurViewSet(viewsets.ModelViewSet):
    serializer_class = IndicateurSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet", "activite", "frequence_collecte", "elements_strategiques")
    search_fields = ("libelle",)

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)
        return (
            Indicateur.objects.filter(
                Q(projet__isnull=True, activite__isnull=True)
                | Q(projet__id__in=ids)
                | Q(activite__projet__id__in=ids)
            )
            # Rattachés à un élément masqué à cet utilisateur (apps.core.masquage) : exclus.
            .exclude(Q(activite_id__in=activites_masquees(self.request.user))
                     | Q(elements_strategiques__in=elements_masques(self.request.user)))
            .select_related("projet", "activite__projet")
            .distinct()
        )

    def perform_destroy(self, instance):
        supprimer_indicateur_cascade(instance)

    @action(detail=False, methods=["get"], url_path="formules/catalogue")
    def formules_catalogue(self, request):
        """Ce que l'éditeur de formules propose : mesures, filtres, choix, modèles prêts à copier."""
        from .formules import catalogue

        return Response(catalogue())

    @action(detail=False, methods=["post"], url_path="formules/apercu")
    def formules_apercu(self, request):
        """
        Résultat immédiat d'une formule en cours d'écriture, sur les vraies données : {valeur, termes,
        non_calculable, explication}. Données du projet indiqué (?projet= ou « projet »), sinon de tous les
        projets visibles.
        """
        from .formules import FormuleInvalide, evaluer, explication

        visibles = visible_projets_ids(self.request.user)
        projet = request.data.get("projet")
        if projet:
            if int(projet) not in set(visibles):
                raise ValidationError({"projet": v("Projet non accessible.")})
            ids = [int(projet)]
        else:
            ids = list(visibles)
        try:
            resultat = evaluer(request.data.get("formule"), ids)
        except FormuleInvalide as exc:
            return Response({"erreur": str(exc)}, status=400)
        return Response({**resultat, "explication": explication(request.data["formule"])})

    @action(detail=False, methods=["get"], url_path="pour-projet")
    def pour_projet(self, request):
        """
        Liste allégée (id, libellé), non paginée, des indicateurs rattachés à
        un projet (quel que soit leur niveau de rattachement) — alimente le
        sélecteur de grille d'alerte par indicateur (potentiellement des
        centaines d'indicateurs, une pagination classique serait inutile ici).
        """
        from .services import indicateurs_pour_projet

        projet_id = request.query_params.get("projet")
        ids = visible_projets_ids(self.request.user)
        if not projet_id or int(projet_id) not in ids:
            return Response([])
        indicateurs = indicateurs_pour_projet(projet_id).order_by("libelle")
        return Response([{"id": i.id, "libelle": i.libelle} for i in indicateurs])

    @action(detail=False, methods=["get"], url_path="modele-import")
    @dans_la_langue_demandee
    def modele_import(self, request):
        contenu = generer_modele_import_indicateurs()
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=modele_import_indicateurs.xlsx"
        return response

    @action(detail=False, methods=["post"], url_path="importer", parser_classes=[MultiPartParser, FormParser])
    def importer(self, request):
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
        try:
            resultat = importer_indicateurs(fichier)
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
        return Response(resultat)


class ValeurIndicateurViewSet(AvertissementsSaisieMixin, SuppressionAtomiqueMixin, viewsets.ModelViewSet):
    serializer_class = ValeurIndicateurSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("indicateur",)

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)
        return ValeurIndicateur.tous.filter(
            Q(indicateur__projet__isnull=True, indicateur__activite__isnull=True)
            | Q(indicateur__projet__id__in=ids)
            | Q(indicateur__activite__projet__id__in=ids)
        ).exclude(indicateur__activite_id__in=activites_masquees(self.request.user)).distinct()

    def perform_create(self, serializer):
        super().perform_create(serializer)
        valeur = serializer.instance
        indicateur = valeur.indicateur
        taux = taux_indicateur(indicateur)
        paliers = paliers_pour(indicateur=indicateur, projet=indicateur.projet_rattache)
        palier = palier_pour_taux(taux, paliers)
        # Le palier le plus bas de la palette (première borne, la plus critique) déclenche
        # l'alerte — quel que soit son libellé, qui est propre à chaque projet/organisation.
        if palier is not None and paliers and palier.id == paliers[0].id:
            projet = indicateur.projet_rattache
            titre = f"Indicateur en alerte critique : {indicateur.libelle}"
            contexte = f"Projet {projet.nom}" if projet else "Indicateur stratégique (sans projet)"
            message = f"{contexte} — taux de réalisation {taux}% ({palier.libelle})."
            lien = f"/indicateurs/{indicateur.id}"
            if projet and projet.utilisateurs_affectes.exists():
                notifier(list(projet.utilisateurs_affectes.all()), Notification.Type.INDICATEUR_ALERTE, titre, message, lien)
            notifier_par_role(
                [ROLE_CHARGE_SE], Notification.Type.INDICATEUR_ALERTE, titre, message, lien
            )


class EnqueteViewSet(viewsets.ModelViewSet):
    """
    Données d'enquête : import d'un fichier (champ « fichier », plus « titre » et « projet »), réglage du plan de
    sondage (poids, strate, grappe), réponses d'une colonne (colonnes/?colonne=) et estimations pondérées avec
    leur marge d'erreur (calcul/).
    """

    serializer_class = EnqueteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filterset_fields = ("projet",)

    def get_queryset(self):
        ids = visible_projets_ids(self.request.user)
        qs = Enquete.objects.filter(Q(projet__isnull=True) | Q(projet__id__in=ids)).select_related("projet", "cree_par")
        return qs if self.action in ("modalites", "calcul") else qs.defer("donnees")

    def create(self, request, *args, **kwargs):
        from .enquetes import EnqueteInvalide, lire

        fichier = request.FILES.get("fichier")
        if fichier is None:
            raise ValidationError({"fichier": v("Choisissez un fichier.")})
        projet = request.data.get("projet") or None
        if projet and int(projet) not in set(visible_projets_ids(request.user)):
            raise ValidationError({"projet": v("Projet non accessible.")})
        try:
            lu = lire(fichier)
        except EnqueteInvalide as exc:
            raise ValidationError({"fichier": str(exc)})
        titre = (request.data.get("titre") or fichier.name.rsplit(".", 1)[0]).strip()[:200]
        enquete = Enquete.objects.create(titre=titre, projet_id=projet, fichier_source=fichier.name[:255], cree_par=request.user,
                                         date_debut=request.data.get("date_debut") or None, date_fin=request.data.get("date_fin") or None, **lu)
        return Response(self.get_serializer(enquete).data, status=201)

    @action(detail=True, methods=["get"])
    def modalites(self, request, pk=None):
        """Réponses d'une colonne (?colonne=) et leur nombre."""
        from .enquetes import EnqueteInvalide, modalites

        try:
            return Response(modalites(self.get_object(), request.query_params.get("colonne", "")))
        except EnqueteInvalide as exc:
            raise ValidationError({"colonne": str(exc)})

    @action(detail=True, methods=["get"])
    def calcul(self, request, pk=None):
        """
        Estimation pondérée (lecture seule, ouverte à qui consulte) : ?calcul=&colonne=&valeurs=…&valeurs=…&par= →
        résultats avec intervalle de confiance à 95 %.
        """
        from .enquetes import EnqueteInvalide, estimer

        d = request.query_params
        try:
            return Response(estimer(self.get_object(), d.get("calcul"), d.get("colonne", ""), d.getlist("valeurs"), d.get("par") or None))
        except EnqueteInvalide as exc:
            raise ValidationError({"calcul": str(exc)})
