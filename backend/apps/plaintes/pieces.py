"""
Pièces jointes des dossiers (lot 8) et compléments du plaignant.

- Type réel contrôlé d'après le contenu du fichier (jamais d'après son nom ni le type annoncé par le
  navigateur) : documents (PDF, Word, Excel, OpenDocument, texte), images (JPEG, PNG, WebP), audio
  (MP3, M4A, OGG, WAV, AMR, WebM). L'extension du nom est remise d'accord avec le type réel.
- Taille maximale réglée par le mécanisme, jamais au-dessus du plafond de la plateforme
  (PLAINTES_PLAFOND_PIECE_MO).
- Métadonnées effacées au dépôt : photos (EXIF, position GPS), propriétés des documents Office et
  OpenDocument, auteur et logiciel des PDF, étiquettes ID3 des MP3. Les autres formats audio sont
  gardés tels quels (indiqué sur la pièce).
- Contenu toujours chiffré (même clé que les données protégées, chiffrement.py), dans un répertoire
  privé hors de toute racine web, rangé par dossier. Aucune adresse permanente : un lien signé, valable
  quelques minutes (PLAINTES_DUREE_LIEN_PIECE_MIN), est délivré après contrôle d'accès ; l'accès est
  vérifié de nouveau au téléchargement, qui est inscrit au journal du dossier.
- Le nom d'origine est chiffré ; les journaux techniques et les messages d'erreur ne contiennent ni
  nom ni contenu.
"""
import io
import logging
import os
import re
import zipfile
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import ROLE_ADMIN
from apps.core.vocabulaire import v

from .chiffrement import _fernet
from .models import ActionDossier, Mecanisme, PieceJointe, StatutDossier

logger = logging.getLogger(__name__)

SEL_LIEN = "plaintes.piece"
PIECES_PAR_ENVOI = 5  # formulaire public et complément
PIECES_PUBLIQUES_PAR_DOSSIER = 20  # au total, pour un même plaignant
PIECES_PAR_AJOUT = 10  # ajout par l'équipe

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "txt": "text/plain",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "amr": "audio/amr",
    "webm": "audio/webm",
}
FORMATS_ACCEPTES = "PDF, Word, Excel, OpenDocument, texte, JPEG, PNG, WebP, MP3, M4A, OGG, WAV, AMR, WebM"


# --- Contrôles -----------------------------------------------------------------------------------

def plafond_mo() -> int:
    return max(1, int(getattr(settings, "PLAINTES_PLAFOND_PIECE_MO", 10)))


def taille_max_mo(mecanisme=None) -> int:
    mecanisme = mecanisme or Mecanisme.courant()
    return max(1, min(mecanisme.taille_max_piece_mo or plafond_mo(), plafond_mo()))


def _zip(contenu):
    try:
        archive = zipfile.ZipFile(io.BytesIO(contenu))
        return archive, set(archive.namelist())
    except (zipfile.BadZipFile, ValueError):
        return None, set()


def type_reel(contenu: bytes) -> str | None:
    """Extension correspondant au contenu, ou None si le format n'est pas accepté."""
    debut = contenu[:16]
    if debut.startswith(b"%PDF-"):
        return "pdf"
    if debut.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if debut.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if debut[:4] == b"RIFF" and debut[8:12] == b"WEBP":
        return "webp"
    if debut[:4] == b"RIFF" and debut[8:12] == b"WAVE":
        return "wav"
    if debut.startswith(b"ID3") or (len(debut) > 1 and debut[0] == 0xFF and debut[1] & 0xE0 == 0xE0 and debut[1] & 0x06):
        return "mp3"
    if debut.startswith(b"OggS"):
        return "ogg"
    if debut.startswith(b"#!AMR"):
        return "amr"
    if debut.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if debut[4:8] == b"ftyp" and debut[8:12] in (b"M4A ", b"M4B "):
        return "m4a"
    if debut.startswith(b"PK\x03\x04"):
        archive, noms = _zip(contenu)
        if archive is None:
            return None
        if "[Content_Types].xml" in noms and "word/document.xml" in noms:
            return "docx"
        if "[Content_Types].xml" in noms and "xl/workbook.xml" in noms:
            return "xlsx"
        if "mimetype" in noms:
            nature = archive.read("mimetype")[:60]
            if nature == b"application/vnd.oasis.opendocument.text":
                return "odt"
            if nature == b"application/vnd.oasis.opendocument.spreadsheet":
                return "ods"
        return None
    if b"\x00" not in contenu[:4096]:
        try:
            contenu.decode("utf-8")
            return "txt"
        except UnicodeDecodeError:
            return None
    return None


# --- Effacement des métadonnées --------------------------------------------------------------------

