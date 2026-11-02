"""
API du mécanisme de plaintes : paramétrage (lot 1) et dossiers reçus (lot 2). Droits du module
« Plaintes et retours » (apps.core.modules : /api/v1/plaintes/) ; un module caché est refusé même
en lecture (les dossiers contiennent des données personnelles). Pages publiques : public.py.
"""
import io

import django_filters
from django.utils import timezone
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.langues import dans_la_langue_demandee, en_langue, langue_demandee, traduire
from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.core.vocabulaire import v

from . import confidentiel, delais, pilotage, traitement

from .controles import controler_activation
from .models import (
    ActionCorrective,
    Canal, Categorie, Circuit, Dossier, EtapeCircuit, JourFerie, Mecanisme, Prestataire, Priorite, StatutDossier, TypeRetour,
    VueDossiers,
)
from .modeles_mecanisme import MODELES, appliquer_modele, liste_modeles
from .reception import dossiers_visibles, recevoir
from .serializers import (
    ActionCorrectiveSerializer,
    CategorieSerializer,
    CircuitSerializer,
    DossierDetailSerializer,
    DossierSerializer,
    EtapeCircuitSerializer,
    JourFerieSerializer,
    PrestataireSerializer,
    MecanismeSerializer,
    PrioriteSerializer,
    TypeRetourSerializer,
    VueDossiersSerializer,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@api_view(["GET", "PATCH"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def mecanisme(request):
    """Le mécanisme de l'organisation ; « controles » : ce qui manque pour l'activer."""
    objet = Mecanisme.courant()
    if request.method == "PATCH":
        serializer = MecanismeSerializer(objet, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if {"jours_ouvres", "delai_defaut_jours"} & set(request.data):
            delais.recalculer_ouverts()
        objet.refresh_from_db()
    return Response(MecanismeSerializer(objet).data)


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def activer(request):
    """Ouvre le mécanisme ; refusé, avec la liste de ce qui manque, si un contrôle échoue."""
    objet = Mecanisme.courant()
    erreurs = controler_activation(objet)
    if erreurs:
        return Response({"detail": "Le mécanisme ne peut pas encore être activé.", "controles": erreurs},
                        status=status.HTTP_400_BAD_REQUEST)
    objet.actif = True
    objet.save(update_fields=["actif", "updated_at"])
    return Response(MecanismeSerializer(objet).data)


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def desactiver(request):
    objet = Mecanisme.courant()
    objet.actif = False
    objet.save(update_fields=["actif", "updated_at"])
    return Response(MecanismeSerializer(objet).data)


@api_view(["GET", "POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def modeles(request):
    """GET : modèles prêts à l'emploi ; POST {modele} : le copie dans la configuration (ajouts seulement)."""
    if request.method == "GET":
        with en_langue(langue_demandee(request)):
            return Response([{**m, "libelle": traduire(m["libelle"]), "description": traduire(m["description"])}
                             for m in liste_modeles()])
    code = request.data.get("modele")
    if code not in MODELES:
        raise ValidationError({"modele": "Choisissez un modèle de la liste."})
    ajouts = appliquer_modele(code)
    return Response({"ajouts": ajouts, "mecanisme": MecanismeSerializer(Mecanisme.courant()).data})


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def canevas(request):
    """Canevas Excel du paramétrage, prérempli avec la configuration actuelle."""
    from .excel import exporter_parametrage

    response = HttpResponse(exporter_parametrage(), content_type=XLSX)
    response["Content-Disposition"] = "attachment; filename=parametrage_plaintes.xlsx"
    return response


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@parser_classes([MultiPartParser, FormParser])
def importer_canevas(request):
    from .excel import importer_parametrage

    fichier = request.data.get("fichier")
    if not fichier:
        raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
    try:
        return Response(importer_parametrage(fichier))
    except (KeyError, OSError, ValueError) as exc:
        raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})


class _Base(viewsets.ModelViewSet):
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    pagination_class = None
    # Un changement de délai (catégorie, priorité, étape, calendrier) se répercute sur les dossiers ouverts.
    recalcule_les_delais = False

    def perform_update(self, serializer):
        avant = {c: getattr(serializer.instance, c, None) for c in ("delai_jours", "date")}
        super().perform_update(serializer)
        if self.recalcule_les_delais and any(getattr(serializer.instance, c, None) != a for c, a in avant.items()):
            delais.recalculer_ouverts()

    def perform_create(self, serializer):
        super().perform_create(serializer)
        if isinstance(serializer.instance, JourFerie):
            delais.recalculer_ouverts()

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError({"detail": "Cet élément est encore utilisé : retirez d'abord ce qui en dépend."})
        if isinstance(instance, JourFerie):
            delais.recalculer_ouverts()


class TypeRetourViewSet(_Base):
    queryset = TypeRetour.objects.all()
    serializer_class = TypeRetourSerializer


class PrioriteViewSet(_Base):
    recalcule_les_delais = True
    queryset = Priorite.objects.all()
    serializer_class = PrioriteSerializer

    def perform_destroy(self, instance):
        if instance.urgente and not Priorite.objects.filter(urgente=True, actif=True).exclude(pk=instance.pk).exists():
            raise ValidationError({"detail": "Gardez au moins une priorité urgente active."})
        super().perform_destroy(instance)


class CircuitViewSet(_Base):
    queryset = Circuit.objects.prefetch_related("etapes__role", "etapes__responsable")
    serializer_class = CircuitSerializer


class EtapeCircuitViewSet(_Base):
    recalcule_les_delais = True
    queryset = EtapeCircuit.objects.select_related("role", "responsable")
    serializer_class = EtapeCircuitSerializer
    filterset_fields = ("circuit",)


class CategorieViewSet(_Base):
    recalcule_les_delais = True
    queryset = Categorie.objects.select_related("parent", "circuit")
    serializer_class = CategorieSerializer

    def perform_destroy(self, instance):
        if instance.verrouillee:
            raise ValidationError({"detail": "Cette catégorie protège les personnes : elle ne peut pas être supprimée."})
        if instance.sous_categories.exists():
            raise ValidationError({"detail": "Supprimez ou déplacez d'abord ses sous-catégories."})
        super().perform_destroy(instance)


class FiltreDossiers(django_filters.FilterSet):
    date_du = django_filters.DateFilter(field_name="date_reception", lookup_expr="gte")
    date_au = django_filters.DateFilter(field_name="date_reception", lookup_expr="lte")
    # Une catégorie principale inclut ses sous-catégories.
    categorie = django_filters.NumberFilter(method="filtrer_categorie")
    sans_responsable = django_filters.BooleanFilter(field_name="responsable", lookup_expr="isnull")

    class Meta:
        model = Dossier
        fields = ("statut", "canal", "projet", "type_retour", "priorite", "responsable", "sensible", "en_recours")

    def filtrer_categorie(self, queryset, nom, valeur):
        return queryset.filter(Q(categorie_id=valeur) | Q(categorie__parent_id=valeur))


# Vues prêtes de la liste (?vue=…).
VUES = {
    "mes_dossiers": lambda qs, u: qs.filter(responsable=u),
    "a_traiter": lambda qs, u: qs.filter(responsable=u, statut__in=(StatutDossier.RECU, StatutDossier.EN_COURS)),
    "urgents": lambda qs, u: qs.filter(priorite__urgente=True).exclude(statut=StatutDossier.CLOTURE),
    "sans_responsable": lambda qs, u: qs.filter(responsable__isnull=True).exclude(statut=StatutDossier.CLOTURE),
    "attente_decision": lambda qs, u: qs.filter(statut=StatutDossier.EN_COURS, decision=""),
    "a_cloturer": lambda qs, u: qs.filter(Q(statut=StatutDossier.REPONDU) | Q(statut=StatutDossier.EN_COURS) & ~Q(decision="")),
    "recours": lambda qs, u: qs.filter(en_recours=True),
    "en_retard": lambda qs, u: qs.exclude(statut=StatutDossier.CLOTURE).filter(
        Q(echeance__lt=timezone.localdate()) | Q(echeance_etape__lt=timezone.localdate())),
    "a_anonymiser": lambda qs, u: qs.filter(pk__in=[d.pk for d in confidentiel.a_anonymiser(qs)]),
    "confidentiels": lambda qs, u: qs.filter(sensible=True),
}


class PrestataireViewSet(_Base):
    """Annuaire des prestataires d'assistance (référencement)."""

    queryset = Prestataire.objects.all()
    serializer_class = PrestataireSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def signaler_sensible(request, pk):
    """
    Marquage manuel : tout utilisateur qui voit le dossier peut le signaler comme sensible, même en
    lecture seule sur le module (d'où une route hors de /plaintes/). Il en perd aussitôt l'accès s'il
    n'est pas habilité.
    """
    dossier = dossiers_visibles(request.user).filter(pk=pk).first()
    if dossier is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    confidentiel.signaler_sensible(dossier, request.user, request.data)
    visible = dossiers_visibles(request.user).filter(pk=pk).exists()
    return Response({"numero": dossier.numero, "visible": visible})


class JourFerieViewSet(_Base):
    """Calendrier des jours fériés de l'organisation (délais en jours ouvrés)."""

    queryset = JourFerie.objects.all()
    serializer_class = JourFerieSerializer
    recalcule_les_delais = True


class DossierViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """
    Dossiers. Création = saisie par un agent (même interface d'entrée que le formulaire public,
    voir reception.py). Traitement par actions (POST …/{id}/affecter/, …/cloturer/…), dont les règles
    sont dans traitement.py. Un dossier interdit n'apparaît ni dans les listes, ni dans les compteurs,
    ni dans la recherche, ni dans les dossiers liés.
    """

    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_class = FiltreDossiers
    search_fields = ("numero",)

    def get_serializer_class(self):
        return DossierDetailSerializer if self.action != "list" else DossierSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "visibles": dossiers_visibles(self.request.user)}

    def get_queryset(self):
        qs = dossiers_visibles(self.request.user).select_related(
            "type_retour", "categorie__parent", "priorite", "projet", "circuit", "etape", "saisi_par", "responsable",
            "gestionnaire_initial",
        )
        vue = VUES.get(self.request.query_params.get("vue", ""))
        if vue:
            qs = vue(qs, self.request.user)
        if self.action == "retrieve":
            qs = qs.prefetch_related("actions__auteur")
        return qs

    def create(self, request, *args, **kwargs):
        canal = request.data.get("canal")
        if canal == Canal.FORMULAIRE:
            raise ValidationError({"canal": "Choisissez le canal par lequel le retour a été reçu."})
        dossier, code = recevoir(request.data, canal, saisi_par=request.user)
        visible = dossiers_visibles(request.user).filter(pk=dossier.pk).exists()
        reponse = {"numero": dossier.numero, "code_suivi": code, "sensible": dossier.sensible, "visible": visible}
        if visible:
            reponse["dossier"] = DossierSerializer(dossier).data
        return Response(reponse, status=status.HTTP_201_CREATED)

    def _agir(self, fonction, *args):
        dossier = self.get_object()
        fonction(dossier, self.request.user, *args)
        # Le dossier peut ne plus être visible (devenu confidentiel) : on renvoie ce qui reste accessible.
        visible = dossiers_visibles(self.request.user).filter(pk=dossier.pk).first()
        if visible is None:
            return Response({"numero": dossier.numero, "visible": False})
        return Response(DossierDetailSerializer(visible, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def classer(self, request, pk=None):
        return self._agir(traitement.classer, request.data)

    @action(detail=True, methods=["post"])
    def affecter(self, request, pk=None):
        return self._agir(traitement.affecter, request.data.get("responsable"))

    @action(detail=True, methods=["post"])
    def recuser(self, request, pk=None):
        return self._agir(traitement.recuser, request.data)

    @action(detail=True, methods=["post"])
    def etape(self, request, pk=None):
        return self._agir(traitement.changer_etape, request.data)

    @action(detail=True, methods=["post"])
    def noter(self, request, pk=None):
        return self._agir(traitement.noter, request.data)

    @action(detail=True, methods=["post"])
    def communiquer(self, request, pk=None):
        return self._agir(traitement.communiquer, request.data)

    @action(detail=True, methods=["post"])
    def decider(self, request, pk=None):
        return self._agir(traitement.decider, request.data)

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        return self._agir(traitement.cloturer, request.data)

    @action(detail=True, methods=["post"])
    def rouvrir(self, request, pk=None):
        return self._agir(traitement.rouvrir, request.data)

    @action(detail=True, methods=["post"])
    def recours(self, request, pk=None):
        return self._agir(traitement.recours, request.data)

    @action(detail=True, methods=["post"])
    def prolonger(self, request, pk=None):
        return self._agir(delais.prolonger, request.data)

    @action(detail=False, methods=["post"], url_path="exporter-liste")
    @dans_la_langue_demandee
    def exporter_liste(self, request):
        """
        Liste des dossiers filtrés (mêmes filtres et vues que la liste) en Excel : sans les dossiers
        confidentiels, coordonnées seulement pour l'Administrateur qui les demande, export inscrit au journal.
        """
        from apps.accounts.constants import ROLE_ADMIN

        from .export_pilotage import liste_dossiers_excel

        qs = self.filter_queryset(self.get_queryset()).select_related("etape", "responsable")
        avec_coordonnees = bool(request.data.get("coordonnees")) and request.user.role == ROLE_ADMIN
        contenu, nombre = liste_dossiers_excel(list(qs), request.user, avec_coordonnees)
        reponse = HttpResponse(contenu, content_type=XLSX)
        reponse["Content-Disposition"] = "attachment; filename=dossiers_plaintes.xlsx"
        reponse["X-Nombre-Dossiers"] = str(nombre)
        return reponse

    @action(detail=True, methods=["post"], url_path="lever-sensibilite")
    def lever_sensibilite(self, request, pk=None):
        return self._agir(confidentiel.lever_sensibilite, request.data)

    @action(detail=True, methods=["post"], url_path="mettre-en-cause")
    def mettre_en_cause(self, request, pk=None):
        return self._agir(confidentiel.mettre_en_cause, request.data)

    @action(detail=True, methods=["post"])
    def assistance(self, request, pk=None):
        return self._agir(confidentiel.orienter_assistance, request.data)

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        return self._agir(confidentiel.suspendre, request.data)

    @action(detail=True, methods=["post"])
    def anonymiser(self, request, pk=None):
        return self._agir(confidentiel.anonymiser, request.data)

    @action(detail=True, methods=["post"])
    @dans_la_langue_demandee
    def exporter(self, request, pk=None):
        """Fiche PDF en filigrane ; motif exigé pour un dossier confidentiel ; export tracé au journal."""
        from .export_fiche import fiche_pdf
        from .models import ActionDossier

        dossier = self.get_object()
        motif = (request.data.get("motif") or "").strip()
        if dossier.sensible and not motif:
            raise ValidationError({"motif": v("Indiquez le motif de l'export de ce dossier confidentiel.")})
        if dossier.sensible and request.data.get("confirmation") is not True:
            raise ValidationError({"confirmation": v("Confirmez l'export de ce dossier confidentiel.")})
        ActionDossier.objects.create(dossier=dossier, type=ActionDossier.Type.EXPORT, auteur=request.user, texte=motif)
        reponse = HttpResponse(fiche_pdf(dossier, request.user), content_type="application/pdf")
        reponse["Content-Disposition"] = f'attachment; filename="dossier_{dossier.numero}.pdf"'
        return reponse

    @action(detail=True, methods=["post"])
    def lier(self, request, pk=None):
        """{numero, delier?} : lie (ou délie) un autre dossier visible."""
        autre = dossiers_visibles(request.user).filter(numero__iexact=(request.data.get("numero") or "").strip()).first()
        if autre is None:
            raise ValidationError({"numero": v("Aucun dossier accessible ne porte ce numéro.")})
        return self._agir(traitement.lier, autre, bool(request.data.get("delier")))

    @action(detail=True, methods=["get"], url_path="possiblement-lies")
    def possiblement_lies(self, request, pk=None):
        dossier = self.get_object()
        proches = traitement.dossiers_possiblement_lies(dossier, dossiers_visibles(request.user))
        return Response([{"id": d.id, "numero": d.numero, "date_reception": d.date_reception, "statut": d.statut}
                         for d in proches])

    @action(detail=True, methods=["get"], url_path="responsables-possibles")
    def responsables_possibles(self, request, pk=None):
        """Personnes à qui le dossier peut être confié (circuit confidentiel : points focaux et Administrateurs)."""
        dossier = self.get_object()
        personnes = traitement.personnes_habilitees(dossier).order_by("first_name", "last_name", "username")
        if dossier.en_recours and dossier.gestionnaire_initial_id:
            personnes = personnes.exclude(pk=dossier.gestionnaire_initial_id)
        from apps.accounts.models import Role

        libelles = dict(Role.objects.values_list("code", "libelle"))
        return Response([{"id": u.id, "nom": traitement.nom_personne(u), "role": libelles.get(u.role, u.role)}
                         for u in personnes])


class VueDossiersViewSet(viewsets.ModelViewSet):
    """Filtres enregistrés de l'utilisateur connecté (chacun ne voit que les siens)."""

    serializer_class = VueDossiersSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        return VueDossiers.objects.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def qr_formulaire(request):
    """QR code (PNG) de l'adresse du formulaire public, éventuellement propre à un projet (?projet=)."""
    import segno

    origine = request.query_params.get("origine", "")
    if not origine.startswith(("http://", "https://")):
        origine = request.headers.get("Origin") or request.build_absolute_uri("/")
    lien = origine.rstrip("/") + "/plainte"
    projet = request.query_params.get("projet", "")
    if projet.isdigit():
        lien += f"?projet={projet}"
    sortie = io.BytesIO()
    segno.make(lien, error="m").save(sortie, kind="png", scale=10, border=2)
    response = HttpResponse(sortie.getvalue(), content_type="image/png")
    response["Content-Disposition"] = "attachment; filename=qr_formulaire_plaintes.png"
    return response


# --- Lot 6 : pilotage ------------------------------------------------------------------------------

def _periode(request):
    from datetime import date

    def lire(cle):
        try:
            return date.fromisoformat(request.query_params.get(cle, "")[:10])
        except ValueError:
            return None

    projet = request.query_params.get("projet", "")
    return lire("du"), lire("au"), int(projet) if projet.isdigit() else None


def _vue(request):
    vue = request.query_params.get("vue") or request.data.get("vue") or "pilotage"
    if vue not in pilotage.VUES:
        raise ValidationError({"vue": v("Vue inconnue.")})
    if vue == "confidentielle" and not pilotage.habilite_confidentiel(request.user):
        raise PermissionDenied(v("La vue confidentielle est réservée aux personnes habilitées."))
    return vue


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def tableau_de_bord(request):
    """Éléments calculés d'une vue (?vue=, ?du=, ?au=, ?projet=)."""
    vue = _vue(request)
    du, au, projet = _periode(request)
    return Response(pilotage.calculer_vue(vue, request.user, du, au, projet))


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def catalogue_tableau(request):
    """Vues accessibles et catalogue des éléments (pour personnaliser une vue)."""
    habilite = pilotage.habilite_confidentiel(request.user)
    return Response({
        "vues": [{"code": c, "libelle": v(l)} for c, (l, _) in pilotage.VUES.items() if c != "confidentielle" or habilite],
        "elements": [{"code": c, "libelle": v(l), "nature": n, "confidentiel": conf}
                     for c, (l, n, conf) in pilotage.CATALOGUE.items() if not conf or habilite],
        "peut_regler_organisation": request.user.role == "ADMIN",
    })


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def configuration_tableau(request):
    """
    Composition d'une vue. PUT {vue, elements, portee} : « utilisateur » (sa copie, sans rien changer pour
    les autres) ou « organisation » (Administrateur). DELETE ?vue= : revenir à la vue de l'organisation.
    """
    from .models import TableauPlaintes

    vue = _vue(request)
    if request.method == "GET":
        return Response({"vue": vue, **pilotage.configuration(vue, request.user)})
    if request.method == "DELETE":
        TableauPlaintes.objects.filter(vue=vue, utilisateur=request.user).delete()
        return Response({"vue": vue, **pilotage.configuration(vue, request.user)})
    portee = request.data.get("portee", "utilisateur")
    if portee == "organisation" and request.user.role != "ADMIN":
        raise PermissionDenied(v("Seul l'Administrateur modifie la vue de l'organisation."))
    utilisateur = None if portee == "organisation" else request.user
    TableauPlaintes.objects.update_or_create(vue=vue, utilisateur=utilisateur,
                                             defaults={"elements": pilotage.nettoyer(vue, request.data.get("elements"))})
    return Response({"vue": vue, **pilotage.configuration(vue, request.user)})


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def export_tableau(request, format_):
    from .export_pilotage import vue_excel, vue_pdf

    vue = _vue(request)
    du, au, projet = _periode(request)
    resultat = pilotage.calculer_vue(vue, request.user, du, au, projet)
    if format_ == "pdf":
        reponse = HttpResponse(vue_pdf(resultat, request.user), content_type="application/pdf")
    else:
        reponse = HttpResponse(vue_excel(resultat), content_type=XLSX)
    reponse["Content-Disposition"] = f"attachment; filename=tableau_plaintes_{vue}.{'pdf' if format_ == 'pdf' else 'xlsx'}"
    return reponse


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def retours_projet(request, projet_id):
    """Encart « Retours des communautés » de la fiche projet."""
    return Response(pilotage.retours_projet(projet_id, request.user))


class ActionCorrectiveViewSet(_Base):
    """Actions correctives (responsable, échéance, statut), reliées à plusieurs dossiers."""

    serializer_class = ActionCorrectiveSerializer
    filterset_fields = ("projet", "statut", "responsable", "dossiers")

    def get_queryset(self):
        return ActionCorrective.objects.select_related("projet", "responsable").prefetch_related("dossiers")

    def _journaliser(self, action, ajoutes):
        from .models import ActionDossier

        ActionDossier.objects.bulk_create([
            ActionDossier(dossier=d, type=ActionDossier.Type.ACTION_CORRECTIVE, auteur=self.request.user,
                          texte=v("Action corrective liée : ") + action.titre) for d in ajoutes])

    def perform_create(self, serializer):
        action = serializer.save(cree_par=self.request.user)
        self._journaliser(action, action.dossiers.all())

    def perform_update(self, serializer):
        avant = set(serializer.instance.dossiers.values_list("pk", flat=True))
        # Les liens vers des dossiers que l'utilisateur ne voit pas sont conservés tels quels.
        invisibles = set(serializer.instance.dossiers.exclude(pk__in=dossiers_visibles(self.request.user)).values_list("pk", flat=True))
        action = serializer.save()
        if "dossiers" in serializer.validated_data and invisibles:
            action.dossiers.add(*invisibles)
        if action.statut == ActionCorrective.Statut.REALISEE and not action.date_realisation:
            ActionCorrective.objects.filter(pk=action.pk).update(date_realisation=timezone.localdate())
        self._journaliser(action, action.dossiers.exclude(pk__in=avant))
