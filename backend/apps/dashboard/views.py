import re
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.constants import ROLE_ADMIN
from apps.beneficiaries.models import ParticipationProjet
from apps.core.permissions import HasGlobalVisibilityOrAssigned, peut_personnaliser_tableau_de_bord
from apps.core.vocabulaire import oublier_vocabulaire, v
from apps.geo.models import NiveauAdministratif, Zone
from apps.indicators.models import Indicateur
from apps.indicators.services import palier_pour_taux, paliers_pour, valeur_realisee_totale, taux_realisation
from apps.notifications.services import lister_echeances
from apps.projects.models import Projet
from apps.projects.queryset_filters import visible_projets_ids

from .filtres import filtrer_projets
from .models import ConfigurationMenu, ConfigurationTableauDeBord
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
        Q(projet__id__in=projet_ids) | Q(activite__projet__id__in=projet_ids)
    ).distinct()


def _resume_indicateurs(indicateurs):
    """
    Chaque indicateur suit la palette de SON projet (elles peuvent différer
    d'un projet à l'autre) — les compteurs sont donc regroupés par
    (libellé, couleur) du palier atteint plutôt que par 3 statuts fixes.

    Mêmes règles que valeur_realisee_totale et paliers_pour (grille de l'indicateur, sinon de son projet,
    sinon globale), calculées en quelques requêtes pour tous les indicateurs au lieu de plusieurs par
    indicateur.
    """
    from apps.indicators.models import PalierAlerte, ValeurIndicateur

    lignes = list(indicateurs.values_list("id", "valeur_cible", "projet_id", "activite__projet_id"))
    ids = [ligne[0] for ligne in lignes]
    # Saisies approuvées seulement (gestionnaire par défaut), comme indicateur.valeurs.
    realises = dict(ValeurIndicateur.objects.filter(indicateur_id__in=ids).values("indicateur_id")
                    .annotate(total=Sum("valeur_realisee")).values_list("indicateur_id", "total"))
    par_indicateur, par_projet, globale = defaultdict(list), defaultdict(list), []
    projets = {ligne[2] or ligne[3] for ligne in lignes} - {None}
    paliers = PalierAlerte.objects.filter(Q(indicateur_id__in=ids) | Q(projet_id__in=projets) | Q(
        projet__isnull=True, indicateur__isnull=True, activite__isnull=True)).order_by("borne_min")
    for palier in paliers:
        if palier.indicateur_id is not None:
            par_indicateur[palier.indicateur_id].append(palier)
        elif palier.projet_id is not None:
            par_projet[palier.projet_id].append(palier)
        elif palier.activite_id is None:
            globale.append(palier)

    compteurs = {}
    for numero, valeur_cible, projet_id, projet_activite_id in lignes:
        taux = taux_realisation(realises.get(numero) or Decimal("0"), valeur_cible)
        projet = projet_id or projet_activite_id
        grille = par_indicateur.get(numero) or (par_projet.get(projet) if projet else None) or globale
        palier = palier_pour_taux(taux, grille)
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

    from apps.projects.budgets import activites_comptees
    from apps.projects.models import Activite
    from apps.suivi.models import PointSuivi

    # Sans double compte : seules les dépenses des activités comptées (apps.projects.budgets).
    comptees = activites_comptees(
        Activite.objects.filter(projet__id__in=ids).only("id", "activite_parent_id", "budget_realise"), "budget_realise"
    )
    depenses = (
        PointSuivi.objects.filter(activite_id__in=comptees, budget_realise__isnull=False)
        .annotate(mois=TruncMonth("periode_fin"))
        .values("mois", "activite__projet__code")
        .annotate(total=Sum("budget_realise"))
    )
    par_mois: dict = {}
    for d in depenses:
        code = d["activite__projet__code"]
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
    from collections import Counter

    from django.db.models import Count

    from apps.projects.models import Activite, ParametresCalcul
    from apps.reports.services import taux_execution_financiere_global, taux_execution_physique_global

    def compter(queryset, champ):
        return {r[champ]: r["n"] for r in queryset.values(champ).annotate(n=Count("id", distinct=True))}

    activites = Activite.objects.filter(projet__id__in=ids)
    participations = ParticipationProjet.objects.filter(projet__id__in=ids)
    # Par projet : activités lues une fois pour tous (taux, statuts), bénéficiaires par sexe en une requête.
    liste = list(projets.order_by("code"))
    parametres = ParametresCalcul.courants()
    activites_de = defaultdict(list)
    for activite in Activite.objects.filter(projet__in=liste).prefetch_related("sous_activites", "jalons_livrables", "taux_manuels"):
        activites_de[activite.projet_id].append(activite)
    sexes_de = defaultdict(dict)
    for r in (participations.filter(projet__in=liste).values("projet_id", "beneficiaire__sexe")
              .annotate(n=Count("beneficiaire", distinct=True))):
        sexes_de[r["projet_id"]][r["beneficiaire__sexe"]] = r["n"]
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
            {"code": p.code, **Counter(a.statut for a in activites_de[p.id])} for p in liste
        ],
        "beneficiaires_par_projet_sexe": [
            {"code": p.code, **sexes_de[p.id]} for p in liste
        ],
        **_evolutions(projets, ids),
        "execution_par_projet": [
            {
                "code": p.code,
                "physique": taux_execution_physique_global(p, parametres, activites_de[p.id]),
                "financier": taux_execution_financiere_global(p, activites_de[p.id]),
            }
            for p in liste
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
    return Response(donnees_consolidees(visible_projets_ids(request.user), request.query_params))


FORMATS_EXPORT = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def dashboard_consolide_export(request):
    """
    Tableau de bord en fichier (?fichier=xlsx, pdf, docx ou pptx) : mêmes chiffres et mêmes filtres que
    l'écran (voir dashboard_consolide).
    """
    fichier = request.query_params.get("fichier", "xlsx")  # « format » est réservé par DRF
    if fichier not in FORMATS_EXPORT:
        raise ValidationError({"fichier": "Format inconnu : xlsx, pdf, docx ou pptx."})
    return reponse_export(donnees_consolidees(visible_projets_ids(request.user), request.query_params),
                          request.query_params, fichier)


def reponse_export(donnees, filtres, fichier="xlsx"):
    from django.http import HttpResponse

    from apps.core.models import IdentiteOrganisation

    organisation = IdentiteOrganisation.courante().nom
    if fichier == "xlsx":
        from .excel import excel_tableau_de_bord

        contenu = excel_tableau_de_bord(donnees, filtres, organisation)
    else:
        from . import rapport

        contenu = {"pdf": rapport.pdf, "docx": rapport.word, "pptx": rapport.powerpoint}[fichier](
            rapport.contenu(donnees, filtres, organisation))
    reponse = HttpResponse(contenu, content_type=FORMATS_EXPORT[fichier])
    reponse["Content-Disposition"] = f"attachment; filename=tableau_de_bord_{timezone.localdate():%Y-%m-%d}.{fichier}"
    return reponse


def donnees_consolidees(ids_visibles, filtres) -> dict:
    """Chiffres du tableau de bord pour ces projets (aussi servis par un lien de partage)."""
    projets = filtrer_projets(Projet.objects.filter(id__in=ids_visibles), filtres)
    ids = list(projets.values_list("id", flat=True))
    projets = Projet.objects.filter(id__in=ids)
    indicateurs = _indicateurs_pour_projets(ids)
    nombre_beneficiaires = (
        ParticipationProjet.objects.filter(projet__id__in=ids).values("beneficiaire").distinct().count()
    )

    return {
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


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def dashboard_echeances(request):
    """
    Activités, sous-activités et projets (parmi ceux visibles par l'utilisateur) en retard ou dont
    l'échéance approche — alimente le bandeau défilant du tableau de bord.
    """
    ids = list(visible_projets_ids(request.user))
    from apps.core.masquage import activites_masquees

    masquees = activites_masquees(request.user)  # échéances d'éléments masqués à cet utilisateur : exclues
    return Response([e for e in lister_echeances(ids) if not (
        (e["type"] == "ACTIVITE" and e["id"] in masquees) or (e["type"] == "SOUS_ACTIVITE" and e.get("activite_id") in masquees))])


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def dashboard_projet(request, projet_id):
    ids = list(visible_projets_ids(request.user))
    projet = Projet.objects.filter(id__in=ids, id=projet_id).first()
    if projet is None:
        return Response({"detail": v('Projet introuvable ou non accessible.')}, status=404)

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
            "nombre_elements_planification": projet.activites.count(),
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
            raise PermissionDenied(v('Ton rôle ne permet pas de personnaliser le tableau de bord.'))
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


LONGUEUR_MAX_LIBELLE_MENU = 60
# Nom d'une icône lucide (ex : « Briefcase ») ; la liste proposée est dans le frontend.
NOM_ICONE = re.compile(r"[A-Z][A-Za-z0-9]{0,39}")


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def configuration_menu(request):
    """
    Noms et icônes des rubriques du menu latéral, communs à tous :
    libelles { route: libellé } et icones { route: nom d'icône }. Lecture :
    tout utilisateur connecté. Modification : Administrateur. Une valeur vide
    (ou absente) rend à la rubrique son nom / son icône par défaut.
    """
    configuration = ConfigurationMenu.courante()
    if request.method == "PUT":
        if request.user.role != ROLE_ADMIN:
            raise PermissionDenied("Seul l'Administrateur peut renommer les rubriques du menu.")
        libelles = _dictionnaire_par_route(request.data.get("libelles", configuration.libelles), "libelles")
        icones = _dictionnaire_par_route(request.data.get("icones", configuration.icones), "icones")
        vocabulaire = _vocabulaire_valide(request.data.get("vocabulaire", configuration.vocabulaire))
        from apps.core.models import CODES_LANGUES

        langue_defaut = request.data.get("langue_defaut", configuration.langue_defaut)
        if langue_defaut not in CODES_LANGUES:
            raise ValidationError({"langue_defaut": "Langue inconnue."})
        configuration.langue_defaut = langue_defaut
        if any(len(v) > LONGUEUR_MAX_LIBELLE_MENU for v in libelles.values()):
            raise ValidationError({"libelles": f"{LONGUEUR_MAX_LIBELLE_MENU} caractères maximum par libellé."})
        if not all(NOM_ICONE.fullmatch(v) for v in icones.values()):
            raise ValidationError({"icones": "Nom d'icône invalide."})
        configuration.libelles = libelles
        configuration.icones = icones
        configuration.vocabulaire = vocabulaire
        configuration.modifie_par = request.user
        configuration.save()
        oublier_vocabulaire()
    return Response(
        {
            "libelles": configuration.libelles,
            "icones": configuration.icones,
            "vocabulaire": configuration.vocabulaire,
            "langue_defaut": configuration.langue_defaut,
            "peut_modifier": request.user.role == ROLE_ADMIN,
        }
    )


def _vocabulaire_valide(valeur):
    """{ clé de terme: {singulier, pluriel, feminin} } — un terme sans singulier ni pluriel est retiré."""
    from apps.core.vocabulaire import CLES_TERMES

    if not isinstance(valeur, dict):
        raise ValidationError({"vocabulaire": "Dictionnaire { terme : {singulier, pluriel, feminin} } attendu."})
    resultat = {}
    for cle, choix in valeur.items():
        if cle not in CLES_TERMES or not isinstance(choix, dict):
            raise ValidationError({"vocabulaire": f"Terme inconnu : {cle}."})
        singulier = str(choix.get("singulier") or "").strip()
        pluriel = str(choix.get("pluriel") or "").strip()
        if len(singulier) > LONGUEUR_MAX_LIBELLE_MENU or len(pluriel) > LONGUEUR_MAX_LIBELLE_MENU:
            raise ValidationError({"vocabulaire": f"{LONGUEUR_MAX_LIBELLE_MENU} caractères maximum par terme."})
        if singulier or pluriel:
            resultat[cle] = {"singulier": singulier, "pluriel": pluriel, "feminin": bool(choix.get("feminin"))}
    return resultat


def _dictionnaire_par_route(valeur, champ):
    """{ route: texte } nettoyé — les valeurs vides sont retirées (retour au défaut)."""
    if not isinstance(valeur, dict) or not all(
        isinstance(cle, str) and cle.startswith("/") and isinstance(v, str) for cle, v in valeur.items()
    ):
        raise ValidationError({champ: "Dictionnaire { route : texte } attendu."})
    return {cle: v.strip() for cle, v in valeur.items() if v.strip()}
