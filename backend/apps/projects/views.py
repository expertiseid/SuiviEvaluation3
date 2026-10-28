from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.constants import ROLE_ADMIN, ROLES_NOTIFIEES_MODIFICATION_ACTIVITE
from apps.core.models import EtatApprobation
from apps.core.permissions import (
    HasGlobalVisibilityOrAssigned,
    IsAdminOrCreateForAuthenticated,
    IsAdminOrReadOnly,
    SuppressionAtomiqueMixin,
    peut_approuver,
)
from apps.indicators.exports import generer_xlsform
from apps.notifications.models import Notification
from apps.notifications.services import notifier, notifier_par_role

from .approbation import LIBELLES_CHAMPS, creer_demande, exige_demande, traiter_demande, traiter_saisie
from .coherence import controler_projet
from .import_excel import generer_modele_import_projet, importer_projet
from .models import (
    Activite,
    DemandeModification,
    Equipe,
    FenetreRapportage,
    JalonLivrable,
    NiveauActivite,
    ParametresCalcul,
    ParametresRapportage,
    PartenaireProjet,
    Projet,
    SousActivite,
    TauxManuel,
)
from .queryset_filters import visible_projets_ids
from .serializers import (
    ActiviteSerializer,
    EquipeSerializer,
    FenetreRapportageSerializer,
    JalonLivrableSerializer,
    NiveauActiviteSerializer,
    ParametresCalculSerializer,
    ParametresRapportageSerializer,
    ProjetSerializer,
    ProjetWriteSerializer,
    SousActiviteSerializer,
    TauxManuelSerializer,
    PartenaireProjetSerializer,
)
from .services import (
    dupliquer_activite,
    supprimer_activite_cascade,
    supprimer_projet_cascade,
    supprimer_sous_activite_cascade,
    synchroniser_projets_associes_activite,
    synchroniser_projets_associes_equipe,
)


class EquipeViewSet(viewsets.ModelViewSet):
    queryset = Equipe.objects.all()
    serializer_class = EquipeSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    search_fields = ("nom",)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        synchroniser_projets_associes_equipe(serializer.instance)


