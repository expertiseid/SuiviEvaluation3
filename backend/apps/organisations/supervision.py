"""
Vue d'ensemble de la console Expertise-ID : organisations, demandes à traiter, paiements, disque commun
des fichiers (Volume agrandi tout seul sur le serveur de données) et état des deux serveurs (plateforme,
données). Mesures prises à la demande, en lecture seule ; rien n'est gardé.
"""
import os
import shutil
import time
from datetime import timedelta

from django.conf import settings
from django.db import connections
from django.db.models import Sum
from django.utils import timezone

from . import quota
from .models import Organisation, PaiementAbonnement


def _lire(chemin: str) -> str:
    try:
        with open(chemin) as fichier:
            return fichier.read()
    except OSError:
        return ""


def _memoire() -> dict:
    """Mémoire de la machine (/proc/meminfo, la même pour tous les conteneurs) en octets."""
    valeurs = {}
    for ligne in _lire("/proc/meminfo").splitlines():
        nom, _, reste = ligne.partition(":")
        if nom in ("MemTotal", "MemAvailable") and reste.split():
            valeurs[nom] = int(reste.split()[0]) * 1024
    return {"total": valeurs.get("MemTotal"), "libre": valeurs.get("MemAvailable")}


def _disque(chemin) -> dict | None:
    try:
        usage = shutil.disk_usage(chemin)
    except OSError:
        return None
    return {"total": usage.total, "utilise": usage.used, "libre": usage.free}


def serveur_plateforme() -> dict:
    charge = _lire("/proc/loadavg").split()
    secondes = _lire("/proc/uptime").split()
    return {
        "processeurs": os.cpu_count(),
        "charge": float(charge[0]) if charge else None,
        "memoire": _memoire(),
        "disque": _disque("/"),
        "allume_depuis": int(float(secondes[0])) if secondes else None,
    }


def serveur_donnees() -> dict:
    """Base de données (PostgreSQL) : joignable, temps de réponse, taille de toutes les bases."""
    adresse = connections.databases["central"].get("HOST") or "local"
    try:
        debut = time.monotonic()
        with connections["central"].cursor() as curseur:
            curseur.execute("SELECT 1")
            reponse_ms = round((time.monotonic() - debut) * 1000, 1)
            curseur.execute("SELECT sum(pg_database_size(datname)), count(*) FROM pg_database WHERE NOT datistemplate")
            taille, bases = curseur.fetchone()
    except Exception:
        return {"adresse": adresse, "joignable": False}
    return {"adresse": adresse, "joignable": True, "reponse_ms": reponse_ms, "taille_bases": int(taille or 0), "bases": bases}


def disque_commun() -> dict | None:
    """Disque des fichiers des clients (Volume du serveur de données) et plafond de son agrandissement."""
    disque = _disque(settings.MEDIA_ROOT)
    if disque is None:
        return None
    return {**disque, "plafond_go": getattr(settings, "VOLUME_PLAFOND_GO", 0) or None, "seuil": 80}


def vue_ensemble() -> dict:
    from apps.accounts.models import DemandeInscription

    organisations = list(Organisation.objects.using("central").order_by("nom"))
    clientes = [o for o in organisations if o.statut == Organisation.Statut.ACTIVE and not o.mode_demo]
    espaces = []
    for org in organisations:
        if org.statut == Organisation.Statut.EN_ATTENTE:
            continue
        espaces.append({"id": org.pk, "nom": org.nom, "statut": org.statut, "mode_demo": org.mode_demo, **quota.etat(org)})
    espaces.sort(key=lambda e: e["utilise"] or 0, reverse=True)

    paiements = PaiementAbonnement.objects.using("central")
    depuis = timezone.now() - timedelta(days=30)
    recus = (paiements.filter(statut=PaiementAbonnement.Statut.PAYE, paye_le__gte=depuis)
             .values("devise").annotate(total=Sum("montant")).order_by("devise"))
    a_traiter = DemandeInscription.Statut.ABONNEMENT_REQUIS, DemandeInscription.Statut.OFFRE_CHOISIE
    return {
        "organisations": {
            "actives": len(clientes),
            "suspendues": sum(o.statut == Organisation.Statut.SUSPENDUE for o in organisations),
            "demonstration": sum(o.mode_demo for o in organisations),
        },
        "demandes_a_traiter": DemandeInscription.objects.using("central").filter(statut__in=a_traiter).count(),
        "paiements_30_jours": list(recus),
        "paiements": [
            {"date": p.paye_le or p.cree_le, "organisation": p.organisation.nom if p.organisation else (p.demande.organisation if p.demande else ""),
             "nature": p.nature, "nature_libelle": p.get_nature_display(), "offre": p.offre, "mois": p.mois, "tranches": p.tranches,
             "montant": p.montant, "devise": p.devise, "statut": p.statut, "statut_libelle": p.get_statut_display()}
            for p in paiements.select_related("organisation", "demande").order_by("-cree_le")[:30]
        ],
        "stockage": {
            "vendu_go": sum(quota.limite_go(o) or 0 for o in clientes),
            "utilise": sum(e["utilise"] or 0 for e in espaces),
            "espaces": espaces,
        },
        "disque": disque_commun(),
        "serveurs": {"plateforme": serveur_plateforme(), "donnees": serveur_donnees()},
    }
