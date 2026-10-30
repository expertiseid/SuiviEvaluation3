"""
Contrôle de cohérence des données saisies.

Deux usages :
- à la saisie : avertissements_saisie() signale tout de suite ce qui cloche dans un point de
  suivi ou une valeur d'indicateur qu'on vient d'enregistrer (non bloquant) ;
- rapport par projet : controler_projet() passe en revue planification, suivis, indicateurs et
  budgets, et renvoie chaque incohérence avec sa gravité et l'élément concerné.

Gravité : « erreur » (donnée certainement fausse : fin avant début, période dans le futur,
valeur en % au-delà de 100…) ou « attention » (à vérifier : dépassement de cible, dates hors du
projet, saisies qui se chevauchent…). Rien n'est bloqué : les règles de saisie restent celles
des formulaires.
"""
from dataclasses import asdict, dataclass

from django.utils import timezone

ERREUR = "erreur"
ATTENTION = "attention"


@dataclass
class Incoherence:
    gravite: str
    categorie: str  # Planification, Suivi, Indicateurs, Budget
    element: str
    message: str
    lien: str = ""


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else "?"


def _nombre(valeur):
    return f"{float(valeur):,.2f}".rstrip("0").rstrip(".").replace(",", " ")


# ------------------------------------------------------------------------------- à la saisie

def _chevauchements(saisie, autres):
    return [a for a in autres if a.periode_debut <= saisie.periode_fin and a.periode_fin >= saisie.periode_debut]


def avertissements_saisie(saisie) -> list[str]:
    """Incohérences d'un point de suivi ou d'une valeur d'indicateur qu'on vient d'enregistrer."""
    from apps.indicators.models import ValeurIndicateur
    from apps.suivi.models import PointSuivi

    messages = []
    aujourdhui = timezone.localdate()
    if saisie.periode_fin > aujourdhui:
        messages.append(f"La période se termine dans le futur ({_fmt(saisie.periode_fin)}) : une réalisation ne peut pas encore avoir eu lieu.")
    if saisie.periode_fin < saisie.periode_debut:
        messages.append("La fin de la période est avant son début.")

    if isinstance(saisie, PointSuivi):
        cible = saisie.activite or saisie.sous_activite
        projet = saisie.activite.projet if saisie.activite else saisie.sous_activite.activite.projet
        filtre = {"activite": saisie.activite} if saisie.activite else {"sous_activite": saisie.sous_activite}
        autres = PointSuivi.tous.filter(**filtre).exclude(pk=saisie.pk)
        if _chevauchements(saisie, autres):
            messages.append("Cette période chevauche une autre saisie de la même activité : les quantités risquent d'être comptées deux fois.")
        if (cible.date_debut and saisie.periode_fin < cible.date_debut) or (cible.date_fin and saisie.periode_debut > cible.date_fin):
            messages.append(f"La période est en dehors des dates prévues de l'activité ({_fmt(cible.date_debut)} → {_fmt(cible.date_fin)}).")
        if saisie.periode_fin < projet.date_debut or saisie.periode_debut > projet.date_fin:
            messages.append(f"La période est en dehors des dates du projet ({_fmt(projet.date_debut)} → {_fmt(projet.date_fin)}).")
        if cible.quantite_prevue:
            total = sum(float(p.quantite_realisee or 0) for p in PointSuivi.tous.filter(**filtre))
            if total > float(cible.quantite_prevue):
                messages.append(
                    f"Le total réalisé ({_nombre(total)} {cible.unite_quantite}) dépasse la quantité prévue "
                    f"({_nombre(cible.quantite_prevue)}) : à vérifier."
                )
        if saisie.activite and saisie.budget_realise and saisie.activite.budget_alloue:
            total = sum(float(p.budget_realise or 0) for p in PointSuivi.tous.filter(activite=saisie.activite))
            if total > float(saisie.activite.budget_alloue):
                messages.append(
                    f"Le budget dépensé ({_nombre(total)} FCFA) dépasse le budget alloué à l'activité ({_nombre(saisie.activite.budget_alloue)} FCFA)."
                )
    elif isinstance(saisie, ValeurIndicateur):
        indicateur = saisie.indicateur
        if _chevauchements(saisie, ValeurIndicateur.tous.filter(indicateur=indicateur).exclude(pk=saisie.pk)):
            messages.append("Cette période chevauche une autre valeur du même indicateur : elles s'additionnent.")
        if indicateur.unite.strip() == "%" and saisie.valeur_realisee > 100:
            messages.append("Valeur supérieure à 100 alors que l'indicateur est en %.")
        if saisie.valeur_realisee < 0:
            messages.append("Valeur négative.")
    return messages


