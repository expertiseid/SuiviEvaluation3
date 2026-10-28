
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrReadOnly, has_global_visibility
from apps.indicators.services import indicateurs_pour_projet, valeur_realisee_totale
from apps.projects.budgets import activites_comptees, total_budget
from apps.projects.models import Activite, Projet
from apps.projects.queryset_filters import visible_projets_ids
from apps.projects.taux import ArbreTaux
from apps.reports.services import taux_execution_financiere_global

from .models import CadreStrategique, ElementStrategique, TypeNiveau
from .serializers import CadreStrategiqueSerializer, ElementStrategiqueSerializer, TypeNiveauSerializer
from .services import (
    exporter_structuration,
    generer_modele_import,
    importer_structuration,
    supprimer_cadre_strategique_cascade,
)


class CadreStrategiqueViewSet(viewsets.ModelViewSet):
    serializer_class = CadreStrategiqueSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def get_queryset(self):
        """
        Un rôle à visibilité globale voit tous les cadres stratégiques ; un
        rôle restreint (chef de projet, animateur de terrain) ne voit que
        ceux rattachés à un projet auquel il est affecté — cohérent avec la
        restriction déjà appliquée sur les projets eux-mêmes.
        """
        if has_global_visibility(self.request.user):
            return CadreStrategique.objects.all()
        return CadreStrategique.objects.filter(
            projets__id__in=visible_projets_ids(self.request.user)
        ).distinct()

    def perform_destroy(self, instance):
        supprimer_cadre_strategique_cascade(instance)

    @action(detail=True, methods=["get"], url_path="export")
    def export_structuration(self, request, pk=None):
        cadre = self.get_object()
        contenu = exporter_structuration(cadre)
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f"attachment; filename=plan_strategique_{cadre.id}.xlsx"
        return response

    @action(detail=True, methods=["get"], url_path="recap")
    def recap(self, request, pk=None):
        """
        Récapitulatif des projets rattachés à ce cadre stratégique (via
        Projet.cadre_strategique) et de leur contribution financière — limité
        aux projets visibles par l'utilisateur (un chef de projet non
        affecté à un projet donné ne doit pas en voir le budget ici non plus).
        """
        cadre = self.get_object()
        ids = visible_projets_ids(request.user)
        projets = Projet.objects.filter(cadre_strategique=cadre, id__in=ids)

        lignes = []
        for projet in projets:
            arbre_taux = ArbreTaux(projet)
            activites = Activite.objects.filter(
                projet=projet
            ).order_by("code_activite", "libelle")
            indicateurs = indicateurs_pour_projet(projet.id).order_by("libelle")
            budget_activites_alloue_total = total_budget(activites, "budget_alloue")
            budget_activites_realise_total = total_budget(activites, "budget_realise")
            lignes.append(
                {
                    "id": projet.id,
                    "code": projet.code,
                    "nom": projet.nom,
                    "statut": projet.statut,
                    "date_debut": projet.date_debut,
                    "date_fin": projet.date_fin,
                    "chef_de_projet_nom": projet.chef_de_projet_nom,
                    "element_strategique": projet.element_strategique_id,
                    "element_strategique_nom": str(projet.element_strategique) if projet.element_strategique else None,
                    "bailleur_nom": projet.partenaire_bailleur.nom if projet.partenaire_bailleur else None,
                    "budget_total": projet.budget_total,
                    "budget_activites_alloue_total": budget_activites_alloue_total,
                    "budget_activites_realise_total": budget_activites_realise_total,
                    "financement_bailleurs_total": projet.financement_bailleurs_total,
                    "taux_execution_physique": arbre_taux.taux_projet().taux,
                    "taux_execution_financiere": taux_execution_financiere_global(projet),
                    "nombre_activites": activites.count(),
                    "nombre_indicateurs": indicateurs.count(),
                    "activites": [
                        {
                            "id": a.id,
                            "code": a.code_activite,
                            "libelle": a.libelle,
                            "statut": a.statut,
                            "taux_realisation": arbre_taux.resultat(a.id).taux,
                            "quantite_realisee": a.quantite_realisee,
                            "quantite_prevue": a.quantite_prevue,
                            "unite_quantite": a.unite_quantite,
                            "budget_alloue": a.budget_alloue,
                            "budget_realise": a.budget_realise,
                        }
                        for a in activites
                    ],
                    "indicateurs": [
                        {
                            "id": i.id,
                            "libelle": i.libelle,
                            "valeur_realisee": valeur_realisee_totale(i),
                            "valeur_cible": i.valeur_cible,
                            "unite": i.unite,
                        }
                        for i in indicateurs
                    ],
                }
            )

        taux_physiques = [p["taux_execution_physique"] for p in lignes if p["taux_execution_physique"] is not None]
        taux_financiers = [p["taux_execution_financiere"] for p in lignes if p["taux_execution_financiere"] is not None]

        return Response(
            {
                "budget_total": sum((p["budget_total"] for p in lignes), start=0),
                "nombre_activites_total": sum(p["nombre_activites"] for p in lignes),
                "nombre_indicateurs_total": sum(p["nombre_indicateurs"] for p in lignes),
                "taux_execution_physique_moyen": round(sum(taux_physiques) / len(taux_physiques), 1) if taux_physiques else None,
                "taux_execution_financiere_moyen": round(sum(taux_financiers) / len(taux_financiers), 1) if taux_financiers else None,
                "projets": lignes,
            }
        )


    @action(detail=True, methods=["get"], url_path="recap-axes")
    def recap_axes(self, request, pk=None):
        """
        Données de l'onglet « Axes & budgets » : les éléments du cadre et les
        activités qui y sont rattachées (Activite.axe_strategique) — plus
        celles des projets du cadre non encore rattachées à un élément. Une
        activité sans élément propre hérite de l'élément de rattachement de son
        projet (Projet.element_strategique), s'il en a un. Le
        regroupement par niveau (orientation, axe…) se fait à l'écran, un
        élément cumulant les activités de ses sous-éléments. Limité aux
        projets visibles par l'utilisateur.
        """
        from django.db.models import Q

        cadre = self.get_object()
        ids = visible_projets_ids(request.user)
        elements = ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre).select_related("type_niveau")
        activites = (
            Activite.objects.filter(projet__id__in=ids)
            .filter(
                Q(axe_strategique__type_niveau__cadre_strategique=cadre)
                | Q(projet__cadre_strategique=cadre, axe_strategique__isnull=True)
            )
            .select_related("projet__element_strategique__type_niveau")
            .order_by("projet__code", "code_activite", "libelle")
        )
        arbres_taux = _ArbresTaux()
        # Budgets sans double compte : calculés sur toutes les activités des projets concernés
        # (un niveau parent peut être rattaché à un autre élément du cadre que ses activités).
        activites = list(activites)
        toutes = list(
            Activite.objects.filter(projet__id__in={a.projet_id for a in activites}).only(
                "id", "activite_parent_id", "budget_alloue", "budget_realise"
            )
        )
        alloue_compte = activites_comptees(toutes, "budget_alloue")
        realise_compte = activites_comptees(toutes, "budget_realise")
        parent_de = {a.id: a.activite_parent_id for a in toutes}

        def ancetres(activite_id):
            resultat, courant = [], parent_de.get(activite_id)
            while courant is not None:
                resultat.append(courant)
                courant = parent_de.get(courant)
            return resultat
        return Response(
            {
                "elements": [
                    {
                        "id": e.id,
                        "code": e.code,
                        "nom": e.nom,
                        "type_niveau": e.type_niveau_id,
                        "ordre_niveau": e.type_niveau.ordre,
                        "element_parent": e.element_parent_id,
                    }
                    for e in elements
                ],
                "activites": [
                    {
                        "id": a.id,
                        "code": a.code_activite,
                        "libelle": a.libelle,
                        "projet_id": a.projet.id,
                        "projet_code": a.projet.code,
                        "axe": a.axe_strategique_id or _element_du_projet_dans_cadre(a.projet, cadre),
                        "budget_alloue": a.budget_alloue,
                        "budget_realise": a.budget_realise,
                        # Part comptée dans les totaux (0 si le détail est saisi en dessous).
                        "budget_alloue_compte": a.budget_alloue if a.id in alloue_compte else 0,
                        "budget_realise_compte": a.budget_realise if a.id in realise_compte else 0,
                        # Éléments au-dessus : dans un groupe, un élément dont un élément en dessous
                        # figure aussi n'entre pas dans la moyenne des taux (déjà compté via lui).
                        "ancetres": ancetres(a.id),
                        "taux_physique": arbres_taux.taux(a),
                        "taux_financier": a.taux_execution_financiere,
                    }
                    for a in activites
                ],
            }
        )


