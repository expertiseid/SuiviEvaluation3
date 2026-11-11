"""
Effacement définitif (RGPD, droit à l'effacement) : quand un projet, un élément de la planification ou
un bénéficiaire est supprimé, rien de ce qui en dépendait ne doit subsister.

Pendant `with effacement_definitif():`, toutes les lignes supprimées (y compris en cascade) sont relevées,
puis, une fois la transaction validée :
- leurs copies dans les tables d'historique (django-simple-history garde une copie à chaque
  modification et à la suppression) sont effacées ;
- leurs fichiers (documents, versions, pièces justificatives) sont retirés du stockage, sauf si une
  autre ligne les utilise encore.
En cas d'échec de la suppression (transaction annulée), rien n'est effacé.
"""
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

_releve: ContextVar = ContextVar("effacement_releve", default=None)


@receiver(post_delete, dispatch_uid="effacement-definitif-releve")
def _relever(sender, instance, **kwargs):
    releve = _releve.get()
    if releve is None:
        return
    releve["lignes"][sender].add(instance.pk)
    for champ in instance._meta.concrete_fields:
        if isinstance(champ, models.FileField):
            fichier = getattr(instance, champ.attname)
            if fichier:
                releve["fichiers"].add((sender, champ.attname, fichier.storage, fichier.name))


def _modele_historique(modele):
    try:
        return modele.history.model
    except AttributeError:
        return None


def _effacer_historique(lignes):
    for modele, cles in lignes.items():
        historique = _modele_historique(modele)
        if historique is not None and cles:
            historique.objects.filter(**{f"{modele._meta.pk.attname}__in": cles}).delete()


def _effacer_fichiers(fichiers):
    for modele, champ, stockage, nom in fichiers:
        if modele._base_manager.filter(**{champ: nom}).exists():
            continue  # fichier encore utilisé par une autre ligne
        try:
            stockage.delete(nom)
        except OSError:
            pass  # déjà absent


@contextmanager
def effacement_definitif():
    """Suppression sans reste : historique et fichiers des lignes supprimées, après validation."""
    if _releve.get() is not None:  # déjà dans un effacement (suppression imbriquée) : il s'en charge
        yield
        return
    releve = {"lignes": defaultdict(set), "fichiers": set()}
    with transaction.atomic():
        jeton = _releve.set(releve)
        try:
            yield
        finally:
            _releve.reset(jeton)  # le relevé s'arrête avant l'effacement de l'historique
        _effacer_historique(releve["lignes"])
        fichiers = list(releve["fichiers"])
        transaction.on_commit(lambda: _effacer_fichiers(fichiers))
