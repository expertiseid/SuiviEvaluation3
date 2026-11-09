"""
Espace de stockage de chaque organisation, selon son offre : Standard 25 Go, Standard 50 Go,
Standard et Partenariat 100 Go. Expertise-ID peut l'agrandir dans la console (Organisation.stockage_go,
sur demande du client).

Compté : les fichiers de l'organisation (documents, images, pièces jointes des plaintes) et sa base de
données. Un envoi de fichier qui dépasserait l'espace est refusé (StockageOrganisation._save) ; les
pièces jointes des plaintes ne sont jamais refusées (le mécanisme de plainte doit rester ouvert),
mais elles comptent. Espace occupé gardé en cache 10 minutes, augmenté à chaque fichier ajouté.

Alertes (alerter) : à 90 % puis à 100 %, les administrateurs de l'organisation sont prévenus une fois
par seuil (cloche et courriel, lien vers la page Stockage) ; Expertise-ID aussi quand l'espace est plein.
Vérifié après chaque fichier ajouté, à chaque refus, et toutes les heures (check_deadlines).

Disque commun (Volume Hetzner, alerter_disque) : agrandi tout seul à 80 % jusqu'à un plafond ; Expertise-ID
est prévenue par courriel, une fois par jour, s'il approche du plafond ou se remplit malgré tout. Vérifié toutes les heures (surveiller_disque).
"""
import os
import shutil
from contextlib import nullcontext

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from rest_framework.exceptions import APIException

from . import contexte

GO = 1024 ** 3


class StockagePlein(APIException):
    """Fichier refusé (espace plein) : l'interface affiche une fenêtre explicative (code « stockage_plein »)."""
    status_code = 400
    default_code = "stockage_plein"
OFFRE_GO = {"STANDARD_25": 25, "STANDARD_50": 50, "STANDARD": 100, "STOCKAGE_PLUS": 100, "PARTENARIAT": 100}
CLE = "stockage-utilise"
DUREE = 600


def limite_go(org):
    """Espace en Go : celui fixé par Expertise-ID, sinon celui de l'offre ; None = sans limite (offre inconnue)."""
    return float(org.stockage_go) if org.stockage_go else OFFRE_GO.get(org.offre)


def lisible(go) -> str:
    """« 25 Go », « 1,5 Go », « 10 Mo » (espace en Go, décimales possibles)."""
    if go < 1:
        return f"{round(go * 1024)} Mo"
    return f"{round(go, 1):g} Go".replace(".", ",")


def _taille_dossier(chemin: str) -> int:
    total = 0
    for racine, _, fichiers in os.walk(chemin):
        for nom in fichiers:
            try:
                total += os.path.getsize(os.path.join(racine, nom))
            except OSError:
                pass
    return total


def _taille_base(org) -> int:
    try:
        with connections["central"].cursor() as curseur:
            curseur.execute("SELECT pg_database_size(%s)", [org.base])
            return curseur.fetchone()[0] or 0
    except Exception:
        return 0


def _mesurer(org) -> int:
    dossiers = (str(settings.MEDIA_ROOT), str(settings.PLAINTES_STOCKAGE_PRIVE))
    fichiers = sum(_taille_dossier(os.path.join(d, "organisations", org.sous_domaine)) for d in dossiers)
    return fichiers + _taille_base(org)


def _cles_de(org):
    """Les clés du cache sont propres à chaque organisation : celles de `org`, même depuis la console."""
    courante = contexte.courante()
    return nullcontext() if courante and courante.pk == org.pk else contexte.cles_de(org)


def utilise(org) -> int:
    """Espace occupé (octets) par l'organisation : fichiers et base."""
    with _cles_de(org):
        valeur = cache.get(CLE)
        if valeur is None:
            valeur = _mesurer(org)
            cache.set(CLE, valeur, DUREE)
    return valeur


def etat(org) -> dict:
    go = limite_go(org)
    return {"utilise": utilise(org), "limite": int(go * GO) if go else None, "limite_go": go}


def verifier(taille: int):
    """Avant d'écrire `taille` octets pour l'organisation courante : refus si son espace serait dépassé."""
    from apps.organisations.models import Organisation

    org = contexte.courante()
    if org is None or not taille:
        return
    org = Organisation.objects.using("central").filter(pk=org.pk).first() or org  # limite à jour (console, achat)
    go = limite_go(org)
    if go and utilise(org) + taille > go * GO:
        alerter(org, plein=True)
        raise StockagePlein({"detail": f"Espace de stockage plein ({lisible(go)}) : supprimez des fichiers ou "
                                       "augmentez votre stockage depuis la page Stockage.",
                             "code": "stockage_plein", "taille": taille, "utilise": utilise(org), "limite": int(go * GO)})


