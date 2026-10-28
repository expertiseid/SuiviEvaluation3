"""
Périodes de rapportage : quand la saisie est-elle ouverte pour un projet ?

- Réglage général (ParametresRapportage) : contrôle inactif → saisie toujours ouverte ; actif →
  ouverte seulement pendant une période de rapportage générale ou propre au projet.
- Réglage du projet (Projet.saisie) : « Selon le réglage général », « Toujours ouverte », ou
  « Fermée, sauf pendant les périodes propres au projet » (les périodes générales ne
  l'ouvrent pas : moyen de pression sur un projet en retard de rapportage).
- Périmètre fermé (Projet.perimetre_fermeture, sinon réglage général) : les réalisations
  seulement (points de suivi, valeurs d'indicateurs, taux manuels, avancement des tâches,
  achèvement et validation des jalons et livrables), ou tout le projet.

L'administrateur n'est jamais bloqué (corrections). Le contrôle est appliqué à l'enregistrement
(apps.projects.verrou), donc aussi aux imports Excel.
"""
from dataclasses import dataclass

from django.utils import timezone

from .models import FenetreRapportage, ParametresRapportage, PerimetreFermeture, Projet


@dataclass
class EtatSaisie:
    ouverte: bool
    perimetre: str  # ce qui est fermé quand la saisie l'est
    message: str  # explication à afficher (vide si ouverte sans contrôle)
    fenetre: FenetreRapportage | None = None  # période en cours
    prochaine: FenetreRapportage | None = None


def _texte_fenetre(f):
    return f"« {f.libelle} » (du {f.date_debut:%d/%m/%Y} au {f.date_fin:%d/%m/%Y})"


def etat_saisie(projet, date=None, parametres=None) -> EtatSaisie:
    date = date or timezone.localdate()
    parametres = parametres or ParametresRapportage.courants()
    perimetre = projet.perimetre_fermeture or parametres.perimetre

    if projet.saisie == Projet.Saisie.OUVERTE or (projet.saisie == Projet.Saisie.HERITE and not parametres.controle_actif):
        return EtatSaisie(True, perimetre, "")

    fenetres = FenetreRapportage.objects.filter(projet=projet)
    if projet.saisie == Projet.Saisie.HERITE:
        fenetres = FenetreRapportage.objects.filter(projet__isnull=True) | fenetres
    courante = fenetres.filter(date_debut__lte=date, date_fin__gte=date).order_by("date_fin").first()
    if courante is not None:
        return EtatSaisie(True, perimetre, f"Période de rapportage ouverte : {_texte_fenetre(courante)}.", courante)

    prochaine = fenetres.filter(date_debut__gt=date).order_by("date_debut").first()
    quoi = "la saisie des réalisations est fermée" if perimetre == PerimetreFermeture.REALISATIONS else "le projet est en lecture seule"
    suite = f" Prochaine période de rapportage : {_texte_fenetre(prochaine)}." if prochaine else " Aucune période de rapportage n'est prévue."
    return EtatSaisie(False, perimetre, f"Hors période de rapportage, {quoi}.{suite}", None, prochaine)


# Champs dont la modification est une « réalisation » (le reste de ces objets est de la planification).
CHAMPS_REALISATION = {
    "SousActivite": ("avancement", "statut", "quantite_realisee"),
    "JalonLivrable": ("achevement", "valide", "date_validation"),
}
MODELES_REALISATION = ("PointSuivi", "ValeurIndicateur", "TauxManuel")


def est_une_realisation(instance) -> bool:
    nom = type(instance).__name__
    if nom in MODELES_REALISATION:
        return True
    champs = CHAMPS_REALISATION.get(nom)
    if not champs or instance.pk is None:
        return False
    ancien = type(instance).objects.filter(pk=instance.pk).values(*champs).first()
    return ancien is not None and any(ancien[c] != getattr(instance, c) for c in champs)
