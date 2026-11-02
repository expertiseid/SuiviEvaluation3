"""
Délais et alertes du mécanisme de plaintes (lot 4).

- Échéance du dossier : le plus court des délais fixés par sa catégorie et sa priorité (sinon le
  délai par défaut du mécanisme), compté depuis la réception, plus les prolongations accordées.
- Échéance de l'étape : délai de l'étape en cours, compté depuis l'entrée dans l'étape.
- Jours calendaires ou ouvrés (sans samedis, dimanches ni jours fériés de l'organisation).
- Contrôle par la tâche planifiée (verifier_echeances), jamais au chargement des pages : rappel au
  gestionnaire quand l'échéance approche, puis retard signalé au gestionnaire et escaladé aux
  superviseurs ; au plus un rappel par dossier et par jour ; le passage en retard est inscrit au
  journal (historique des retards).
- Notifications d'événements (nouveau dossier, affectation, urgence, recours) : dans l'application
  et par courriel si le mécanisme le prévoit. Pour un dossier confidentiel, elles ne disent rien de
  son contenu et ne vont qu'aux personnes habilitées.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.constants import ROLE_ADMIN, ROLE_COORDO_GENERAL
from apps.core.vocabulaire import v

from .models import ActionDossier, Dossier, JourFerie, Mecanisme, RappelDossier, StatutDossier

# Prolongation d'un délai : réservée à ces rôles (comme la réouverture).
ROLES_PROLONGATION = {ROLE_ADMIN, ROLE_COORDO_GENERAL}
# Superviseurs destinataires des escalades et des dossiers urgents (dossiers ordinaires).
ROLES_SUPERVISION = {ROLE_ADMIN, ROLE_COORDO_GENERAL}


def ajouter_jours(depart, jours, ouvres, feries=None):
    """Date `jours` jours après `depart`, en jours calendaires ou ouvrés."""
    if not ouvres:
        return depart + timedelta(days=jours)
    if feries is None:
        feries = set(JourFerie.objects.values_list("date", flat=True))
    date = depart
    while jours > 0:
        date += timedelta(days=1)
        if date.weekday() < 5 and date not in feries:
            jours -= 1
    return date


def delai_dossier(dossier, mecanisme=None):
    """Délai de traitement (jours) : le plus court entre catégorie et priorité, sinon celui par défaut."""
    mecanisme = mecanisme or Mecanisme.courant()
    delais = [d for d in (
        dossier.categorie.delai_jours if dossier.categorie_id else None,
        dossier.categorie.parent.delai_jours if dossier.categorie_id and dossier.categorie.parent_id else None,
        dossier.priorite.delai_jours if dossier.priorite_id else None,
    ) if d]
    return min(delais) if delais else mecanisme.delai_defaut_jours


def recalculer(dossier, entree_etape=None, enregistrer=True):
    """Recalcule les échéances (après réception, classement, changement d'étape, prolongation…)."""
    mecanisme = Mecanisme.courant()
    feries = set(JourFerie.objects.values_list("date", flat=True)) if mecanisme.jours_ouvres else set()
    if entree_etape is not None:
        dossier.date_entree_etape = entree_etape
    dossier.date_entree_etape = dossier.date_entree_etape or dossier.date_reception
    dossier.echeance = ajouter_jours(dossier.date_reception, delai_dossier(dossier, mecanisme) + dossier.jours_prolongation,
                                     mecanisme.jours_ouvres, feries)
    delai_etape = dossier.etape.delai_jours if dossier.etape_id and dossier.etape.delai_jours else None
    dossier.echeance_etape = (
        ajouter_jours(dossier.date_entree_etape, delai_etape, mecanisme.jours_ouvres, feries) if delai_etape else None
    )
    if not est_en_retard(dossier):
        dossier.en_retard = False
    if enregistrer:
        Dossier.objects.filter(pk=dossier.pk).update(
            echeance=dossier.echeance, echeance_etape=dossier.echeance_etape,
            date_entree_etape=dossier.date_entree_etape, en_retard=dossier.en_retard,
        )
    return dossier


def recalculer_ouverts():
    """Après un changement de délai, de calendrier ou de jours ouvrés dans le paramétrage."""
    ouverts = Dossier.objects.exclude(statut=StatutDossier.CLOTURE).select_related("categorie__parent", "priorite", "etape")
    for dossier in ouverts:
        recalculer(dossier)


def est_en_retard(dossier, aujourdhui=None):
    aujourdhui = aujourdhui or timezone.localdate()
    if dossier.statut == StatutDossier.CLOTURE:
        return False
    return bool((dossier.echeance and dossier.echeance < aujourdhui) or (dossier.echeance_etape and dossier.echeance_etape < aujourdhui))


@transaction.atomic
def prolonger(dossier, auteur, donnees):
    """Prolongation motivée du délai, par un rôle autorisé ; tracée au journal."""
    if dossier.statut == StatutDossier.CLOTURE:
        raise ValidationError({"detail": v("Ce dossier est clôturé : rouvrez-le d'abord.")})
    if auteur.role not in ROLES_PROLONGATION:
        raise ValidationError({"detail": v("La prolongation est réservée à l'Administrateur et au Coordonnateur général.")})
    try:
        jours = int(donnees.get("jours"))
    except (TypeError, ValueError):
        jours = 0
    erreurs = {}
    if not 1 <= jours <= 180:
        erreurs["jours"] = v("Indiquez un nombre de jours entre 1 et 180.")
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        erreurs["motif"] = v("Indiquez le motif de la prolongation.")
    if erreurs:
        raise ValidationError(erreurs)
    ancienne = dossier.echeance
    dossier.jours_prolongation += jours
    Dossier.objects.filter(pk=dossier.pk).update(jours_prolongation=dossier.jours_prolongation)
    recalculer(dossier)
    ActionDossier.objects.create(
        dossier=dossier, type=ActionDossier.Type.PROLONGATION, auteur=auteur, texte=motif,
        details={"jours": jours, "de": ancienne.isoformat() if ancienne else "", "a": dossier.echeance.isoformat()},
    )
    return dossier


# --- Notifications -------------------------------------------------------------------------------

def superviseurs(dossier, sauf=None):
    """Destinataires des escalades : habilités du circuit confidentiel, sinon Administrateurs et coordination."""
    from apps.accounts.models import User

    from .traitement import personnes_habilitees

    if dossier.sensible:
        qs = personnes_habilitees(dossier)
    else:
        qs = User.objects.filter(is_active=True, role__in=ROLES_SUPERVISION)
    if sauf is not None:
        qs = qs.exclude(pk=sauf.pk)
    return list(qs.exclude(pk__in=dossier.mis_en_cause_utilisateurs.values("pk")).distinct())


# Coupé pendant la génération des données de démonstration (seed_demo_plaintes).
NOTIFICATIONS_ACTIVES = True


def notifier_dossier(dossier, destinataires, titre_ordinaire, titre_confidentiel, message=""):
    """Notification sur un dossier ; un dossier confidentiel n'est désigné que par son numéro, sans contenu."""
    from apps.notifications.models import Notification
    from apps.notifications.services import notifier

    if not NOTIFICATIONS_ACTIVES:
        return []

    # Jamais une personne mise en cause.
    vises = set(dossier.mis_en_cause_utilisateurs.values_list("pk", flat=True))
    destinataires = [d for d in {d.pk: d for d in destinataires if d is not None}.values() if d.pk not in vises]
    if not destinataires:
        return []
    titre = titre_confidentiel if dossier.sensible else titre_ordinaire
    if dossier.sensible:
        message = v("Connectez-vous à la plateforme pour consulter ce dossier.")
    return notifier(destinataires, Notification.Type.PLAINTE, titre, message, f"/plaintes/dossiers/{dossier.pk}",
                    courriel=Mecanisme.courant().notifications_courriel)


def destinataires_premiere_etape(dossier):
    """Personnes chargées de la première étape du circuit (personne désignée, sinon titulaires du rôle)."""
    from apps.accounts.models import User

    etape = dossier.etape
    if etape is None:
        return []
    if etape.responsable_id:
        return [etape.responsable]
    if etape.role_id and not dossier.sensible:
        return list(User.objects.filter(is_active=True, role=etape.role.code))
    return []


def notifier_reception(dossier):
    destinataires = destinataires_premiere_etape(dossier)
    if dossier.sensible:
        destinataires += superviseurs(dossier)
    notifier_dossier(dossier, destinataires, v(f"Nouveau dossier {dossier.numero} à prendre en charge"),
                     v(f"Un nouveau dossier confidentiel ({dossier.numero}) vous concerne"), dossier.description[:300])
    if dossier.priorite_id and dossier.priorite.urgente:
        notifier_urgence(dossier)


def notifier_urgence(dossier):
    notifier_dossier(dossier, superviseurs(dossier), v(f"Dossier urgent {dossier.numero} à traiter immédiatement"),
                     v(f"Dossier confidentiel urgent {dossier.numero} à traiter immédiatement"), v("Ce dossier est marqué urgent : il demande un traitement immédiat."))


def notifier_affectation(dossier):
    notifier_dossier(dossier, [dossier.responsable], v(f"Le dossier {dossier.numero} vous a été affecté"),
                     v(f"Un dossier confidentiel ({dossier.numero}) vous a été affecté"), dossier.description[:300])


def notifier_recours(dossier):
    notifier_dossier(dossier, superviseurs(dossier), v(f"Recours sur le dossier {dossier.numero} : à réaffecter"),
                     v(f"Recours sur le dossier confidentiel {dossier.numero}"),
                     v("Le plaignant conteste la réponse : le dossier doit être réexaminé par une autre personne."))


# --- Contrôle planifié ----------------------------------------------------------------------------

def verifier_echeances(aujourdhui=None):
    """
    Rappels et escalades du jour. Renvoie le nombre de dossiers signalés. Rejouable sans doublon :
    au plus un rappel par dossier et par jour (RappelDossier).
    """
    aujourdhui = aujourdhui or timezone.localdate()
    mecanisme = Mecanisme.courant()
    if not mecanisme.actif:
        return 0
    limite = aujourdhui + timedelta(days=mecanisme.rappel_jours_avant)
    signales = 0
    ouverts = Dossier.objects.exclude(statut=StatutDossier.CLOTURE).exclude(echeance=None).select_related(
        "responsable", "circuit", "etape", "categorie", "priorite")
    for dossier in ouverts:
        retard = est_en_retard(dossier, aujourdhui)
        proche = not retard and dossier.echeance <= limite
        if retard and not dossier.en_retard:
            # Historique des retards : le passage en retard est inscrit au journal.
            Dossier.objects.filter(pk=dossier.pk).update(en_retard=True)
            ActionDossier.objects.create(
                dossier=dossier, type=ActionDossier.Type.RETARD,
                texte=v("Échéance dépassée."),
                details={"echeance": dossier.echeance.isoformat(),
                         "echeance_etape": dossier.echeance_etape.isoformat() if dossier.echeance_etape else ""},
            )
        if not (retard or proche):
            continue
        _, nouveau = RappelDossier.objects.get_or_create(dossier=dossier, date=aujourdhui,
                                                         defaults={"motif": "RETARD" if retard else "PROCHE"})
        if not nouveau:
            continue
        signales += 1
        if retard:
            destinataires = [dossier.responsable] if dossier.responsable else []
            if mecanisme.escalade_active or not destinataires:
                destinataires += superviseurs(dossier)
            notifier_dossier(dossier, destinataires, v(f"Le dossier {dossier.numero} est en retard"),
                             v(f"Le dossier confidentiel {dossier.numero} est en retard"),
                             v("L'échéance de traitement est dépassée."))
        else:
            destinataires = [dossier.responsable] if dossier.responsable else superviseurs(dossier)
            notifier_dossier(dossier, destinataires, v(f"Échéance proche pour le dossier {dossier.numero}"),
                             v(f"Échéance proche pour le dossier confidentiel {dossier.numero}"),
                             v("L'échéance de traitement approche."))
    signaler_conservation(aujourdhui)
    return signales


def signaler_conservation(aujourdhui):
    """
    Dossiers arrivés au terme de leur durée de conservation : proposés aux Administrateurs pour
    anonymisation (une notification par jour, rien n'est supprimé sans confirmation).
    """
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    from apps.notifications.services import notifier

    from .confidentiel import a_anonymiser

    nombre = len(a_anonymiser(aujourdhui=aujourdhui))
    if not nombre or not NOTIFICATIONS_ACTIVES:
        return 0
    titre = v(f"{nombre} dossier(s) de plaintes à anonymiser (fin de conservation)")
    admins = User.objects.filter(is_active=True, role=ROLE_ADMIN)
    deja = Notification.objects.filter(type=Notification.Type.PLAINTE, titre=titre, created_at__date=aujourdhui)
    destinataires = [u for u in admins if not deja.filter(destinataire=u).exists()]
    notifier(destinataires, Notification.Type.PLAINTE, titre,
             v("La durée de conservation est écoulée : confirmez l'anonymisation de ces dossiers."),
             "/plaintes?vue=a_anonymiser", courriel=Mecanisme.courant().notifications_courriel)
    return nombre
