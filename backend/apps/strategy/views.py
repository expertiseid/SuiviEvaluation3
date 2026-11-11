
import datetime

from django.db.models import Q
from django.http import HttpResponse
from rest_framework.generics import get_object_or_404  # répond 404 (pas 500) si l'identifiant n'est pas un nombre
from django.utils.text import slugify
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.masquage import elements_masques
from apps.core.langues import dans_la_langue_demandee
from apps.core.permissions import HasGlobalVisibilityOrAssigned, IsAdminOrReadOnly, has_global_visibility
from apps.indicators.services import indicateurs_pour_projet, valeur_realisee_totale
from apps.projects.budgets import activites_comptees, total_budget
from apps.projects.models import Activite, Projet
from apps.projects.queryset_filters import visible_projets_ids
from apps.projects.taux import ArbreTaux
from apps.reports.services import taux_execution_financiere_global

from .models import AppreciationStrategique, CadreStrategique, ElementStrategique, TypeDocument, TypeNiveau
from .serializers import (
    AppreciationStrategiqueSerializer,
    CadreStrategiqueSerializer,
    ElementStrategiqueSerializer,
    TypeDocumentSerializer,
    TypeNiveauSerializer,
)
from .services import (
    exporter_structuration,
    generer_modele_import,
    importer_structuration,
    supprimer_cadre_strategique_cascade,
)


class TypeDocumentViewSet(viewsets.ModelViewSet):
    """Maillons de la chaîne des documents stratégiques (une rubrique du menu chacun)."""

    queryset = TypeDocument.objects.all()
    serializer_class = TypeDocumentSerializer
    permission_classes = (IsAdminOrReadOnly,)
    pagination_class = None

    def perform_destroy(self, instance):
        if instance.documents.exists():
            raise ValidationError({"detail": f"« {instance.nom} » contient des documents : les supprimer ou les déplacer d'abord."})
        if TypeDocument.objects.count() <= 1:
            raise ValidationError({"detail": "Il faut garder au moins un maillon."})
        instance.delete()


