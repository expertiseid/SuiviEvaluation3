"""
Synchronise la "photo actuelle" d'une Activite/SousActivite
(quantite_realisee/budget_realise/statut) sur la SOMME de ses PointSuivi —
même principe que taux_realisation_actuel côté Indicateur, qui dérive du
total des ValeurIndicateur plutôt que d'un champ saisi à part : on garde un
seul historique source de vérité (PointSuivi, une ligne = ce qui a été
accompli PENDANT une période précise), et les champs sur
Activite/SousActivite ne sont qu'une valeur dérivée mise en cache pour les
écrans qui n'ont pas besoin de l'historique complet (Planification,
exports, rapports).
"""
from decimal import Decimal

from django.db.models import Max, Min, Sum


def valeur_attendue_a(date, debut, fin, depart, arrivee):
    """
    Port Python de `valeurAttendueA` (frontend/src/utils/suivi.ts) : valeur
    interpolée linéairement à `date` entre (debut, depart) et (fin, arrivee).
    Doit rester IDENTIQUE à la version frontend — les deux calculent la même
    ligne « progression attendue » et le même « attendu aujourd'hui », côté
    écran pour l'un, côté exports Excel/PDF pour l'autre.
    """
    depart = float(depart)
    arrivee = float(arrivee)
    if not debut or not fin or fin <= debut:
        return arrivee
    t = min(1.0, max(0.0, (date - debut).days / (fin - debut).days))
    return depart + (arrivee - depart) * t


def taux_de(valeur, cible):
    if valeur is None or not cible:
        return None
    return round(float(valeur) / float(cible) * 1000) / 10


def ecart_texte(valeur_reelle, valeur_attendue, unite=""):
    if valeur_reelle is None or valeur_attendue is None:
        return None
    ecart = round((float(valeur_reelle) - float(valeur_attendue)) * 10) / 10
    suffixe = f" {unite}" if unite else ""
    if ecart > 0:
        return f"{ecart}{suffixe} de plus que prévu à cette date"
    if ecart < 0:
        return f"{abs(ecart)}{suffixe} de moins que prévu à cette date"
    return "exactement comme prévu à cette date"