# ------------------------------------------------------------------------- rapport par projet

def controler_projet(projet) -> list[dict]:
    from apps.indicators.models import ValeurIndicateur
    from apps.indicators.services import indicateurs_pour_projet
    from apps.suivi.models import PointSuivi

    from .budgets import avertissements_budget, total_budget
    from .models import Activite
    from .taux import ArbreTaux

    aujourdhui = timezone.localdate()
    resultat = []
    lien_planif = f"/projets/{projet.id}"
    lien_suivi = f"/suivi/{projet.id}"

    def ajouter(gravite, categorie, element, message, lien=lien_planif):
        resultat.append(Incoherence(gravite, categorie, element, message, lien))

    if projet.date_fin < projet.date_debut:
        ajouter(ERREUR, "Planification", projet.code, "La date de fin du projet est avant sa date de début.")

    # Chaîne des documents stratégiques : projet rattaché à un document qui n'est pas du dernier maillon.
    from apps.strategy.chaine import avertissements_projet

    for message in avertissements_projet(projet):
        ajouter(ATTENTION, "Stratégie", projet.code, message, lien=f"/strategie/{projet.cadre_strategique_id}")

    activites = list(Activite.objects.filter(projet=projet).prefetch_related("sous_activites"))
    par_id = {a.id: a for a in activites}
    arbre = ArbreTaux(projet)
    for a in activites:
        if a.date_debut and a.date_fin and a.date_fin < a.date_debut:
            ajouter(ERREUR, "Planification", a.libelle, f"Fin ({_fmt(a.date_fin)}) avant le début ({_fmt(a.date_debut)}).")
        if (a.date_debut and a.date_debut < projet.date_debut) or (a.date_fin and a.date_fin > projet.date_fin):
            ajouter(ATTENTION, "Planification", a.libelle,
                    f"Dates ({_fmt(a.date_debut)} → {_fmt(a.date_fin)}) en dehors de celles du projet ({_fmt(projet.date_debut)} → {_fmt(projet.date_fin)}).")
        parent = par_id.get(a.activite_parent_id)
        if parent and parent.date_debut and parent.date_fin and a.date_debut and a.date_fin and (
            a.date_debut < parent.date_debut or a.date_fin > parent.date_fin
        ):
            ajouter(ATTENTION, "Planification", a.libelle, f"Dates en dehors de celles de « {parent.libelle} ».")
        for sa in a.sous_activites.all():
            if sa.date_debut and sa.date_fin and sa.date_fin < sa.date_debut:
                ajouter(ERREUR, "Planification", sa.libelle, "Fin avant le début (sous-activité).")
            elif a.date_debut and a.date_fin and sa.date_debut and sa.date_fin and (sa.date_debut < a.date_debut or sa.date_fin > a.date_fin):
                ajouter(ATTENTION, "Planification", sa.libelle, f"Dates en dehors de celles de son activité « {a.libelle} ».")

        resultat_taux = arbre.resultat(a.id)
        for avertissement in resultat_taux.avertissements:
            ajouter(ATTENTION, "Planification", a.libelle, avertissement)
        if resultat_taux.methode == "QUANTITE" and not arbre.enfants[a.id] and not a.quantite_prevue:
            ajouter(ATTENTION, "Planification", a.libelle, "Calcul par quantité sans quantité prévue : le taux ne peut pas être calculé.")
        if resultat_taux.taux is not None and resultat_taux.taux > 100:
            ajouter(ATTENTION, "Suivi", a.libelle, f"Taux de réalisation de {resultat_taux.taux} % : la cible est dépassée, à vérifier.", lien_suivi)
        if a.statut == Activite.Statut.REALISEE and resultat_taux.taux is not None and resultat_taux.taux < 100:
            ajouter(ATTENTION, "Suivi", a.libelle, f"Marquée « Réalisée » mais taux de {resultat_taux.taux} %.", lien_suivi)
        if a.budget_alloue and a.budget_realise and a.budget_realise > a.budget_alloue:
            ajouter(ATTENTION, "Budget", a.libelle,
                    f"Dépensé ({_nombre(a.budget_realise)} FCFA) supérieur au budget alloué ({_nombre(a.budget_alloue)} FCFA).", lien_suivi)

    for element_id, messages in avertissements_budget(activites).items():
        for message in messages:
            ajouter(ATTENTION, "Budget", par_id[element_id].libelle, message)
    alloue = total_budget(activites, "budget_alloue")
    if projet.budget_total and alloue > projet.budget_total:
        ajouter(ATTENTION, "Budget", projet.code,
                f"Les budgets des activités ({_nombre(alloue)} FCFA) dépassent le budget total du projet ({_nombre(projet.budget_total)} FCFA).")

    # Saisies de suivi (toutes, y compris en attente : elles finiront par compter).
    points = list(PointSuivi.tous.filter(activite__projet=projet).select_related("activite"))
    points += list(PointSuivi.tous.filter(sous_activite__activite__projet=projet).select_related("sous_activite"))
    par_cible = {}
    for p in points:
        cible = p.activite or p.sous_activite
        par_cible.setdefault((type(cible).__name__, cible.id), []).append(p)
        if p.periode_fin > aujourdhui:
            ajouter(ERREUR, "Suivi", cible.libelle, f"Saisie pour une période future ({_fmt(p.periode_debut)} → {_fmt(p.periode_fin)}).", lien_suivi)
        if p.periode_fin < projet.date_debut or p.periode_debut > projet.date_fin:
            ajouter(ATTENTION, "Suivi", cible.libelle, f"Saisie ({_fmt(p.periode_debut)} → {_fmt(p.periode_fin)}) en dehors des dates du projet.", lien_suivi)
    for saisies in par_cible.values():
        saisies.sort(key=lambda p: (p.periode_debut, p.id))
        for precedente, suivante in zip(saisies, saisies[1:]):
            if suivante.periode_debut <= precedente.periode_fin:
                cible = suivante.activite or suivante.sous_activite
                ajouter(ATTENTION, "Suivi", cible.libelle,
                        f"Saisies qui se chevauchent ({_fmt(precedente.periode_debut)} → {_fmt(precedente.periode_fin)} et "
                        f"{_fmt(suivante.periode_debut)} → {_fmt(suivante.periode_fin)}) : risque de double compte.", lien_suivi)

    for indicateur in indicateurs_pour_projet(projet.id):
        valeurs = list(ValeurIndicateur.tous.filter(indicateur=indicateur).order_by("periode_debut", "id"))
        lien = f"/indicateurs/{indicateur.id}"
        for v in valeurs:
            if v.periode_fin > aujourdhui:
                ajouter(ERREUR, "Indicateurs", indicateur.libelle, f"Valeur pour une période future ({_fmt(v.periode_fin)}).", lien)
            if indicateur.unite.strip() == "%" and v.valeur_realisee > 100:
                ajouter(ERREUR, "Indicateurs", indicateur.libelle, f"Valeur de {_nombre(v.valeur_realisee)} alors que l'indicateur est en %.", lien)
        for precedente, suivante in zip(valeurs, valeurs[1:]):
            if suivante.periode_debut <= precedente.periode_fin:
                ajouter(ATTENTION, "Indicateurs", indicateur.libelle, "Valeurs dont les périodes se chevauchent : elles s'additionnent.", lien)
        if indicateur.unite.strip() == "%" and indicateur.valeur_cible > 100:
            ajouter(ERREUR, "Indicateurs", indicateur.libelle, "Cible supérieure à 100 alors que l'indicateur est en %.", lien)

    ordre = {ERREUR: 0, ATTENTION: 1}
    return [asdict(i) for i in sorted(resultat, key=lambda i: (ordre[i.gravite], i.categorie, i.element))]