class ProjetViewSet(viewsets.ModelViewSet):
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("statut", "partenaire_bailleur", "partenaire_mise_en_oeuvre")
    search_fields = ("nom", "code")

    def get_queryset(self):
        return (
            Projet.objects.select_related(
                "partenaire_bailleur", "partenaire_mise_en_oeuvre", "element_strategique__type_niveau"
            )
            .filter(id__in=visible_projets_ids(self.request.user))
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProjetWriteSerializer
        return ProjetSerializer

    def perform_update(self, serializer):
        # Rouvrir un projet clôturé (lecture seule, voir verrou.py) est réservé à l'administrateur.
        if self.request.user.role != ROLE_ADMIN:
            if serializer.instance.statut == Projet.Statut.CLOTURE:
                raise PermissionDenied("Seul un administrateur peut rouvrir un projet clôturé.")
            # Ouverture de la saisie (périodes de rapportage) et approbations : réglées par l'administrateur.
            for champ in ("saisie", "perimetre_fermeture", "approbation_realisations", "approbation_planification"):
                if champ in serializer.validated_data and serializer.validated_data[champ] != getattr(serializer.instance, champ):
                    raise PermissionDenied("Seul un administrateur peut régler l'ouverture de la saisie et les approbations du projet.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        supprimer_projet_cascade(instance)

    @action(detail=True, methods=["get"])
    def coherence(self, request, pk=None):
        """Contrôle de cohérence du projet : incohérences repérées, des plus graves aux moins graves."""
        return Response(controler_projet(self.get_object()))

    @action(detail=True, methods=["get"], url_path="export/xlsform")
    def export_xlsform(self, request, pk=None):
        projet = self.get_object()
        contenu = generer_xlsform(projet)
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f"attachment; filename=xlsform_{projet.code}.xlsx"
        return response

    @action(detail=False, methods=["get"], url_path="modele-import")
    def modele_import(self, request):
        contenu = generer_modele_import_projet()
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=modele_import_projet.xlsx"
        return response

    @action(detail=False, methods=["post"], url_path="importer", parser_classes=[MultiPartParser, FormParser])
    def importer(self, request):
        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
        try:
            resultat = importer_projet(fichier)
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
        return Response(resultat)


def _donnees_requete(request):
    donnees = request.data
    return donnees.dict() if hasattr(donnees, "dict") else dict(donnees)


class DemandeApprobationMixin:
    """
    Projets avec approbation de la planification (voir apps.projects.approbation) : pour qui
    ne peut pas approuver, un ajout, une modification ou une suppression devient une demande
    (réponse 202 avec un message), appliquée une fois approuvée. Les données sont validées
    tout de suite, pour ne pas laisser passer une demande impossible à appliquer.
    """

    cible_demande = None

    def _projet_de(self, instance=None, validated=None):
        if instance is not None:
            return instance.projet if isinstance(instance, Activite) else instance.activite.projet
        if "projet" in validated:
            return validated["projet"]
        return validated["activite"].projet

    def _demande(self, projet, action, instance=None, donnees=None):
        demande = creer_demande(
            projet=projet, cible=self.cible_demande, action=action, utilisateur=self.request.user,
            instance=instance, donnees=donnees,
        )
        return Response(
            {
                "demande_approbation": demande.id,
                "message": f"{demande.get_action_display()} envoyée pour approbation : elle sera appliquée une fois approuvée.",
            },
            status=202,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        projet = self._projet_de(validated=serializer.validated_data)
        if exige_demande(projet, request.user):
            return self._demande(projet, DemandeModification.Action.CREATION, donnees=_donnees_requete(request))
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        projet = self._projet_de(instance)
        if exige_demande(projet, request.user):
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
            serializer.is_valid(raise_exception=True)
            return self._demande(projet, DemandeModification.Action.MODIFICATION, instance, _donnees_requete(request))
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        projet = self._projet_de(instance)
        if exige_demande(projet, request.user):
            return self._demande(projet, DemandeModification.Action.SUPPRESSION, instance)
        return super().destroy(request, *args, **kwargs)


class ActiviteViewSet(DemandeApprobationMixin, viewsets.ModelViewSet):
    cible_demande = DemandeModification.Cible.ACTIVITE
    serializer_class = ActiviteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet", "activite_parent", "responsable")

    CHAMPS_SURVEILLES = ("date_debut", "date_fin", "budget_alloue", "quantite_prevue", "statut")

    def get_queryset(self):
        return Activite.objects.filter(projet__id__in=visible_projets_ids(self.request.user))

    def perform_destroy(self, instance):
        supprimer_activite_cascade(instance)

    @action(detail=False, methods=["get"], url_path="pour-projet")
    def pour_projet(self, request):
        """
        Liste allégée (id, libellé), non paginée, des éléments d'un projet (tous niveaux) —
        alimente le sélecteur de grille d'alerte par activité (potentiellement
        des centaines d'activités, une pagination classique serait inutile ici).
        """
        projet_id = request.query_params.get("projet")
        ids = visible_projets_ids(self.request.user)
        if not projet_id or int(projet_id) not in ids:
            return Response([])
        activites = self.get_queryset().filter(projet__id=projet_id).order_by("libelle")
        return Response([{"id": a.id, "libelle": a.libelle} for a in activites])

    @action(detail=True, methods=["post"])
    def dupliquer(self, request, pk=None):
        """Copie l'élément et tout ce qui est en dessous, sans les réalisations (voir services)."""
        activite = self.get_object()
        if exige_demande(activite.projet, request.user):
            raise PermissionDenied("Ce projet exige une approbation des changements : la duplication est réservée aux approbateurs.")
        copie = dupliquer_activite(activite)
        return Response(self.get_serializer(copie).data, status=201)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        synchroniser_projets_associes_activite(serializer.instance)

    def perform_update(self, serializer):
        instance = serializer.instance
        anciennes_valeurs = {champ: getattr(instance, champ) for champ in self.CHAMPS_SURVEILLES}
        deja_planifiee = anciennes_valeurs["date_debut"] is not None or anciennes_valeurs["date_fin"] is not None

        super().perform_update(serializer)
        synchroniser_projets_associes_activite(serializer.instance)

        activite = serializer.instance
        changements = [
            champ for champ in self.CHAMPS_SURVEILLES if anciennes_valeurs[champ] != getattr(activite, champ)
        ]
        if changements and deja_planifiee:
            projet = activite.projet
            titre = f"Activité modifiée : {activite.libelle}"
            message = f"Projet {projet.nom} — champ(s) modifié(s) : {', '.join(changements)}."
            lien = f"/projets/{projet.id}"
            if projet.utilisateurs_affectes.exists():
                notifier(list(projet.utilisateurs_affectes.all()), Notification.Type.ACTIVITE_MODIFIEE, titre, message, lien)
            notifier_par_role(
                ROLES_NOTIFIEES_MODIFICATION_ACTIVITE,
                Notification.Type.ACTIVITE_MODIFIEE,
                titre,
                message,
                lien,
                exclure=self.request.user,
            )


class NiveauActiviteViewSet(viewsets.ModelViewSet):
    serializer_class = NiveauActiviteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet",)

    def get_queryset(self):
        return NiveauActivite.objects.filter(projet__id__in=visible_projets_ids(self.request.user))


class SousActiviteViewSet(DemandeApprobationMixin, viewsets.ModelViewSet):
    cible_demande = DemandeModification.Cible.SOUS_ACTIVITE
    serializer_class = SousActiviteSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite", "statut")

    def get_queryset(self):
        return SousActivite.objects.filter(activite__projet__id__in=visible_projets_ids(self.request.user))

    def perform_destroy(self, instance):
        supprimer_sous_activite_cascade(instance)


class PartenaireProjetViewSet(SuppressionAtomiqueMixin, viewsets.ModelViewSet):
    """
    Rôle de chaque partenaire dans un projet et éléments qu'il réalise. Ajouter un partenaire ici
    l'ajoute aussi au projet (consortium, ou mise en œuvre si le projet n'en a pas encore).
    """

    serializer_class = PartenaireProjetSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet", "partenaire")

    def get_queryset(self):
        return PartenaireProjet.objects.filter(projet__id__in=visible_projets_ids(self.request.user)).select_related(
            "partenaire"
        ).prefetch_related("elements")

    def perform_create(self, serializer):
        role = serializer.save()
        projet = role.projet
        if role.nature == PartenaireProjet.Nature.MISE_EN_OEUVRE:
            if projet.partenaire_mise_en_oeuvre_id is None:
                projet.partenaire_mise_en_oeuvre = role.partenaire
                projet.save(update_fields=["partenaire_mise_en_oeuvre"])
        else:
            projet.partenaires_consortium.add(role.partenaire)


class JalonLivrableViewSet(viewsets.ModelViewSet):
    """Jalons et livrables d'un élément (méthodes « jalons pondérés » et « livrables »)."""

    serializer_class = JalonLivrableSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite", "type")

    def get_queryset(self):
        return JalonLivrable.objects.filter(activite__projet__id__in=visible_projets_ids(self.request.user))

    def _validation(self, serializer):
        # La validation d'un livrable garde son auteur et sa date ; la retirer les efface.
        valide = serializer.validated_data.get("valide")
        if valide is True and not (serializer.instance and serializer.instance.valide):
            return {"valide_par": self.request.user, "date_validation": timezone.localdate()}
        if valide is False:
            return {"valide_par": None, "date_validation": None}
        return {}

    def perform_create(self, serializer):
        serializer.save(**self._validation(serializer))

    def perform_update(self, serializer):
        serializer.save(**self._validation(serializer))


class TauxManuelViewSet(SuppressionAtomiqueMixin, viewsets.ModelViewSet):
    """Taux saisis à la main (méthode « saisie manuelle »), historisés."""

    serializer_class = TauxManuelSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("activite",)

    def get_queryset(self):
        return TauxManuel.tous.filter(activite__projet__id__in=visible_projets_ids(self.request.user))

    def perform_create(self, serializer):
        serializer.save(saisi_par=self.request.user)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAdminOrReadOnly])
def parametres_calcul(request):
    """Méthode de calcul et d'agrégation par défaut de l'organisation (modification : Administrateur)."""
    parametres = ParametresCalcul.courants()
    if request.method in ("PUT", "PATCH"):
        serializer = ParametresCalculSerializer(parametres, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(ParametresCalculSerializer(parametres).data)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAdminOrReadOnly])