class _ArbresTaux:
    """Taux des éléments de plusieurs projets : un ArbreTaux par projet, chargé à la demande."""

    def __init__(self):
        self.arbres = {}

    def taux(self, activite):
        if activite.projet_id not in self.arbres:
            self.arbres[activite.projet_id] = ArbreTaux(activite.projet)
        return self.arbres[activite.projet_id].resultat(activite.id).taux


def _element_du_projet_dans_cadre(projet, cadre):
    element = projet.element_strategique
    if element is not None and element.type_niveau.cadre_strategique_id == cadre.id:
        return element.id
    return None


class TypeNiveauViewSet(viewsets.ModelViewSet):
    queryset = TypeNiveau.objects.select_related("niveau_parent", "cadre_strategique")
    serializer_class = TypeNiveauSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("cadre_strategique",)


class ElementStrategiqueViewSet(viewsets.ModelViewSet):
    serializer_class = ElementStrategiqueSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("type_niveau", "element_parent")

    def get_queryset(self):
        qs = ElementStrategique.objects.select_related("type_niveau", "element_parent").prefetch_related(
            "parents_secondaires", "structures", "parties_prenantes"
        )
        cadre_id = self.request.query_params.get("cadre_strategique")
        if cadre_id:
            qs = qs.filter(type_niveau__cadre_strategique_id=cadre_id)
        return qs

    @action(detail=False, methods=["get"], url_path="modele-import")
    def modele_import(self, request):
        cadre_id = request.query_params.get("cadre_strategique")
        if not cadre_id:
            raise ValidationError({"cadre_strategique": "Paramètre requis."})
        cadre = get_object_or_404(CadreStrategique, pk=cadre_id)
        contenu = generer_modele_import(cadre)
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=modele_import_structuration.xlsx"
        return response

    @action(
        detail=False,
        methods=["post"],
        url_path="importer",
        parser_classes=[MultiPartParser, FormParser],
    )
    def importer(self, request):
        fichier = request.data.get("fichier")
        cadre_id = request.data.get("cadre_strategique")
        if not cadre_id:
            raise ValidationError({"cadre_strategique": "Paramètre requis."})
        cadre = get_object_or_404(CadreStrategique, pk=cadre_id)
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
        try:
            resultat = importer_structuration(fichier, cadre)
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
        return Response(resultat)