def construire_dashboard_suivi(projet) -> dict:
    """
    Construit le même dict que renvoie l'API `suivi_dashboard_projet` —
    extrait ici pour être réutilisé tel quel par les exports Excel/PDF, qui
    ont besoin de repartir exactement des mêmes chiffres que ceux affichés à
    l'écran (pas de recalcul séparé qui pourrait diverger).
    """
    from apps.indicators.services import (
        indicateurs_pour_projet,
        palier_pour_taux,
        paliers_pour,
        taux_realisation,
        valeur_realisee_totale,
    )
    from apps.projects.models import Activite
    from apps.reports.services import statut_global, taux_execution_financiere_global

    def _serialiser_palier(palier):
        if palier is None:
            return None
        return {"id": palier.id, "libelle": palier.libelle, "couleur": palier.couleur, "borne_min": palier.borne_min}

    indicateurs_detail = []
    for indicateur in indicateurs_pour_projet(projet.id).select_related("activite"):
        taux = taux_realisation(valeur_realisee_totale(indicateur), indicateur.valeur_cible)
        historique = []
        cumul = Decimal("0")
        for v in indicateur.valeurs.order_by("periode_fin"):
            cumul += v.valeur_realisee
            historique.append(
                {
                    "id": v.id,
                    "periode_debut": v.periode_debut,
                    "periode_fin": v.periode_fin,
                    "valeur_realisee": v.valeur_realisee,
                    "valeur_cumulee": cumul,
                    "commentaire": v.commentaire,
                    "taux": taux_realisation(cumul, indicateur.valeur_cible),
                }
            )
        if indicateur.activite_id and indicateur.activite.date_debut and indicateur.activite.date_fin:
            periode_debut_planifiee = indicateur.activite.date_debut
            periode_fin_planifiee = indicateur.activite.date_fin
        else:
            periode_debut_planifiee = projet.date_debut
            periode_fin_planifiee = projet.date_fin
        palier = palier_pour_taux(taux, paliers_pour(indicateur=indicateur, projet=projet))
        indicateurs_detail.append(
            {
                "id": indicateur.id,
                "libelle": indicateur.libelle,
                "unite": indicateur.unite,
                "valeur_reference": indicateur.valeur_reference,
                "valeur_cible": indicateur.valeur_cible,
                "taux_actuel": taux,
                "palier_actuel": _serialiser_palier(palier),
                "periode_debut_planifiee": periode_debut_planifiee,
                "periode_fin_planifiee": periode_fin_planifiee,
                "historique": historique,
            }
        )

    activites_detail = []
    activites = (
        Activite.objects.filter(projet=projet)
        .prefetch_related("sous_activites", "points_suivi", "sous_activites__points_suivi")
    )
    from apps.projects.taux import ArbreTaux

    arbre_taux = ArbreTaux(projet)
    for activite in activites:
        historique = []
        cumul_quantite = Decimal("0")
        cumul_budget = Decimal("0")
        for p in activite.points_suivi.order_by("periode_fin"):
            cumul_quantite += p.quantite_realisee or Decimal("0")
            cumul_budget += p.budget_realise or Decimal("0")
            historique.append(
                {
                    "id": p.id,
                    "periode_debut": p.periode_debut,
                    "periode_fin": p.periode_fin,
                    "quantite_realisee": p.quantite_realisee,
                    "quantite_cumulee": cumul_quantite,
                    "budget_realise": p.budget_realise,
                    "budget_cumule": cumul_budget,
                    "statut": p.statut,
                    "commentaire": p.commentaire,
                }
            )
        sous_activites_detail = []
        for sous_activite in activite.sous_activites.all():
            sous_historique = []
            cumul_sous = Decimal("0")
            for p in sous_activite.points_suivi.order_by("periode_fin"):
                cumul_sous += p.quantite_realisee or Decimal("0")
                sous_historique.append(
                    {
                        "id": p.id,
                        "periode_debut": p.periode_debut,
                        "periode_fin": p.periode_fin,
                        "quantite_realisee": p.quantite_realisee,
                        "quantite_cumulee": cumul_sous,
                        "statut": p.statut,
                        "commentaire": p.commentaire,
                    }
                )
            sous_activites_detail.append(
                {
                    "id": sous_activite.id,
                    "libelle": sous_activite.libelle,
                    "statut": sous_activite.statut,
                    "quantite_prevue": sous_activite.quantite_prevue,
                    "unite_quantite": sous_activite.unite_quantite,
                    "date_debut": sous_activite.date_debut,
                    "date_fin": sous_activite.date_fin,
                    "historique": sous_historique,
                }
            )
        resultat_taux = arbre_taux.resultat(activite.id)
        taux_activite = resultat_taux.taux
        palier_activite = palier_pour_taux(taux_activite, paliers_pour(activite=activite, projet=projet))
        activites_detail.append(
            {
                "id": activite.id,
                "code_activite": activite.code_activite,
                "libelle": activite.libelle,
                "statut": activite.statut,
                "valeur_reference": activite.valeur_reference,
                "quantite_prevue": activite.quantite_prevue,
                "unite_quantite": activite.unite_quantite,
                "budget_alloue": activite.budget_alloue,
                "date_debut": activite.date_debut,
                "date_fin": activite.date_fin,
                "taux_realisation": taux_activite,
                # Méthode réglée sur l'élément (vide = héritée) et méthode appliquée (ou AGREGATION).
                "methode_calcul": activite.methode_calcul,
                "methode_calcul_effective": resultat_taux.methode,
                "taux_avertissements": resultat_taux.avertissements,
                "taux_execution_financiere": activite.taux_execution_financiere,
                "palier_actuel": _serialiser_palier(palier_activite),
                "sous_activites": sous_activites_detail,
                "historique": historique,
            }
        )

    return {
        "projet": {"id": projet.id, "code": projet.code, "nom": projet.nom, "statut": projet.statut},
        "taux_execution_physique_global": arbre_taux.taux_projet().taux,
        "taux_execution_financiere_global": taux_execution_financiere_global(projet),
        "statut_global": statut_global(projet),
        "indicateurs": indicateurs_detail,
        "activites": activites_detail,
    }


