import logging

from django.core.mail import send_mail
from django.conf import settings

from .models import Notification

logger = logging.getLogger(__name__)


def notifier(destinataires, type_, titre, message="", lien="", courriel=True):
    """
    Crée une notification in-app pour chaque destinataire et tente un envoi
    email best-effort (un échec d'envoi ne doit jamais faire échouer l'action
    métier qui a déclenché la notification). `courriel=False` : dans l'application seulement.
    """
    destinataires = [d for d in destinataires if d is not None]
    notifications = Notification.objects.bulk_create(
        [
            Notification(destinataire=d, type=type_, titre=titre, message=message, lien=lien)
            for d in destinataires
        ]
    )

    emails = [d.email for d in destinataires if d.email] if courriel else []
    if emails:
        try:
            send_mail(
                subject=f"[Expertise-ID Monitora] {titre}",
                message=message or titre,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=emails,
                fail_silently=True,
            )
        except Exception:
            logger.exception("Échec de l'envoi email pour la notification '%s'", titre)

    return notifications


def notifier_par_role(roles, type_, titre, message="", lien="", exclure=None):
    from apps.accounts.models import User

    qs = User.objects.filter(role__in=roles, is_active=True)
    if exclure is not None:
        qs = qs.exclude(pk=exclure.pk)
    return notifier(list(qs), type_, titre, message, lien)


def lister_echeances(projet_ids, seuil_jours=None):
    """
    Liste des activités, sous-activités et projets (parmi projet_ids) dont
    l'échéance est proche (<=seuil_jours) ou déjà dépassée — source de vérité
    unique partagée par la commande check_deadlines (qui notifie) et le
    tableau de bord (qui affiche), pour qu'ils ne divergent jamais.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.indicators.models import ParametresAlerte
    from apps.projects.models import Activite, Projet, SousActivite

    today = timezone.localdate()
    if seuil_jours is None:
        seuil_jours = ParametresAlerte.instance().seuil_echeance_jours
    limite = today + timedelta(days=seuil_jours)

    echeances = []

    activites = Activite.objects.exclude(statut=Activite.Statut.REALISEE).filter(
        date_fin__isnull=False,
        date_fin__lte=limite,
        projet__id__in=projet_ids,
    ).select_related("projet")
    for activite in activites:
        projet = activite.projet
        echeances.append(
            {
                "type": "ACTIVITE",
                "id": activite.id,
                "libelle": activite.libelle,
                "projet_id": projet.id,
                "projet_nom": projet.nom,
                "date_fin": activite.date_fin,
                "en_retard": activite.date_fin < today,
                "lien": f"/suivi/{projet.id}#activite-{activite.id}",
            }
        )

    sous_activites = SousActivite.objects.exclude(statut=SousActivite.Statut.TERMINEE).filter(
        date_fin__isnull=False,
        date_fin__lte=limite,
        activite__projet__id__in=projet_ids,
    ).select_related("activite__projet")
    for sous_activite in sous_activites:
        projet = sous_activite.activite.projet
        echeances.append(
            {
                "type": "SOUS_ACTIVITE",
                "id": sous_activite.id,
                "activite_id": sous_activite.activite_id,
                "libelle": sous_activite.libelle,
                "projet_id": projet.id,
                "projet_nom": projet.nom,
                "date_fin": sous_activite.date_fin,
                "en_retard": sous_activite.date_fin < today,
                "lien": f"/suivi/{projet.id}#sous-activite-{sous_activite.id}",
            }
        )

    projets = Projet.objects.exclude(statut=Projet.Statut.CLOTURE).filter(id__in=projet_ids, date_fin__lte=limite)
    for projet in projets:
        echeances.append(
            {
                "type": "PROJET",
                "id": projet.id,
                "libelle": projet.nom,
                "projet_id": projet.id,
                "projet_nom": projet.nom,
                "date_fin": projet.date_fin,
                "en_retard": projet.date_fin < today,
                "est_rappel": False,
                "lien": f"/suivi/{projet.id}",
            }
        )

    # Rappels à date calendaire fixe (indépendants du seuil de jours) : une fois la date
    # atteinte, l'alerte reste active tant que la date de rappel n'est pas retirée/changée.
    activites_rappel = Activite.objects.exclude(statut=Activite.Statut.REALISEE).filter(
        date_rappel__isnull=False,
        date_rappel__lte=today,
        projet__id__in=projet_ids,
    ).select_related("projet")
    for activite in activites_rappel:
        projet = activite.projet
        echeances.append(
            {
                "type": "ACTIVITE",
                "id": activite.id,
                "libelle": activite.libelle,
                "projet_id": projet.id,
                "projet_nom": projet.nom,
                "date_fin": activite.date_rappel,
                "en_retard": False,
                "est_rappel": True,
                "lien": f"/suivi/{projet.id}#activite-{activite.id}",
            }
        )

    projets_rappel = Projet.objects.exclude(statut=Projet.Statut.CLOTURE).filter(
        id__in=projet_ids, date_rappel__isnull=False, date_rappel__lte=today
    )
    for projet in projets_rappel:
        echeances.append(
            {
                "type": "PROJET",
                "id": projet.id,
                "libelle": projet.nom,
                "projet_id": projet.id,
                "projet_nom": projet.nom,
                "date_fin": projet.date_rappel,
                "en_retard": False,
                "est_rappel": True,
                "lien": f"/suivi/{projet.id}",
            }
        )

    for echeance in echeances:
        echeance.setdefault("est_rappel", False)

    echeances.sort(key=lambda e: e["date_fin"])
    return echeances