class CadreStrategiqueViewSet(viewsets.ModelViewSet):
    """
    Documents stratégiques, de tous les maillons de la chaîne (?type_document= pour un maillon) :
    structuration, récapitulatifs (qui comptent aussi ce qui est rattaché en dessous, voir
    chaine.py) et chaîne en Excel.
    """
    serializer_class = CadreStrategiqueSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def get_queryset(self):
        """
        Un rôle à visibilité globale voit tous les cadres stratégiques ; un
        rôle restreint (chef de projet, animateur de terrain) ne voit que
        ceux rattachés à un projet auquel il est affecté — cohérent avec la
        restriction déjà appliquée sur les projets eux-mêmes — et ceux
        auxquels il est affecté directement.
        """
        queryset = CadreStrategique.objects.select_related(
            "type_document", "document_parent", "element_parent", "partenaire_mise_en_oeuvre",
        ).prefetch_related(
            "structures", "parties_prenantes", "partenaires_consortium", "zones", "utilisateurs_affectes",
            "elements_parents_secondaires",
        )
        type_document = self.request.query_params.get("type_document")
        if type_document:
            # Maillon de la chaîne ; le premier maillon reprend aussi les documents sans type.
            from .models import TypeDocument

            premier = TypeDocument.objects.order_by("ordre", "id").first()
            if premier and str(premier.id) == type_document:
                queryset = queryset.filter(Q(type_document_id=type_document) | Q(type_document__isnull=True))
            else:
                queryset = queryset.filter(type_document_id=type_document)
        if has_global_visibility(self.request.user):
            return queryset
        # Rôle restreint : les documents auxquels comptent ses projets (et ceux au-dessus d'eux).
        from .chaine import documents_des_projets

        # Plus les documents auxquels il est affecté directement (fiche du document).
        projets = Projet.objects.filter(id__in=visible_projets_ids(self.request.user))
        return queryset.filter(Q(id__in=documents_des_projets(projets)) | Q(utilisateurs_affectes=self.request.user)).distinct()

    def perform_destroy(self, instance):
        supprimer_cadre_strategique_cascade(instance)

    @action(detail=True, methods=["get"], url_path="export")
    @dans_la_langue_demandee
    def export_structuration(self, request, pk=None):
        cadre = self.get_object()
        contenu = exporter_structuration(cadre)
        response = HttpResponse(
            contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f"attachment; filename=plan_strategique_{cadre.id}.xlsx"
        return response

    def _fichier(self, contenu, nom):
        """Réponse de téléchargement d'un classeur Excel."""
        response = HttpResponse(contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={nom}"
        return response

    @action(detail=False, methods=["get"], url_path="chaine/modele")
    @dans_la_langue_demandee
    def modele_chaine(self, request):
        """Modèle Excel de la chaîne des documents (maillons, documents, éléments)."""
        from .import_chaine import generer_modele_chaine

        return self._fichier(generer_modele_chaine(), "modele_chaine_documents.xlsx")

    @action(detail=False, methods=["get"], url_path="chaine/export")
    @dans_la_langue_demandee
    def export_chaine(self, request):
        """Toute la chaîne actuelle au format du modèle (réimportable)."""
        from .import_chaine import exporter_chaine

        return self._fichier(exporter_chaine(), "chaine_documents.xlsx")

    @action(detail=False, methods=["post"], url_path="chaine/importer", parser_classes=[MultiPartParser, FormParser])
    def importer_chaine(self, request):
        """Import de la chaîne : maillons, documents et leur rattachement, éléments et leurs contributions."""
        from .import_chaine import importer_chaine

        fichier = request.data.get("fichier")
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
        try:
            return Response(importer_chaine(fichier))
        except ValidationError:
            raise
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})

    @action(detail=True, methods=["get"], url_path="recap")
    def recap(self, request, pk=None):
        """
        Récapitulatif des projets rattachés à ce cadre stratégique (via
        Projet.cadre_strategique) et de leur contribution financière — limité
        aux projets visibles par l'utilisateur (un chef de projet non
        affecté à un projet donné ne doit pas en voir le budget ici non plus).
        """
        from .chaine import Chaine

        cadre = self.get_object()
        ids = visible_projets_ids(request.user)
        # Projets du document et ceux des documents rattachés en dessous (sur toute la chaîne).
        chaine = Chaine()
        projets, element_atteint = [], {}
        for projet in Projet.objects.filter(id__in=ids).select_related("cadre_strategique", "partenaire_bailleur").order_by("code"):
            compte, element = chaine.atteint(chaine.depart_projet(projet), cadre.id)
            if compte:
                projets.append(projet)
                element_atteint[projet.id] = element
        noms_elements = {e.id: str(e) for e in ElementStrategique.objects.filter(id__in=[e for e in element_atteint.values() if e])}

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
                    # Élément du document auquel le projet arrive (directement ou par la chaîne).
                    "element_strategique": element_atteint[projet.id],
                    "element_strategique_nom": noms_elements.get(element_atteint[projet.id]),
                    # Document par lequel il arrive, quand ce n'est pas celui-ci.
                    "via_document": projet.cadre_strategique.nom if projet.cadre_strategique_id != cadre.id else None,
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


    @action(detail=True, methods=["get"], url_path="suivi")
    def suivi(self, request, pk=None):
        """
        Vue d'ensemble du suivi du document : pour chaque élément, avancement calculé depuis les
        projets, nombre d'indicateurs propres et dernière appréciation renseignée.
        """
        from apps.indicators.models import IndicateurElement

        from .chaine import activites_rattachees
        from .suivi import contribution_projets

        cadre = self.get_object()
        ids = list(visible_projets_ids(request.user))
        rattachees = activites_rattachees(cadre, ids)
        elements = list(ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre).exclude(
            id__in=elements_masques(request.user)).select_related("type_niveau"))
        indicateurs = {}
        for element_id in IndicateurElement.objects.filter(element_strategique__in=elements).values_list("element_strategique_id", flat=True):
            indicateurs[element_id] = indicateurs.get(element_id, 0) + 1
        dernieres = {}
        for a in AppreciationStrategique.objects.filter(element__in=elements).order_by("periode_fin", "id"):
            dernieres[a.element_id] = a
        arbres = {}
        lignes = []
        for e in elements:
            calcule = contribution_projets(e, ids, arbres, rattachees)
            derniere = dernieres.get(e.id)
            lignes.append({
                "id": e.id, "code": e.code, "nom": e.nom, "element_parent": e.element_parent_id,
                "niveau": e.type_niveau.nom_niveau, "ordre_niveau": e.type_niveau.ordre,
                "taux_physique": calcule["taux_physique"], "taux_financier": calcule["taux_financier"],
                "nombre_projets": len(calcule["projets"]), "nombre_indicateurs": indicateurs.get(e.id, 0),
                "derniere_appreciation": {
                    "etat": derniere.etat, "libelle_periode": derniere.libelle_periode, "periode_fin": derniere.periode_fin,
                } if derniere else None,
            })
        return Response({"elements": lignes})

    @action(detail=True, methods=["get"], url_path="tableau")
    @dans_la_langue_demandee
    def tableau(self, request, pk=None):
        """
        Export du mode Tableau de l'arborescence (n'importe quel maillon) : ?fichier=xlsx|pdf,
        ?contenu=simple pour la structure seule (sans activités ni chiffres),
        ?programmation=trimestres|dates, ?annee= (programmation par trimestres ; défaut : l'année
        en cours si les activités la couvrent, sinon la première).
        """
        from .tableau import (
            annees_possibles, exporter_simple_excel, exporter_simple_pdf, exporter_tableau_excel, exporter_tableau_pdf,
            lignes_simples, lignes_tableau,
        )

        cadre = self.get_object()
        if request.query_params.get("contenu") == "simple":
            # Export simple : la structure seule (éléments, niveaux, contributions), sans chiffres.
            nom = f"structure_{slugify(cadre.code or cadre.nom)[:60] or cadre.id}"
            lignes = lignes_simples(cadre, request.user)
            if request.query_params.get("fichier") == "pdf":
                response = HttpResponse(exporter_simple_pdf(cadre, lignes), content_type="application/pdf")
                response["Content-Disposition"] = f"attachment; filename={nom}.pdf"
                return response
            return self._fichier(exporter_simple_excel(cadre, lignes), f"{nom}.xlsx")
        lignes = lignes_tableau(cadre, visible_projets_ids(request.user), request.user)
        par_trimestre = request.query_params.get("programmation", "trimestres") != "dates"
        annees = annees_possibles(lignes)
        try:
            annee = int(request.query_params.get("annee") or 0)
        except ValueError:
            annee = 0
        if not annee:
            annee = datetime.date.today().year if datetime.date.today().year in annees else annees[0]
        nom = f"tableau_{slugify(cadre.code or cadre.nom)[:60] or cadre.id}"
        if request.query_params.get("fichier") == "pdf":
            response = HttpResponse(exporter_tableau_pdf(cadre, lignes, par_trimestre, annee), content_type="application/pdf")
            response["Content-Disposition"] = f"attachment; filename={nom}.pdf"
            return response
        return self._fichier(exporter_tableau_excel(cadre, lignes, par_trimestre, annee), f"{nom}.xlsx")

    @action(detail=True, methods=["get"], url_path="recap-axes")
    def recap_axes(self, request, pk=None):
        """
        Données de l'onglet « Axes & budgets » : les éléments du cadre et les
        activités qui y sont rattachées (Activite.axe_strategique) — plus
        celles des projets du cadre non encore rattachées à un élément. Une
        activité sans élément propre hérite de l'élément de rattachement de son
        projet (Projet.element_strategique), s'il en a un. Les activités des
        documents rattachés en dessous (chaîne des documents, voir chaine.py)
        arrivent sur l'élément de ce document auquel elles remontent. Le
        regroupement par niveau (orientation, axe…) se fait à l'écran, un
        élément cumulant les activités de ses sous-éléments. Limité aux
        projets visibles par l'utilisateur.
        """
        from .tableau import donnees_recap_axes

        return Response(donnees_recap_axes(self.get_object(), visible_projets_ids(request.user), request.user))