def dernier_point_suivi(activite=None, sous_activite=None):
    from .models import PointSuivi

    qs = PointSuivi.objects.filter(activite=activite) if activite else PointSuivi.objects.filter(sous_activite=sous_activite)
    return qs.order_by("-periode_fin").first()


def synchroniser_activite_depuis_suivi(activite):
    from .models import PointSuivi

    points = PointSuivi.objects.filter(activite=activite)
    totaux = points.aggregate(
        quantite=Sum("quantite_realisee"), budget=Sum("budget_realise"), debut=Min("periode_debut"), fin=Max("periode_fin")
    )
    activite.quantite_realisee = totaux["quantite"]
    activite.budget_realise = totaux["budget"]
    dernier = points.order_by("-periode_fin").first()
    if dernier and dernier.statut:
        activite.statut = dernier.statut
    champs = ["quantite_realisee", "budget_realise", "statut", "updated_at"]
    if dernier:
        # Dates réelles dérivées des saisies (suivi global ou par période) :
        # début = première période saisie ; fin = dernière période saisie,
        # seulement une fois l'activité réalisée. Sans aucune saisie, les
        # dates éventuellement renseignées à la main sont conservées.
        activite.date_debut_reelle = totaux["debut"]
        activite.date_fin_reelle = totaux["fin"] if activite.statut == "REALISEE" else None
        champs += ["date_debut_reelle", "date_fin_reelle"]
    activite.save(update_fields=champs)


def synchroniser_sous_activite_depuis_suivi(sous_activite):
    from .models import PointSuivi

    points = PointSuivi.objects.filter(sous_activite=sous_activite)
    totaux = points.aggregate(quantite=Sum("quantite_realisee"))
    sous_activite.quantite_realisee = totaux["quantite"]
    dernier = points.order_by("-periode_fin").first()
    if dernier and dernier.statut:
        sous_activite.statut = dernier.statut
    sous_activite.save(update_fields=["quantite_realisee", "statut", "updated_at"])


def realise_tranche(tranche) -> Decimal | None:
    """
    Somme des PointSuivi (activité/sous-activité) ou ValeurIndicateur
    (indicateur) dont la période est entièrement CONTENUE dans celle de la
    tranche — une saisie qui déborde la tranche n'y est pas comptée, pour ne
    jamais compter deux fois un même point sur deux tranches voisines.
    """
    if tranche.activite_id or tranche.sous_activite_id:
        return _points_suivi_tranche(tranche).aggregate(total=Sum("quantite_realisee"))["total"]

    from apps.indicators.models import ValeurIndicateur

    return ValeurIndicateur.objects.filter(
        indicateur=tranche.indicateur,
        periode_debut__gte=tranche.periode_debut,
        periode_fin__lte=tranche.periode_fin,
    ).aggregate(total=Sum("valeur_realisee"))["total"]


def budget_realise_tranche(tranche) -> Decimal | None:
    """Budget réalisé sur la tranche (activités uniquement), même règle que realise_tranche."""
    if not tranche.activite_id:
        return None
    return _points_suivi_tranche(tranche).aggregate(total=Sum("budget_realise"))["total"]


def _points_suivi_tranche(tranche):
    from .models import PointSuivi

    return PointSuivi.objects.filter(
        activite_id=tranche.activite_id,
        sous_activite_id=tranche.sous_activite_id,
        periode_debut__gte=tranche.periode_debut,
        periode_fin__lte=tranche.periode_fin,
    )


