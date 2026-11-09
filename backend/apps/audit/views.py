from django.db.models import Q
from rest_framework.generics import get_object_or_404  # répond 404 (pas 500) si l'identifiant n'est pas un nombre
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.projects.queryset_filters import visible_projets_ids


def _projets_visibles(user):
    from apps.projects.models import Projet

    return Projet.objects.filter(id__in=visible_projets_ids(user))


def _indicateurs_visibles(user):
    from apps.indicators.models import Indicateur

    ids = visible_projets_ids(user)
    return Indicateur.objects.filter(
        Q(projet__isnull=True, activite__isnull=True) | Q(projet__id__in=ids) | Q(activite__projet__id__in=ids)
    ).distinct()


# Historiques consultables, chacun limité à ce que l'utilisateur voit déjà (mêmes règles que les fiches
# Projet et Indicateur). Tout autre modèle est refusé : ni bénéficiaires (données personnelles), ni
# plaintes (règles de confidentialité propres, historique dans le journal du dossier), ni comptes.
HISTORIQUES = {
    ("projects", "projet"): _projets_visibles,
    ("indicators", "indicateur"): _indicateurs_visibles,
}


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def historique_generique(request, app_label, model_name, object_id):
    """
    Historique des modifications d'une fiche (django-simple-history) :
    GET /api/v1/audit/{app}/{model}/{id}/historique/ — seulement pour les modèles de HISTORIQUES.
    """
    visibles = HISTORIQUES.get((app_label.lower(), model_name.lower()))
    if visibles is None:
        return Response({"detail": "Historique non disponible pour ce module."}, status=404)
    instance = get_object_or_404(visibles(request.user), pk=object_id)

    records = list(instance.history.order_by("-history_date"))
    entries = []
    for i, record in enumerate(records):
        changements = []
        if i + 1 < len(records):
            delta = record.diff_against(records[i + 1])
            changements = [
                {"champ": c.field, "ancienne_valeur": c.old, "nouvelle_valeur": c.new} for c in delta.changes
            ]
        entries.append(
            {
                "date": record.history_date,
                "utilisateur": str(record.history_user) if record.history_user else None,
                "type": record.get_history_type_display(),
                "changements": changements,
            }
        )
    return Response(entries)