def parametres_rapportage(request):
    """Contrôle des périodes de rapportage de l'organisation (modification : Administrateur)."""
    parametres = ParametresRapportage.courants()
    if request.method in ("PUT", "PATCH"):
        serializer = ParametresRapportageSerializer(parametres, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(ParametresRapportageSerializer(parametres).data)


class FenetreRapportageViewSet(viewsets.ModelViewSet):
    """Périodes de rapportage, générales (projet vide) ou propres à un projet ; gérées par l'Administrateur."""

    serializer_class = FenetreRapportageSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("projet",)
    pagination_class = None

    def get_queryset(self):
        return FenetreRapportage.objects.select_related("projet")


# ------------------------------------------------------------------------------ approbations

def _saisies_a_lister(user, etats):
    """Points de suivi, valeurs d'indicateurs et taux manuels des projets visibles, selon leur état."""
    from django.db.models import Q

    from apps.indicators.models import ValeurIndicateur
    from apps.suivi.models import PointSuivi

    ids = visible_projets_ids(user)
    filtre_auteur = {} if peut_approuver(user) else {"saisi_par": user}
    points = PointSuivi.tous.filter(
        Q(activite__projet__id__in=ids) | Q(sous_activite__activite__projet__id__in=ids),
        etat_approbation__in=etats, **filtre_auteur,
    ).select_related("activite__projet", "sous_activite__activite__projet", "saisi_par")
    valeurs = ValeurIndicateur.tous.filter(
        Q(indicateur__projet__id__in=ids) | Q(indicateur__activite__projet__id__in=ids),
        etat_approbation__in=etats, **filtre_auteur,
    ).select_related("indicateur__projet", "indicateur__activite__projet", "saisi_par")
    taux = TauxManuel.tous.filter(
        activite__projet__id__in=ids, etat_approbation__in=etats, **filtre_auteur
    ).select_related("activite__projet", "saisi_par")

    def commun(objet, type_, projet, element):
        return {
            "type": type_, "id": objet.id, "projet_id": projet.id if projet else None,
            "projet_code": projet.code if projet else "", "element": element,
            "saisi_par_nom": (objet.saisi_par.get_full_name() or objet.saisi_par.username) if objet.saisi_par else "",
            "etat": objet.etat_approbation, "motif_rejet": objet.motif_rejet, "commentaire": objet.commentaire,
        }

    lignes = []
    for p in points:
        cible = p.activite or p.sous_activite
        projet = p.activite.projet if p.activite else p.sous_activite.activite.projet
        lignes.append({
            **commun(p, "point", projet, cible.libelle), "date": p.date_saisie,
            "periode": f"{p.periode_debut:%d/%m/%Y} → {p.periode_fin:%d/%m/%Y}",
            "valeur": f"{float(p.quantite_realisee):g} {cible.unite_quantite}".strip() if p.quantite_realisee is not None else "",
            "budget": p.budget_realise, "statut": p.statut,
        })
    for v in valeurs:
        projet = v.indicateur.projet_rattache
        lignes.append({
            **commun(v, "valeur", projet, v.indicateur.libelle), "date": v.date_saisie,
            "periode": f"{v.periode_debut:%d/%m/%Y} → {v.periode_fin:%d/%m/%Y}",
            "valeur": f"{float(v.valeur_realisee):g} {v.indicateur.unite}".strip(), "budget": None, "statut": "",
        })
    for t in taux:
        lignes.append({
            **commun(t, "taux", t.activite.projet, t.activite.libelle), "date": t.created_at,
            "periode": f"au {t.date:%d/%m/%Y}", "valeur": f"{float(t.taux):g} %", "budget": None, "statut": "",
        })
    return sorted(lignes, key=lambda l: l["date"], reverse=True)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def approbations(request):
    """
    Écran « Approbations » : saisies et demandes de modification en attente (approbateur : celles
    de tous les projets visibles ; sinon : les siennes, en attente ou rejetées).
    """
    approbateur = peut_approuver(request.user)
    etats = [EtatApprobation.EN_ATTENTE] if approbateur else [EtatApprobation.EN_ATTENTE, EtatApprobation.REJETEE]
    demandes = DemandeModification.objects.filter(
        projet__id__in=visible_projets_ids(request.user), etat__in=etats
    ).select_related("projet", "demandeur")
    if not approbateur:
        demandes = demandes.filter(demandeur=request.user)
    return Response({
        "peut_approuver": approbateur,
        "saisies": _saisies_a_lister(request.user, etats),
        "demandes": [
            {
                "id": d.id, "projet_id": d.projet_id, "projet_code": d.projet.code, "cible": d.get_cible_display(),
                "action": d.action, "action_libelle": d.get_action_display(), "libelle": d.libelle,
                "changements": d.changements, "etat": d.etat, "motif_rejet": d.motif_rejet,
                # Valeurs d'un ajout, avec les noms de champs lisibles (identifiants techniques exclus).
                "valeurs": [
                    {"champ": LIBELLES_CHAMPS.get(champ, champ), "valeur": valeur}
                    for champ, valeur in d.donnees.items()
                    if valeur not in ("", None, []) and champ not in ("projet", "activite", "activite_parent")
                ],
                "demandeur_nom": (d.demandeur.get_full_name() or d.demandeur.username) if d.demandeur else "",
                "date": d.created_at,
            }
            for d in demandes
        ],
    })


def _decision(request):
    approuver = request.data.get("approuver")
    if not isinstance(approuver, bool):
        raise ValidationError({"approuver": "Indique true (approuver) ou false (rejeter)."})
    motif = (request.data.get("motif") or "").strip()
    if not approuver and not motif:
        raise ValidationError({"motif": "Indique le motif du rejet : il sera montré à l'auteur."})
    return approuver, motif


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def traiter_saisie_vue(request, type_saisie, pk):
    from apps.indicators.models import ValeurIndicateur
    from apps.suivi.models import PointSuivi

    modele = {"point": PointSuivi, "valeur": ValeurIndicateur, "taux": TauxManuel}.get(type_saisie)
    if modele is None:
        raise ValidationError({"type": "Type de saisie inconnu."})
    saisie = get_object_or_404(modele.tous, pk=pk)
    approuver, motif = _decision(request)
    traiter_saisie(saisie, request.user, approuver, motif)
    return Response({"etat": saisie.etat_approbation})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def traiter_demande_vue(request, pk):
    demande = get_object_or_404(DemandeModification, pk=pk, projet__id__in=visible_projets_ids(request.user))
    approuver, motif = _decision(request)
    traiter_demande(demande, request.user, approuver, motif)
    return Response({"etat": demande.etat})
