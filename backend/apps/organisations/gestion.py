"""
Cycle de vie de l'espace d'une organisation : création de sa base, installation des tables, compte
administrateur, suppression. Utilisé par les commandes (management/commands) et, à l'étape 2, par la
console Expertise-ID (bouton « Activer »).
"""
from django.core.management import call_command
from django.db import connections
from django.utils import timezone

from apps.core.vocabulaire import v

from . import contexte
from .models import FORME, RESERVES, Organisation


class ErreurOrganisation(Exception):
    pass


def verifier_sous_domaine(sous_domaine: str, reserve_permis=False) -> str:
    """`reserve_permis` : sous-domaine réservé accepté (espace d'Expertise-ID, commandes d'exploitation)."""
    sous_domaine = (sous_domaine or "").strip().lower()
    if not FORME.match(sous_domaine):
        raise ErreurOrganisation(v("Sous-domaine invalide : 3 à 40 caractères, lettres minuscules, chiffres et tirets."))
    if sous_domaine in RESERVES and not reserve_permis:
        raise ErreurOrganisation(v("Ce sous-domaine est réservé."))
    if Organisation.objects.using("central").filter(sous_domaine=sous_domaine).exists():
        raise ErreurOrganisation(v("Ce sous-domaine est déjà pris."))
    return sous_domaine


def _executer_hors_transaction(requete: str):
    """CREATE/DROP DATABASE : sur la base centrale, hors transaction."""
    connexion = connections["central"]
    connexion.ensure_connection()
    ancien = connexion.connection.autocommit
    connexion.connection.autocommit = True
    try:
        with connexion.cursor() as curseur:
            curseur.execute(requete)
    finally:
        connexion.connection.autocommit = ancien


def base_existe(nom: str) -> bool:
    with connections["central"].cursor() as curseur:
        curseur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [nom])
        return curseur.fetchone() is not None


def creer_base(org: Organisation):
    if not FORME.match(org.sous_domaine) or org.base != Organisation.nom_de_base(org.sous_domaine):
        raise ErreurOrganisation("Nom de base inattendu.")
    if base_existe(org.base):
        raise ErreurOrganisation(f"La base {org.base} existe déjà.")
    _executer_hors_transaction(f'CREATE DATABASE "{org.base}"')


def installer(org: Organisation, sortie=None, zones=False):
    """Tables de la plateforme dans la base de l'organisation (et, au besoin, le référentiel des zones)."""
    with contexte.dans_organisation(org):
        call_command("migrate", interactive=False, verbosity=0, stdout=sortie)
        if zones:
            call_command("seed_zones_bfa", stdout=sortie)


def creer_administrateur(org: Organisation, identifiant: str, courriel: str, mot_de_passe: str = None,
                         empreinte: str = None, nom: str = ""):
    """Premier compte de l'organisation (Administrateur). `empreinte` : mot de passe déjà haché (inscription)."""
    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User
    from apps.core.models import IdentiteOrganisation

    with contexte.dans_organisation(org):
        prenom, _, famille = (nom or "").partition(" ")
        compte = User(username=identifiant, email=courriel, role=ROLE_ADMIN, is_staff=True,
                      first_name=prenom[:150], last_name=famille[:150])
        if empreinte:
            compte.password = empreinte
        else:
            compte.set_password(mot_de_passe)
        compte.save()
        identite = IdentiteOrganisation.courante()
        identite.nom = org.nom
        identite.save()
        return compte.pk


def creer(nom: str, sous_domaine: str, courriel: str = "", offre: str = "", mode_demo=False, sortie=None, zones=False):
    """Inscrit l'organisation au registre, crée et installe sa base ; elle reste « en attente » jusqu'à activer()."""
    sous_domaine = verifier_sous_domaine(sous_domaine)
    org = Organisation.objects.using("central").create(
        nom=nom, sous_domaine=sous_domaine, base=Organisation.nom_de_base(sous_domaine),
        courriel_contact=courriel, offre=offre, mode_demo=mode_demo,
    )
    try:
        creer_base(org)
        installer(org, sortie=sortie, zones=zones)
    except Exception:
        if base_existe(org.base):
            _executer_hors_transaction(f'DROP DATABASE "{org.base}"')
        org.delete(using="central")
        raise
    return org


def activer(org: Organisation):
    from . import quota

    org.statut = Organisation.Statut.ACTIVE
    org.active_le = org.active_le or timezone.now()
    if org.base_vide is None:  # base neuve : sa taille ne sera pas comptée dans l'espace utilisé
        org.base_vide = quota._taille_base(org) or None
    org.save(using="central")
    return org


def supprimer(org: Organisation):
    """Supprime définitivement l'espace : sa base et son inscription au registre (irréversible)."""
    connections.close_all()
    _executer_hors_transaction(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{org.base}' AND pid <> pg_backend_pid()"
    )
    if base_existe(org.base):
        _executer_hors_transaction(f'DROP DATABASE "{org.base}"')
    org.delete(using="central")


def actives():
    return Organisation.objects.using("central").filter(statut=Organisation.Statut.ACTIVE).order_by("sous_domaine")
