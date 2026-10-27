"""
Calculs agrégés de progression d'un projet — jamais stockés, toujours
recalculés à la volée pour éviter toute désynchronisation.
"""
SEUIL_STATUT_ATTEINT = 80


def taux_execution_physique_global(projet):
    """Taux du projet, agrégé selon sa méthode d'agrégation (voir apps.projects.taux)."""
    from apps.projects.taux import ArbreTaux

    return ArbreTaux(projet).taux_projet().taux


def taux_execution_financiere_global(projet):
    """Σ budget_realise / Σ budget_alloue des activités du projet, sans double compte (apps.projects.budgets)."""
    from apps.projects.budgets import total_budget
    from apps.projects.models import Activite

    activites = list(Activite.objects.filter(projet=projet).only("id", "activite_parent_id", "budget_alloue", "budget_realise"))
    planifie = total_budget(activites, "budget_alloue")
    if not planifie:
        return None
    return round(float(total_budget(activites, "budget_realise")) / float(planifie) * 100, 1)


def statut_global(projet):
    from apps.projects.models import Activite

    taux_phys = taux_execution_physique_global(projet)
    taux_fin = taux_execution_financiere_global(projet)

    en_retard = Activite.objects.filter(
        projet=projet
    ).exclude(statut=Activite.Statut.REALISEE).filter(date_fin__isnull=False)
    if any(a.alerte_retard for a in en_retard):
        return "EN_RETARD"

    if taux_phys is not None and taux_fin is not None and taux_phys >= SEUIL_STATUT_ATTEINT and taux_fin >= SEUIL_STATUT_ATTEINT:
        return "ATTEINT"
    return "EN_COURS"
