"""
Plateforme multi-organisations : deux organisations réelles (deux bases PostgreSQL) ; aucune donnée,
aucun jeton, aucun fichier, aucune clé ne passe de l'une à l'autre.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.double_auth import jetons

from . import comptes, contexte, gestion
from .models import Organisation

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "central"])


REGLAGES = {"MULTI_ORGANISATIONS": True, "DOUBLE_AUTH_OBLIGATOIRE": True,
            "ALLOWED_HOSTS": ["testserver", "localhost"]}


@pytest.fixture(scope="module")
def _bases(django_db_setup, django_db_blocker, tmp_path_factory):
    """Les deux bases d'essai sont créées une fois pour le fichier, puis supprimées."""
    from django.test import override_settings

    dossier = tmp_path_factory.mktemp("orgs")
    reglages = {**REGLAGES, "MEDIA_ROOT": str(dossier / "media"), "PLAINTES_STOCKAGE_PRIVE": str(dossier / "prive")}
    orgs = []
    with django_db_blocker.unblock(), override_settings(**reglages):
        try:
            for sd, nom in (("essai-iso-a", "Organisation A"), ("essai-iso-b", "Organisation B")):
                org = gestion.creer(nom, sd)
                gestion.creer_administrateur(org, "admin", f"admin@{sd}.org", mot_de_passe="Un-mot-de-passe-solide-1")
                orgs.append(gestion.activer(org))
            yield orgs, reglages
        finally:
            from django.db import connections

            for org in orgs:
                gestion.supprimer(org)
            connections["central"].close()


@pytest.fixture
def deux_organisations(_bases, settings):
    orgs, reglages = _bases
    for cle, valeur in reglages.items():
        setattr(settings, cle, valeur)
    # Les tests transactionnels vident la base centrale entre deux tests : le registre est reposé.
    for org in orgs:
        Organisation.objects.using("central").update_or_create(pk=org.pk, defaults={
            "nom": org.nom, "sous_domaine": org.sous_domaine, "base": org.base, "statut": "ACTIVE"})
    comptes.reconstruire()  # index des comptes (courriel → organisation), vidé lui aussi
    return orgs


def _client(org=None, compte_id=None):
    """Adresse unique : l'organisation vient du jeton de connexion."""
    client = APIClient()
    if compte_id is not None:
        from apps.accounts.models import User

        with contexte.dans_organisation(org):
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons(User.objects.get(pk=compte_id))['access']}")
    return client


def _admin(org):
    from apps.accounts.models import User

    with contexte.dans_organisation(org):
        return User.objects.get(username="admin").pk


def _code(mail):
    import re

    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def test_isolation_complete(deux_organisations):
    from apps.documents.models import Dossier

    org_a, org_b = deux_organisations
    a, b = _client(org_a, _admin(org_a)), _client(org_b, _admin(org_b))

    # Données : chaque organisation ne voit que les siennes, dans sa propre base.
    assert a.post("/api/v1/dossiers/", {"nom": "Dossier de A"}, format="json").status_code == 201
    assert [d["nom"] for d in b.get("/api/v1/dossiers/", {"libres": "true"}).data] == []
    with contexte.dans_organisation(org_b):
        assert not Dossier.objects.filter(nom="Dossier de A").exists()
    with contexte.dans_organisation(org_a):
        assert Dossier.objects.filter(nom="Dossier de A").exists()
    assert not Dossier.objects.filter(nom="Dossier de A").exists()  # base centrale

    # L'organisation vient du jeton : demander une autre organisation ne sert à rien.
    a.credentials(HTTP_AUTHORIZATION=a._credentials["HTTP_AUTHORIZATION"], HTTP_X_ORGANISATION=org_b.sous_domaine)
    assert [d["nom"] for d in a.get("/api/v1/dossiers/", {"libres": "true"}).data] == ["Dossier de A"]
    # Un jeton falsifié est refusé.
    assert APIClient(HTTP_AUTHORIZATION="Bearer faux.jeton.signe").get("/api/v1/dossiers/").json()["code"] == "token_not_valid"

    # Fichiers : rangés dans le dossier de l'organisation ; le lien signé de A ne sert pas pour B.
    a = _client(org_a, _admin(org_a))
    fichier = SimpleUploadedFile("rapport.txt", b"contenu de A")
    assert a.post("/api/v1/documents/", {"nom": "rapport", "fichier": fichier}, format="multipart").status_code == 201
    lien = a.get("/api/v1/documents/").data["results"][0]["derniere_version"]["fichier"]
    chemin = lien.split("testserver")[1]
    assert chemin.endswith(f"?org={org_a.sous_domaine}")
    assert APIClient().get(chemin).status_code == 200
    assert APIClient().get(chemin.replace(org_a.sous_domaine, org_b.sous_domaine)).status_code == 404
    with contexte.dans_organisation(org_a):
        from apps.documents.models import DocumentVersion

        assert "/organisations/essai-iso-a/" in DocumentVersion.objects.get().fichier.path

    # Chiffrement : une clé par organisation.
    from apps.plaintes.chiffrement import chiffrer, dechiffrer

    with contexte.dans_organisation(org_a):
        secret = chiffrer("Récit confidentiel")
        assert dechiffrer(secret) == "Récit confidentiel"
    with contexte.dans_organisation(org_b):
        assert dechiffrer(secret) != "Récit confidentiel"


