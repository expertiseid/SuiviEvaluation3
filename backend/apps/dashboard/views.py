from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.beneficiaries.models import ParticipationProjet
from apps.core.permissions import HasGlobalVisibilityOrAssigned, peut_personnaliser_tableau_de_bord
from apps.geo.models import NiveauAdministratif, Zone
from apps.indicators.models import Indicateur
from apps.indicators.services import palier_pour_taux, paliers_pour, valeur_realisee_totale, taux_realisation
from apps.notifications.services import lister_echeances
from apps.projects.models import Projet
from apps.projects.queryset_filters import visible_projets_ids

from .filtres import filtrer_projets
from .models import ConfigurationTableauDeBord
from .repartitions import repartitions_projets


def _zones_couvertes(projet_ids):
    """
    Nombre de zones distinctes couvertes par les projets, un compteur par
    niveau administratif du (ou des) pays concernés — Région/Province/
    Commune/Village pour le Burkina Faso, ou tout autre gabarit paramétré
    par pays. Chaque niveau du référentiel apparaît toujours, y compris à 0,
    pour que la couverture géographique reste lisible d'un coup d'œil même
    quand aucune commune ou village n'est encore assigné.
    """
    pays_projets = {code for pays in Projet.objects.filter(id__in=projet_ids).values_list("pays", flat=True) for code in pays}
    if not pays_projets:
        return []

    niveaux = NiveauAdministratif.objects.filter(pays__in=pays_projets).order_by("ordre")
    zones = Zone.objects.filter(projets__id__in=projet_ids).select_related("niveau_administratif").distinct()
    compteurs: dict[int, int] = {}
    for zone in zones:
        compteurs[zone.niveau_administratif_id] = compteurs.get(zone.niveau_administratif_id, 0) + 1

    return [{"niveau": niveau.nom_niveau, "count": compteurs.get(niveau.id, 0)} for niveau in niveaux]


def _indicateurs_pour_projets(projet_ids):
    return Indicateur.objects.filter(
        Q(projet__id__in=projet_ids)
        | Q(objectif_general__projet__id__in=projet_ids)
        | Q(objectif_specifique__objectif_general__projet__id__in=projet_ids)
        | Q(activite__objectif_specifique__objectif_general__projet__id__in=projet_ids)
    ).distinct()


def _resume_indicateurs(indicateurs):
    """
    Chaque indicateur suit la palette de SON projet (elles peuvent différer
    d'un projet à l'autre) — les compteurs sont donc regroupés par
    (libellé, couleur) du palier atteint plutôt que par 3 statuts fixes.
    """
    compteurs = {}
    for indicateur in indicateurs:
        taux = taux_realisation(valeur_realisee_totale(indicateur), indicateur.valeur_cible)
        palier = palier_pour_taux(taux, paliers_pour(indicateur=indicateur, projet=indicateur.projet_rattache))
        if palier is None:
            continue
        cle = (palier.libelle, palier.couleur)
        compteurs[cle] = compteurs.get(cle, 0) + 1
    return sorted(
        [{"libelle": libelle, "couleur": couleur, "count": count} for (libelle, couleur), count in compteurs.items()],
        key=lambda r: r["libelle"],
    )


