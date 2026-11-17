"""
Budget et efficience (tableau de bord) : budget initial et révisé, engagé, dépensé, solde, taux
d'engagement et d'exécution financière, écart entre dépenses attendues à date et réelles, lignes en
dépassement, financements acquis, reçus (décaissés par les bailleurs) et restant à trouver, coûts par
bénéficiaire, par activité réalisée et par unité produite (prévu / réel).

Les montants des activités sont additionnés sans double compte (apps.projects.budgets) : dans chaque
branche, seul compte le niveau le plus bas où un montant est saisi. Quelques requêtes pour tous les projets.
"""
import datetime
from collections import defaultdict
from decimal import Decimal

ECARTS_UNITAIRES_MAX = 15


def _pourcent(partie, total):
    return round(float(partie) / float(total) * 100, 1) if total else None


def _total(activites, champ, comptees):
    return sum((getattr(a, champ) or Decimal("0") for a in activites if a.id in comptees), Decimal("0"))


def finances(projet_ids, aujourd_hui=None) -> dict:
    from django.db.models import Sum

    from apps.beneficiaries.models import ParticipationProjet
    from apps.partners.models import Financement, RallongeFinancement
    from apps.suivi.services import valeur_attendue_a

    from .budgets import activites_comptees
    from .models import Activite, Projet

    aujourd_hui = aujourd_hui or datetime.date.today()
    projets = list(Projet.objects.filter(id__in=projet_ids).only("id", "code", "budget_total", "fonds_propres"))
    activites = list(Activite.objects.filter(projet_id__in=projet_ids).only(
        "id", "projet_id", "activite_parent_id", "code_activite", "libelle", "statut", "budget_alloue", "budget_revise",
        "budget_engage", "budget_realise", "quantite_prevue", "quantite_realisee", "unite_quantite", "date_debut", "date_fin"))
    avec_enfants = {a.activite_parent_id for a in activites if a.activite_parent_id}
    comptees = {champ: activites_comptees(activites, champ)
                for champ in ("budget_alloue", "budget_applicable", "budget_engage", "budget_realise")}

    def bloc(liste):
        initial = _total(liste, "budget_alloue", comptees["budget_alloue"])
        revise = _total(liste, "budget_applicable", comptees["budget_applicable"])
        engage = _total(liste, "budget_engage", comptees["budget_engage"])
        depense = _total(liste, "budget_realise", comptees["budget_realise"])
        # Dépense attendue aujourd'hui : chaque budget compté, réparti régulièrement entre ses dates.
        attendu = sum((Decimal(str(valeur_attendue_a(aujourd_hui, a.date_debut, a.date_fin, 0, a.budget_applicable)))
                       for a in liste if a.id in comptees["budget_applicable"] and a.date_debut and a.date_fin),
                      Decimal("0"))
        return {
            "budget_initial": initial, "budget_revise": revise, "engage": engage, "depense": depense,
            "solde_non_engage": revise - engage, "reste_a_depenser": revise - depense,
            # Rien d'engagé saisi : taux inconnu (et non 0 %).
            "taux_engagement": _pourcent(engage, revise) if any(a.budget_engage is not None for a in liste) else None,
            "taux_execution": _pourcent(depense, revise),
            "depense_attendue_a_date": attendu.quantize(Decimal("1")), "ecart_a_date": (depense - attendu).quantize(Decimal("1")),
        }

    # Lignes budgétaires (activités de terrain) dont la dépense dépasse le budget applicable.
    terrain = [a for a in activites if a.id not in avec_enfants]
    budgetees = [a for a in terrain if a.budget_applicable]
    depassements = [a for a in budgetees if (a.budget_realise or 0) > a.budget_applicable]

    # Financements acquis (conventions et rallonges), reçus des bailleurs, et besoin restant.
    acquis_par_projet = defaultdict(Decimal)
    recu_par_projet = defaultdict(Decimal)
    recu_saisi = False
    for f in Financement.objects.filter(projet_id__in=projet_ids).values("projet_id", "montant_finance", "montant_recu"):
        acquis_par_projet[f["projet_id"]] += f["montant_finance"] or 0
        recu_par_projet[f["projet_id"]] += f["montant_recu"] or 0
        recu_saisi = recu_saisi or f["montant_recu"] is not None
    for r in (RallongeFinancement.objects.filter(financement__projet_id__in=projet_ids)
              .values("financement__projet_id").annotate(t=Sum("montant"))):
        acquis_par_projet[r["financement__projet_id"]] += r["t"] or 0
    budget_projets = sum((p.budget_total or 0 for p in projets), Decimal("0"))
    fonds_propres = sum((p.fonds_propres or 0 for p in projets), Decimal("0"))
    acquis, recu = sum(acquis_par_projet.values(), Decimal("0")), sum(recu_par_projet.values(), Decimal("0"))

    beneficiaires = ParticipationProjet.objects.filter(projet_id__in=projet_ids).values("beneficiaire").distinct().count()
    realisees = [a for a in terrain if a.statut == Activite.Statut.REALISEE and a.budget_realise]
    global_ = bloc(activites)

    # Coût unitaire prévu (budget ÷ quantité prévue) et réel (dépense ÷ quantité réalisée), par activité.
    unitaires = []
    for a in terrain:
        if a.budget_applicable and a.quantite_prevue and a.budget_realise and a.quantite_realisee:
            prevu = a.budget_applicable / a.quantite_prevue
            reel = a.budget_realise / a.quantite_realisee
            unitaires.append({"code": a.code_activite, "libelle": a.libelle, "unite": a.unite_quantite,
                              "prevu": prevu.quantize(Decimal("1")), "reel": reel.quantize(Decimal("1")),
                              "ecart_pourcent": _pourcent(reel - prevu, prevu), "projet_id": a.projet_id})
    codes = {p.id: p.code for p in projets}
    for u in unitaires:
        u["projet"] = codes.get(u.pop("projet_id"), "")

    par_projet_activites = defaultdict(list)
    for a in activites:
        par_projet_activites[a.projet_id].append(a)
    return {
        **global_,
        "budget_projets": budget_projets, "fonds_propres": fonds_propres,
        "financements_acquis": acquis, "financements_recus": recu,
        "taux_decaissement": _pourcent(recu, acquis) if recu_saisi else None,
        "besoin_de_financement": max(budget_projets - fonds_propres - acquis, Decimal("0")),
        "lignes_budgetees": len(budgetees), "lignes_en_depassement": len(depassements),
        "part_lignes_en_depassement": _pourcent(len(depassements), len(budgetees)),
        "beneficiaires_uniques": beneficiaires,
        "cout_par_beneficiaire": (global_["depense"] / beneficiaires).quantize(Decimal("1")) if beneficiaires else None,
        "cout_par_activite_realisee": (sum((a.budget_realise for a in realisees), Decimal("0")) / len(realisees)).quantize(Decimal("1"))
        if realisees else None,
        "couts_unitaires": sorted(unitaires, key=lambda u: -abs(u["ecart_pourcent"] or 0))[:ECARTS_UNITAIRES_MAX],
        "par_projet": sorted(
            ({"code": p.code, **{c: v for c, v in bloc(par_projet_activites.get(p.id, [])).items()
                                 if c in ("budget_revise", "engage", "depense", "taux_engagement", "taux_execution", "ecart_a_date")},
              "financements_acquis": acquis_par_projet.get(p.id, Decimal("0")), "financements_recus": recu_par_projet.get(p.id, Decimal("0"))}
             for p in projets),
            key=lambda ligne: ligne["code"]),
    }