def _image_sans_metadonnees(contenu, extension):
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(contenu)) as image:
        image.load()
        image = ImageOps.exif_transpose(image)  # garde le bon sens de la photo, sans garder l'EXIF
        sortie = io.BytesIO()
        if extension == "jpg":
            image.convert("RGB").save(sortie, "JPEG", quality=92)
        elif extension == "png":
            image.save(sortie, "PNG")
        else:
            image.save(sortie, "WEBP", quality=92)
    return sortie.getvalue()


CORE_VIDE = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
             b' xmlns:dc="http://purl.org/dc/elements/1.1/"/>')
APP_VIDE = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"/>')
META_ODF_VIDE = (b'<?xml version="1.0" encoding="UTF-8"?><office:document-meta '
                 b'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2">'
                 b'<office:meta/></office:document-meta>')


def _archive_sans_metadonnees(contenu, extension):
    """Réécrit l'archive en vidant les propriétés (auteur, dernier modificateur, société, dates)."""
    remplacements = {"docProps/core.xml": CORE_VIDE, "docProps/app.xml": APP_VIDE} if extension in ("docx", "xlsx") \
        else {"meta.xml": META_ODF_VIDE}
    source = zipfile.ZipFile(io.BytesIO(contenu))
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w") as cible:
        for info in source.infolist():
            donnees = remplacements.get(info.filename, None)
            if donnees is None:
                donnees = source.read(info.filename)
            # « mimetype » des OpenDocument : premier et non compressé, sinon le fichier est jugé abîmé.
            compression = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            cible.writestr(zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0)), donnees, compress_type=compression)
    return sortie.getvalue()


def _pdf_sans_metadonnees(contenu):
    """
    Blanchit, à longueur égale (la table des positions du PDF reste juste), l'auteur, le logiciel et
    les autres propriétés du dictionnaire d'information, ainsi que le bloc XMP en clair. Renvoie
    (contenu, effacé) : « effacé » est faux si le PDF range des objets compressés où ces propriétés
    pourraient se cacher.
    """
    def chaine(m):
        texte = m.group(2)
        return m.group(1) + (b"(" + b" " * (len(texte) - 2) + b")" if texte.startswith(b"(") else b"<" + b"0" * (len(texte) - 2) + b">")

    resultat = re.sub(rb"(/(?:Author|Creator|Producer|Title|Subject|Keywords)\s*)(\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]*>)",
                      chaine, contenu)
    resultat = re.sub(rb"<x:xmpmeta.*?</x:xmpmeta>", lambda m: b" " * len(m.group(0)), resultat, flags=re.S)
    return resultat, b"/ObjStm" not in contenu


def _mp3_sans_metadonnees(contenu):
    if contenu.startswith(b"ID3") and len(contenu) > 10:
        taille = 0
        for octet in contenu[6:10]:
            taille = (taille << 7) | (octet & 0x7F)
        pied = 10 if contenu[5] & 0x10 else 0
        contenu = contenu[10 + taille + pied:]
    if len(contenu) > 128 and contenu[-128:-125] == b"TAG":
        contenu = contenu[:-128]
    return contenu


def sans_metadonnees(contenu, extension):
    """(contenu nettoyé, métadonnées effacées ?). Une image illisible est refusée."""
    if extension in ("jpg", "png", "webp"):
        try:
            return _image_sans_metadonnees(contenu, extension), True
        except Exception:  # image tronquée, piégée ou trop grande : refusée sans détail
            raise ValidationError({"fichiers": v("Une image est illisible ou abîmée : elle n'a pas été acceptée.")})
    if extension in ("docx", "xlsx", "odt", "ods"):
        try:
            return _archive_sans_metadonnees(contenu, extension), True
        except (zipfile.BadZipFile, KeyError, ValueError, OSError):
            raise ValidationError({"fichiers": v("Un document est abîmé : il n'a pas été accepté.")})
    if extension == "pdf":
        return _pdf_sans_metadonnees(contenu)
    if extension == "mp3":
        return _mp3_sans_metadonnees(contenu), True
    if extension == "txt":
        return contenu, True
    return contenu, False


# --- Préparation et enregistrement -----------------------------------------------------------------

def _nom(nom_envoye, extension):
    base = os.path.splitext(os.path.basename(nom_envoye or ""))[0].strip()[:150] or v("piece-jointe")
    return f"{base}.{extension}"


