"""Sauvegarde complète d'un espace dans un zip et reprise (transfert.py, vues_transfert.py)."""
import io
import json
import zipfile

import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN, ROLE_CHEF_PROJET
from apps.accounts.models import User
from apps.core.models import EvenementAudit
from apps.plaintes.chiffrement import _fernet
from apps.projects.models import Projet

from . import transfert


@pytest.fixture(autouse=True)
def stockage(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.PLAINTES_STOCKAGE_PRIVE = str(tmp_path / "prive")
    return tmp_path


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_tr", password="x", role=ROLE_ADMIN, email="adm.tr@monong.org")


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def _projet(code):
    return Projet.objects.create(nom=f"Projet {code}", code=code, date_debut="2026-01-01", date_fin="2026-12-31")


def test_aller_retour_donnees_fichiers_et_pieces_chiffrees(admin, stockage, tmp_path):
    _projet("TR-1")
    (stockage / "media" / "ged").mkdir(parents=True)
    (stockage / "media" / "ged" / "rapport.pdf").write_bytes(b"%PDF rapport")
    prive = stockage / "prive" / "dossier-1"
    prive.mkdir(parents=True)
    (prive / "piece.bin").write_bytes(_fernet().encrypt(b"photo confidentielle"))

    zip_ = str(tmp_path / "sauvegarde.zip")
    manifeste = transfert.exporter(zip_)
    assert manifeste["objets"] > 0 and manifeste["pieces_illisibles"] == 0
    with zipfile.ZipFile(zip_) as archive:
        assert archive.read("fichiers/ged/rapport.pdf") == b"%PDF rapport"
        # Les pièces sont déchiffrées : la clé de cet espace n'existe pas ailleurs.
        assert archive.read("prive/dossier-1/piece.bin") == b"photo confidentielle"
        assert any(o["model"] == "projects.projet" for o in json.loads(archive.read("donnees.json")))

    # L'espace change ensuite : la reprise remet exactement l'état sauvegardé.
    Projet.objects.all().delete()
    _projet("TR-2")
    (stockage / "media" / "ged" / "rapport.pdf").unlink()
    audits_avant = EvenementAudit.objects.count()
    EvenementAudit.objects.create(action=EvenementAudit.Action.EXPORT, objet="après la sauvegarde")

    compte_rendu = transfert.importer(zip_, admin)

    assert list(Projet.objects.values_list("code", flat=True)) == ["TR-1"]
    assert (stockage / "media" / "ged" / "rapport.pdf").read_bytes() == b"%PDF rapport"
    piece = stockage / "prive" / "dossier-1" / "piece.bin"
    assert piece.read_bytes() != b"photo confidentielle"  # rechiffrée sur le disque
    assert _fernet().decrypt(piece.read_bytes()) == b"photo confidentielle"
    # Journal d'audit : rien n'est effacé, les événements sauvegardés s'y ajoutent.
    assert EvenementAudit.objects.filter(objet="après la sauvegarde").exists()
    assert EvenementAudit.objects.count() >= audits_avant + 1
    assert compte_rendu["compte_garde"] is False  # l'administrateur était déjà dans la sauvegarde
    assert User.objects.filter(username="adm_tr").exists()


def test_reprise_garde_l_administrateur_absent_de_la_sauvegarde(admin, tmp_path):
    zip_ = str(tmp_path / "sauvegarde.zip")
    transfert.exporter(zip_)
    autre = User.objects.create_user(username="adm_autre", password="x", role=ROLE_ADMIN, email="autre@monong.org")
    compte_rendu = transfert.importer(zip_, autre)
    assert compte_rendu["compte_garde"] is True
    garde = User.objects.get(email="autre@monong.org")
    assert garde.role == ROLE_ADMIN and garde.check_password("x")


def test_fichier_invalide_refuse(admin, tmp_path):
    zip_ = tmp_path / "faux.zip"
    with zipfile.ZipFile(zip_, "w") as archive:
        archive.writestr("autre.txt", "rien")
    with zipfile.ZipFile(zip_) as archive, pytest.raises(transfert.TransfertRefuse):
        transfert.lire_manifeste(archive)


def test_sauvegarde_d_une_version_plus_recente_refusee(admin, tmp_path):
    zip_ = str(tmp_path / "sauvegarde.zip")
    transfert.exporter(zip_)
    contenu = io.BytesIO()
    with zipfile.ZipFile(zip_) as source, zipfile.ZipFile(contenu, "w") as copie:
        for nom in source.namelist():
            donnees = source.read(nom)
            if nom == "manifeste.json":
                manifeste = json.loads(donnees)
                manifeste["migrations"]["core"].append("9999_du_futur")
                donnees = json.dumps(manifeste).encode()
            copie.writestr(nom, donnees)
    with zipfile.ZipFile(contenu) as archive, pytest.raises(transfert.TransfertRefuse, match="plus récente"):
        transfert.lire_manifeste(archive)


def test_api_reservee_a_l_administrateur_et_par_morceaux(admin, db):
    chef = User.objects.create_user(username="chef_tr", password="x", role=ROLE_CHEF_PROJET)
    assert _client(chef).get("/api/v1/transfert/exporter/").status_code == 403

    reponse = _client(admin).get("/api/v1/transfert/exporter/")
    assert reponse.status_code == 200
    contenu = b"".join(reponse.streaming_content)
    assert EvenementAudit.objects.filter(action=EvenementAudit.Action.EXPORT, module="organisation").exists()

    client = _client(admin)
    moitie = len(contenu) // 2
    for numero, morceau in enumerate((contenu[:moitie], contenu[moitie:])):
        r = client.post("/api/v1/transfert/morceau/", {"identifiant": "essai-reprise-1", "numero": numero,
                                                       "morceau": io.BytesIO(morceau)}, format="multipart")
        assert r.status_code == 200
    analyse = client.post("/api/v1/transfert/reprendre/", {"identifiant": "essai-reprise-1"}, format="json")
    assert analyse.status_code == 200 and analyse.data["manifeste"]["objets"] > 0
    assert Projet.objects.count() == 0
    reprise = client.post("/api/v1/transfert/reprendre/", {"identifiant": "essai-reprise-1", "confirmation": "REMPLACER"},
                          format="json")
    assert reprise.status_code == 200, reprise.data
    assert client.post("/api/v1/transfert/morceau/", {"identifiant": "../../etc", "numero": 0,
                                                      "morceau": io.BytesIO(b"x")}, format="multipart").status_code == 400


def test_ajouter_garde_l_existant_et_ne_duplique_pas_les_referentiels(admin, stockage, tmp_path):
    from apps.geo.models import NiveauAdministratif, Zone
    from apps.partners.models import Bailleur

    region = NiveauAdministratif.objects.get_or_create(pays="BF", ordre=1, defaults={"nom_niveau": "Région"})[0]
    Zone.objects.create(niveau_administratif=region, nom="Zone d'essai")
    Bailleur.objects.create(nom="Union européenne")
    projet = _projet("COMMUN-1")
    (stockage / "media" / "ged").mkdir(parents=True)
    (stockage / "media" / "ged" / "note.pdf").write_bytes(b"version de la sauvegarde")
    zip_ = str(tmp_path / "sauvegarde.zip")
    transfert.exporter(zip_)

    # L'espace d'arrivée a ses propres données, dont un projet au même code et un fichier au même nom.
    Projet.objects.filter(pk=projet.pk).update(nom="Projet de l'espace d'arrivée")
    _projet("ICI-1")
    (stockage / "media" / "ged" / "note.pdf").write_bytes(b"version de l'espace")

    zones, niveaux = Zone.objects.count(), NiveauAdministratif.objects.count()
    compte_rendu = transfert.importer(zip_, admin, "ajouter")

    codes = set(Projet.objects.values_list("code", flat=True))
    assert codes == {"COMMUN-1", "ICI-1", "COMMUN-1-R1"}
    assert Projet.objects.get(code="COMMUN-1").nom == "Projet de l'espace d'arrivée"
    assert Zone.objects.count() == zones and NiveauAdministratif.objects.count() == niveaux
    assert Bailleur.objects.count() == 1
    assert User.objects.filter(username="adm_tr").count() == 1
    assert compte_rendu["renommes"] == 1 and compte_rendu["reutilises"] > 0
    # Le fichier existant n'est pas écrasé.
    assert (stockage / "media" / "ged" / "note.pdf").read_bytes() == b"version de l'espace"


def test_api_mode_ajouter_demande_sa_propre_confirmation(admin, db):
    client = _client(admin)
    contenu = b"".join(client.get("/api/v1/transfert/exporter/").streaming_content)
    client.post("/api/v1/transfert/morceau/", {"identifiant": "essai-ajout-1", "numero": 0, "morceau": io.BytesIO(contenu)},
                format="multipart")
    _projet("APRES-1")
    sans = client.post("/api/v1/transfert/reprendre/", {"identifiant": "essai-ajout-1", "mode": "ajouter",
                                                        "confirmation": "REMPLACER"}, format="json")
    assert sans.status_code == 200 and "manifeste" in sans.data  # mauvais mot : simple analyse
    avec = client.post("/api/v1/transfert/reprendre/", {"identifiant": "essai-ajout-1", "mode": "ajouter",
                                                        "confirmation": "AJOUTER"}, format="json")
    assert avec.status_code == 200 and avec.data["mode"] == "ajouter"
    assert Projet.objects.filter(code="APRES-1").exists()


def test_extrait_d_un_projet_seul_puis_ajout(admin, stockage, tmp_path):
    from apps.projects.models import Activite

    choisi, autre = _projet("CHOISI-1"), _projet("AUTRE-1")
    Activite.objects.create(projet=choisi, libelle="Former les producteurs")
    Activite.objects.create(projet=autre, libelle="Ne doit pas partir")
    chef = User.objects.create_user(username="chef_extrait", password="x", role=ROLE_CHEF_PROJET, email="chef@monong.org")
    choisi.utilisateurs_affectes.add(chef)
    zip_ = str(tmp_path / "extrait.zip")
    manifeste = transfert.exporter(zip_, {"projets": [choisi.pk], "cadres": [], "avec_projets": True})
    assert manifeste["selection"] is True
    with zipfile.ZipFile(zip_) as archive:
        objets = json.loads(archive.read("donnees.json"))
    codes = {o["fields"]["code"] for o in objets if o["model"] == "projects.projet"}
    assert codes == {"CHOISI-1"}
    assert {o["fields"]["libelle"] for o in objets if o["model"] == "projects.activite"} == {"Former les producteurs"}

    # Un extrait ne remplace jamais un espace.
    with pytest.raises(transfert.TransfertRefuse, match="Ajouter"):
        transfert.importer(zip_, admin, "remplacer")

    # Reprise ailleurs (simulée : ici, ce projet et ce compte n'existent plus sous ces noms).
    Projet.objects.filter(pk=choisi.pk).update(code="ANCIEN-1")
    User.objects.filter(pk=chef.pk).update(username="ancien_chef", email="ancien@monong.org")
    compte_rendu = transfert.importer(zip_, admin, "ajouter")
    repris = Projet.objects.get(code="CHOISI-1")
    assert list(Activite.objects.filter(projet=repris).values_list("libelle", flat=True)) == ["Former les producteurs"]
    assert Projet.objects.filter(code="AUTRE-1").count() == 1
    # Les comptes cités arrivent désactivés.
    assert User.objects.get(email="chef@monong.org").is_active is False
    assert User.objects.get(username="ancien_chef").is_active is True
    assert compte_rendu["comptes_desactives"] >= 1


def test_retirer_apres_extrait_seulement_avec_le_fichier_recu(admin, db):
    import hashlib

    from apps.projects.models import Activite
    from apps.strategy.models import CadreStrategique

    choisi, autre = _projet("PARTANT-1"), _projet("RESTANT-1")
    Activite.objects.create(projet=choisi, libelle="Part avec le projet")
    cadre = CadreStrategique.objects.create(nom="Cadre partant")
    programme = CadreStrategique.objects.create(nom="Programme partant", document_parent=cadre)
    Projet.objects.filter(pk=choisi.pk).update(cadre_strategique=programme)
    client = _client(admin)

    # Cadre exporté sans ses projets : le retirer laisserait un projet sans cadre.
    sans = client.get("/api/v1/transfert/exporter/", {"cadres": cadre.pk, "avec_projets": 0})
    contenu = b"".join(sans.streaming_content)
    refus = client.post("/api/v1/transfert/retirer/", {"recu": sans["X-Recu-Extrait"], "confirmation": "SUPPRIMER",
                                                       "empreinte": hashlib.sha256(contenu).hexdigest()}, format="json")
    assert refus.status_code == 400 and CadreStrategique.objects.filter(pk=cadre.pk).exists()

    reponse = client.get("/api/v1/transfert/exporter/", {"cadres": cadre.pk})
    contenu = b"".join(reponse.streaming_content)
    recu, empreinte = reponse["X-Recu-Extrait"], hashlib.sha256(contenu).hexdigest()
    # Fichier incomplet, confirmation absente ou autre administrateur : rien n'est retiré.
    assert client.post("/api/v1/transfert/retirer/", {"recu": recu, "confirmation": "SUPPRIMER",
                                                      "empreinte": hashlib.sha256(contenu[:-10]).hexdigest()},
                       format="json").status_code == 400
    assert client.post("/api/v1/transfert/retirer/", {"recu": recu, "empreinte": empreinte}, format="json").status_code == 400
    autre_admin = User.objects.create_user(username="adm_tr2", password="x", role=ROLE_ADMIN)
    assert _client(autre_admin).post("/api/v1/transfert/retirer/", {"recu": recu, "confirmation": "SUPPRIMER",
                                                                    "empreinte": empreinte}, format="json").status_code == 400
    assert Projet.objects.filter(pk=choisi.pk).exists()

    retrait = client.post("/api/v1/transfert/retirer/", {"recu": recu, "confirmation": "SUPPRIMER", "empreinte": empreinte},
                          format="json")
    assert retrait.status_code == 200, retrait.data
    assert retrait.data["projets"] == 1 and retrait.data["cadres"] == 2
    assert not Projet.objects.filter(pk=choisi.pk).exists()
    assert not CadreStrategique.objects.filter(pk__in=[cadre.pk, programme.pk]).exists()
    assert not Activite.objects.filter(libelle="Part avec le projet").exists()
    assert Projet.objects.filter(pk=autre.pk).exists()
    assert EvenementAudit.objects.filter(action=EvenementAudit.Action.SUPPRESSION, module="organisation").exists()


def test_extrait_emporte_les_actions_correctives_sans_les_plaintes_des_autres(admin, db):
    import datetime

    from apps.plaintes.models import ActionCorrective, Categorie, Dossier, TypeRetour
    from apps.plaintes.reception import recevoir

    def plainte(projet):
        donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Récit.", "consentement": True,
                   "categorie": Categorie.objects.first().id, "nom": "Awa", "telephone": "70000000",
                   "mode_reponse": "TELEPHONE", "date_reception": datetime.date.today().isoformat(), "projet": projet.pk}
        with pytest.MonkeyPatch.context() as m:
            m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
            return recevoir(donnees, "TELEPHONE")[0]

    client = _client(admin)
    assert client.post("/api/v1/plaintes/modeles/", {"modele": "standard"}, format="json").status_code == 200
    from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_CHARGE_SE
    from apps.plaintes.habilitations import habiliter_d_office
    from apps.plaintes.models import EtapeCircuit, Mecanisme

    point_focal = User.objects.create_user(username="pf_tr", password="x", role=ROLE_CHARGE_SE,
                                           niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    habiliter_d_office(point_focal)
    assert client.post("/api/v1/plaintes/mecanisme/activer/").status_code == 200
    choisi, autre = _projet("PLAINTE-1"), _projet("PLAINTE-2")
    ici, ailleurs = plainte(choisi), plainte(autre)
    assert Dossier.objects.get(pk=ici.pk).projet_id == choisi.pk
    commune = ActionCorrective.objects.create(titre="Réparer le forage")
    commune.dossiers.add(ici, ailleurs)

    elements = transfert.selection(projets=[choisi.pk])
    assert elements[ActionCorrective] == {commune.pk}
    # La plainte de l'autre projet ne part pas, même citée par l'action commune.
    assert elements[Dossier] == {ici.pk}


def test_vider_l_espace_apres_sa_sauvegarde_complete(admin, stockage, db):
    import hashlib

    from apps.beneficiaries.models import Beneficiaire
    from apps.core.models import IdentiteOrganisation
    from apps.geo.models import NiveauAdministratif, Zone
    from apps.partners.models import Partenaire
    from apps.strategy.models import CadreStrategique

    projet = _projet("VIDE-1")
    CadreStrategique.objects.create(nom="Cadre à vider")
    partenaire = Partenaire.objects.create(nom="ONG partenaire")
    chef = User.objects.create_user(username="chef_vide", password="x", role=ROLE_CHEF_PROJET, partenaire=partenaire)
    projet.utilisateurs_affectes.add(chef)
    zones = Zone.objects.count() + NiveauAdministratif.objects.count()
    (stockage / "media" / "ged").mkdir(parents=True)
    (stockage / "media" / "ged" / "orphelin.pdf").write_bytes(b"%PDF")

    client = _client(admin)
    reponse = client.get("/api/v1/transfert/exporter/")
    contenu = b"".join(reponse.streaming_content)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
        vide = client.post("/api/v1/transfert/retirer/", {"recu": reponse["X-Recu-Extrait"], "confirmation": "SUPPRIMER",
                                                          "empreinte": hashlib.sha256(contenu).hexdigest()}, format="json")
    assert vide.status_code == 200, vide.data
    assert vide.data["vide"] is True and vide.data["objets"] > 0
    # Les données partent…
    assert not Projet.objects.exists() and not CadreStrategique.objects.exists()
    assert not Partenaire.objects.exists() and not Beneficiaire.objects.exists()
    assert not (stockage / "media" / "ged" / "orphelin.pdf").exists()
    # … les comptes, les zones et les réglages restent.
    assert User.objects.filter(username="adm_tr").exists()
    garde = User.objects.get(username="chef_vide")
    assert garde.partenaire_id is None and garde.check_password("x")
    assert Zone.objects.count() + NiveauAdministratif.objects.count() == zones
    assert IdentiteOrganisation.objects.count() <= 1
    assert EvenementAudit.objects.filter(action=EvenementAudit.Action.SUPPRESSION, module="organisation").exists()

    # Et la sauvegarde remet tout en place.
    zip_ = stockage / "sauvegarde.zip"
    zip_.write_bytes(contenu)
    transfert.importer(str(zip_), admin, "ajouter")
    assert Projet.objects.filter(code="VIDE-1").exists() and CadreStrategique.objects.filter(nom="Cadre à vider").exists()
