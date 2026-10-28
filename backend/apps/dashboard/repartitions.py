"""
Répartitions complémentaires du tableau de bord consolidé (blocs
affichables à la demande) : pays et zones, détail du budget, bailleurs,
partenaires de consortium et de mise en œuvre, cibles.
"""
from collections import defaultdict
from decimal import Decimal


from django.db.models import Sum

from apps.partners.models import Financement, RallongeFinancement

PAYS_LIBELLE = {"BF": "Burkina Faso", "ML": "Mali", "NE": "Niger", "CI": "Côte d'Ivoire", "SN": "Sénégal",
                "TG": "Togo", "BJ": "Bénin", "GH": "Ghana", "TD": "Tchad", "MR": "Mauritanie", "GN": "Guinée"}


def _lignes(compteurs):
    """{cle: {"nombre", "montant", "projets"}} → liste triée par montant décroissant."""
    return sorted(
        (
            {"libelle": cle, "nombre": len(v["projets"]), "montant": v["montant"], "projets": sorted(v["projets"])}
            for cle, v in compteurs.items()
        ),
        key=lambda l: (-l["montant"], l["libelle"]),
    )


def _compteur():
    return defaultdict(lambda: {"montant": Decimal("0"), "projets": set()})


def repartitions_projets(projets):
    projets = list(
        projets.select_related("partenaire_bailleur", "partenaire_mise_en_oeuvre").prefetch_related(
            "partenaires_consortium", "zones__niveau_administratif"
        )
    )

    # ----- Pays et zones (zones d'intervention renseignées sur la fiche projet) -----
    par_pays = _compteur()
    par_zone = defaultdict(_compteur)  # niveau → zone → compteur
    for p in projets:
        for code in p.pays or []:
            par_pays[PAYS_LIBELLE.get(code, code)]["projets"].add(p.code)
            par_pays[PAYS_LIBELLE.get(code, code)]["montant"] += p.budget_total
        for zone in p.zones.all():
            c = par_zone[(zone.niveau_administratif.ordre, zone.niveau_administratif.nom_niveau)][zone.nom]
            c["projets"].add(p.code)
            c["montant"] += p.budget_total
    zones = [
        {"niveau": nom_niveau, "zones": _lignes(compteurs)}
        for (_ordre, nom_niveau), compteurs in sorted(par_zone.items())
    ]

    # ----- Budget total et détail -----
    ids = [p.id for p in projets]
    financements = Financement.objects.filter(projet_id__in=ids).select_related("bailleur", "projet")
    finance_par_projet = defaultdict(Decimal)
    par_bailleur = _compteur()
    rallonges = dict(
        RallongeFinancement.objects.filter(financement__in=financements)
        .values("financement").annotate(total=Sum("montant")).values_list("financement", "total")
    )
    for f in financements:
        montant = f.montant_finance + rallonges.get(f.id, 0)  # rallonges comprises
        finance_par_projet[f.projet_id] += montant
        par_bailleur[f.bailleur.nom]["projets"].add(f.projet.code)
        par_bailleur[f.bailleur.nom]["montant"] += montant
    # Projet sans financement détaillé mais avec un bailleur principal : on
    # lui attribue la part non couverte par les fonds propres.
    for p in projets:
        if p.id not in finance_par_projet and p.partenaire_bailleur:
            part = max(p.budget_total - p.fonds_propres, Decimal("0"))
            par_bailleur[p.partenaire_bailleur.nom]["projets"].add(p.code)
            par_bailleur[p.partenaire_bailleur.nom]["montant"] += part
            finance_par_projet[p.id] += part

    from apps.projects.budgets import total_budget
    from apps.projects.models import Activite

    activites_budget = list(
        Activite.objects.filter(projet__id__in=ids).only("id", "activite_parent_id", "budget_alloue", "budget_realise")
    )
    budget = {
        "total": sum((p.budget_total for p in projets), Decimal("0")),
        "fonds_propres": sum((p.fonds_propres for p in projets), Decimal("0")),
        "financements_bailleurs": sum(finance_par_projet.values(), Decimal("0")),
        "alloue_activites": total_budget(activites_budget, "budget_alloue"),
        "depense_activites": total_budget(activites_budget, "budget_realise"),
        "par_projet": [
            {
                "code": p.code,
                "nom": p.nom,
                "total": p.budget_total,
                "fonds_propres": p.fonds_propres,
                "financements_bailleurs": finance_par_projet.get(p.id, Decimal("0")),
            }
            for p in sorted(projets, key=lambda p: p.code)
        ],
    }

    # ----- Partenaires (pas de montant propre : budget total des projets concernés) -----
    par_consortium = _compteur()
    par_mise_en_oeuvre = _compteur()
    for p in projets:
        for partenaire in p.partenaires_consortium.all():
            par_consortium[partenaire.nom]["projets"].add(p.code)
            par_consortium[partenaire.nom]["montant"] += p.budget_total
        if p.partenaire_mise_en_oeuvre:
            par_mise_en_oeuvre[p.partenaire_mise_en_oeuvre.nom]["projets"].add(p.code)
            par_mise_en_oeuvre[p.partenaire_mise_en_oeuvre.nom]["montant"] += p.budget_total

    # ----- Cibles (fiche projet) -----
    def somme(champ):
        return sum((getattr(p, champ) or 0 for p in projets))

    cibles = {
        "totale": somme("cible_totale"),
        "femmes": somme("cible_femmes"),
        "hommes": somme("cible_hommes"),
        "jeunes": somme("cible_jeunes"),
        "pdi": somme("cible_pdi"),
        "par_projet": [
            {
                "code": p.code,
                "totale": p.cible_totale or 0,
                "femmes": p.cible_femmes or 0,
                "hommes": p.cible_hommes or 0,
                "jeunes": p.cible_jeunes or 0,
                "pdi": p.cible_pdi or 0,
            }
            for p in sorted(projets, key=lambda p: p.code)
        ],
    }

    return {
        "projets_par_pays": _lignes(par_pays),
        "projets_par_zone": zones,
        "budget_detail": budget,
        "projets_par_bailleur": _lignes(par_bailleur),
        "projets_par_consortium": _lignes(par_consortium),
        "projets_par_mise_en_oeuvre": _lignes(par_mise_en_oeuvre),
        "cibles": cibles,
    }