def _evolutions(projets, ids):
    """
    Courbes mois par mois : dépenses cumulées par projet (budget réalisé des
    points de suivi, au mois de fin de la saisie) et nombre cumulé de
    bénéficiaires inscrits (date d'inscription).
    """
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth

    from apps.suivi.models import PointSuivi

    depenses = (
        PointSuivi.objects.filter(
            activite__objectif_specifique__objectif_general__projet__id__in=ids, budget_realise__isnull=False
        )
        .annotate(mois=TruncMonth("periode_fin"))
        .values("mois", "activite__objectif_specifique__objectif_general__projet__code")
        .annotate(total=Sum("budget_realise"))
    )
    par_mois: dict = {}
    for d in depenses:
        code = d["activite__objectif_specifique__objectif_general__projet__code"]
        par_mois.setdefault(d["mois"], {})[code] = float(d["total"])
    codes = list(projets.order_by("code").values_list("code", flat=True))
    cumul = {code: 0.0 for code in codes}
    depenses_par_mois = []
    for mois in sorted(par_mois):
        for code, total in par_mois[mois].items():
            cumul[code] = cumul.get(code, 0.0) + total
        depenses_par_mois.append({"mois": mois.strftime("%Y-%m"), **cumul})

    # Nouveaux bénéficiaires inscrits à chaque projet, mois par mois (date
    # d'inscription de chaque participation) — non cumulé.
    inscriptions = (
        ParticipationProjet.objects.filter(projet__id__in=ids)
        .annotate(mois=TruncMonth("date_inscription"))
        .values("mois", "projet__code")
        .annotate(n=Count("beneficiaire", distinct=True))
    )
    par_mois_insc: dict = {}
    for r in inscriptions:
        par_mois_insc.setdefault(r["mois"], {})[r["projet__code"]] = r["n"]
    inscriptions_par_mois = [
        {"mois": mois.strftime("%Y-%m"), **{code: par_mois_insc[mois].get(code, 0) for code in codes}}
        for mois in sorted(par_mois_insc)
    ]

    return {"depenses_par_mois": depenses_par_mois, "inscriptions_par_mois": inscriptions_par_mois}


def _repartitions(projets, ids):
    """Répartitions pour les graphiques en camembert du tableau de bord consolidé."""
    from django.db.models import Count

    from apps.projects.models import Activite
    from apps.reports.services import taux_execution_financiere_global, taux_execution_physique_global

    def compter(queryset, champ):
        return {r[champ]: r["n"] for r in queryset.values(champ).annotate(n=Count("id", distinct=True))}

    activites = Activite.objects.filter(objectif_specifique__objectif_general__projet__id__in=ids)
    participations = ParticipationProjet.objects.filter(projet__id__in=ids)
    return {
        "projets_par_statut": compter(projets, "statut"),
        "activites_par_statut": compter(activites, "statut"),
        "beneficiaires_par_sexe": {
            r["beneficiaire__sexe"]: r["n"]
            for r in participations.values("beneficiaire__sexe").annotate(n=Count("beneficiaire", distinct=True))
        },
        "beneficiaires_par_projet": {
            r["projet__code"]: r["n"]
            for r in participations.values("projet__code").annotate(n=Count("beneficiaire", distinct=True))
        },
        "activites_par_projet": [
            {"code": p.code, **compter(activites.filter(objectif_specifique__objectif_general__projet=p), "statut")}
            for p in projets.order_by("code")
        ],
        "beneficiaires_par_projet_sexe": [
            {
                "code": p.code,
                **{
                    r["beneficiaire__sexe"]: r["n"]
                    for r in participations.filter(projet=p)
                    .values("beneficiaire__sexe")
                    .annotate(n=Count("beneficiaire", distinct=True))
                },
            }
            for p in projets.order_by("code")
        ],
        **_evolutions(projets, ids),
        "execution_par_projet": [
            {
                "code": p.code,
                "physique": taux_execution_physique_global(p),
                "financier": taux_execution_financiere_global(p),
            }
            for p in projets.order_by("code")
        ],
    }


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def dashboard_consolide(request):
    """
    Filtres facultatifs (voir filtres.py) : ?annee= ou ?date_debut=&date_fin=,
    ?periode=actifs|demarres|demarres_fin_prevue|demarres_termines,
    ?statuts=EN_COURS,CLOTURE. Toutes les statistiques portent sur les
    projets retenus.
    """
    projets = filtrer_projets(Projet.objects.filter(id__in=visible_projets_ids(request.user)), request.query_params)
    ids = list(projets.values_list("id", flat=True))
    projets = Projet.objects.filter(id__in=ids)
    indicateurs = _indicateurs_pour_projets(ids)
    nombre_beneficiaires = (
        ParticipationProjet.objects.filter(projet__id__in=ids).values("beneficiaire").distinct().count()
    )

    return Response(
        {
            "nombre_projets": projets.count(),
            "budget_total": sum((p.budget_total for p in projets), start=0),
            "nombre_beneficiaires": nombre_beneficiaires,
            "indicateurs_par_statut": _resume_indicateurs(indicateurs),
            "zones_couvertes": _zones_couvertes(ids),
            **_repartitions(projets, ids),
            **repartitions_projets(projets),
            "projets": [
                {"id": p.id, "code": p.code, "nom": p.nom, "statut": p.statut, "budget_total": p.budget_total}
                for p in projets
            ],
        }
    )


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def dashboard_echeances(request):
    """
    Activités, sous-activités et projets (parmi ceux visibles par l'utilisateur) en retard ou dont
    l'échéance approche — alimente le bandeau défilant du tableau de bord.
    """
    ids = list(visible_projets_ids(request.user))
    return Response(lister_echeances(ids))


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def dashboard_projet(request, projet_id):
    ids = list(visible_projets_ids(request.user))
    projet = Projet.objects.filter(id__in=ids, id=projet_id).first()
    if projet is None:
        return Response({"detail": "Projet introuvable ou non accessible."}, status=404)

    indicateurs = _indicateurs_pour_projets([projet_id])
    nombre_beneficiaires = (
        ParticipationProjet.objects.filter(projet=projet).values("beneficiaire").distinct().count()
    )

    indicateurs_detail = []
    for indicateur in indicateurs:
        taux = taux_realisation(valeur_realisee_totale(indicateur), indicateur.valeur_cible)
        palier = palier_pour_taux(taux, paliers_pour(indicateur=indicateur, projet=projet))
        indicateurs_detail.append(
            {
                "id": indicateur.id,
                "libelle": indicateur.libelle,
                "taux_realisation": taux,
                "palier_actuel": (
                    {"libelle": palier.libelle, "couleur": palier.couleur} if palier else None
                ),
            }
        )

    return Response(
        {
            "projet": {"id": projet.id, "code": projet.code, "nom": projet.nom, "statut": projet.statut},
            "nombre_objectifs_generaux": 1 if hasattr(projet, "objectif_general") else 0,
            "nombre_beneficiaires": nombre_beneficiaires,
            "indicateurs": indicateurs_detail,
            "indicateurs_par_statut": _resume_indicateurs(indicateurs),
            "zones_couvertes": _zones_couvertes([projet_id]),
        }
    )


