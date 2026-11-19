"""
Avancement et retards des activités (tableau de bord) : démarrage, achèvement, exécution à date, retards,
respect des délais, durée de réalisation, activités suspendues et annulées, jalons, activités incomplètes (sans responsable, calendrier ou
budget) et justificatifs.

On compte les activités de terrain : les éléments de la planification sans élément en dessous. Les
regroupements (objectifs, résultats…) n'ont pas d'échéance propre, ils suivent leurs activités. Tout est
calculé en quelques requêtes pour l'ensemble des projets.
"""
import datetime
from collections import defaultdict
from statistics import mean

ACTIVITES_EN_RETARD_MAX = 20


def _pourcent(partie, total):
    return round(partie / total * 100, 1) if total else None


def _moyenne(valeurs):
    return round(mean(valeurs), 1) if valeurs else None


def avancement(projet_ids, aujourd_hui=None) -> dict:
    from django.db.models import Count, Q

    from apps.documents.models import Document

    from .models import Activite, JalonLivrable, Projet

    aujourd_hui = aujourd_hui or datetime.date.today()
    terrain = (Activite.objects.filter(projet_id__in=projet_ids, enfants__isnull=True)
               .annotate(nb_responsables=Count("responsables", distinct=True)))
    activites = list(terrain.values(
        "id", "projet_id", "code_activite", "libelle", "statut", "date_debut", "date_fin", "date_debut_reelle",
        "date_fin_reelle", "budget_alloue", "responsable_id", "equipe_responsable_id", "nb_responsables"))
    ids = [a["id"] for a in activites]
    avec_documents = set(Document.objects.filter(Q(activite_id__in=ids) | Q(sous_activite__activite_id__in=ids))
                         .values_list("activite_id", "sous_activite__activite_id").distinct().iterator()) if ids else set()
    justifiees = {i for paire in avec_documents for i in paire if i is not None}
    codes = dict(Projet.objects.filter(id__in=projet_ids).values_list("id", "code"))

    def stats(toutes):
        # Les activités annulées ne sont plus prévues ; les suspendues le restent et sont comptées à part.
        liste = [a for a in toutes if a["statut"] != Activite.Statut.ANNULEE]
        prevues = len(liste)
        terminees = [a for a in liste if a["statut"] == Activite.Statut.REALISEE]
        demarrees = [a for a in liste if a["statut"] in (Activite.Statut.EN_COURS, Activite.Statut.REALISEE) or a["date_debut_reelle"]]
        attendues = [a for a in liste if a["date_fin"] and a["date_fin"] <= aujourd_hui]
        en_retard = [a for a in attendues if a["statut"] != Activite.Statut.REALISEE]
        datees = [a for a in terminees if a["date_fin"] and a["date_fin_reelle"]]
        a_temps = [a for a in datees if a["date_fin_reelle"] <= a["date_fin"]]
        return {
            "prevues": prevues,
            "suspendues": sum(1 for a in liste if a["statut"] == Activite.Statut.SUSPENDUE),
            "annulees": len(toutes) - prevues,
            "demarrees": len(demarrees),
            "terminees": len(terminees),
            "taux_demarrage": _pourcent(len(demarrees), prevues),
            "taux_achevement": _pourcent(len(terminees), prevues),
            # Exécution à date : parmi les activités dont l'échéance est passée, celles terminées.
            "attendues_a_date": len(attendues),
            "taux_execution_a_date": _pourcent(len(attendues) - len(en_retard), len(attendues)),
            "en_retard": len(en_retard),
            "part_en_retard": _pourcent(len(en_retard), prevues),
            "retard_moyen_jours": _moyenne([(aujourd_hui - a["date_fin"]).days for a in en_retard]),
            "demarrage_en_retard": sum(1 for a in liste if a["statut"] == Activite.Statut.NON_REALISEE
                                       and not a["date_debut_reelle"] and a["date_debut"] and a["date_debut"] < aujourd_hui),
            "terminees_dans_les_delais": _pourcent(len(a_temps), len(datees)),
            "retard_moyen_a_l_achevement_jours": _moyenne(
                [(a["date_fin_reelle"] - a["date_fin"]).days for a in datees if a["date_fin_reelle"] > a["date_fin"]]),
            "duree_moyenne_realisation_jours": _moyenne(
                [(a["date_fin_reelle"] - a["date_debut_reelle"]).days for a in terminees
                 if a["date_debut_reelle"] and a["date_fin_reelle"]]),
            "sans_responsable": sum(1 for a in liste if not (a["responsable_id"] or a["equipe_responsable_id"] or a["nb_responsables"])),
            "sans_calendrier": sum(1 for a in liste if not (a["date_debut"] and a["date_fin"])),
            "sans_budget": sum(1 for a in liste if not a["budget_alloue"]),
            "avec_justificatifs": _pourcent(sum(1 for a in liste if a["id"] in justifiees), prevues),
        }

    par_projet = defaultdict(list)
    for a in activites:
        par_projet[a["projet_id"]].append(a)
    jalons = list(JalonLivrable.objects.filter(activite_id__in=ids).values("achevement", "valide", "date_prevue"))
    atteint = [bool(j["valide"] or (j["achevement"] or 0) >= 100) for j in jalons]
    retards = sorted(
        (a for a in activites if a["date_fin"] and a["date_fin"] < aujourd_hui
         and a["statut"] not in (Activite.Statut.REALISEE, Activite.Statut.ANNULEE)),
        key=lambda a: a["date_fin"])
    return {
        **stats(activites),
        "jalons": {
            "total": len(jalons), "atteints": sum(atteint), "part_atteints": _pourcent(sum(atteint), len(jalons)),
            "en_retard": sum(1 for j, ok in zip(jalons, atteint) if not ok and j["date_prevue"] and j["date_prevue"] < aujourd_hui),
        },
        "par_projet": sorted(
            ({"code": codes.get(pid, ""), **{c: v for c, v in stats(liste).items()
                                              if c in ("prevues", "terminees", "taux_achevement", "taux_execution_a_date",
                                                       "en_retard", "retard_moyen_jours", "terminees_dans_les_delais",
                                                       "suspendues", "annulees")}}
             for pid, liste in par_projet.items()),
            key=lambda ligne: (-(ligne["en_retard"] or 0), ligne["code"])),
        "activites_en_retard": [
            {"projet": codes.get(a["projet_id"], ""), "code": a["code_activite"], "libelle": a["libelle"],
             "date_fin": a["date_fin"], "jours": (aujourd_hui - a["date_fin"]).days, "statut": a["statut"]}
            for a in retards[:ACTIVITES_EN_RETARD_MAX]
        ],
    }
