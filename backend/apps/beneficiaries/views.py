from django.db.models import F, Min
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.constants import ROLE_CHARGE_SE
from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.core.vocabulaire import v
from apps.notifications.models import Notification
from apps.notifications.services import notifier_par_role

from .models import Beneficiaire, ParticipationProjet, SignalementDoublon, StatutParticulier, TypeActiviteBeneficiaire
from .serializers import (
    BeneficiaireSerializer,
    ParticipationProjetSerializer,
    SignalementDoublonSerializer,
    StatutParticulierSerializer,
    TypeActiviteBeneficiaireSerializer,
)
from .services.deletion import supprimer_beneficiaire_cascade
from .services.duplicate_detection import rechercher_doublons
from .services.export_excel import exporter_beneficiaires, exporter_beneficiaires_pdf
from .services.import_excel import generer_modele_import, importer_beneficiaires


class StatutParticulierViewSet(viewsets.ModelViewSet):
    queryset = StatutParticulier.objects.all()
    serializer_class = StatutParticulierSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)


class TypeActiviteBeneficiaireViewSet(viewsets.ModelViewSet):
    queryset = TypeActiviteBeneficiaire.objects.all()
    serializer_class = TypeActiviteBeneficiaireSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)


class BeneficiaireViewSet(viewsets.ModelViewSet):
    queryset = Beneficiaire.objects.select_related("zone").prefetch_related(
        "statuts_particuliers", "participations__projet"
    )
    serializer_class = BeneficiaireSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("sexe", "zone", "statuts_particuliers")
    # Code et nom du projet inclus : taper « PRAN » ou « eau potable » retrouve
    # les bénéficiaires inscrits à ce projet.
    search_fields = (
        "nom",
        "prenom",
        "telephone",
        "numero_piece_identite",
        "participations__projet__code",
        "participations__projet__nom",
    )

    def get_queryset(self):
        queryset = super().get_queryset()

        # Affichage groupé projet par projet (écran Bénéficiaires) : une
        # requête par groupe, filtrée sur un projet ou sur « sans projet ».
        projet = self.request.query_params.get("projet")
        if projet:
            return queryset.filter(participations__projet=projet).distinct()
        if self.request.query_params.get("sans_projet") in ("1", "true"):
            return queryset.filter(participations__isnull=True)

        # Sans filtre : classement par projet d'abord (code du premier projet
        # par ordre alphabétique pour un bénéficiaire inscrit à plusieurs
        # projets ; sans projet en fin de liste), puis par nom/prénom.
        return queryset.annotate(premier_projet=Min("participations__projet__code")).order_by(
            F("premier_projet").asc(nulls_last=True), "nom", "prenom"
        )

    def perform_destroy(self, instance):
        supprimer_beneficiaire_cascade(instance)

    @action(detail=False, methods=["get"], url_path="modele-import")
    def modele_import(self, request):
        contenu = generer_modele_import()
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=modele_import_beneficiaires.xlsx"
        return response

    @action(detail=False, methods=["get"], url_path="exporter")
    def exporter(self, request):
        """
        Export Excel ou PDF (?fichier=excel|pdf — « format » est réservé par DRF) : ?projets=1,3 pour un ou
        plusieurs projets, sinon tous les bénéficiaires (une feuille/section
        par projet, plus « Sans projet »).
        """
        from apps.projects.models import Projet
        from apps.projects.queryset_filters import visible_projets_ids

        projets_visibles = Projet.objects.filter(id__in=visible_projets_ids(request.user)).order_by("code")
        ids = [i for i in request.query_params.get("projets", "").split(",") if i.strip().isdigit()]
        queryset = self.filter_queryset(self.get_queryset())
        if ids:
            projets = list(projets_visibles.filter(id__in=ids))
            if len(projets) != len(set(ids)):
                raise ValidationError({"projets": v('Projet introuvable ou non accessible.')})
            queryset = queryset.filter(participations__projet__in=projets).distinct()
            nom = "beneficiaires_" + "_".join(p.code for p in projets)
            tous = False
        else:
            projets, nom, tous = list(projets_visibles), "beneficiaires_tous_projets", True

        if request.query_params.get("fichier") == "pdf":
            contenu = exporter_beneficiaires_pdf(queryset, projets, inclure_sans_projet=tous)
            response = HttpResponse(contenu, content_type="application/pdf")
            response["Content-Disposition"] = f"attachment; filename={nom}.pdf"
            return response
        response = HttpResponse(
            exporter_beneficiaires(queryset, projets, inclure_sans_projet=tous),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={nom}.xlsx"
        return response

    @action(
        detail=False,
        methods=["post"],
        url_path="importer",
        parser_classes=[MultiPartParser, FormParser],
    )
    def importer(self, request):
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})

        # Projet facultatif (import depuis la fiche projet) : chaque bénéficiaire
        # importé y est alors inscrit, sauf si sa ligne indique un autre Code projet.
        projet = None
        projet_id = request.data.get("projet")
        if projet_id:
            from apps.projects.models import Projet
            from apps.projects.queryset_filters import visible_projets_ids

            projet = Projet.objects.filter(id=projet_id, id__in=visible_projets_ids(request.user)).first()
            if projet is None:
                raise ValidationError({"projet": v('Projet introuvable ou non accessible.')})

        try:
            resultat = importer_beneficiaires(fichier, request.user, projet=projet)
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
        return Response(resultat)

    @action(detail=True, methods=["post"], url_path="verifier-doublons")
    def verifier_doublons(self, request, pk=None):
        beneficiaire = self.get_object()
        candidats = rechercher_doublons(beneficiaire)

        signalements = []
        for item in candidats:
            b1, b2 = sorted([beneficiaire, item["candidat"]], key=lambda b: b.pk)
            signalement, cree = SignalementDoublon.objects.get_or_create(
                beneficiaire_1=b1,
                beneficiaire_2=b2,
                defaults={"score": item["score"], "methode": item["methode"]},
            )
            signalements.append(signalement)
            if cree:
                notifier_par_role(
                    [ROLE_CHARGE_SE],
                    Notification.Type.DOUBLON_SIGNALE,
                    f"{v('Doublon bénéficiaire potentiel : ')}{b1} / {b2}",
                    message=f"Détecté via {signalement.get_methode_display()} (score {signalement.score}).",
                    lien="/doublons",
                )

        serializer = SignalementDoublonSerializer(signalements, many=True)
        return Response(serializer.data)


class ParticipationProjetViewSet(viewsets.ModelViewSet):
    serializer_class = ParticipationProjetSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("beneficiaire", "projet", "activite", "sous_activite")

    def get_queryset(self):
        from apps.projects.queryset_filters import visible_projets_ids

        return ParticipationProjet.objects.filter(projet__id__in=visible_projets_ids(self.request.user))


class SignalementDoublonViewSet(viewsets.ModelViewSet):
    queryset = SignalementDoublon.objects.select_related("beneficiaire_1", "beneficiaire_2")
    serializer_class = SignalementDoublonSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("statut", "methode")

    def perform_update(self, serializer):
        instance = serializer.instance
        nouveau_statut = serializer.validated_data.get("statut", instance.statut)
        if nouveau_statut != SignalementDoublon.Statut.SIGNALE and instance.statut == SignalementDoublon.Statut.SIGNALE:
            serializer.save(traite_par=self.request.user, date_traitement=timezone.now())
        else:
            serializer.save()
