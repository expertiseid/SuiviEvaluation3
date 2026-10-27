"""
Calculs de taux/statut d'alerte : volontairement non stockés en base pour
éviter toute désynchronisation si un seuil ou une valeur cible change après
coup. Toujours recalculés à la volée par les serializers/endpoints.
"""
from decimal import Decimal

from django.db.models import Sum


def taux_realisation(valeur_realisee: Decimal, valeur_cible: Decimal) -> float:
    if not valeur_cible:
        return 0.0
    return round(float(valeur_realisee) / float(valeur_cible) * 100, 1)


def paliers_pour_projet(projet):
    """
    Palette de paliers d'alerte effective d'un projet : la sienne si elle en
    a définie, sinon la palette globale par défaut — jamais vide tant qu'au
    moins un palier global existe (voir migration de seed).
    """
    from .models import PalierAlerte

    if projet is not None:
        paliers = list(PalierAlerte.objects.filter(projet=projet).order_by("borne_min"))
        if paliers:
            return paliers
    # Grille globale : les trois FK de portée doivent être vides (une portée non-vide,
    # même avec projet=None, appartient à un indicateur ou une activité précis, pas au global).
    return list(
        PalierAlerte.objects.filter(projet__isnull=True, indicateur__isnull=True, activite__isnull=True).order_by(
            "borne_min"
        )
    )


def paliers_pour(*, indicateur=None, activite=None, projet=None):
    """
    Résout la palette effective d'un indicateur OU d'une activité, avec la
    chaîne d'héritage Indicateur/Activité > Projet > Global — chacun sans
    grille propre hérite du niveau supérieur, jusqu'à la grille globale par
    défaut qui n'est jamais vide (voir migration de seed).
    """
    from .models import PalierAlerte

    if indicateur is not None:
        paliers = list(PalierAlerte.objects.filter(indicateur=indicateur).order_by("borne_min"))
        if paliers:
            return paliers
    if activite is not None:
        paliers = list(PalierAlerte.objects.filter(activite=activite).order_by("borne_min"))
        if paliers:
            return paliers
    return paliers_pour_projet(projet)


def palier_pour_taux(taux, paliers):
    """Le palier dont la borne_min est la plus haute tout en restant <= taux."""
    if taux is None or not paliers:
        return None
    choisi = paliers[0]
    for palier in paliers:
        if float(taux) >= palier.borne_min:
            choisi = palier
    return choisi


def valeur_realisee_totale(indicateur) -> Decimal:
    """
    Somme de toutes les ValeurIndicateur saisies : chaque saisie représente
    ce qui a été réalisé PENDANT sa période (pas un total cumulé), donc le
    total réalisé à date est leur somme, pas la dernière saisie seule.
    """
    total = indicateur.valeurs.aggregate(total=Sum("valeur_realisee"))["total"]
    return total or Decimal("0")


def indicateurs_pour_projet(projet_id):
    from django.db.models import Q

    from .models import Indicateur

    return Indicateur.objects.filter(
        Q(projet__id=projet_id) | Q(activite__projet__id=projet_id)
    ).distinct()


def supprimer_indicateur_cascade(indicateur):
    """
    ValeurIndicateur.indicateur est en PROTECT (même logique que pour Projet :
    ne jamais perdre une saisie par accident via un autre chemin de code), donc
    la suppression volontaire d'un indicateur doit d'abord supprimer ses
    valeurs saisies (qui entraînent elles-mêmes, en CASCADE, leurs pièces
    justificatives).
    """
    from django.db import transaction

    with transaction.atomic():
        indicateur.valeurs.all().delete()
        indicateur.delete()