def saisies_tranche(tranche) -> list[dict]:
    """
    Saisies comptées dans le réalisé de la tranche (même règle que
    realise_tranche), dans l'ordre chronologique — affichées et exportées
    dans le suivi par période.
    """
    if tranche.activite_id or tranche.sous_activite_id:
        return [
            {
                "id": p.id,
                "periode_debut": p.periode_debut,
                "periode_fin": p.periode_fin,
                "quantite": p.quantite_realisee,
                "budget": p.budget_realise,
                "statut": p.statut,
                "commentaire": p.commentaire,
            }
            for p in _points_suivi_tranche(tranche).order_by("periode_debut", "id")
        ]

    from apps.indicators.models import ValeurIndicateur

    valeurs = ValeurIndicateur.objects.filter(
        indicateur_id=tranche.indicateur_id,
        periode_debut__gte=tranche.periode_debut,
        periode_fin__lte=tranche.periode_fin,
    ).order_by("periode_debut", "id")
    return [
        {
            "id": v.id,
            "periode_debut": v.periode_debut,
            "periode_fin": v.periode_fin,
            "quantite": v.valeur_realisee,
            "budget": None,
            "statut": "",
            "commentaire": v.commentaire,
        }
        for v in valeurs
    ]


def statut_tranche(tranche, realise, aujourdhui) -> str:
    """ATTEINTE : réalisé >= cible. EN_RETARD : échéance passée, cible non atteinte. EN_COURS : sinon."""
    if realise is not None and tranche.cible and realise >= tranche.cible:
        return "ATTEINTE"
    if tranche.periode_fin < aujourdhui:
        return "EN_RETARD"
    return "EN_COURS"


STATUT_TRANCHE_LABEL = {"ATTEINTE": "Atteinte", "EN_RETARD": "En retard", "EN_COURS": "En cours"}

# Origine des valeurs d'un élément sur une période : objectifs définis par
# l'utilisateur (TranchePlanifiee), ou pas encore définis — jamais calculés
# automatiquement, c'est à l'utilisateur de fixer les objectifs de la période.
SOURCE_SAISIE = "saisi"
SOURCE_A_DEFINIR = "a_definir"


def chevauche_periode(debut, fin, periode) -> bool | None:
    """Les dates globales de l'élément recoupent-elles la période ? None si l'élément n'a pas de dates."""
    if not debut or not fin:
        return None
    return debut <= periode.date_fin and fin >= periode.date_debut