class TypeNiveauViewSet(viewsets.ModelViewSet):
    queryset = TypeNiveau.objects.select_related("niveau_parent", "cadre_strategique")
    serializer_class = TypeNiveauSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("cadre_strategique",)


class ElementStrategiqueViewSet(viewsets.ModelViewSet):
    serializer_class = ElementStrategiqueSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("type_niveau", "element_parent")

    @action(detail=True, methods=["get"], permission_classes=[HasGlobalVisibilityOrAssigned])
    def suivi(self, request, pk=None):
        """Suivi d'un élément : avancement calculé, indicateurs (avec saisie directe), appréciations."""
        from .suivi import suivi_element

        return Response(suivi_element(self.get_object(), list(visible_projets_ids(request.user)), request))

    @action(detail=False, methods=["get"])
    def arborescence(self, request):
        """Tous les éléments des documents stratégiques, en version allégée (sélecteur « Visibilité » des utilisateurs)."""
        return Response(list(self.get_queryset().order_by("id").values(
            "id", "code", "nom", "element_parent", "type_niveau__cadre_strategique", "type_niveau__cadre_strategique__nom")))

    def get_queryset(self):
        qs = ElementStrategique.objects.select_related(
            "type_niveau__cadre_strategique__type_document", "element_parent", "contribue_a__type_niveau__cadre_strategique__type_document"
        ).prefetch_related(
            "parents_secondaires", "structures", "parties_prenantes"
        )
        cadre_id = self.request.query_params.get("cadre_strategique")
        if cadre_id:
            qs = qs.filter(type_niveau__cadre_strategique_id=cadre_id)
        # Éléments masqués à cet utilisateur (apps.core.masquage) : ni eux ni ce qui est en dessous.
        return qs.exclude(id__in=elements_masques(self.request.user))

    @action(detail=False, methods=["get"], url_path="modele-import")
    @dans_la_langue_demandee
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
        if not str(cadre_id).isdigit():
            raise ValidationError({"cadre_strategique": "Identifiant invalide."})
        cadre = get_object_or_404(CadreStrategique, pk=cadre_id)
        if not fichier:
            raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
        try:
            resultat = importer_structuration(fichier, cadre)
        except Exception as exc:  # fichier corrompu, mauvais format, etc.
            raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
        return Response(resultat)


class AppreciationStrategiqueViewSet(viewsets.ModelViewSet):
    """Appréciations d'un élément de document stratégique par période (?element=)."""

    queryset = AppreciationStrategique.objects.select_related("saisi_par").prefetch_related("pieces_justificatives__uploaded_by")
    serializer_class = AppreciationStrategiqueSerializer
    permission_classes = (HasGlobalVisibilityOrAssigned,)
    filterset_fields = ("element",)

    def perform_create(self, serializer):
        serializer.save(saisi_par=self.request.user)
