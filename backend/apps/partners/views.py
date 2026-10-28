from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned, IsAdminOrCreateForAuthenticated, IsAdminOrReadOnly

from .models import (
    Bailleur,
    CategoriePartiePrenante,
    Financement,
    Partenaire,
    PartiePrenante,
    RallongeFinancement,
    StructureOrganisation,
)
from .serializers import (
    BailleurSerializer,
    CategoriePartiePrenanteSerializer,
    FinancementSerializer,
    RallongeFinancementSerializer,
    PartenaireSerializer,
    PartiePrenanteSerializer,
    StructureOrganisationSerializer,
)


def _synchroniser_budget_total(projet):
    """
    Maintient l'invariant documenté sur Projet.budget_total (« Coût total =
    fonds propres + financements bailleurs ») à chaque ajout/modification/
    suppression d'un financement — sans ça, le coût total affiché restait
    figé à sa valeur de création du projet et ne reflétait jamais les
    financements bailleurs ajoutés ensuite.
    """
    projet.budget_total = projet.fonds_propres + projet.financement_bailleurs_total
    projet.save(update_fields=["budget_total"])


class PartenaireViewSet(viewsets.ModelViewSet):
    queryset = Partenaire.objects.all()
    serializer_class = PartenaireSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    filterset_fields = ("type",)
    search_fields = ("nom",)


class BailleurViewSet(viewsets.ModelViewSet):
    queryset = Bailleur.objects.all()
    serializer_class = BailleurSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    filterset_fields = ("type",)
    search_fields = ("nom",)


class FinancementViewSet(viewsets.ModelViewSet):
    queryset = Financement.objects.select_related("bailleur", "projet")
    serializer_class = FinancementSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("projet", "bailleur")

    def perform_create(self, serializer):
        super().perform_create(serializer)
        _synchroniser_budget_total(serializer.instance.projet)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        _synchroniser_budget_total(serializer.instance.projet)

    def perform_destroy(self, instance):
        projet = instance.projet
        super().perform_destroy(instance)
        _synchroniser_budget_total(projet)


class RallongeFinancementViewSet(viewsets.ModelViewSet):
    """Fonds supplémentaires d'un bailleur (motif obligatoire) ; le coût total du projet suit."""

    queryset = RallongeFinancement.objects.select_related("financement__bailleur", "saisi_par")
    serializer_class = RallongeFinancementSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("financement", "financement__projet")

    def perform_create(self, serializer):
        serializer.save(saisi_par=self.request.user)
        _synchroniser_budget_total(serializer.instance.financement.projet)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        _synchroniser_budget_total(serializer.instance.financement.projet)

    def perform_destroy(self, instance):
        projet = instance.financement.projet
        super().perform_destroy(instance)
        _synchroniser_budget_total(projet)


class StructureOrganisationViewSet(viewsets.ModelViewSet):
    """Structure de l'organisation (directions, services…) : paramétrée par l'Administrateur."""

    queryset = StructureOrganisation.objects.all()
    serializer_class = StructureOrganisationSerializer
    permission_classes = (IsAdminOrReadOnly,)
    pagination_class = None
    search_fields = ("nom", "sigle")

    @action(detail=True, methods=["get", "post"])
    def affectations(self, request, pk=None):
        """
        Projets et utilisateurs d'une structure, réglés depuis l'écran Organisation.
        POST {projets: [ids], utilisateurs: [ids]} : la liste remplace l'existante. Un utilisateur
        ajouté devient « Organisation (interne) » de cette structure ; un utilisateur retiré n'a plus
        de service.
        """
        from apps.accounts.models import User
        from apps.projects.models import Projet

        structure = self.get_object()
        if request.method == "POST":
            projets = set(map(int, request.data.get("projets", [])))
            utilisateurs = set(map(int, request.data.get("utilisateurs", [])))
            with transaction.atomic():
                for projet in Projet.objects.filter(structures=structure).exclude(id__in=projets):
                    projet.structures.remove(structure)
                for projet in Projet.objects.filter(id__in=projets):
                    projet.structures.add(structure)
                User.objects.filter(structure_interne=structure).exclude(id__in=utilisateurs).update(structure_interne=None)
                User.objects.filter(id__in=utilisateurs).update(
                    structure_interne=structure, type_structure=User.TypeStructure.INTERNE, partenaire=None, partie_prenante=None
                )
        reponse = {
            "projets": list(Projet.objects.filter(structures=structure).values_list("id", flat=True)),
            "utilisateurs": list(User.objects.filter(structure_interne=structure).values_list("id", flat=True)),
        }
        if request.method == "GET":  # choix possibles, au complet (les listes de l'API sont paginées)
            reponse["choix_projets"] = [
                {"value": str(p.id), "label": f"{p.code} — {p.nom}"} for p in Projet.objects.order_by("code")
            ]
            reponse["choix_utilisateurs"] = [
                {
                    "value": str(u.id),
                    "label": f"{(u.get_full_name() or u.username)} ({u.username})"
                    + (f" — actuellement : {u.structure_interne}" if u.structure_interne_id and u.structure_interne_id != structure.id else ""),
                }
                for u in User.objects.select_related("structure_interne").order_by("username")
            ]
        return Response(reponse)


class CategoriePartiePrenanteViewSet(viewsets.ModelViewSet):
    queryset = CategoriePartiePrenante.objects.all()
    serializer_class = CategoriePartiePrenanteSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    pagination_class = None


class PartiePrenanteViewSet(viewsets.ModelViewSet):
    """Parties prenantes : enregistrées une fois, sélectionnées ensuite (créables à la volée)."""

    queryset = PartiePrenante.objects.select_related("categorie")
    serializer_class = PartiePrenanteSerializer
    permission_classes = (IsAdminOrCreateForAuthenticated,)
    pagination_class = None
    filterset_fields = ("categorie",)
    search_fields = ("nom",)
