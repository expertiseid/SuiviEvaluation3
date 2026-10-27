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
    """Σ budget_realise / Σ budget_planifie sur toutes les activités du projet."""
    from django.db.models import Sum

    from apps.projects.models import Activite

    totaux = Activite.objects.filter(projet=projet).aggregate(
        realise=Sum("budget_realise"), planifie=Sum("budget_alloue")
    )
    planifie = totaux["planifie"] or 0
    if not planifie:
        return None
    return round(float(totaux["realise"] or 0) / float(planifie) * 100, 1)


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
