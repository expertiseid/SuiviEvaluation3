"""
Sauvegarde complète et reprise d'un espace (transfert.py), réservées à l'Administrateur.

Le fichier de reprise peut dépasser la taille maximale d'un envoi (100 Mo derrière le serveur web) :
l'écran l'envoie par morceaux (POST transfert/morceau/), puis demande la reprise (POST transfert/reprendre/).
"""
import hashlib
import os
import re
import tempfile
import zipfile
from pathlib import Path

from django.core import signing
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.organisations import contexte

from . import transfert
from .audit import A, auditer
from .permissions import IsAdmin

TAILLE_MORCEAU_MAX = 60 * 1024 * 1024
# Confirmation attendue selon le mode : « ajouter » garde tout l'existant ; « remplacer » l'efface.
CONFIRMATIONS = {"ajouter": "AJOUTER", "remplacer": "REMPLACER"}
# Retrait après un extrait : le reçu (signé à l'export) ne vaut qu'une heure, pour cet administrateur.
SEL_RETRAIT = "transfert.retrait"
DUREE_RECU = 3600


def _dossier_envois() -> Path:
    dossier = Path(tempfile.gettempdir()) / "reprises" / (contexte.identifiant() or "-")
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def _fichier_envoi(identifiant: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{8,64}", identifiant or ""):
        raise ValueError
    return _dossier_envois() / f"{identifiant}.zip"


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
        compte_rendu = transfert.importer(str(cible), request.user, mode)
    except zipfile.BadZipFile:
        return Response({"detail": "Ce fichier n'est pas un zip valide."}, status=status.HTTP_400_BAD_REQUEST)
    except transfert.TransfertRefuse as erreur:
        return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
    cible.unlink(missing_ok=True)
    auditer(None, A.CONFIGURATION, "Reprise d'une sauvegarde complète", module="organisation",
            auteur=f"{request.user.username}", mode=mode, origine=compte_rendu["origine"], date_sauvegarde=compte_rendu["date_sauvegarde"],
            objets=compte_rendu["objets"])
    return Response(compte_rendu)
