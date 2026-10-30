import threading

from django.db.models import F, Min
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.constants import ROLE_CHARGE_SE
from apps.core.langues import dans_la_langue_demandee
from apps.core.permissions import HasGlobalVisibilityOrAssigned, IsAdminOrReadOnly, peut_modifier
from apps.core.vocabulaire import v
from apps.notifications.models import Notification
from apps.notifications.services import notifier_par_role

from .models import (
    Beneficiaire,
    ParticipationProjet,
    SignalementDoublon,
    StatutParticulier,
    TypeActiviteBeneficiaire,
    VariableBeneficiaire,
)
from .serializers import (
    BeneficiaireSerializer,
    ParticipationProjetSerializer,
    SignalementDoublonSerializer,
    StatutParticulierSerializer,
    TypeActiviteBeneficiaireSerializer,
    VariableBeneficiaireSerializer,
)
from .services.carte import cartes_pdf, qr_svg
from .services.deletion import supprimer_beneficiaire_cascade
from .services.duplicate_detection import enregistrer_signalements, reverifier_signalements
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
    # Cartes imprimables : gourmandes (surtout en A0), deux à la fois au plus.
    _GENERATIONS = threading.BoundedSemaphore(2)
    queryset = Beneficiaire.objects.select_related("zone").prefetch_related(
        "statuts_particuliers", "participations__projet"
    )
    serializer_class = BeneficiaireSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("sexe", "zone", "statuts_particuliers")
    # Code et nom du projet inclus : taper « PRAN » ou « eau potable » retrouve
    # les bénéficiaires inscrits à ce projet.
    search_fields = (
        "identifiant",
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
        from apps.geo.services.synthese import ids_parametre

        projets = ids_parametre(self.request.query_params, "projet")
        if projets:
            return queryset.filter(participations__projet__in=projets).distinct()
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
    @dans_la_langue_demandee
    def modele_import(self, request):
        # Colonnes de localisation aux niveaux administratifs du pays choisi (?pays=BF par défaut).
        # Avec ?projet= : variables personnalisées de ce projet seulement.
        from apps.projects.models import Projet

        projet = Projet.objects.filter(id=request.query_params.get("projet") or 0).first()
        contenu = generer_modele_import((request.query_params.get("pays") or "BF").upper()[:2], projet=projet)
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=modele_import_beneficiaires.xlsx"
        return response

    @action(detail=False, methods=["get"], url_path="exporter")
    @dans_la_langue_demandee
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

    def _origine(self):
        """Adresse de la plateforme vue par l'utilisateur (pour le lien du QR code)."""
        origine = self.request.query_params.get("origine", "")
        if not origine.startswith(("http://", "https://")):
            origine = self.request.headers.get("Origin") or self.request.build_absolute_uri("/")
        return origine

    @action(detail=True, methods=["get"])
    def qr(self, request, pk=None):
        """QR code (SVG) de la fiche du bénéficiaire."""
        return HttpResponse(qr_svg(self.get_object(), self._origine(), echelle=6), content_type="image/svg+xml")

    @action(detail=False, methods=["get"])
    @dans_la_langue_demandee
    def cartes(self, request):
        """Cartes à imprimer (PDF) : `?ids=1,2,3`, ou `?projet=` pour tous les inscrits d'un projet."""
        queryset = self.get_queryset()
        ids = [i for i in request.query_params.get("ids", "").split(",") if i.isdigit()]
        if ids:
            queryset = queryset.filter(id__in=ids)
        elif not request.query_params.get("projet"):
            raise ValidationError({"ids": v("Choisir les bénéficiaires ou un projet.")})
        beneficiaires = list(queryset.select_related("zone__parent__parent").prefetch_related("participations__projet").order_by("nom", "prenom"))
        reponse = HttpResponse(cartes_pdf(beneficiaires, self._origine()), content_type="application/pdf")
        reponse["Content-Disposition"] = 'attachment; filename="cartes_beneficiaires.pdf"'
        return reponse

    def _zones_filtre(self):
        """Zones choisies (?zone=1,2…), dans l'ordre demandé ; liste vide sans filtre."""
        from apps.geo.models import Zone
        from apps.geo.services.synthese import ids_parametre

        ids = ids_parametre(self.request.query_params, "zone")
        zones = {z.id: z for z in Zone.objects.select_related("niveau_administratif").filter(id__in=ids)}
        if len(zones) != len(set(ids)):
            raise NotFound("Zone inconnue.")
        return [zones[i] for i in dict.fromkeys(ids)]

    def _carte_selon_filtres(self):
        """
        Filtres du tableau de bord appliqués à la carte (?statuts=, ?annee= ou ?date_debut=&date_fin=,
        ?periode=) : projets retenus parmi les visibles, et bénéficiaires inscrits à l'un d'eux
        (tous les bénéficiaires visibles sans filtre).
        """
        from apps.dashboard.filtres import filtres_actifs, projets_retenus
        from apps.projects.queryset_filters import visible_projets_ids

        retenus = projets_retenus(visible_projets_ids(self.request.user), self.request.query_params)
        beneficiaires = self.get_queryset()
        if filtres_actifs(self.request.query_params):
            beneficiaires = beneficiaires.filter(participations__projet__in=retenus).distinct()
        return retenus, beneficiaires

    @action(detail=False, methods=["get"])
    def carte(self, request):
        """
        Carte des bénéficiaires (?projet= pour un ou plusieurs projets, ?zone= pour une ou plusieurs
        régions, provinces… ; plusieurs valeurs séparées par des virgules ; filtres du tableau de bord
        ?statuts=, ?annee= ou ?date_debut=&date_fin=, ?periode=) :
        ceux qui ont une position GPS (points), les autres regroupés au centre de leur localité
        ou, à défaut, de la zone parente placée la plus proche ; plus le nombre sans localisation.
        """
        from apps.dashboard.filtres import filtres_actifs

        from .services.carte_donnees import donnees_carte, projets_des_zones

        zones = self._zones_filtre()
        retenus, beneficiaires = self._carte_selon_filtres()
        donnees = donnees_carte(beneficiaires, zones)
        # Projets présents dans les zones (indépendamment du filtre projet), pour filtrer la liste.
        donnees["projets_zone"] = projets_des_zones(zones, retenus) if zones else None
        # Projets retenus par les filtres du tableau de bord (None sans filtre), pour la liste.
        donnees["projets_retenus"] = retenus if filtres_actifs(request.query_params) else None
        return Response(donnees)

    @action(detail=False, methods=["get"], url_path="carte/export")
    @dans_la_langue_demandee
    def carte_export(self, request):
        """
        Carte imprimable (modèle des cartes officielles HIMO) : mêmes filtres que la carte
        (?projet=, ?zone=, filtres du tableau de bord), plus sortie=pdf|png, papier=A0|A1|A3|A4,
        orientation=auto|portrait|paysage, fond=neutre|osm|satellite|aucun,
        etendue=pays|beneficiaires (sans zone choisie : tout le pays, ou autour des bénéficiaires),
        titre= et sous_titre= (sinon déduits du contenu de la carte),
        couches=regions,provinces,communes,routes,villages,noms,beneficiaires (noms des bénéficiaires)
        importees=1,2 (couches importées), et par_zone=<indicateur(s) du catalogue, séparés par des
        virgules, voir apps.geo.services.synthese> avec niveau_zone=1|2|3 : régions, provinces ou
        communes coloriées selon le premier, tous écrits sur chaque zone et dans le tableau.
        """
        from apps.geo.models import CoucheImportee
        from apps.projects.models import Projet

        from .services.carte_donnees import donnees_carte
        from .services.carte_officielle import COUCHES, FONDS, PAPIERS, rendre_carte

        p = request.query_params
        sortie, papier, orientation = p.get("sortie", "pdf"), p.get("papier", "A3").upper(), p.get("orientation", "auto")
        fond = p.get("fond", "aucun")
        etendue = p.get("etendue", "pays")
        if sortie not in ("pdf", "png") or papier not in PAPIERS or orientation not in ("auto", "portrait", "paysage") or fond not in FONDS:
            raise ValidationError({"detail": "Paramètres invalides (sortie, papier, orientation ou fond)."})
        couches = {c: True for c in p.get("couches", "points,regions,provinces,routes,noms").split(",") if c in COUCHES}
        ids = [i for i in p.get("importees", "").split(",") if i.isdigit()]
        couches["importees"] = list(CoucheImportee.objects.filter(id__in=ids))
        from apps.geo.services.synthese import COURTS, INDICATEURS, ids_parametre, synthese_par_zone

        zones = self._zones_filtre()
        retenus, beneficiaires = self._carte_selon_filtres()
        donnees = donnees_carte(beneficiaires, zones)
        projets = list(Projet.objects.filter(id__in=ids_parametre(p, "projet")).filter(id__in=retenus).order_by("code"))
        projet = projets[0] if len(projets) == 1 else None
        portee = ", ".join(z.nom for z in zones)
        if projet:
            donnees["projet"], donnees["projet_nom"] = projet.code, projet.nom
        elif projets:
            donnees["projet_nom"] = ", ".join(x.code for x in projets)
        par_zone = None
        indicateurs = [i for i in p.get("par_zone", "").split(",") if i]
        if indicateurs:
            if any(i not in INDICATEURS for i in indicateurs):
                raise ValidationError({"detail": "Indicateur par zone inconnu."})
            synthese = synthese_par_zone(donnees["pays"], int(p.get("niveau_zone") or 1), retenus,
                                         projets=[x.id for x in projets], dans_zones=zones)
            if synthese["niveau"]:
                # Zones coloriées selon le premier indicateur ; tous sont écrits sur la carte et dans le tableau.
                par_zone = {"indicateur": indicateurs[0], "indicateurs": indicateurs, "libelle_court": COURTS[indicateurs[0]],
                            "entete": COURTS[indicateurs[0]], "synthese": synthese}

        verrou = BeneficiaireViewSet._GENERATIONS
        if not verrou.acquire(timeout=5):
            return Response({"detail": "Des cartes sont en cours de génération, réessayez dans une minute."}, status=503)
        try:
            contenu = rendre_carte(donnees, couches, papier=papier, orientation=orientation, sortie=sortie, titre_portee=portee, fond=fond,
                                   par_zone=par_zone, etendue=etendue,
                                   titre=(p.get("titre") or "").strip()[:120], sous_titre=(p.get("sous_titre") or "").strip()[:200])
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})
        finally:
            verrou.release()
        if p.get("titre"):
            sujet = "carte_" + p["titre"].strip()[:60]
        elif par_zone:
            sujet = f"carte_{par_zone['indicateur']}_par_{par_zone['synthese']['niveau']['nom'].lower()}"
        else:
            sujet = "carte"
        nom = "_".join(x for x in [sujet, projet.code if projet else "", "_".join(z.nom for z in zones[:3]), papier] if x)
        nom = "".join(c if c.isalnum() or c in "-_" else "_" for c in nom)
        reponse = HttpResponse(contenu, content_type="image/png" if sortie == "png" else "application/pdf")
        reponse["Content-Disposition"] = f'attachment; filename="{nom}.{sortie}"'
        return reponse

    @action(detail=False, methods=["get"], url_path=r"identifiant/(?P<identifiant>[\w-]+)")
    def par_identifiant(self, request, identifiant=None):
        """Retrouve un bénéficiaire par son identifiant (lien du QR code)."""
        beneficiaire = self.get_queryset().filter(identifiant__iexact=identifiant).first()
        if beneficiaire is None:
            raise NotFound(v("Aucun bénéficiaire avec cet identifiant (ou vous n'y avez pas accès)."))
        return Response({"id": beneficiaire.id})

    @action(detail=True, methods=["post"], url_path="verifier-doublons")
    def verifier_doublons(self, request, pk=None):
        beneficiaire = self.get_object()

        signalements = []
        for signalement, cree in enregistrer_signalements(beneficiaire):
            b1, b2 = signalement.beneficiaire_1, signalement.beneficiaire_2
            signalements.append(signalement)
            if cree:
                notifier_par_role(
                    [ROLE_CHARGE_SE],
                    Notification.Type.DOUBLON_SIGNALE,
                    f"{v('Doublon bénéficiaire potentiel : ')}{b1} / {b2}",
                    message=f"Motifs : {', '.join(signalement.motifs)}.",
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

    @action(detail=False, methods=["post"])
    def reverifier(self, request):
        """Repasse les signalements en attente avec les règles actuelles (retire les faux positifs)."""
        if not peut_modifier(request.user):
            raise PermissionDenied()
        return Response(reverifier_signalements())


class VariableBeneficiaireViewSet(viewsets.ModelViewSet):
    """Variables personnalisées à collecter sur les bénéficiaires (paramétrées par l'Administrateur)."""

    queryset = VariableBeneficiaire.objects.prefetch_related("projets")
    serializer_class = VariableBeneficiaireSerializer
    permission_classes = (IsAdminOrReadOnly,)
    pagination_class = None

    @action(detail=False, methods=["get"], url_path="choix-projets")
    def choix_projets(self, request):
        """Projets proposés pour une variable (liste complète et légère)."""
        from apps.projects.models import Projet
        from apps.projects.queryset_filters import visible_projets_ids

        projets = Projet.objects.filter(id__in=visible_projets_ids(request.user)).order_by("code")
        return Response([{"value": str(p.id), "label": f"{p.code} — {p.nom}"} for p in projets])

    def perform_destroy(self, instance):
        # Les réponses déjà saisies à cette variable sont retirées des fiches.
        cle = str(instance.id)
        for b in Beneficiaire.objects.filter(reponses__has_key=cle):
            b.reponses.pop(cle, None)
            Beneficiaire.objects.filter(pk=b.pk).update(reponses=b.reponses)
        instance.delete()
