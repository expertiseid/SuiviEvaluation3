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


def taux_indicateur(indicateur, valeur=None):
    """
    Taux d'atteinte d'un indicateur (%), selon ses réglages ; None quand il n'est pas calculable (cible nulle,
    référence égale à la cible…) — jamais un chiffre trompeur.

    - `valeur` : valeur retenue (voir valeur_actuelle), par défaut celle d'aujourd'hui.
    - Progression : (niveau actuel − référence) ÷ (cible − référence) × 100. Le niveau actuel est la
      référence plus la somme des saisies (valeurs cumulables), ou la dernière valeur saisie. Une cible
      inférieure à la référence (indicateur à la baisse) se calcule de la même façon.
    - Réalisé ÷ cible : valeur ÷ cible × 100 (plus haut = mieux), ou cible ÷ valeur × 100 (plus bas = mieux).
    """
    from .models import Indicateur

    if valeur is None:
        valeur = valeur_actuelle(indicateur)
    if valeur is None:
        return None
    valeur, cible = float(valeur), float(indicateur.valeur_cible)
    reference = indicateur.valeur_reference
    if indicateur.calcul_taux == Indicateur.CalculTaux.PROGRESSION and reference is not None:
        reference = float(reference)
        if cible == reference:
            return None
        cumulable = indicateur.agregation == Indicateur.Agregation.SOMME and not indicateur.formule
        niveau = reference + valeur if cumulable else valeur
        return round((niveau - reference) / (cible - reference) * 100, 1)
    if indicateur.sens == Indicateur.Sens.BAISSE:
        if valeur <= 0:
            return 100.0 if cible >= 0 else None  # rien (ou moins) : l'objectif de baisse est atteint
        return round(max(cible, 0) / valeur * 100, 1)
    if not cible:
        return None
    return round(valeur / cible * 100, 1)


# Fréquence de collecte → durée d'une période (mois). Une saisie est attendue au plus tard une période après
# la fin de la dernière période saisie, plus un délai de collecte et de saisie.
MOIS_PAR_FREQUENCE = {"MENSUELLE": 1, "TRIMESTRIELLE": 3, "SEMESTRIELLE": 6, "ANNUELLE": 12}
DELAI_SAISIE_JOURS = 30


def _plus_mois(jour, mois):
    import calendar

    annee, mois_total = divmod(jour.month - 1 + mois, 12)
    annee, mois_suivant = jour.year + annee, mois_total + 1
    return jour.replace(year=annee, month=mois_suivant, day=min(jour.day, calendar.monthrange(annee, mois_suivant)[1]))


def actualisation(indicateur, derniere_fin=None, aujourd_hui=None):
    """
    L'indicateur est-il à jour ? {derniere_saisie, attendue_le, en_retard, jours_de_retard}. Une nouvelle valeur
    est attendue une période (selon la fréquence) après la fin de la dernière période saisie, plus un délai de
    saisie ; sans aucune saisie, à partir du début du projet ou de l'élément. Rien n'est attendu au-delà de la
    fin prévue, une fois celle-ci couverte. `derniere_fin` : déjà connue (calcul en lot ; False : aucune
    saisie), sinon lue.
    """
    import datetime

    aujourd_hui = aujourd_hui or datetime.date.today()
    if indicateur.formule:  # calculé : toujours à jour
        return {"derniere_saisie": None, "attendue_le": None, "en_retard": False, "jours_de_retard": 0}
    if derniere_fin is None:
        derniere_fin = indicateur.valeurs.order_by("-periode_fin").values_list("periode_fin", flat=True).first()
    elif derniere_fin is False:  # calcul en lot : aucune saisie
        derniere_fin = None
    element = indicateur.activite if indicateur.activite_id else indicateur.projet
    debut = getattr(element, "date_debut", None)
    fin_prevue = getattr(element, "date_fin", None)
    mois = MOIS_PAR_FREQUENCE.get(indicateur.frequence_collecte, 12)
    if derniere_fin is not None and fin_prevue is not None and derniere_fin >= fin_prevue:
        attendue = None  # toute la période prévue est couverte
    elif derniere_fin is not None:
        attendue = _plus_mois(derniere_fin, mois) + datetime.timedelta(days=DELAI_SAISIE_JOURS)
    elif debut is not None:
        attendue = _plus_mois(debut, mois) + datetime.timedelta(days=DELAI_SAISIE_JOURS)
    else:
        attendue = None
    retard = (aujourd_hui - attendue).days if attendue is not None and attendue < aujourd_hui else 0
    return {"derniere_saisie": derniere_fin, "attendue_le": attendue, "en_retard": retard > 0, "jours_de_retard": retard}


