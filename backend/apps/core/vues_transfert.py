"""
Sauvegarde complète et reprise d'un espace (transfert.py), réservées à l'Administrateur.

Le fichier de reprise peut dépasser la taille maximale d'un envoi (100 Mo derrière le serveur web) :
l'écran l'envoie par morceaux (POST transfert/morceau/), puis demande la reprise (POST transfert/reprendre/).
La reprise d'un gros espace dépasse le délai d'une requête (300 s) : elle se fait en arrière-plan, et
l'écran en suit l'avancement (GET transfert/reprise/?identifiant=) jusqu'au compte rendu.
"""
import contextlib
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.db import connections
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.organisations import contexte

from . import transfert
from .audit import A, auditer
from .permissions import IsAdmin

logger = logging.getLogger(__name__)

TAILLE_MORCEAU_MAX = 60 * 1024 * 1024
# Confirmation attendue selon le mode : « ajouter » garde tout l'existant ; « remplacer » l'efface.
CONFIRMATIONS = {"ajouter": "AJOUTER", "remplacer": "REMPLACER"}
# Retrait après un extrait : le reçu (signé à l'export) ne vaut qu'une heure, pour cet administrateur.
SEL_RETRAIT = "transfert.retrait"
DUREE_RECU = 3600
# Reprise en arrière-plan : son état est rafraîchi toutes les 15 s ; sans nouvelle depuis 90 s, elle s'est
# arrêtée (serveur redémarré) — tout a été annulé avec elle.
BATTEMENT = 15
SILENCE_MAX = 90
REPRISE_ARRETEE = ("La reprise s'est arrêtée (serveur redémarré) : rien n'a été modifié. Recommencez-la.")


