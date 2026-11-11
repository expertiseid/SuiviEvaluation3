"""
API du mécanisme de plaintes : paramétrage (lot 1) et dossiers reçus (lot 2). Droits du module
« Plaintes et retours » (apps.core.modules : /api/v1/plaintes/) ; un module caché est refusé même
en lecture (les dossiers contiennent des données personnelles). Pages publiques : public.py.
"""
import io

import django_filters
from django.conf import settings
from django.utils import timezone
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from rest_framework.generics import get_object_or_404  # répond 404 (pas 500) si l'identifiant n'est pas un nombre
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, parser_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.audit import A, auditer
from apps.core.langues import dans_la_langue_demandee, en_langue, langue_demandee, traduire
from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.core.vocabulaire import v

from . import confidentiel, delais, pilotage, traitement
from .audit_plaintes import configuration as auditer_configuration

from .controles import controler_activation
from .models import (
    ActionCorrective,
    Canal, Categorie, DemandeDroits, HabilitationSensible, Circuit, Dossier, EtapeCircuit, JourFerie, Mecanisme, ModeleMessage, Prestataire, Priorite,
    StatutDossier, TypeRetour, VueDossiers,
)
from .modeles_mecanisme import MODELES, appliquer_modele, liste_modeles
from .reception import dossiers_visibles, lire_envoi, recevoir
from .serializers import (
    ActionCorrectiveSerializer,
    CategorieSerializer,
    CircuitSerializer,
    DossierDetailSerializer,
    DemandeDroitsSerializer,
    DossierSerializer,
    EtapeCircuitSerializer,
    HabilitationSerializer,
    JourFerieSerializer,
    PrestataireSerializer,
    MecanismeSerializer,
    ModeleMessageSerializer,
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
        avant = {c: getattr(objet, c) for c in serializer.validated_data}
        serializer.save()
        changes = sorted(c for c in avant if avant[c] != getattr(objet, c))
        if changes:
            auditer_configuration(request.user, "Mécanisme", "modification", champs=changes)
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
    auditer_configuration(request.user, "Mécanisme", "activation")
    return Response(MecanismeSerializer(objet).data)


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def desactiver(request):
    objet = Mecanisme.courant()
    objet.actif = False
    objet.save(update_fields=["actif", "updated_at"])
    auditer_configuration(request.user, "Mécanisme", "desactivation")
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
    auditer_configuration(request.user, "Modèle de mécanisme", "application", modele=code)
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
        rapport = importer_parametrage(fichier)
        auditer_configuration(request.user, "Canevas de paramétrage", "import", crees=rapport.get("crees"),
                              mis_a_jour=rapport.get("mis_a_jour"), erreurs=len(rapport.get("erreurs", [])))
        return Response(rapport)
    except (KeyError, OSError, ValueError) as exc:
        raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})


class _Base(viewsets.ModelViewSet):
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    pagination_class = None
    # Un changement de délai (catégorie, priorité, étape, calendrier) se répercute sur les dossiers ouverts.
    recalcule_les_delais = False
    # Paramétrage : chaque création, modification et suppression va au journal d'audit.
    audite = True

    def _auditer(self, instance, operation, **details):
        if self.audite:
            auditer_configuration(self.request.user, f"{instance._meta.verbose_name} « {instance} »"[:255], operation,
                                  identifiant=instance.pk, **details)

    def perform_update(self, serializer):
        avant = {c: getattr(serializer.instance, c, None) for c in serializer.validated_data}
        super().perform_update(serializer)
        changes = sorted(c for c, a in avant.items() if getattr(serializer.instance, c, None) != a)
        if changes:
            self._auditer(serializer.instance, "modification", champs=changes)
        if self.recalcule_les_delais and {"delai_jours", "date"} & set(changes):
            delais.recalculer_ouverts()

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._auditer(serializer.instance, "creation")
        if isinstance(serializer.instance, JourFerie):
            delais.recalculer_ouverts()

    def perform_destroy(self, instance):
        pk, libelle = instance.pk, f"{instance._meta.verbose_name} « {instance} »"[:255]
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError({"detail": "Cet élément est encore utilisé : retirez d'abord ce qui en dépend."})
        if self.audite:
            auditer_configuration(self.request.user, libelle, "suppression", identifiant=pk)
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


