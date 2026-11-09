"""
Activation d'un profil d'organisation (console Expertise-ID) : création de son espace à partir de la
demande d'inscription — base, tables, référentiel des zones, compte administrateur avec l'identifiant
et le mot de passe choisis à l'inscription — puis courriel « Votre espace est prêt ».

La création prend de quelques secondes à une minute : elle se fait en arrière-plan ; la demande passe
« Espace en cours de création », puis « Abonnement activé » (ou revient à son état, avec l'erreur).
"""
import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.db import connections

from . import contexte, gestion

logger = logging.getLogger(__name__)


def creer_espace(demande, zones=True):
    """Crée et ouvre l'espace de la demande ; renvoie l'organisation (appel synchrone)."""
    from apps.accounts.models import DemandeInscription

    org = gestion.creer(demande.organisation, demande.sous_domaine, courriel=demande.courriel, offre=demande.offre, zones=zones)
    gestion.creer_administrateur(org, demande.identifiant, demande.courriel, empreinte=demande.mot_de_passe, nom=demande.contact_nom)
    gestion.activer(org)
    demande.statut = DemandeInscription.Statut.ACTIVEE
    demande.erreur_activation = ""
    demande.save(using="central", update_fields=["statut", "erreur_activation"])
    # Offre Partenariat : validée par Expertise-ID, le courriel le dit ; offre payée en ligne : espace prêt.
    partenariat = demande.offre == DemandeInscription.Offre.PARTENARIAT
    sujet = f"Votre partenariat est validé : l'espace de {org.nom} est prêt" if partenariat else f"Votre espace est prêt : {org.nom}"
    debut = (f"Expertise-ID a validé votre demande de partenariat. L'espace de {org.nom} sur la plateforme "
             "Expertise-ID Monitora est ouvert et prêt.") if partenariat else (
        f"L'espace de {org.nom} sur la plateforme Expertise-ID Monitora est prêt.")
    send_mail(
        sujet,
        f"Bonjour {demande.contact_nom},\n\n{debut}\n\n"
        f"Connectez-vous ici : {contexte.adresse()}/login\nAdresse courriel : {demande.courriel}\nMot de passe : celui "
        "que vous avez choisi à l'inscription.\n\nÀ chaque connexion, un code vous sera envoyé à cette adresse "
        "courriel.\n\nExpertise-ID",
        getattr(settings, "DEFAULT_FROM_EMAIL", None), [demande.courriel], fail_silently=True,
    )
    return org


def lancer(demande, zones=True, en_arriere_plan=True):
    """Marque la demande « en cours de création » et crée l'espace (en arrière-plan par défaut)."""
    from apps.accounts.models import DemandeInscription

    statut_precedent = demande.statut
    demande.statut = DemandeInscription.Statut.EN_ACTIVATION
    demande.erreur_activation = ""
    demande.save(using="central", update_fields=["statut", "erreur_activation"])

    def travail():
        try:
            creer_espace(demande, zones=zones)
        except Exception as erreur:  # l'erreur est montrée dans la console ; rien n'est laissé à moitié créé
            logger.exception("Activation de l'espace %s impossible.", demande.sous_domaine)
            demande.statut = statut_precedent
            demande.erreur_activation = f"{type(erreur).__name__} : {erreur}"[:2000]
            demande.save(using="central", update_fields=["statut", "erreur_activation"])
        finally:
            if en_arriere_plan:
                connections.close_all()

    if en_arriere_plan:
        threading.Thread(target=travail, name=f"activation-{demande.sous_domaine}", daemon=True).start()
    else:
        travail()
