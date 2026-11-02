"""
Habilitation aux dossiers confidentiels (lot 9).

- Distincte des rôles : seule une personne habilitée peut être responsable d'une étape d'un circuit
  confidentiel, voir les dossiers confidentiels de ce circuit, s'en voir confier un ou en être notifiée.
  L'Administrateur garde son accès d'office (choix de l'organisation) : il n'a pas besoin d'habilitation.
- Double validation : une personne (Administrateur ou habilitée) la demande, avec un motif ; une
  deuxième personne, Administrateur ou habilitée, la valide. Personne ne s'habilite soi-même, et la
  personne qui demande ne valide pas sa propre demande.
- Première habilitation de l'organisation (aucune deuxième personne ne peut valider) : un code est
  envoyé par courriel à la personne qui demande ; une fois le code saisi, l'habilitation prend effet
  après un délai de sécurité de 24 heures.
- Retrait immédiat (à la requête suivante, l'accès est recalculé à chaque requête) ; les dossiers
  confidentiels ouverts confiés à la personne lui sont retirés, pour être réaffectés.
- Toute demande, validation, refus, entrée en vigueur et retrait est inscrit au journal d'audit et
  notifié aux personnes habilitées et aux Administrateurs.
"""
import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import ROLE_ADMIN
from apps.core.audit import A, auditer
from apps.core.vocabulaire import v

from .models import HabilitationSensible, StatutDossier

H = HabilitationSensible.Statut
DELAI_PREMIERE = timedelta(hours=24)


def _empreinte(code: str) -> str:
    return hashlib.sha256((code or "").strip().upper().encode()).hexdigest()


def condition_active(prefixe=""):
    """Habilitation en vigueur : active, ou confirmée et sortie du délai de sécurité."""
    return Q(**{f"{prefixe}statut": H.ACTIVE}) | Q(**{f"{prefixe}statut": H.EN_DELAI, f"{prefixe}active_le__lte": timezone.now()})


def habilitations_actives():
    return HabilitationSensible.objects.filter(condition_active())


def est_habilite(utilisateur) -> bool:
    """Administrateur, ou habilitation en vigueur."""
    if utilisateur is None or not utilisateur.is_active:
        return False
    return utilisateur.role == ROLE_ADMIN or habilitations_actives().filter(utilisateur=utilisateur).exists()


def ids_habilites():
    return set(habilitations_actives().values_list("utilisateur_id", flat=True))


def valideurs_possibles(habilitation):
    """Personnes qui peuvent valider : Administrateurs actifs et habilités, sauf le demandeur et l'intéressé."""
    from apps.accounts.models import User

    exclus = {habilitation.utilisateur_id, habilitation.demandee_par_id}
    return User.objects.filter(is_active=True).filter(Q(role=ROLE_ADMIN) | Q(pk__in=ids_habilites())).exclude(pk__in=exclus)


def _nom(u):
    from .traitement import nom_personne

    return nom_personne(u)


def _notifier(habilitation, titre, avec_valideurs=False):
    """Prévient les habilités, les Administrateurs et la personne concernée (sans motif ni détail)."""
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    from apps.notifications.services import notifier

    from .models import Mecanisme

    destinataires = set(User.objects.filter(is_active=True).filter(Q(role=ROLE_ADMIN) | Q(pk__in=ids_habilites())))
    destinataires.add(habilitation.utilisateur)
    if avec_valideurs:
        destinataires |= set(valideurs_possibles(habilitation))
    notifier([d for d in destinataires if d.is_active], Notification.Type.PLAINTE, titre,
             v("Plaintes et retours › Paramétrage › Habilitations."), "/plaintes/parametrage?onglet=habilitations",
             courriel=Mecanisme.courant().notifications_courriel)


def _auditer(auteur, habilitation, operation):
    auditer(auteur, A.HABILITATION, _nom(habilitation.utilisateur) or habilitation.utilisateur.username,
            operation=operation, habilitation=habilitation.pk)


def _peut_gerer(auteur):
    if not est_habilite(auteur):
        raise PermissionDenied(v("Seuls l'Administrateur et les personnes habilitées gèrent les habilitations confidentielles."))


