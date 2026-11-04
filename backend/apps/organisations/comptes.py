"""
Index des comptes (CompteOrganisation, base centrale) : quelle organisation pour quelle adresse courriel.

- Tenu à jour automatiquement : chaque enregistrement ou suppression d'un utilisateur dans l'espace
  d'une organisation met l'index à jour (signaux ci-dessous).
- Les adresses fictives (exemple, test…) ne sont pas indexées : elles ne peuvent pas recevoir le code
  de connexion, donc pas se connecter.
- Une adresse n'appartient qu'à un compte de toute la plateforme : l'écran Utilisateurs et l'inscription
  le vérifient (courriel_pris) avant d'enregistrer.
- Reconstruction complète : manage.py indexer_comptes.
"""
from django.db.models.signals import post_delete, post_save

from . import contexte
from .models import CompteOrganisation, Organisation


def normaliser(courriel) -> str:
    return (courriel or "").strip().lower()


def indexable(courriel) -> bool:
    from apps.core.courriel import adresse_fictive

    courriel = normaliser(courriel)
    return "@" in courriel and not adresse_fictive(courriel)


def organisation_du_courriel(courriel):
    """Organisation active du compte qui porte cette adresse, sinon None."""
    compte = CompteOrganisation.objects.using("central").select_related("organisation").filter(
        courriel=normaliser(courriel)).first()
    return compte.organisation if compte else None


def courriel_pris(courriel, org=None, utilisateur_id=None) -> bool:
    """Adresse déjà portée par un autre compte de la plateforme (ou par une inscription en cours) ?"""
    from apps.accounts.models import DemandeInscription

    courriel = normaliser(courriel)
    if not indexable(courriel):
        return False
    autres = CompteOrganisation.objects.using("central").filter(courriel=courriel)
    if org is not None and utilisateur_id is not None:
        autres = autres.exclude(organisation=org, utilisateur_id=utilisateur_id)
    if autres.exists():
        return True
    return DemandeInscription.objects.using("central").filter(courriel__iexact=courriel).exclude(
        statut__in=[DemandeInscription.Statut.REFUSEE, DemandeInscription.Statut.ACTIVEE]).exists()


def synchroniser(utilisateur, org=None):
    """Remet à jour l'entrée de ce compte (dans l'espace courant, ou celui donné)."""
    org = org or contexte.courante()
    if org is None or org.pk is None:
        return
    CompteOrganisation.objects.using("central").filter(organisation=org, utilisateur_id=utilisateur.pk).delete()
    courriel = normaliser(utilisateur.email)
    if indexable(courriel) and not CompteOrganisation.objects.using("central").filter(courriel=courriel).exists():
        CompteOrganisation.objects.using("central").create(courriel=courriel, organisation=org, utilisateur_id=utilisateur.pk)


def _apres_enregistrement(sender, instance, **kwargs):
    if contexte.actif() and contexte.courante() is not None:
        synchroniser(instance)


def _apres_suppression(sender, instance, **kwargs):
    org = contexte.courante()
    if contexte.actif() and org is not None:
        CompteOrganisation.objects.using("central").filter(organisation=org, utilisateur_id=instance.pk).delete()


def brancher():
    from apps.accounts.models import User

    post_save.connect(_apres_enregistrement, sender=User, dispatch_uid="index-comptes-enregistrement")
    post_delete.connect(_apres_suppression, sender=User, dispatch_uid="index-comptes-suppression")


def reconstruire(sortie=None):
    """Index complet, organisation par organisation ; renvoie les adresses en double (non indexées)."""
    from apps.accounts.models import User

    doublons = []
    for org in Organisation.objects.using("central").exclude(statut=Organisation.Statut.EN_ATTENTE).order_by("pk"):
        with contexte.dans_organisation(org):
            for u in User.objects.all():
                courriel = normaliser(u.email)
                deja = CompteOrganisation.objects.using("central").filter(courriel=courriel).exclude(
                    organisation=org, utilisateur_id=u.pk).first()
                if indexable(courriel) and deja:
                    doublons.append(f"{courriel} : {org.sous_domaine} ({u.username}) et {deja.organisation.sous_domaine}")
                    continue
                synchroniser(u, org)
    return doublons