TYPES_GRAPHIQUES = {"camembert", "colonnes", "colonnes-empilees", "barres", "courbes", "aires", "tableau"}


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def dashboard_configuration(request):
    """
    Configuration du tableau de bord commune à tous (blocs masqués, types de
    graphiques). Lecture : tout utilisateur connecté. Modification :
    Administrateur ou rôle ayant le droit de personnaliser le tableau de bord.
    """
    configuration = ConfigurationTableauDeBord.courante()
    if request.method == "PUT":
        if not peut_personnaliser_tableau_de_bord(request.user):
            raise PermissionDenied("Ton rôle ne permet pas de personnaliser le tableau de bord.")
        blocs = request.data.get("blocs_masques", configuration.blocs_masques)
        types = request.data.get("types_graphiques", configuration.types_graphiques)
        if not isinstance(blocs, list) or not all(isinstance(b, str) for b in blocs):
            raise ValidationError({"blocs_masques": "Liste de clés de blocs attendue."})
        if not isinstance(types, dict) or not set(types.values()) <= TYPES_GRAPHIQUES:
            raise ValidationError({"types_graphiques": "Type de graphique inconnu."})
        configuration.blocs_masques = blocs
        configuration.types_graphiques = types
        configuration.modifie_par = request.user
        configuration.save()
    return Response(
        {
            "blocs_masques": configuration.blocs_masques,
            "types_graphiques": configuration.types_graphiques,
            "peut_modifier": peut_personnaliser_tableau_de_bord(request.user),
        }
    )