def preparer(fichiers, mecanisme=None, maximum=PIECES_PAR_ENVOI):
    """
    Contrôle et nettoie les fichiers envoyés, avant toute écriture : un seul fichier refusé fait refuser
    l'envoi (rien n'est enregistré). Renvoie une liste de dictionnaires prêts pour enregistrer().
    """
    fichiers = [f for f in (fichiers or []) if f]
    if not fichiers:
        return []
    if len(fichiers) > maximum:
        raise ValidationError({"fichiers": v(f"Joignez au plus {maximum} fichiers à la fois.")})
    limite = taille_max_mo(mecanisme)
    prets = []
    for fichier in fichiers:
        if fichier.size > limite * 1024 * 1024:
            raise ValidationError({"fichiers": v(f"Un fichier dépasse la taille maximale de {limite} Mo.")})
        if fichier.size == 0:
            raise ValidationError({"fichiers": v("Un fichier est vide.")})
        contenu = fichier.read()
        extension = type_reel(contenu)
        if extension is None:
            raise ValidationError({"fichiers": v(f"Format de fichier non accepté. Formats acceptés : {FORMATS_ACCEPTES}.")})
        contenu, efface = sans_metadonnees(contenu, extension)
        prets.append({"nom": _nom(fichier.name, extension), "type_mime": MIME[extension], "contenu": contenu,
                      "metadonnees_effacees": efface})
    return prets


def repertoire() -> Path:
    """Répertoire privé de l'organisation courante (plateforme multi-organisations : un dossier chacune)."""
    from apps.organisations.stockage import racine_fichiers

    return Path(racine_fichiers(getattr(settings, "PLAINTES_STOCKAGE_PRIVE")))


def chemin(piece) -> Path:
    return repertoire() / str(piece.dossier.uid) / f"{piece.uid}.bin"


def enregistrer(dossier, prets, source, auteur=None):
    """Crée les pièces et écrit leur contenu chiffré. Une écriture ratée annule la transaction en cours."""
    pieces = []
    for pret in prets:
        piece = PieceJointe.objects.create(
            dossier=dossier, nom=pret["nom"], type_mime=pret["type_mime"], taille=len(pret["contenu"]),
            source=source, ajoute_par=auteur, metadonnees_effacees=pret["metadonnees_effacees"],
        )
        cible = chemin(piece)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(_fernet().encrypt(pret["contenu"]))
        os.chmod(cible, 0o600)
        pieces.append(piece)
    return pieces


def lire(piece) -> bytes:
    return _fernet().decrypt(chemin(piece).read_bytes())


def effacer_fichier(piece):
    try:
        chemin(piece).unlink(missing_ok=True)
    except OSError:
        logger.warning("Pièce jointe %s : fichier non effacé.", piece.pk)


@receiver(post_delete, sender=PieceJointe)
def _effacer_apres_suppression(sender, instance, **kwargs):
    """Une pièce supprimée (retrait, anonymisation, suppression du dossier) ne laisse aucun fichier."""
    transaction.on_commit(lambda: effacer_fichier(instance))


# --- Actions de l'équipe ---------------------------------------------------------------------------

def _modifiable(dossier):
    if dossier.anonymise:
        raise ValidationError({"detail": v("Ce dossier est anonymisé : il ne peut plus être modifié.")})


@transaction.atomic
def ajouter(dossier, auteur, fichiers):
    _modifiable(dossier)
    prets = preparer(fichiers, maximum=PIECES_PAR_AJOUT)
    if not prets:
        raise ValidationError({"fichiers": v("Choisissez au moins un fichier.")})
    pieces = enregistrer(dossier, prets, PieceJointe.Source.EQUIPE, auteur)
    ActionDossier.objects.create(
        dossier=dossier, type=ActionDossier.Type.PIECE_JOINTE, auteur=auteur,
        texte="\n".join(p.nom for p in pieces), details={"ajout": len(pieces)},
    )
    return dossier


@transaction.atomic
def retirer(dossier, auteur, donnees):
    """Retrait motivé : Administrateur, gestionnaire du dossier, ou personne qui a ajouté la pièce."""
    _modifiable(dossier)
    piece = dossier.pieces.filter(pk=donnees.get("piece") if str(donnees.get("piece", "")).isdigit() else None).first()
    if piece is None:
        raise ValidationError({"piece": v("Pièce jointe introuvable.")})
    if not (auteur.role == ROLE_ADMIN or dossier.responsable_id == auteur.pk or piece.ajoute_par_id == auteur.pk):
        raise PermissionDenied(v("Seuls l'Administrateur, le gestionnaire du dossier ou la personne qui l'a ajoutée "
                                 "peuvent retirer cette pièce."))
    motif = (donnees.get("motif") or "").strip()
    if not motif:
        raise ValidationError({"motif": v("Indiquez pourquoi cette pièce est retirée.")})
    ActionDossier.objects.create(
        dossier=dossier, type=ActionDossier.Type.PIECE_JOINTE, auteur=auteur,
        texte=f"{piece.nom}\n{motif}", details={"retrait": 1},
    )
    piece.delete()
    return dossier


