"""
Reprise d'une installation à organisation unique comme espace de la plateforme multi-organisations
(étape 4) : les données de l'ancienne installation deviennent celles d'une organisation.

La base a déjà été copiée dans « org_<sous-domaine> » (scripts/reprendre_installation.sh : pg_dump puis
pg_restore, la base d'origine reste intacte). Ensuite, ici :
1. inscription au registre (active), tables mises à jour ;
2. dans la copie, on vide les tables de la base centrale (registre, demandes d'inscription) : elles
   n'ont rien à faire dans la base d'une organisation ;
3. rechiffrement des données protégées des plaintes : clé de l'installation → clé de l'organisation ;
4. fichiers : MEDIA_ROOT et pièces jointes des plaintes (rechiffrées) recopiés dans le dossier de
   l'organisation. Les originaux restent en place (sauvegarde), à effacer à la main une fois vérifié.
"""
import shutil
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import connections, transaction

from . import contexte
from .gestion import ErreurOrganisation, activer, base_existe, installer, verifier_sous_domaine
from .models import Organisation


def _tables_centrales():
    return [m._meta.db_table for m in apps.get_models()
            if contexte.est_central(m._meta.app_label, m._meta.model_name)]


def _champs_chiffres():
    from apps.plaintes.chiffrement import TexteChiffre

    for modele in apps.get_models():
        champs = [f.column for f in modele._meta.concrete_fields if isinstance(f, TexteChiffre)]
        if champs:
            yield modele._meta.db_table, modele._meta.pk.column, champs


def rechiffrer(ancienne, nouvelle) -> int:
    """Base de l'organisation courante : chaque valeur chiffrée avec `ancienne` l'est avec `nouvelle` (SQL direct)."""
    from apps.plaintes.chiffrement import PREFIXE

    total = 0
    with transaction.atomic(), connections["default"].cursor() as curseur:
        for table, pk, champs in _champs_chiffres():
            colonnes = ", ".join(f'"{c}"' for c in champs)
            curseur.execute(f'SELECT "{pk}", {colonnes} FROM "{table}"')
            for ligne in curseur.fetchall():
                valeurs = {}
                for colonne, valeur in zip(champs, ligne[1:]):
                    if isinstance(valeur, str) and valeur.startswith(PREFIXE):
                        clair = ancienne.decrypt(valeur[len(PREFIXE):].encode())  # InvalidToken : on arrête tout
                        valeurs[colonne] = PREFIXE + nouvelle.encrypt(clair).decode()
                if valeurs:
                    affectations = ", ".join(f'"{c}" = %s' for c in valeurs)
                    curseur.execute(f'UPDATE "{table}" SET {affectations} WHERE "{pk}" = %s', [*valeurs.values(), ligne[0]])
                    total += len(valeurs)
    return total


def _copier_fichiers(racine: Path, cible: Path, transformer=None) -> int:
    """Copie l'arborescence de `racine` dans `cible`, sans le dossier « organisations »."""
    nombre = 0
    if not racine.is_dir():
        return 0
    for source in racine.rglob("*"):
        relatif = source.relative_to(racine)
        if not source.is_file() or relatif.parts[0] == "organisations":
            continue
        destination = cible / relatif
        if destination.exists():
            raise ErreurOrganisation(f"Fichier déjà présent dans l'espace : {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if transformer:
            destination.write_bytes(transformer(source.read_bytes()))
        else:
            shutil.copy2(source, destination)
        nombre += 1
    return nombre


def reprendre(sous_domaine: str, nom: str, courriel: str = "", sortie=None):
    from apps.plaintes.chiffrement import _fernet_pour

    def dire(texte):
        if sortie:
            sortie.write(texte)

    sous_domaine = verifier_sous_domaine(sous_domaine, reserve_permis=True)
    base = Organisation.nom_de_base(sous_domaine)
    if not base_existe(base):
        raise ErreurOrganisation(f"La base {base} n'existe pas : copier d'abord l'installation (scripts/reprendre_installation.sh).")
    org = Organisation(nom=nom, sous_domaine=sous_domaine, base=base, courriel_contact=courriel)

    with contexte.dans_organisation(org):
        with connections["default"].cursor() as curseur:
            curseur.execute("SELECT to_regclass('accounts_user')")
            if curseur.fetchone()[0] is None:
                raise ErreurOrganisation(f"La base {base} n'est pas une copie de l'installation.")
            for table in _tables_centrales():
                curseur.execute("SELECT to_regclass(%s)", [table])
                if curseur.fetchone()[0] is not None:
                    curseur.execute(f'DELETE FROM "{table}"')
                    dire(f"   table centrale vidée dans la copie : {table}")
        installer(org, sortie=sortie)
        nombre = rechiffrer(_fernet_pour(""), _fernet_pour(sous_domaine))
        dire(f"   {nombre} valeur(s) protégée(s) rechiffrée(s) avec la clé de l'espace")

        media = Path(settings.MEDIA_ROOT)
        dire(f"   {_copier_fichiers(media, media / 'organisations' / sous_domaine)} fichier(s) recopié(s)")
        prive = Path(settings.PLAINTES_STOCKAGE_PRIVE)
        ancienne, nouvelle = _fernet_pour(""), _fernet_pour(sous_domaine)
        pieces = _copier_fichiers(prive, prive / "organisations" / sous_domaine,
                                  transformer=lambda contenu: nouvelle.encrypt(ancienne.decrypt(contenu)))
        dire(f"   {pieces} pièce(s) jointe(s) de plaintes recopiée(s) et rechiffrée(s)")

    org.save(using="central")
    activer(org)
    return org