def _dossier_envois() -> Path:
    dossier = Path(tempfile.gettempdir()) / "reprises" / (contexte.identifiant() or "-")
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def _fichier_envoi(identifiant: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{8,64}", identifiant or ""):
        raise ValueError
    return _dossier_envois() / f"{identifiant}.zip"


def _fichier_etat(cible: Path) -> Path:
    """État de la reprise lancée, à côté du fichier : lu par tous les processus du serveur."""
    return cible.with_suffix(".etat.json")


def _ecrire_etat(cible: Path, etat: dict):
    provisoire = cible.with_suffix(f".etat.{threading.get_ident()}.tmp")
    provisoire.write_text(json.dumps({**etat, "maj": time.time()}, ensure_ascii=False), encoding="utf-8")
    provisoire.replace(_fichier_etat(cible))


def _lire_etat(chemin: Path) -> dict:
    """État de la reprise ; « en cours » sans nouvelle depuis SILENCE_MAX : arrêtée avec le serveur."""
    etat = json.loads(chemin.read_text(encoding="utf-8"))
    if etat["etat"] == "en_cours" and time.time() - etat.get("maj", 0) > SILENCE_MAX:
        etat = {"etat": "erreur", "detail": REPRISE_ARRETEE}
    return etat


def _reponse_etat(cible: Path) -> Response:
    etat = _lire_etat(_fichier_etat(cible))
    etat.pop("maj", None)
    code = {"en_cours": status.HTTP_202_ACCEPTED, "erreur": status.HTTP_400_BAD_REQUEST}.get(etat["etat"], status.HTTP_200_OK)
    return Response(etat, status=code)


def _reprise_en_cours(sauf: Path) -> bool:
    """Une autre reprise tourne-t-elle dans cet espace ? (deux à la fois s'attendraient l'une l'autre)"""
    for chemin in _dossier_envois().glob("*.etat.json"):
        if chemin != _fichier_etat(sauf):
            try:
                if _lire_etat(chemin)["etat"] == "en_cours":
                    return True
            except (OSError, ValueError, KeyError):
                continue
    return False


def _espace_de_demo() -> bool:
    org = contexte.courante()
    return bool(org and getattr(org, "mode_demo", False))


@api_view(["GET"])
@permission_classes([IsAdmin])
def exporter(request):
    """
    Télécharge la sauvegarde de l'espace (un fichier zip) : complète, ou limitée à des projets
    (?projets=1,2) et des cadres stratégiques (?cadres=3), avec ou sans leurs projets (?avec_projets=0).
    """
    from apps.geo.services.synthese import ids_parametre

    projets, cadres = ids_parametre(request.query_params, "projets"), ids_parametre(request.query_params, "cadres")
    choix = {"projets": projets, "cadres": cadres, "avec_projets": request.query_params.get("avec_projets") != "0"} \
        if projets or cadres else None
    descripteur, chemin = tempfile.mkstemp(suffix=".zip")
    os.close(descripteur)
    try:
        manifeste = transfert.exporter(chemin, choix)
    except Exception:
        os.unlink(chemin)
        raise
    auditer(request.user, A.EXPORT, "Sauvegarde d'une partie de l'espace" if choix else "Sauvegarde complète de l'espace",
            module="organisation", objets=manifeste["objets"], taille=os.path.getsize(chemin),
            **({"projets": projets, "cadres": cadres} if choix else {}))
    nom = f"{'extrait' if choix else 'sauvegarde'}-{manifeste['identifiant'] or 'plateforme'}-{manifeste['date'][:10]}.zip"
    empreinte = _empreinte(chemin)
    fichier = open(chemin, "rb")
    os.unlink(chemin)  # le fichier ouvert reste lisible jusqu'à la fin du téléchargement
    reponse = FileResponse(fichier, as_attachment=True, filename=nom, content_type="application/zip")
    # Reçu du fichier : permet ensuite d'en retirer le contenu de l'espace (retirer), une fois le
    # fichier arrivé entier dans le navigateur (même empreinte).
    reponse["X-Recu-Extrait"] = signing.dumps({"u": request.user.pk, "c": choix, "h": empreinte},
                                              salt=contexte.sel(SEL_RETRAIT))
    return reponse


def _empreinte(chemin) -> str:
    calcul = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            calcul.update(bloc)
    return calcul.hexdigest()


@api_view(["POST"])
@permission_classes([IsAdmin])
def retirer(request):
    """
    Supprime de l'espace ce que l'extrait vient d'emporter (ou, après une sauvegarde complète, toutes ses
    données : comptes et réglages restent), sur demande de l'administrateur (case cochée puis confirmation
    « SUPPRIMER »). Le reçu de l'export et l'empreinte du fichier reçu par le navigateur
    garantissent que l'extrait téléchargé est complet avant toute suppression.
    """
    if request.data.get("confirmation") != "SUPPRIMER":
        return Response({"detail": "Confirmation manquante : rien n'a été retiré."}, status=status.HTTP_400_BAD_REQUEST)
    if _espace_de_demo():
        return Response({"detail": "Le retrait n'est pas possible dans l'espace de démonstration."},
                        status=status.HTTP_403_FORBIDDEN)
    try:
        recu = signing.loads(request.data.get("recu") or "", salt=contexte.sel(SEL_RETRAIT), max_age=DUREE_RECU)
    except signing.SignatureExpired:
        return Response({"detail": "Extrait trop ancien : téléchargez-le de nouveau pour le retirer."},
                        status=status.HTTP_400_BAD_REQUEST)
    except signing.BadSignature:
        return Response({"detail": "Reçu d'extrait invalide : rien n'a été retiré."}, status=status.HTTP_400_BAD_REQUEST)
    if recu["u"] != request.user.pk or recu["h"] != (request.data.get("empreinte") or "").lower():
        return Response({"detail": "Le fichier reçu ne correspond pas à l'extrait : rien n'a été retiré."},
                        status=status.HTTP_400_BAD_REQUEST)
    if recu["c"] is None:
        compte_rendu = transfert.vider_donnees()
        auditer(request.user, A.SUPPRESSION, "Données de l'espace effacées après sa sauvegarde complète",
                module="organisation", objets=compte_rendu["objets"])
        return Response({**compte_rendu, "vide": True})
    try:
        compte_rendu = transfert.retirer(recu["c"])
    except transfert.TransfertRefuse as erreur:
        return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
    auditer(request.user, A.SUPPRESSION, "Retrait de l'espace après un extrait", module="organisation",
            projets=compte_rendu["projets"], cadres=compte_rendu["cadres"], elements=compte_rendu["noms"][:50])
    return Response(compte_rendu)


@api_view(["POST"])
@permission_classes([IsAdmin])
@parser_classes([MultiPartParser])
def recevoir_morceau(request):
    """Ajoute un morceau au fichier de reprise en cours d'envoi (le premier, numéro 0, le recommence)."""
    try:
        cible = _fichier_envoi(request.data.get("identifiant", ""))
        numero = int(request.data.get("numero", ""))
    except ValueError:
        return Response({"detail": "Envoi invalide."}, status=status.HTTP_400_BAD_REQUEST)
    morceau = request.FILES.get("morceau")
    if morceau is None or morceau.size > TAILLE_MORCEAU_MAX:
        return Response({"detail": "Morceau manquant ou trop gros."}, status=status.HTTP_400_BAD_REQUEST)
    with open(cible, "wb" if numero == 0 else "ab") as f:
        for bloc in morceau.chunks():
            f.write(bloc)
    return Response({"recu": cible.stat().st_size})


@api_view(["POST"])
@permission_classes([IsAdmin])
def reprendre(request):
    """
    Analyse le fichier envoyé (sans confirmation : renvoie son manifeste), ou, avec la confirmation du
    mode choisi, ajoute la sauvegarde au contenu de l'espace (« ajouter ») ou le remplace (« remplacer »).
    """
    mode = request.data.get("mode") or "remplacer"
    if mode not in CONFIRMATIONS:
        return Response({"detail": "Mode de reprise inconnu."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cible = _fichier_envoi(request.data.get("identifiant", ""))
    except ValueError:
        return Response({"detail": "Envoi invalide."}, status=status.HTTP_400_BAD_REQUEST)
    if _fichier_etat(cible).exists() and request.data.get("confirmation") == CONFIRMATIONS[mode]:
        return _reponse_etat(cible)  # reprise déjà lancée pour ce fichier (double clic) : son avancement
    if not cible.exists():
        return Response({"detail": "Fichier introuvable : envoyez-le de nouveau."}, status=status.HTTP_400_BAD_REQUEST)
    if _espace_de_demo():
        return Response({"detail": "La reprise d'une sauvegarde n'est pas possible dans l'espace de démonstration."},
                        status=status.HTTP_403_FORBIDDEN)
    try:
        if request.data.get("confirmation") != CONFIRMATIONS[mode]:
            with zipfile.ZipFile(cible) as archive:
                manifeste = transfert.lire_manifeste(archive)
            return Response({"manifeste": {c: manifeste.get(c) for c in ("organisation", "date", "objets", "selection")}})
        with zipfile.ZipFile(cible) as archive:
            transfert.lire_manifeste(archive)  # fichier lisible : vérifié avant de lancer la reprise
    except zipfile.BadZipFile:
        return Response({"detail": "Ce fichier n'est pas un zip valide."}, status=status.HTTP_400_BAD_REQUEST)
    except transfert.TransfertRefuse as erreur:
        return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)

    if _reprise_en_cours(cible):
        return Response({"detail": "Une reprise est déjà en cours dans cet espace : attendez qu'elle se termine "
                                   "avant d'en lancer une autre."}, status=status.HTTP_409_CONFLICT)

    org, administrateur = contexte.courante(), request.user
    en_arriere_plan = getattr(settings, "REPRISE_EN_ARRIERE_PLAN", True)
    avancement = {"etat": "en_cours", "traites": 0, "total": 0}
    _ecrire_etat(cible, avancement)
    fini, verrou = threading.Event(), threading.Lock()

    def battre():
        """Signe de vie, même quand l'ajout attend la base (et en mode « remplacer », sans avancement)."""
        while not fini.wait(BATTEMENT):
            with verrou:
                if not fini.is_set():
                    _ecrire_etat(cible, avancement)

    def terminer(etat):
        with verrou:  # plus aucun signe de vie ne repassera « en cours » par-dessus
            fini.set()
            _ecrire_etat(cible, etat)

    def avancer(traites, total):
        avancement.update(traites=traites, total=total)
        _ecrire_etat(cible, avancement)

    def travail():
        try:
            with contexte.dans_organisation(org) if org is not None else contextlib.nullcontext():
                compte_rendu = transfert.importer(str(cible), administrateur, mode, progression=avancer)
                auditer(None, A.CONFIGURATION, "Reprise d'une sauvegarde complète", module="organisation",
                        auteur=administrateur.username, mode=mode, origine=compte_rendu["origine"],
                        date_sauvegarde=compte_rendu["date_sauvegarde"], objets=compte_rendu["objets"])
            terminer({"etat": "termine", "compte_rendu": compte_rendu})
        except zipfile.BadZipFile:
            terminer({"etat": "erreur", "detail": "Ce fichier n'est pas un zip valide."})
        except transfert.TransfertRefuse as erreur:
            terminer({"etat": "erreur", "detail": str(erreur)})
        except Exception:  # tout est annulé (transaction) ; le détail reste dans le journal du serveur
            logger.exception("Reprise de la sauvegarde %s impossible.", cible.name)
            terminer({"etat": "erreur", "detail": "La reprise a échoué : rien n'a été modifié."})
        finally:
            fini.set()  # au cas où une erreur inattendue serait passée outre
            cible.unlink(missing_ok=True)
            if en_arriere_plan:
                connections.close_all()

    if en_arriere_plan:
        threading.Thread(target=battre, name=f"reprise-{cible.stem}-vie", daemon=True).start()
        threading.Thread(target=travail, name=f"reprise-{cible.stem}", daemon=True).start()
    else:
        travail()
    return _reponse_etat(cible)


@api_view(["GET"])
@permission_classes([IsAdmin])
def suivre_reprise(request):
    """Avancement de la reprise lancée (?identifiant=) : en cours, terminée (avec son compte rendu) ou en erreur."""
    try:
        cible = _fichier_envoi(request.query_params.get("identifiant", ""))
        return _reponse_etat(cible)
    except ValueError:
        return Response({"detail": "Envoi invalide."}, status=status.HTTP_400_BAD_REQUEST)
    except FileNotFoundError:
        return Response({"detail": "Aucune reprise en cours pour ce fichier."}, status=status.HTTP_404_NOT_FOUND)