def construire_planification_periode(periode) -> dict:
    """
    Données de l'onglet « Planification par période » pour une période —
    arborescence complète de la planification du projet (tous ses niveaux,
    librement nommés, puis sous-activités) dans l'ordre d'affichage, plus les
    indicateurs du projet.
    Pour chaque élément : ses valeurs globales, ses objectifs sur la période
    (définis par l'utilisateur, sinon « à définir ») et le réalisé sur la
    période, toujours calculé.
    Source unique de l'écran et des exports Excel/PDF de la période.
    """
    import datetime

    from apps.indicators.services import indicateurs_pour_projet
    from apps.projects.models import Activite, NiveauActivite

    from .models import TranchePlanifiee

    projet = periode.projet
    aujourdhui = datetime.date.today()
    tranches = {(t.activite_id, t.sous_activite_id, t.indicateur_id): t for t in periode.tranches.all()}
    noms_niveaux = dict(NiveauActivite.objects.filter(projet=projet).values_list("profondeur", "nom_niveau"))

    def valeurs_periode(cle, debut, fin, avec_budget):
        tranche = tranches.get(cle)
        source = SOURCE_SAISIE if tranche is not None else SOURCE_A_DEFINIR
        if tranche is None:
            # Tranche non enregistrée : seulement pour réutiliser le calcul du réalisé.
            tranche = TranchePlanifiee(
                activite_id=cle[0], sous_activite_id=cle[1], indicateur_id=cle[2],
                periode_debut=periode.date_debut, periode_fin=periode.date_fin,
            )
        saisies = saisies_tranche(tranche)
        realise = sum((x["quantite"] or Decimal("0") for x in saisies), Decimal("0"))
        budget_realise = sum((x["budget"] or Decimal("0") for x in saisies), Decimal("0")) if avec_budget else None
        return {
            "source": source,
            "tranche_id": tranche.pk,
            "dans_dates_globales": chevauche_periode(debut, fin, periode),
            "prevu_quantite": tranche.cible,
            "prevu_budget": tranche.budget if avec_budget else None,
            "debut_prevu": tranche.date_debut_prevue,
            "fin_prevue": tranche.date_fin_prevue,
            "realise_quantite": realise,
            "taux": taux_de(realise, tranche.cible),
            "budget_realise": budget_realise,
            "taux_financier": taux_de(budget_realise, tranche.budget) if avec_budget else None,
            "statut": STATUT_TRANCHE_LABEL[statut_tranche(tranche, realise, aujourdhui)]
            if source == SOURCE_SAISIE
            else "À définir",
            "commentaire": tranche.commentaire,
            "saisies": saisies,
        }

    lignes = []

    def ajouter_activite(activite, profondeur):
        lignes.append(
            {
                "type": "activite",
                "id": activite.id,
                "niveau": noms_niveaux.get(profondeur, "Activité"),
                "profondeur": profondeur,
                "code": activite.code_activite,
                "libelle": activite.libelle,
                "unite": activite.unite_quantite,
                "global_quantite": activite.quantite_prevue,
                "global_budget": activite.budget_alloue,
                "global_debut": activite.date_debut,
                "global_fin": activite.date_fin,
                **valeurs_periode((activite.id, None, None), activite.date_debut, activite.date_fin, avec_budget=True),
            }
        )
        for enfant in activite.enfants.all():
            ajouter_activite(enfant, profondeur + 1)
        for sous_activite in activite.sous_activites.all():
            lignes.append(
                {
                    "type": "sous_activite",
                    "id": sous_activite.id,
                    "niveau": "Sous-activité",
                    "profondeur": profondeur + 1,
                    "code": "",
                    "libelle": sous_activite.libelle,
                    "unite": sous_activite.unite_quantite,
                    "global_quantite": sous_activite.quantite_prevue,
                    "global_budget": None,
                    "global_debut": sous_activite.date_debut,
                    "global_fin": sous_activite.date_fin,
                    **valeurs_periode(
                        (None, sous_activite.id, None), sous_activite.date_debut, sous_activite.date_fin, avec_budget=False
                    ),
                }
            )

    racines = Activite.objects.filter(projet=projet, activite_parent__isnull=True).prefetch_related(
        "enfants", "sous_activites"
    )
    for activite in racines:
        ajouter_activite(activite, 0)

    indicateurs = []
    for indicateur in indicateurs_pour_projet(projet.id).select_related("activite").order_by("libelle"):
        # Même fenêtre que le suivi (dates de l'activité liée, sinon du projet).
        if indicateur.activite_id and indicateur.activite.date_debut and indicateur.activite.date_fin:
            debut, fin = indicateur.activite.date_debut, indicateur.activite.date_fin
        else:
            debut, fin = projet.date_debut, projet.date_fin
        indicateurs.append(
            {
                "type": "indicateur",
                "id": indicateur.id,
                "libelle": indicateur.libelle,
                "unite": indicateur.unite,
                "valeur_cible": indicateur.valeur_cible,
                "global_debut": debut,
                "global_fin": fin,
                **valeurs_periode((None, None, indicateur.id), debut, fin, avec_budget=False),
            }
        )

    elements = lignes
    # Mêmes règles que l'exécution globale (reports.services), restreintes
    # aux activités dont l'objectif de la période a été défini.
    activites_definies = [l for l in elements if l["type"] == "activite" and l["source"] == SOURCE_SAISIE]
    taux_activites = [l["taux"] for l in activites_definies if l["taux"] is not None]
    budget_prevu_defini = sum((l["prevu_budget"] or 0) for l in activites_definies)
    budget_realise_defini = sum((l["budget_realise"] or 0) for l in activites_definies)
    return {
        "projet": {"code": projet.code, "nom": projet.nom},
        "periode": {"libelle": periode.libelle, "date_debut": periode.date_debut, "date_fin": periode.date_fin},
        "lignes": lignes,
        "indicateurs": indicateurs,
        "totaux": {
            "budget_prevu": sum((l.get("prevu_budget") or 0) for l in elements),
            "budget_realise": sum((l.get("budget_realise") or 0) for l in elements),
            "nb_definis": sum(1 for l in elements if l["source"] == SOURCE_SAISIE),
            "nb_elements": len(elements),
            "taux_physique": round(sum(taux_activites) / len(taux_activites), 1) if taux_activites else None,
            "taux_financier": taux_de(budget_realise_defini, budget_prevu_defini),
        },
    }