class ModeleMessageViewSet(_Base):
    """Modèles de messages au plaignant, par objet et par langue."""

    queryset = ModeleMessage.objects.all()
    serializer_class = ModeleMessageSerializer

    @action(detail=False, methods=["post"])
    def installer(self, request):
        """Ajoute les modèles par défaut qui manquent (sans écraser ceux de l'organisation)."""
        from .messages import installer_modeles

        return Response({"ajoutes": installer_modeles()})


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
    parser_classes = (JSONParser, MultiPartParser, FormParser)  # pièces jointes : saisie et ajout
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
            qs = qs.prefetch_related("actions__auteur", "pieces__ajoute_par")
        return qs

    def retrieve(self, request, *args, **kwargs):
        from .audit_plaintes import consultation

        dossier = self.get_object()
        consultation(dossier, request.user)
        return Response(self.get_serializer(dossier).data)

    def create(self, request, *args, **kwargs):
        donnees, fichiers = lire_envoi(request)
        canal = donnees.get("canal")
        if canal == Canal.FORMULAIRE:
            raise ValidationError({"canal": "Choisissez le canal par lequel le retour a été reçu."})
        dossier, code = recevoir(donnees, canal, saisi_par=request.user, fichiers=fichiers)
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
    def plaignant(self, request, pk=None):
        return self._agir(traitement.modifier_plaignant, request.data)

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

    @action(detail=True, methods=["get"], url_path="apercu-message")
    def apercu_message(self, request, pk=None):
        """Message prérempli d'après le modèle (?objet=&canal=), à relire avant l'envoi."""
        from . import messages

        # Sans les filtres de la liste : « canal » désigne ici le moyen d'envoi, pas le canal de réception.
        dossier = get_object_or_404(self.get_queryset(), pk=pk)
        canal = request.query_params.get("canal", messages.SMS)
        sujet, texte, langue = messages.rediger(dossier, request.query_params.get("objet", ""), canal)
        return Response({"sujet": sujet, "texte": texte, "langue": langue,
                         "sms_simule": not getattr(settings, "PLAINTES_SMS_URL", ""),
                         "nombre_sms": -(-len(texte) // 160) if canal == messages.SMS else None})

    @action(detail=True, methods=["post"], url_path="envoyer-message")
    def envoyer_message(self, request, pk=None):
        from . import messages

        return self._agir(messages.envoyer, request.data)

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
        auditer(request.user, A.EXPORT, "Liste des dossiers", nombre=nombre, coordonnees=avec_coordonnees)
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
    def effacer(self, request, pk=None):
        """Effacement définitif (droit à l'effacement) : le dossier n'existe plus après."""
        numero = confidentiel.effacer(self.get_object(), request.user, request.data)
        return Response({"numero": numero, "efface": True})

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
    def pieces(self, request, pk=None):
        """Ajout de pièces jointes par l'équipe (multipart, champ « fichiers »)."""
        from . import pieces

        return self._agir(pieces.ajouter, request.FILES.getlist("fichiers"))

    @action(detail=True, methods=["post"], url_path="retirer-piece")
    def retirer_piece(self, request, pk=None):
        from . import pieces

        return self._agir(pieces.retirer, request.data)

    @action(detail=True, methods=["get"], url_path=r"pieces/(?P<piece_id>\d+)/lien")
    def lien_piece(self, request, pk=None, piece_id=None):
        """Lien de téléchargement valable quelques minutes, délivré après contrôle d'accès au dossier."""
        from . import pieces

        piece = get_object_or_404(self.get_object().pieces, pk=piece_id)
        from apps.organisations.contexte import parametre_org

        org = parametre_org()
        return Response({"url": request.build_absolute_uri(f"/api/v1/plaintes-piece/{pieces.lien(piece, request.user)}/"
                                                           + (f"?{org}" if org else "")),
                         "duree_minutes": pieces.duree_lien_minutes()})

    @action(detail=True, methods=["post"])
    def lier(self, request, pk=None):
        """{numero, delier?} : lie (ou délie) un autre dossier visible."""
        autre = dossiers_visibles(request.user).filter(numero__iexact=(request.data.get("numero") or "").strip()).first()
        if autre is None:
            raise ValidationError({"numero": v("Aucun dossier accessible ne porte ce numéro.")})
        return self._agir(traitement.lier, autre, bool(request.data.get("delier")))

    @action(detail=False, methods=["get"])
    def compteurs(self, request):
        """Nombre de dossiers de chaque vue prête (colonne des vues de la liste), sans les autres filtres."""
        visibles = dossiers_visibles(request.user)
        return Response({"tous": visibles.count(), **{cle: vue(visibles, request.user).count() for cle, vue in VUES.items()}})

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


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def telecharger_piece(request, jeton):
    """
    Téléchargement par lien temporaire signé : l'accès de la personne qui a demandé le lien est
    vérifié de nouveau ; le téléchargement est inscrit au journal du dossier. Jamais mis en cache.
    """
    from urllib.parse import quote

    from . import pieces
    from .models import ActionDossier

    piece, utilisateur = pieces.piece_du_lien(jeton)
    if piece is None:
        return Response({"detail": v("Lien expiré ou non autorisé. Rouvrez la fiche du dossier pour en obtenir un nouveau.")},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        contenu = pieces.lire(piece)
    except Exception:  # fichier absent ou clé changée : rien n'est divulgué
        return Response({"detail": v("Ce fichier n'est plus lisible.")}, status=status.HTTP_410_GONE)
    ActionDossier.objects.create(dossier=piece.dossier, type=ActionDossier.Type.TELECHARGEMENT, auteur=utilisateur,
                                 texte=piece.nom, details={"piece": piece.pk})
    reponse = HttpResponse(contenu, content_type=piece.type_mime)
    reponse["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(piece.nom)}"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Cache-Control"] = "no-store"
    return reponse


class HabilitationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Habilitations confidentielles (habilitations.py) : liste et gestion réservées à l'Administrateur et
    aux personnes habilitées. POST = demande ; …/valider/, …/confirmer/ (code reçu par courriel),
    …/retirer/. « actives/ » : personnes habilitées (choix des responsables d'étapes confidentielles).
    """

    permission_classes = (HasGlobalVisibilityOrAssigned,)
    serializer_class = HabilitationSerializer
    pagination_class = None

    def get_queryset(self):
        from . import habilitations

        if self.action != "actives" and not habilitations.est_habilite(self.request.user):
            raise PermissionDenied(v("Seuls l'Administrateur et les personnes habilitées gèrent les habilitations confidentielles."))
        return HabilitationSensible.objects.select_related("utilisateur", "demandee_par", "validee_par", "retiree_par")

    def _rendre(self, habilitation):
        return Response(HabilitationSerializer(habilitation, context=self.get_serializer_context()).data)

    def create(self, request, *args, **kwargs):
        from . import habilitations

        return self._rendre(habilitations.demander(request.user, request.data))

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        from . import habilitations

        return self._rendre(habilitations.valider(request.user, pk, request.data))

    @action(detail=True, methods=["post"])
    def confirmer(self, request, pk=None):
        from . import habilitations

        return self._rendre(habilitations.confirmer(request.user, pk, request.data))

    @action(detail=True, methods=["post"])
    def retirer(self, request, pk=None):
        from . import habilitations

        return self._rendre(habilitations.retirer(request.user, pk, request.data))

    @action(detail=False, methods=["get"])
    def actives(self, request):
        from . import habilitations

        return Response(sorted(habilitations.ids_habilites()))


class DemandeDroitsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Demandes des personnes sur leurs données (droits.py), réservées à l'Administrateur : POST = nouvelle
    demande ; …/traiter/ ; registre/ = registre des traitements (Excel), tracé au journal d'audit.
    """

    serializer_class = DemandeDroitsSerializer
    pagination_class = None

    def get_permissions(self):
        from apps.core.permissions import IsAdmin

        return [IsAdmin()]

    def get_queryset(self):
        return DemandeDroits.objects.select_related("traitee_par")

    def create(self, request, *args, **kwargs):
        from . import droits

        return Response(DemandeDroitsSerializer(droits.enregistrer(request.user, request.data)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def traiter(self, request, pk=None):
        from . import droits

        return Response(DemandeDroitsSerializer(droits.traiter(request.user, self.get_object(), request.data)).data)

    @action(detail=False, methods=["get"])
    @dans_la_langue_demandee
    def registre(self, request):
        from . import droits

        reponse = HttpResponse(droits.registre_excel(), content_type=XLSX)
        reponse["Content-Disposition"] = "attachment; filename=registre_des_traitements.xlsx"
        auditer(request.user, A.EXPORT, "Registre des traitements")
        return reponse


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
    from apps.organisations.contexte import parametre_org

    # Adresse unique de la plateforme : le lien dit de quelle organisation est le formulaire (?org=).
    parametres = [parametre_org()] if parametre_org() else []
    projet = request.query_params.get("projet", "")
    if projet.isdigit():
        parametres.append(f"projet={projet}")
    lien = origine.rstrip("/") + "/plainte" + ("?" + "&".join(parametres) if parametres else "")
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
    auditer(request.user, A.EXPORT, f"Tableau de bord « {vue} »", format=format_)
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
    audite = False  # suivi opérationnel, pas du paramétrage : tracé au journal de chaque dossier lié

    def get_queryset(self):
        return ActionCorrective.objects.select_related("projet", "responsable").prefetch_related("dossiers")

    def _journaliser(self, action, ajoutes):
        from .models import ActionDossier

        for d in ajoutes:  # un par un : chaque entrée est aussi reportée au journal d'audit
            ActionDossier.objects.create(dossier=d, type=ActionDossier.Type.ACTION_CORRECTIVE, auteur=self.request.user,
                                         texte=v("Action corrective liée : ") + action.titre)

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