def ajouter(taille: int):
    """Après l'écriture d'un fichier : l'espace occupé gardé en cache augmente d'autant."""
    org = contexte.courante()
    if org is None or not taille:
        return
    with _cles_de(org):
        try:
            cache.incr(CLE, taille)
        except ValueError:
            pass  # pas encore mesuré : le sera à la prochaine lecture
    alerter(org)


SEUILS = (100, 90)


def alerter(org=None, plein=False):
    """
    Prévient les administrateurs de l'organisation (courante) quand son espace passe 90 % puis 100 %
    (`plein` : un fichier vient d'être refusé). Une fois par seuil ; repasser sous un seuil (fichiers
    supprimés, espace agrandi) permet d'être prévenu à nouveau. À appeler dans la base de l'organisation.
    """
    from apps.organisations.models import Organisation

    org = org or contexte.courante()
    if org is None:
        return
    org = Organisation.objects.using("central").filter(pk=org.pk).first()
    go = limite_go(org) if org else None
    if not go:
        return
    occupe = utilise(org)
    part = 100 if plein else occupe * 100 / (go * GO)
    niveau = next((s for s in SEUILS if part >= s), 0)
    if niveau == org.stockage_alerte:
        return
    Organisation.objects.using("central").filter(pk=org.pk).update(stockage_alerte=niveau)
    if niveau > org.stockage_alerte:
        _prevenir(org, niveau, occupe, go)


def _prevenir(org, niveau, occupe, go):
    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.inscriptions import _envoyer
    from apps.notifications.models import Notification
    from apps.notifications.services import notifier_par_role

    if niveau >= 100:
        titre = "Espace de stockage plein"
        message = (f"Votre organisation utilise tout son espace de stockage ({lisible(go)}) : les nouveaux fichiers sont refusés. "
                   "Supprimez des fichiers inutiles ou augmentez votre stockage depuis la page Stockage.")
        _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), f"Espace de stockage plein : {org.nom}",
                 f"Organisation : {org.nom} ({org.sous_domaine})\nEspace : {lisible(go)}, plein.\n"
                 "Ses administrateurs ont été prévenus et peuvent acheter du stockage depuis la page Stockage.")
    else:
        titre = "Espace de stockage presque plein"
        message = (f"Votre organisation utilise {lisible(occupe / GO)} sur {lisible(go)} ({niveau} %). "
                   "Supprimez des fichiers inutiles ou augmentez votre stockage depuis la page Stockage.")
    notifier_par_role([ROLE_ADMIN], Notification.Type.STOCKAGE, titre, message, lien="/stockage")


def alerter_disque():
    """
    Disque commun des fichiers (Volume agrandi tout seul sur le serveur de données) : courriel à
    Expertise-ID, au plus une fois par jour, quand il atteint 90 % de son plafond (relever le plafond)
    ou qu'il est rempli à 90 % (l'agrandissement automatique n'a pas suivi).
    """
    from apps.accounts.inscriptions import _envoyer

    plafond = getattr(settings, "VOLUME_PLAFOND_GO", 0)
    if not plafond:
        return
    try:
        disque = shutil.disk_usage(settings.MEDIA_ROOT)
    except OSError:
        return
    total_go, part = disque.total / GO, disque.used * 100 / disque.total
    if part >= 90:
        sujet = f"Disque des données rempli à {part:.0f} %"
        texte = ("L'agrandissement automatique n'a pas suivi (plafond atteint ou erreur). "
                 "Agrandir à la main : ssh -t alex@37.27.193.28 sudo agrandir-volume-monitora --essai 100 ; "
                 "journal : journalctl -u agrandir-volume-monitora")
    elif total_go >= 0.9 * plafond:
        sujet = f"Disque des données proche du plafond ({total_go:.0f} Go sur {plafond} Go)"
        texte = ("Au plafond, le disque ne sera plus agrandi tout seul. Pour le relever, changer PLAFOND dans "
                 "/etc/monitora/agrandissement.conf sur le serveur de données (et VOLUME_PLAFOND_GO dans .env.prod).")
    else:
        return
    with contexte.cles_de(None):  # une clé commune à toute la plateforme
        if not cache.add("alerte-disque", 1, 24 * 3600):
            return
    _envoyer(getattr(settings, "COURRIEL_ABONNEMENTS", ""), sujet,
             f"{sujet}.\nTaille : {total_go:.0f} Go, utilisé : {disque.used / GO:.0f} Go, plafond : {plafond} Go.\n{texte}")