def variation(indicateur):
    """
    Variation entre les deux dernières périodes saisies (valeurs approuvées) : {precedente, derniere, ecart,
    pourcent} — pourcent est None quand la valeur précédente est nulle ; None sans deux saisies.
    """
    if indicateur.formule:
        return None
    deux = list(indicateur.valeurs.order_by("-periode_fin", "-id").values_list("valeur_realisee", flat=True)[:2])
    if len(deux) < 2:
        return None
    derniere, precedente = deux
    ecart = derniere - precedente
    return {"precedente": precedente, "derniere": derniere, "ecart": ecart,
            "pourcent": round(float(ecart) / abs(float(precedente)) * 100, 1) if precedente else None}


def valeur_calculee(indicateur):
    """Valeur d'un indicateur calculé par formule (None : non calculable)."""
    from .formules import FormuleInvalide, evaluer, projets_de

    try:
        return evaluer(indicateur.formule, projets_de(indicateur))["valeur"]
    except FormuleInvalide:
        return None


def valeurs_actuelles(indicateurs) -> dict:
    """valeur_actuelle de plusieurs indicateurs en deux requêtes : {numéro : valeur} (absent : rien de saisi)."""
    from .models import Indicateur, ValeurIndicateur

    indicateurs = list(indicateurs)
    calcules = {i.pk: valeur_calculee(i) for i in indicateurs if i.formule}
    indicateurs = [i for i in indicateurs if not i.formule]
    sommes = [i.pk for i in indicateurs if i.agregation != Indicateur.Agregation.DERNIERE]
    dernieres = [i.pk for i in indicateurs if i.agregation == Indicateur.Agregation.DERNIERE]
    resultat = dict(ValeurIndicateur.objects.filter(indicateur_id__in=sommes).values("indicateur_id")
                    .annotate(t=Sum("valeur_realisee")).values_list("indicateur_id", "t")) if sommes else {}
    for numero, valeur in (ValeurIndicateur.objects.filter(indicateur_id__in=dernieres)
                           .order_by("indicateur_id", "-periode_fin", "-id").distinct("indicateur_id")
                           .values_list("indicateur_id", "valeur_realisee") if dernieres else []):
        resultat[numero] = valeur
    resultat.update({numero: valeur for numero, valeur in calcules.items() if valeur is not None})
    return resultat


def valeur_actuelle(indicateur, jusqu_au=None):
    """
    Valeur retenue (saisies approuvées) : somme des valeurs saisies, ou dernière valeur saisie selon
    l'agrégation de l'indicateur ; None si rien n'est saisi pour une « dernière valeur ». `jusqu_au` : à cette
    date de fin de période (historique).
    """
    from .models import Indicateur

    if indicateur.formule:
        return valeur_calculee(indicateur)
    valeurs = indicateur.valeurs.all()
    if jusqu_au is not None:
        valeurs = valeurs.filter(periode_fin__lte=jusqu_au)
    if indicateur.agregation == Indicateur.Agregation.DERNIERE:
        derniere = valeurs.order_by("-periode_fin", "-id").values_list("valeur_realisee", flat=True).first()
        return derniere
    return valeurs.aggregate(total=Sum("valeur_realisee"))["total"] or Decimal("0")


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

    from .models import ValeurIndicateur

    with transaction.atomic():
        ValeurIndicateur.tous.filter(indicateur=indicateur).delete()
        indicateur.delete()
