"""
Filtres du tableau de bord consolidé : année ou plage de dates, façon
d'appliquer la plage aux dates du projet, et statuts. Toutes les
statistiques du tableau de bord sont ensuite calculées sur les projets
retenus.
"""
import datetime

from rest_framework.exceptions import ValidationError

from apps.projects.models import Projet

# Façons de rattacher un projet à la plage [debut, fin] :
PERIODE_ACTIFS = "actifs"  # en cours à un moment de la plage (chevauchement)
PERIODE_DEMARRES = "demarres"  # date de début dans la plage
PERIODE_DEMARRES_FIN_PREVUE = "demarres_fin_prevue"  # début ET fin prévue dans la plage
PERIODE_DEMARRES_TERMINES = "demarres_termines"  # début et fin dans la plage, projet clôturé
PERIODES = (PERIODE_ACTIFS, PERIODE_DEMARRES, PERIODE_DEMARRES_FIN_PREVUE, PERIODE_DEMARRES_TERMINES)


def _date(valeur, nom):
    try:
        return datetime.date.fromisoformat(valeur)
    except ValueError:
        raise ValidationError({nom: "Date invalide (format attendu : AAAA-MM-JJ)."})


def plage_depuis(params):
    """(debut, fin) depuis ?annee=2026 ou ?date_debut=…&date_fin=… ; (None, None) sans filtre de dates."""
    annee = params.get("annee")
    if annee:
        if not annee.isdigit():
            raise ValidationError({"annee": "Année invalide."})
        return datetime.date(int(annee), 1, 1), datetime.date(int(annee), 12, 31)
    debut = _date(params["date_debut"], "date_debut") if params.get("date_debut") else None
    fin = _date(params["date_fin"], "date_fin") if params.get("date_fin") else None
    if debut and fin and debut > fin:
        raise ValidationError({"date_fin": "La date de fin doit suivre la date de début."})
    return debut, fin


def filtrer_projets(queryset, params):
    """Applique les filtres du tableau de bord à un queryset de Projet."""
    statuts = [s for s in params.get("statuts", "").split(",") if s]
    inconnus = set(statuts) - set(Projet.Statut.values)
    if inconnus:
        raise ValidationError({"statuts": f"Statut(s) inconnu(s) : {', '.join(sorted(inconnus))}."})
    if statuts:
        queryset = queryset.filter(statut__in=statuts)

    debut, fin = plage_depuis(params)
    periode = params.get("periode") or PERIODE_ACTIFS
    if periode not in PERIODES:
        raise ValidationError({"periode": "Valeur inconnue."})
    if not (debut or fin):
        return queryset

    def dans_plage(champ):
        filtres = {}
        if debut:
            filtres[f"{champ}__gte"] = debut
        if fin:
            filtres[f"{champ}__lte"] = fin
        return filtres

    if periode == PERIODE_ACTIFS:
        if debut:
            queryset = queryset.filter(date_fin__gte=debut)
        if fin:
            queryset = queryset.filter(date_debut__lte=fin)
        return queryset
    queryset = queryset.filter(**dans_plage("date_debut"))
    if periode in (PERIODE_DEMARRES_FIN_PREVUE, PERIODE_DEMARRES_TERMINES):
        queryset = queryset.filter(**dans_plage("date_fin"))
    if periode == PERIODE_DEMARRES_TERMINES:
        queryset = queryset.filter(statut=Projet.Statut.CLOTURE)
    return queryset