def test_adresse_unique(deux_organisations):
    org_a, _ = deux_organisations
    anonyme = APIClient()
    # Sans compte : la plateforme (connexion, inscription), aucune donnée d'organisation.
    assert anonyme.get("/api/v1/identite/").data["espace"] is None
    assert anonyme.get("/api/v1/projets/").json()["code"] == "connexion_requise"
    # Pages publiques d'une organisation : ?org= (ou X-Organisation) ; inconnue, puis suspendue.
    assert anonyme.get("/api/v1/identite/", {"org": org_a.sous_domaine}).data["nom"] == "Organisation A"
    assert anonyme.get("/api/v1/identite/", {"org": "inconnue"}).json()["code"] == "espace_inconnu"
    Organisation.objects.using("central").filter(pk=org_a.pk).update(statut="SUSPENDUE")
    assert APIClient(HTTP_X_ORGANISATION=org_a.sous_domaine).get("/api/v1/identite/").json()["code"] == "organisation_suspendue"
    Organisation.objects.using("central").filter(pk=org_a.pk).update(statut="ACTIVE")


def test_sous_domaines_refuses(deux_organisations):
    for mauvais in ("www", "admin", "a", "ab", "avec_tiret_bas", "-debut", "essai-iso-a"):
        with pytest.raises(gestion.ErreurOrganisation):
            gestion.verifier_sous_domaine(mauvais)


def test_connexion_par_courriel(deux_organisations, settings):
    """Courriel + mot de passe sur l'adresse unique → code → session dans la bonne organisation."""
    from django.core import mail
    from django.core.cache import cache

    from apps.accounts.models import User

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    cache.clear()
    org_a, org_b = deux_organisations
    client = APIClient()
    mot_de_passe = "Un-mot-de-passe-solide-1"
    assert client.post("/api/v1/auth/token/", {"courriel": "admin@essai-iso-b.org", "password": "faux"}).status_code == 401
    assert client.post("/api/v1/auth/token/", {"courriel": "personne@nulle-part.bf", "password": mot_de_passe}).status_code == 401
    etape = client.post("/api/v1/auth/token/", {"courriel": "ADMIN@essai-iso-b.org", "password": mot_de_passe}).data
    assert etape["jeton"].startswith("essai-iso-b~")
    # Préfixe modifié : la signature ne correspond plus.
    falsifie = etape["jeton"].replace("essai-iso-b~", "essai-iso-a~")
    assert client.post("/api/v1/auth/double-authentification/code/", {"jeton": falsifie, "code": _code(mail)}).status_code == 403
    etape = client.post("/api/v1/auth/token/", {"courriel": "admin@essai-iso-b.org", "password": mot_de_passe}).data
    session = client.post("/api/v1/auth/double-authentification/code/", {"jeton": etape["jeton"], "code": _code(mail)}).data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access']}")
    assert client.get("/api/v1/identite/").data["nom"] == "Organisation B"
    assert client.get("/api/v1/utilisateurs/me/").data["est_operateur"] is False
    # Renouvellement : la marque « org » du jeton de rafraîchissement désigne l'organisation.
    assert APIClient().post("/api/v1/auth/token/refresh/", {"refresh": session["refresh"]}).status_code == 200

    # Une adresse n'appartient qu'à un compte : l'organisation B ne peut pas reprendre celle d'un compte de A.
    reponse = client.post("/api/v1/utilisateurs/", {"username": "copie", "email": "admin@essai-iso-a.org", "role": "ADMIN",
                                                    "password": "Autre-mot-de-passe-1"}, format="json")
    assert reponse.status_code == 400 and "email" in reponse.data

    # Opérateurs Expertise-ID : page à part ({console: true}), comptes de la base centrale seulement.
    User.objects.create_superuser(username="operateur", password=mot_de_passe, email="op@expertise-id.com", role="ADMIN")
    assert client.post("/api/v1/auth/token/", {"courriel": "op@expertise-id.com", "password": mot_de_passe}).status_code == 401
    etape = APIClient().post("/api/v1/auth/token/", {"courriel": "op@expertise-id.com", "password": mot_de_passe, "console": True},
                             format="json").data
    assert etape["jeton"].startswith("~")
    operateur = APIClient()
    session = operateur.post("/api/v1/auth/double-authentification/code/", {"jeton": etape["jeton"], "code": _code(mail)}).data
    operateur.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access']}")
    assert operateur.get("/api/v1/utilisateurs/me/").data["est_operateur"] is True
    assert operateur.get("/api/v1/console/organisations/").status_code == 200
    assert operateur.get("/api/v1/projets/").status_code == 403


