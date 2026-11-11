"""
Suppression volontaire d'un bénéficiaire — ses participations aux projets et
les signalements de doublon le concernant n'ont de sens que rattachés à lui
(contrairement à Projet, PROTECT n'est pas là pour empêcher la suppression
mais pour ne jamais la faire fuiter par un autre chemin de code), donc on les
supprime avec lui plutôt que de bloquer l'opération.
"""


def supprimer_beneficiaire_cascade(beneficiaire):
    from apps.core.effacement import effacement_definitif

    from ..models import ParticipationProjet, SignalementDoublon

    # Sans reste dans l'historique (apps.core.effacement) : droit à l'effacement.
    with effacement_definitif():
        SignalementDoublon.objects.filter(beneficiaire_1=beneficiaire).delete()
        SignalementDoublon.objects.filter(beneficiaire_2=beneficiaire).delete()
        ParticipationProjet.objects.filter(beneficiaire=beneficiaire).delete()
        beneficiaire.delete()
