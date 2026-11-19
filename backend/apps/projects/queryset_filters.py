from django.db.models import Q

from apps.core.permissions import has_global_visibility


def visible_projets_ids(user):
    """
    Rôles à visibilité globale (Admin, Coordonnateur général, Chargé de S&E) :
    tous les projets. Les autres (Chef de projet, Animateur de terrain) :
    uniquement les projets où ils sont affectés explicitement (utilisateurs_affectes),
    ou dont la zone recoupe leurs zones_affectees.
    """
    from apps.projects.models import Projet

    if has_global_visibility(user):
        return Projet.objects.values_list("id", flat=True)

    # Plus les projets sur lesquels il a un droit précis (apps.projects.droits).
    return Projet.objects.filter(
        Q(utilisateurs_affectes=user) | Q(zones__in=user.zones_affectees.all()) | Q(droits_utilisateurs__utilisateur=user)
    ).distinct().values_list("id", flat=True)