@transaction.atomic
def demander(auteur, donnees):
    from apps.accounts.models import User

    _peut_gerer(auteur)
    cible = User.objects.filter(pk=donnees.get("utilisateur") if str(donnees.get("utilisateur", "")).isdigit() else None,
                                is_active=True).first()
    if cible is None:
        raise ValidationError({"utilisateur": v("Choisissez une personne active.")})
    if cible.pk == auteur.pk:
        raise ValidationError({"utilisateur": v("Personne ne peut s'attribuer à soi-même une habilitation : une autre personne doit la demander.")})
    if cible.role == ROLE_ADMIN:
        raise ValidationError({"utilisateur": v("L'Administrateur accède déjà aux dossiers confidentiels.")})
    if HabilitationSensible.objects.filter(utilisateur=cible, statut__in=HabilitationSensible.EN_COURS).exists():
        raise ValidationError({"utilisateur": v("Cette personne a déjà une habilitation en cours ou en attente.")})
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        raise ValidationError({"motif": v("Indiquez pourquoi cette personne doit accéder aux dossiers confidentiels.")})
    habilitation = HabilitationSensible.objects.create(utilisateur=cible, motif=motif, demandee_par=auteur)
    if not valideurs_possibles(habilitation).exists():
        # Première habilitation : personne d'autre ne peut valider. Code par courriel, puis délai.
        code = secrets.token_hex(3).upper()
        habilitation.premiere = True
        habilitation.empreinte_code = _empreinte(code)
        habilitation.save(update_fields=["premiere", "empreinte_code"])
        _envoyer_code(auteur, code)
        _auditer(auteur, habilitation, "demande_premiere")
    else:
        _auditer(auteur, habilitation, "demande")
        transaction.on_commit(lambda: _notifier(
            habilitation, v(f"Habilitation confidentielle à valider pour {_nom(cible)}"), avec_valideurs=True))
    return habilitation


def _envoyer_code(auteur, code):
    from django.conf import settings
    from django.core.mail import send_mail

    if not auteur.email:
        raise ValidationError({"detail": v("Votre compte n'a pas d'adresse courriel : le code de confirmation ne peut pas être envoyé.")})
    texte = v(f"Code de confirmation de la première habilitation confidentielle : {code}\n\n"
              "Saisissez-le dans Plaintes et retours › Paramétrage › Habilitations. L'habilitation prendra "
              "effet 24 heures après la confirmation. Si vous n'êtes pas à l'origine de cette demande, ne "
              "saisissez pas ce code et prévenez votre organisation.")
    transaction.on_commit(lambda: send_mail(v("Confirmation d'une habilitation confidentielle"), texte,
                                            getattr(settings, "DEFAULT_FROM_EMAIL", None), [auteur.email],
                                            fail_silently=True))


def _en_attente(pk):
    habilitation = HabilitationSensible.objects.select_for_update().filter(pk=pk).first()
    if habilitation is None or habilitation.statut != H.EN_ATTENTE:
        raise ValidationError({"detail": v("Cette demande n'est plus en attente.")})
    return habilitation


@transaction.atomic
def valider(auteur, pk, donnees):
    """{accepter: bool, commentaire} — par une deuxième personne, Administrateur ou habilitée."""
    habilitation = _en_attente(pk)
    if habilitation.premiere:
        raise ValidationError({"detail": v("Première habilitation : elle se confirme avec le code reçu par courriel.")})
    if auteur.pk in (habilitation.utilisateur_id, habilitation.demandee_par_id):
        raise PermissionDenied(v("La validation doit venir d'une deuxième personne, ni la personne concernée ni celle qui a demandé."))
    if not valideurs_possibles(habilitation).filter(pk=auteur.pk).exists():
        raise PermissionDenied(v("Seuls l'Administrateur et les personnes habilitées valident une habilitation."))
    accepter = donnees.get("accepter") is True
    commentaire = (donnees.get("commentaire") or "").strip()
    if not accepter and not commentaire:
        raise ValidationError({"commentaire": v("Indiquez pourquoi la demande est refusée.")})
    maintenant = timezone.now()
    habilitation.statut = H.ACTIVE if accepter else H.REFUSEE
    habilitation.validee_par, habilitation.date_validation = auteur, maintenant
    habilitation.active_le = maintenant if accepter else None
    habilitation.commentaire_validation = commentaire
    habilitation.save()
    _auditer(auteur, habilitation, "validation" if accepter else "refus")
    nom = _nom(habilitation.utilisateur)
    titre = v(f"Habilitation confidentielle accordée à {nom}") if accepter else v(f"Habilitation confidentielle refusée pour {nom}")
    transaction.on_commit(lambda: _notifier(habilitation, titre))
    return habilitation


