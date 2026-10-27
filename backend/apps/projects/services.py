"""
Suppression en cascade d'un Projet — les FK de la hiérarchie sont en
PROTECT (choix délibéré, pour ne jamais perdre une arborescence par
accident via un autre chemin de code), donc la suppression volontaire d'un
projet doit désimbriquer manuellement, des feuilles vers la racine, dans
une transaction.
"""
from django.db import transaction
from django.db.models import Q


def supprimer_projet_cascade(projet):
    from apps.beneficiaries.models import ParticipationProjet
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.suivi.models import PointSuivi

    from .models import Activite, JalonLivrable, SousActivite, TauxManuel

    with transaction.atomic():
        activites = Activite.objects.filter(projet=projet)
        sous_activites = SousActivite.objects.filter(activite__in=activites)
        JalonLivrable.objects.filter(activite__in=activites).delete()
        TauxManuel.objects.filter(activite__in=activites).delete()

        indicateurs = Indicateur.objects.filter(Q(projet=projet) | Q(activite__in=activites))

        ValeurIndicateur.objects.filter(indicateur__in=indicateurs).delete()
        indicateurs.delete()

        PointSuivi.objects.filter(Q(activite__in=activites) | Q(sous_activite__in=sous_activites)).delete()
        sous_activites.delete()
        # activite_parent est en PROTECT : puisque TOUS les éléments de ce
        # projet sont supprimés ensemble, on casse d'abord les liens
        # parent/enfant entre eux (plutôt que de calculer un ordre de
        # suppression feuilles-vers-racine) avant le bulk delete.
        activites.update(activite_parent=None)
        activites.delete()

        ParticipationProjet.objects.filter(projet=projet).delete()

        # Documents/Dossiers/Financements/NiveauActivite sont déjà en CASCADE
        # sur Projet, supprimés automatiquement par le projet.delete() ci-dessous.
        projet.delete()


def synchroniser_projets_associes_equipe(equipe):
    for activite in equipe.activites.all():
        synchroniser_projets_associes_activite(activite)


def synchroniser_projets_associes_activite(activite):
    """
    Un intervenant référencé comme responsable d'une activité, ou comme
    membre de son équipe responsable, doit apparaître dans l'onglet
    « Équipe de projet » du projet concerné sans geste manuel supplémentaire.
    """
    projet = activite.projet
    intervenants = list(activite.responsables.all())
    if activite.equipe_responsable_id:
        intervenants += list(activite.equipe_responsable.membres.all())
    for intervenant in intervenants:
        intervenant.projets_associes.add(projet)


def supprimer_activite_cascade(activite):
    from apps.indicators.models import Indicateur, ValeurIndicateur
    from apps.suivi.models import PointSuivi

    from .models import JalonLivrable, SousActivite, TauxManuel

    with transaction.atomic():
        # Les éléments imbriqués (activite_parent) doivent être supprimés
        # avant leur parent (activite_parent est en PROTECT) — récursif, quel
        # que soit le nombre de niveaux.
        for enfant in list(activite.enfants.all()):
            supprimer_activite_cascade(enfant)

        JalonLivrable.objects.filter(activite=activite).delete()
        TauxManuel.objects.filter(activite=activite).delete()
        indicateurs = Indicateur.objects.filter(activite=activite)
        ValeurIndicateur.objects.filter(indicateur__in=indicateurs).delete()
        indicateurs.delete()

        sous_activites = SousActivite.objects.filter(activite=activite)
        PointSuivi.objects.filter(Q(activite=activite) | Q(sous_activite__in=sous_activites)).delete()
        sous_activites.delete()
        activite.delete()


def supprimer_sous_activite_cascade(sous_activite):
    from apps.suivi.models import PointSuivi

    with transaction.atomic():
        PointSuivi.objects.filter(sous_activite=sous_activite).delete()
        sous_activite.delete()


def nommer_niveaux(projet, noms):
    """
    Donne un nom aux premiers niveaux de la planification d'un projet (ex :
    ["Objectif général", "Objectif spécifique", "Activité"]) — sans jamais
    renommer un niveau déjà nommé.
    """
    from .models import NiveauActivite

    deja_nommes = set(NiveauActivite.objects.filter(projet=projet).values_list("profondeur", flat=True))
    NiveauActivite.objects.bulk_create(
        [
            NiveauActivite(projet=projet, profondeur=profondeur, nom_niveau=nom)
            for profondeur, nom in enumerate(noms)
            if profondeur not in deja_nommes
        ]
    )