def test_inscription_puis_activation_par_la_console(deux_organisations, settings, monkeypatch):
    """Profil (courriel + mot de passe) → « Activer » dans la console → connexion par courriel."""
    from django.core import mail
    from django.core.cache import cache

    from apps.accounts.models import DemandeInscription, User

    from . import activation

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    cache.clear()
    # La création se fait d'ordinaire en arrière-plan : ici, tout de suite.
    monkeypatch.setattr(activation.threading, "Thread",
                        lambda target, **k: type("T", (), {"start": staticmethod(target)})())
    anonyme = APIClient()
    profil = {"organisation": "ONG Nouvelle", "type_organisation": "ONG", "pays": "Burkina Faso", "contact_nom": "Awa Kaboré",
              "courriel": "awa@ong-nouvelle.bf", "telephone": "70000000", "mot_de_passe": "Un-mot-de-passe-solide-2026",
              "conditions": True}
    # Adresse déjà utilisée par un compte d'une organisation : refusée.
    assert anonyme.post("/api/v1/public/inscription/", {**profil, "courriel": "admin@essai-iso-a.org"}, format="json").status_code == 400
    assert anonyme.post("/api/v1/public/inscription/", profil, format="json").status_code == 201
    demande = DemandeInscription.objects.using("central").get(courriel="awa@ong-nouvelle.bf")
    assert demande.identifiant == "awa@ong-nouvelle.bf" and demande.sous_domaine == "ong-nouvelle"
    # Avant l'activation : page d'abonnement.
    connexion = anonyme.post("/api/v1/auth/token/", {"courriel": profil["courriel"], "password": profil["mot_de_passe"]})
    assert connexion.status_code == 403 and connexion.data["code"] == "abonnement_requis"

    operateur = User.objects.create_superuser(username="operateur", password="x", email="op@expertise-id.com", role="ADMIN")
    console = APIClient()
    console.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons(operateur)['access']}")
    assert APIClient().get("/api/v1/console/demandes/").status_code == 401
    try:
        assert console.post(f"/api/v1/console/demandes/{demande.pk}/activer/", {"zones": False}, format="json").status_code == 202
        demande.refresh_from_db(using="central")
        assert demande.statut == "ACTIVEE", demande.erreur_activation
        org = Organisation.objects.using("central").get(sous_domaine="ong-nouvelle")
        assert org.statut == "ACTIVE" and any("Votre espace est prêt" in m.subject for m in mail.outbox)
        # Connexion par courriel : mot de passe choisi à l'inscription, puis code.
        client = APIClient()
        etape = client.post("/api/v1/auth/token/", {"courriel": profil["courriel"], "password": profil["mot_de_passe"]}).data
        session = client.post("/api/v1/auth/double-authentification/code/", {"jeton": etape["jeton"], "code": _code(mail)}).data
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access']}")
        moi = client.get("/api/v1/utilisateurs/me/").data
        assert moi["email"] == profil["courriel"] and moi["role"] == "ADMIN" and moi["est_operateur"] is False
        assert client.get("/api/v1/identite/").data["nom"] == "ONG Nouvelle"
        # L'administrateur d'une organisation ne voit jamais les inscriptions des autres.
        assert client.get("/api/v1/demandes-inscription/").status_code == 403
        # Suspension par la console : effet immédiat.
        assert console.post(f"/api/v1/console/organisations/{org.pk}/statut/", {"statut": "SUSPENDUE"}, format="json").status_code == 200
        assert client.get("/api/v1/utilisateurs/me/").json()["code"] == "organisation_suspendue"
    finally:
        org = Organisation.objects.using("central").filter(sous_domaine="ong-nouvelle").first()
        if org:
            gestion.supprimer(org)


def test_demo(deux_organisations):
    _, org_b = deux_organisations
    anonyme = APIClient()
    assert anonyme.get("/api/v1/identite/").data["demo_disponible"] is False
    assert anonyme.post("/api/v1/public/demo/").status_code == 403
    Organisation.objects.using("central").filter(pk=org_b.pk).update(mode_demo=True)
    try:
        assert anonyme.get("/api/v1/identite/").data["demo_disponible"] is True
        visiteur = APIClient()
        visiteur.credentials(HTTP_AUTHORIZATION=f"Bearer {anonyme.post('/api/v1/public/demo/').data['access']}")
        identite = visiteur.get("/api/v1/identite/").data
        assert identite["mode_demo"] is True and identite["espace"]["sous_domaine"] == org_b.sous_domaine
    finally:
        Organisation.objects.using("central").filter(pk=org_b.pk).update(mode_demo=False)