@transaction.atomic
def confirmer(auteur, pk, donnees):
    """Première habilitation : la personne qui l'a demandée saisit le code reçu ; effet dans 24 heures."""
    habilitation = _en_attente(pk)
    if not habilitation.premiere or auteur.pk != habilitation.demandee_par_id:
        raise PermissionDenied(v("Seule la personne qui a demandé cette première habilitation peut la confirmer."))
    if not secrets.compare_digest(_empreinte(donnees.get("code", "")), habilitation.empreinte_code):
        raise ValidationError({"code": v("Code incorrect.")})
    maintenant = timezone.now()
    habilitation.statut = H.EN_DELAI
    habilitation.validee_par, habilitation.date_validation = auteur, maintenant
    habilitation.active_le = maintenant + DELAI_PREMIERE
    habilitation.empreinte_code = ""
    habilitation.save()
    _auditer(auteur, habilitation, "confirmation_courriel")
    transaction.on_commit(lambda: _notifier(
        habilitation, v(f"Habilitation confidentielle de {_nom(habilitation.utilisateur)} : active dans 24 heures")))
    return habilitation


@transaction.atomic
def retirer(auteur, pk, donnees):
    """Retrait immédiat, motivé ; les dossiers confidentiels ouverts confiés à la personne sont à réaffecter."""
    from .models import ActionDossier, Dossier

    _peut_gerer(auteur)
    habilitation = HabilitationSensible.objects.select_for_update().filter(pk=pk, statut__in=HabilitationSensible.EN_COURS).first()
    if habilitation is None:
        raise ValidationError({"detail": v("Cette habilitation n'est plus en cours.")})
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        raise ValidationError({"motif": v("Indiquez le motif du retrait.")})
    habilitation.statut = H.RETIREE
    habilitation.retiree_par, habilitation.date_retrait, habilitation.motif_retrait = auteur, timezone.now(), motif
    habilitation.save()
    personne = habilitation.utilisateur
    for dossier in Dossier.objects.filter(sensible=True, responsable=personne).exclude(statut=StatutDossier.CLOTURE):
        dossier.responsable = None
        dossier.save(update_fields=["responsable", "updated_at"])
        ActionDossier.objects.create(dossier=dossier, type=ActionDossier.Type.AFFECTATION, auteur=auteur,
                                     texte=v("Habilitation confidentielle retirée : dossier à réaffecter."),
                                     details={"de": _nom(personne), "a": ""})
    _auditer(auteur, habilitation, "retrait")
    transaction.on_commit(lambda: _notifier(habilitation, v(f"Habilitation confidentielle retirée à {_nom(personne)}")))
    return habilitation


def habiliter_d_office(*personnes, motif="Habilitation d'office (données de démonstration ou de test)."):
    """Données de démonstration et tests : habilitation en vigueur sans double validation, tracée au journal."""
    for personne in personnes:
        if personne.role == ROLE_ADMIN or habilitations_actives().filter(utilisateur=personne).exists():
            continue
        maintenant = timezone.now()
        h = HabilitationSensible.objects.create(utilisateur=personne, statut=H.ACTIVE, motif=motif,
                                                date_validation=maintenant, active_le=maintenant)
        _auditer(None, h, "habilitation_d_office")


def activer_echues():
    """Tâche horaire : les premières habilitations sorties du délai passent « Active » (journal et notification)."""
    echues = list(HabilitationSensible.objects.filter(statut=H.EN_DELAI, active_le__lte=timezone.now()))
    for habilitation in echues:
        habilitation.statut = H.ACTIVE
        habilitation.save(update_fields=["statut"])
        _auditer(None, habilitation, "entree_en_vigueur")
        _notifier(habilitation, v(f"Habilitation confidentielle de {_nom(habilitation.utilisateur)} : désormais active"))
    return len(echues)
