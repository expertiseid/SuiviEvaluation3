"""Lot 8 : pièces jointes (type réel, métadonnées, chiffrement, liens temporaires, accès) et complément du plaignant."""
import io
import json
import time
import zipfile
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE, ROLE_CHEF_PROJET
from apps.accounts.models import User

from . import pieces
from .models import ActionDossier, Categorie, Dossier, EtapeCircuit, Mecanisme, PieceJointe, TypeRetour

URL = "/api/v1/plaintes/"


def _client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


@pytest.fixture(autouse=True)
def stockage(tmp_path, settings):
    from django.core.cache import cache

    settings.PLAINTES_STOCKAGE_PRIVE = str(tmp_path / "prive")
    cache.clear()  # limites d'envois du formulaire public, comptées par connexion
    yield tmp_path / "prive"
    cache.clear()


@pytest.fixture(autouse=True)
def sans_differe(monkeypatch):
    monkeypatch.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_pj", password="x", role=ROLE_ADMIN)


@pytest.fixture
def gestionnaire(db):
    return User.objects.create_user(username="gest_pj", password="x", role=ROLE_CHEF_PROJET,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def point_focal(db):
    return User.objects.create_user(username="pf_pj", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def actif(admin, point_focal):
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=12, conservation_sensible_mois=24)
    mecanisme = Mecanisme.courant()
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200
    return mecanisme


def _photo_avec_gps():
    image = Image.new("RGB", (40, 30), "red")
    exif = Image.Exif()
    exif[0x010F] = "MarqueTelephone"  # fabricant
    exif[0x8825] = {1: "N", 2: (12.0, 21.0, 0.0)}  # position GPS
    sortie = io.BytesIO()
    image.save(sortie, "JPEG", exif=exif)
    return sortie.getvalue()


def _docx_avec_auteur():
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document>Bonjour</document>")
        z.writestr("docProps/core.xml", "<cp:coreProperties><dc:creator>Awa Témoin</dc:creator></cp:coreProperties>")
    return sortie.getvalue()


def _fichier(nom, contenu, type_annonce="application/octet-stream"):
    return SimpleUploadedFile(nom, contenu, content_type=type_annonce)


def _deposer(fichiers, **champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Le kit n'a pas été remis.",
               "consentement": True, "categorie": Categorie.objects.get(nom="Retard").id, **champs}
    return _client().post("/api/v1/public/plaintes/deposer/", {"donnees": json.dumps(donnees), "fichiers": fichiers},
                          format="multipart")


def test_type_reel_et_metadonnees():
    assert pieces.type_reel(b"%PDF-1.7 ...") == "pdf"
    assert pieces.type_reel(_photo_avec_gps()) == "jpg"
    assert pieces.type_reel(_docx_avec_auteur()) == "docx"
    assert pieces.type_reel(b"MZ\x90\x00\x03programme") is None  # exécutable déguisé
    assert pieces.type_reel("Texte simple, accentué.".encode()) == "txt"

    propre, efface = pieces.sans_metadonnees(_photo_avec_gps(), "jpg")
    assert efface and not Image.open(io.BytesIO(propre)).getexif()
    propre, efface = pieces.sans_metadonnees(_docx_avec_auteur(), "docx")
    assert efface and "Awa" not in zipfile.ZipFile(io.BytesIO(propre)).read("docProps/core.xml").decode()
    pdf = b"%PDF-1.4\n1 0 obj << /Author (Awa Temoin) /Producer <4142> >> endobj\ntrailer"
    propre, efface = pieces.sans_metadonnees(pdf, "pdf")
    assert efface and b"Awa" not in propre and len(propre) == len(pdf)
    mp3 = b"ID3\x04\x00\x00\x00\x00\x00\x05TITRE" + b"\xff\xfb\x90\x00" * 4
    assert pieces.sans_metadonnees(mp3, "mp3")[0].startswith(b"\xff\xfb")


@pytest.mark.django_db
def test_depot_public_avec_pieces_chiffrees(actif, stockage):
    reponse = _deposer([_fichier("photo du lieu.png", _photo_avec_gps(), "image/png"),
                        _fichier("rapport.docx", _docx_avec_auteur())])
    assert reponse.status_code == 201, reponse.content
    dossier = Dossier.objects.get(numero=reponse.data["numero"])
    photo, document = dossier.pieces.order_by("id")
    # Nom remis d'accord avec le type réel ; source plaignant ; métadonnées effacées.
    assert photo.nom == "photo du lieu.jpg" and photo.type_mime == "image/jpeg"
    assert photo.source == PieceJointe.Source.PLAIGNANT and photo.metadonnees_effacees
    # Sur le disque : chiffré, rangé par dossier, sans le nom d'origine.
    brut = pieces.chemin(photo).read_bytes()
    assert pieces.chemin(photo).parent.name == str(dossier.uid) and b"JFIF" not in brut and b"\xff\xd8" not in brut[:4]
    assert pieces.lire(photo).startswith(b"\xff\xd8")
    # Un fichier refusé fait refuser tout l'envoi : aucun dossier créé.
    avant = Dossier.objects.count()
    refuse = _deposer([_fichier("photo.jpg", b"MZ\x90\x00programme", "image/jpeg")])
    assert refuse.status_code == 400 and "fichiers" in refuse.data and Dossier.objects.count() == avant


@pytest.mark.django_db
def test_taille_maximale_et_desactivation(actif):
    Mecanisme.objects.filter(pk=1).update(taille_max_piece_mo=1)
    gros = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    assert _deposer([_fichier("gros.pdf", gros)]).status_code == 400
    Mecanisme.objects.filter(pk=1).update(pieces_formulaire_public=False)
    assert _deposer([_fichier("note.txt", b"bonjour")]).status_code == 400
    assert _client().get("/api/v1/public/plaintes/formulaire/").data["pieces"] is None


@pytest.mark.django_db
def test_lien_temporaire_et_journal(actif, admin, gestionnaire):
    dossier = Dossier.objects.get(numero=_deposer([_fichier("note.txt", "Détail".encode())]).data["numero"])
    piece = dossier.pieces.get()
    # L'adresse est obtenue après contrôle d'accès, puis ouverte sans jeton de connexion.
    lien = _client(gestionnaire).get(f"{URL}dossiers/{dossier.id}/pieces/{piece.id}/lien/")
    assert lien.status_code == 200 and lien.data["duree_minutes"] == 5
    chemin = lien.data["url"].split("testserver")[1]
    fichier = _client().get(chemin)
    assert fichier.status_code == 200 and fichier.content == "Détail".encode()
    assert fichier["Cache-Control"] == "no-store" and "attachment" in fichier["Content-Disposition"]
    assert dossier.actions.filter(type=ActionDossier.Type.TELECHARGEMENT, auteur=gestionnaire).exists()
    # Lien falsifié ou expiré : refusé.
    assert _client().get(chemin[:-3] + "xx/").status_code == 404
    with override_settings(PLAINTES_DUREE_LIEN_PIECE_MIN=1), mock.patch("time.time", return_value=time.time() + 61):
        assert _client().get(chemin).status_code == 404


@pytest.mark.django_db
def test_pieces_dun_dossier_confidentiel(actif, admin, gestionnaire, point_focal):
    """Scénario 13 : l'URL de pièce jointe d'un dossier confidentiel est refusée à qui n'est pas habilité."""
    dossier = Dossier.objects.get(numero=_deposer([_fichier("preuve.txt", b"secret")],
                                                  categorie=Categorie.objects.get(nom="Exploitation et abus sexuels").id).data["numero"])
    assert dossier.sensible
    piece = dossier.pieces.get()
    assert _client(gestionnaire).get(f"{URL}dossiers/{dossier.id}/pieces/{piece.id}/lien/").status_code == 404
    # Un lien obtenu par le point focal ne sert plus si la personne perd l'accès (mise en cause).
    jeton = pieces.lien(piece, point_focal)
    assert _client().get(f"/api/v1/plaintes-piece/{jeton}/").status_code == 200
    dossier.mis_en_cause_utilisateurs.add(point_focal)
    assert _client().get(f"/api/v1/plaintes-piece/{jeton}/").status_code == 404
    # Un jeton fabriqué pour un autre utilisateur ne passe pas sans la signature.
    assert _client().get(f"/api/v1/plaintes-piece/{jeton.replace(':', '!')}/").status_code == 404


@pytest.mark.django_db
def test_ajout_et_retrait_par_lequipe(actif, admin, gestionnaire):
    dossier = Dossier.objects.get(numero=_deposer([]).data["numero"])
    reponse = _client(gestionnaire).post(f"{URL}dossiers/{dossier.id}/pieces/",
                                         {"fichiers": [_fichier("pv.docx", _docx_avec_auteur())]}, format="multipart")
    assert reponse.status_code == 200, reponse.content
    assert len(reponse.data["pieces"]) == 1 and reponse.data["pieces"][0]["source"] == "EQUIPE"
    piece = dossier.pieces.get()
    fichier = pieces.chemin(piece)
    # Retrait : motif exigé ; réservé à l'Administrateur, au gestionnaire ou à l'auteur de l'ajout.
    autre = User.objects.create_user(username="autre_pj", password="x", role=ROLE_CHEF_PROJET,
                                     niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    assert _client(autre).post(f"{URL}dossiers/{dossier.id}/retirer-piece/", {"piece": piece.id, "motif": "x"},
                               format="json").status_code == 403
    assert _client(gestionnaire).post(f"{URL}dossiers/{dossier.id}/retirer-piece/", {"piece": piece.id},
                                      format="json").status_code == 400
    assert _client(gestionnaire).post(f"{URL}dossiers/{dossier.id}/retirer-piece/",
                                      {"piece": piece.id, "motif": "Erreur de dossier"}, format="json").status_code == 200
    assert not dossier.pieces.exists() and not fichier.exists()
    retrait = dossier.actions.filter(type=ActionDossier.Type.PIECE_JOINTE, details__retrait=1).get()
    assert "Erreur de dossier" in retrait.texte


@pytest.mark.django_db
def test_complement_du_plaignant(actif, admin):
    depot = _deposer([], nom="Awa", courriel="awa@exemple.bf", mode_reponse="COURRIEL")
    dossier = Dossier.objects.get(numero=depot.data["numero"])
    code = depot.data["code_suivi"]
    suivi = _client().post("/api/v1/public/plaintes/suivi/", {"code": code}, format="json")
    assert suivi.data["complement_possible"] is True and suivi.data["pieces"]["taille_max_mo"] == 10

    envoi = {"code": code.lower(), "texte": "La distribution a eu lieu sans moi."}
    reponse = _client().post("/api/v1/public/plaintes/complement/",
                             {"donnees": json.dumps(envoi), "fichiers": [_fichier("recu.txt", b"Recu 12")]},
                             format="multipart")
    assert reponse.status_code == 201, reponse.content
    complement = dossier.actions.get(type=ActionDossier.Type.COMPLEMENT)
    assert complement.texte == envoi["texte"] and complement.details == {"pieces": 1}
    assert dossier.pieces.get().source == PieceJointe.Source.PLAIGNANT
    assert _client().post("/api/v1/public/plaintes/complement/", {"code": code}, format="json").status_code == 400
    assert _client().post("/api/v1/public/plaintes/complement/", {"code": "AAAA-BBBB-CCCC", "texte": "x"},
                          format="json").status_code == 404
    Dossier.objects.filter(pk=dossier.pk).update(statut="CLOTURE")
    assert _client().post("/api/v1/public/plaintes/complement/", {"code": code, "texte": "x"},
                          format="json").status_code == 400


@pytest.mark.django_db
def test_anonymisation_efface_les_pieces(actif, admin):
    dossier = Dossier.objects.get(numero=_deposer([_fichier("photo.jpg", _photo_avec_gps())]).data["numero"])
    fichier = pieces.chemin(dossier.pieces.get())
    assert fichier.exists()
    Dossier.objects.filter(pk=dossier.pk).update(statut="CLOTURE")
    assert _client(admin).post(f"{URL}dossiers/{dossier.id}/anonymiser/", {"confirmation": True},
                               format="json").status_code == 200
    assert not dossier.pieces.exists() and not fichier.exists()


@pytest.mark.django_db
def test_fichiers_orphelins_effaces(actif, stockage):
    """Une pièce supprimée hors de l'application (SQL direct) ne laisse pas son fichier indéfiniment."""
    import os

    from django.db import connection

    dossier = Dossier.objects.get(numero=_deposer([_fichier("note.txt", b"x")]).data["numero"])
    garde = Dossier.objects.get(numero=_deposer([_fichier("autre.txt", b"y")]).data["numero"]).pieces.get()
    fichier = pieces.chemin(dossier.pieces.get())
    with connection.cursor() as c:
        c.execute("delete from plaintes_piecejointe where dossier_id = %s", [dossier.id])
    assert pieces.effacer_fichiers_orphelins() == 0  # trop récent : peut-être en cours d'enregistrement
    os.utime(fichier, (0, 0))
    assert pieces.effacer_fichiers_orphelins() == 1
    assert not fichier.exists() and not fichier.parent.exists() and pieces.chemin(garde).exists()
