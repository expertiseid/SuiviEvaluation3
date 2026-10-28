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
    from .verrou import verrou_desactive

    # Suppression complète : permise même pour un projet clôturé (voir verrou.py).
    with transaction.atomic(), verrou_desactive():
        activites = Activite.objects.filter(projet=projet)
        sous_activites = SousActivite.objects.filter(activite__in=activites)
        JalonLivrable.objects.filter(activite__in=activites).delete()
        TauxManuel.tous.filter(activite__in=activites).delete()

        indicateurs = Indicateur.objects.filter(Q(projet=projet) | Q(activite__in=activites))

        ValeurIndicateur.tous.filter(indicateur__in=indicateurs).delete()
        indicateurs.delete()

        PointSuivi.tous.filter(Q(activite__in=activites) | Q(sous_activite__in=sous_activites)).delete()
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
        TauxManuel.tous.filter(activite=activite).delete()
        indicateurs = Indicateur.objects.filter(activite=activite)
        ValeurIndicateur.tous.filter(indicateur__in=indicateurs).delete()
        indicateurs.delete()

        sous_activites = SousActivite.objects.filter(activite=activite)
        PointSuivi.tous.filter(Q(activite=activite) | Q(sous_activite__in=sous_activites)).delete()
        sous_activites.delete()
        activite.delete()


# Champs de planification recopiés lors d'une duplication ; les réalisations (quantités et
# budgets réalisés, dates réelles, statut, suivis, taux manuels, validations) repartent de zéro.
CHAMPS_DUPLIQUES_ACTIVITE = (
    "projet_id", "description", "code_activite", "commentaire", "axe_strategique_id", "budget_alloue",
    "valeur_reference", "quantite_prevue", "unite_quantite", "date_debut", "date_fin", "date_rappel",
    "responsable_id", "equipe_responsable_id", "methode_calcul", "methode_agregation", "poids",
)
CHAMPS_DUPLIQUES_SOUS_ACTIVITE = (
    "libelle", "axe_strategique_id", "quantite_prevue", "unite_quantite", "date_debut", "date_fin", "poids",
)


def dupliquer_activite(activite, parent_id=..., suffixe=" (copie)"):
    """
    Copie un élément de la planification avec tout ce qui est en dessous (éléments imbriqués,
    sous-activités, jalons et livrables), à la même place (même parent) par défaut. Seule la
    planification est copiée : la copie démarre sans aucune réalisation.
    """
    from .models import Activite, JalonLivrable, SousActivite

    with transaction.atomic():
        copie = Activite(
            libelle=f"{activite.libelle}{suffixe}"[:300],
            activite_parent_id=activite.activite_parent_id if parent_id is ... else parent_id,
            **{champ: getattr(activite, champ) for champ in CHAMPS_DUPLIQUES_ACTIVITE},
        )
        copie.save()
        copie.responsables.set(activite.responsables.all())
        for sous_activite in activite.sous_activites.all():
            SousActivite.objects.create(
                activite=copie, **{champ: getattr(sous_activite, champ) for champ in CHAMPS_DUPLIQUES_SOUS_ACTIVITE}
            )
        for jalon in activite.jalons_livrables.all():
            JalonLivrable.objects.create(
                activite=copie, type=jalon.type, libelle=jalon.libelle, poids=jalon.poids, date_prevue=jalon.date_prevue
            )
        for enfant in activite.enfants.all():
            dupliquer_activite(enfant, parent_id=copie.id, suffixe="")
        synchroniser_projets_associes_activite(copie)
    return copie


def supprimer_sous_activite_cascade(sous_activite):
    from apps.suivi.models import PointSuivi

    with transaction.atomic():
        PointSuivi.tous.filter(sous_activite=sous_activite).delete()
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