def effacer_fichiers_orphelins(age_minimal_s=3600):
    """
    Filet de sécurité de la tâche horaire : efface les fichiers dont la pièce n'existe plus (suppression
    faite sans passer par l'application, transaction annulée après l'écriture…). Les fichiers récents
    sont épargnés : leur pièce peut être en cours d'enregistrement. Renvoie le nombre de fichiers effacés.
    """
    import time

    racine = repertoire()
    if not racine.is_dir():
        return 0
    connues = {str(u) for u in PieceJointe.objects.values_list("uid", flat=True)}
    limite = time.time() - age_minimal_s
    effaces = 0
    for dossier in racine.iterdir():
        if not dossier.is_dir():
            continue
        for fichier in dossier.glob("*.bin"):
            if fichier.stem not in connues and fichier.stat().st_mtime < limite:
                fichier.unlink(missing_ok=True)
                effaces += 1
        if not any(dossier.iterdir()):
            dossier.rmdir()
    if effaces:
        logger.info("Pièces jointes : %s fichier(s) orphelin(s) effacé(s).", effaces)
    return effaces


def supprimer_toutes(dossier):
    """Anonymisation : plus aucune pièce ni aucun fichier."""
    for piece in list(dossier.pieces.all()):
        piece.delete()


# --- Liens temporaires -----------------------------------------------------------------------------

def duree_lien_minutes() -> int:
    return max(1, min(int(getattr(settings, "PLAINTES_DUREE_LIEN_PIECE_MIN", 5)), 15))


def lien(piece, utilisateur) -> str:
    from apps.organisations.contexte import sel

    return signing.dumps({"p": piece.pk, "u": utilisateur.pk}, salt=sel(SEL_LIEN))


def piece_du_lien(jeton):
    """
    Pièce désignée par un lien encore valide, si la personne qui l'a demandé y a toujours accès
    (compte actif, dossier visible, pas mise en cause). Sinon None, sans dire pourquoi.
    """
    from apps.accounts.models import User

    from .reception import dossiers_visibles

    try:
        from apps.organisations.contexte import sel

        contenu = signing.loads(jeton, salt=sel(SEL_LIEN), max_age=duree_lien_minutes() * 60)
    except signing.BadSignature:  # comprend le lien expiré
        return None, None
    utilisateur = User.objects.filter(pk=contenu.get("u"), is_active=True).first()
    piece = PieceJointe.objects.select_related("dossier").filter(pk=contenu.get("p")).first()
    if utilisateur is None or piece is None or not dossiers_visibles(utilisateur).filter(pk=piece.dossier_id).exists():
        return None, None
    return piece, utilisateur


# --- Complément du plaignant (page de suivi) -------------------------------------------------------

@transaction.atomic
def completer(dossier, donnees, fichiers):
    """Le plaignant ajoute une précision et/ou des fichiers à son dossier, avec son code de suivi."""
    from . import delais

    mecanisme = Mecanisme.courant()
    if dossier.anonymise or dossier.statut == StatutDossier.CLOTURE:
        raise ValidationError({"detail": v("Ce dossier est clôturé : il ne peut plus être complété. "
                                           "Contactez le mécanisme si vous contestez la réponse.")})
    fichiers = [f for f in (fichiers or []) if f]
    if fichiers and not mecanisme.pieces_formulaire_public:
        raise ValidationError({"fichiers": v("Ce mécanisme n'accepte pas de fichiers joints.")})
    if fichiers and dossier.pieces.filter(source=PieceJointe.Source.PLAIGNANT).count() + len(fichiers) > PIECES_PUBLIQUES_PAR_DOSSIER:
        raise ValidationError({"fichiers": v("Ce dossier a atteint le nombre maximal de fichiers joints.")})
    texte = (donnees.get("texte") or "").strip()[:5000]
    if not texte and not fichiers:
        raise ValidationError({"texte": v("Écrivez votre complément ou joignez un fichier.")})
    prets = preparer(fichiers, mecanisme)
    pieces = enregistrer(dossier, prets, PieceJointe.Source.PLAIGNANT)
    ActionDossier.objects.create(dossier=dossier, type=ActionDossier.Type.COMPLEMENT, texte=texte,
                                 details={"pieces": len(pieces)})
    destinataires = [dossier.responsable] if dossier.responsable_id else delais.destinataires_premiere_etape(dossier)
    transaction.on_commit(lambda: delais.notifier_dossier(
        dossier, destinataires, v(f"Le plaignant a complété le dossier {dossier.numero}"),
        v(f"Complément reçu sur le dossier confidentiel {dossier.numero}"), texte[:300],
    ))
    return dossier
