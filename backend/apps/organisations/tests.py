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
    # Sans adresse courriel, un compte ne pourrait pas se connecter : elle est obligatoire.
    sans = client.post("/api/v1/utilisateurs/", {"username": "sans_courriel", "role": "ADMIN", "password": "Autre-mot-de-passe-1"}, format="json")
    assert sans.status_code == 400 and "email" in sans.data

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
    # Vue d'ensemble (supervision.py) : organisations, disque commun, serveurs ; opérateurs seulement.
    vue = operateur.get("/api/v1/console/vue-ensemble/").data
    assert vue["organisations"]["actives"] >= 2 and vue["serveurs"]["donnees"]["joignable"] is True
    assert {e["nom"] for e in vue["stockage"]["espaces"]} >= {"Organisation A", "Organisation B"}
    assert vue["disque"]["total"] > 0 and vue["serveurs"]["plateforme"]["memoire"]["total"] > 0
    assert client.get("/api/v1/console/vue-ensemble/").status_code == 403


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
    creation = anonyme.post("/api/v1/public/inscription/", profil, format="json")
    assert creation.status_code == 201
    # Offre Partenariat : pas de paiement en ligne, Expertise-ID valide depuis la console.
    anonyme.post("/api/v1/public/inscription/offre/", {"reference": creation.data["reference"], "offre": "PARTENARIAT"}, format="json")
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
        validation = [m for m in mail.outbox if m.to == ["awa@ong-nouvelle.bf"] and "partenariat est validé" in m.subject]
        assert org.statut == "ACTIVE" and len(validation) == 1 and "a validé votre demande de partenariat" in validation[0].body
        assert all("Sous-domaine" not in m.body for m in mail.outbox)
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


def test_espace_de_stockage(deux_organisations, monkeypatch):
    """Espace selon l'offre (25 Go…) : un fichier qui le dépasserait est refusé ; Expertise-ID peut l'agrandir."""
    from django.core.cache import cache
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from rest_framework.exceptions import ValidationError

    from apps.accounts.models import User

    from . import quota

    org_a, _ = deux_organisations
    Organisation.objects.using("central").filter(pk=org_a.pk).update(offre="STANDARD_25")
    org = Organisation.objects.using("central").get(pk=org_a.pk)
    assert quota.limite_go(org) == 25
    monkeypatch.setattr(quota, "GO", 10_000)  # 25 « Go » = 250 000 octets, pour l'essai
    monkeypatch.setattr(quota, "_taille_base", lambda org: 0)
    cache.clear()

    admin = _client(org_a, _admin(org_a))
    depart = admin.get("/api/v1/stockage/").data  # fichiers laissés par les autres essais
    assert depart["limite"] == 250_000 and depart["limite_go"] == 25 and depart["utilise"] < 1000
    depart = depart["utilise"]
    with contexte.cles_de(org), monkeypatch.context() as m:
        m.setattr(contexte, "courante", lambda: org)
        nom = default_storage.save("essai/a.bin", ContentFile(b"x" * 200_000))
        assert quota.utilise(org) == depart + 200_000
        with pytest.raises(ValidationError):
            default_storage.save("essai/b.bin", ContentFile(b"x" * 60_000))
        assert not default_storage.exists("essai/b.bin")

    # Console : Expertise-ID agrandit l'espace à 50 Go, puis revient à celui de l'offre.
    operateur = APIClient()
    operateur.force_authenticate(User.objects.create_superuser(username="op_stockage", password="x", email="op@expertise-id.com", role="ADMIN"))
    reponse = operateur.post(f"/api/v1/console/organisations/{org.pk}/stockage/", {"stockage_go": 50}, format="json")
    assert reponse.status_code == 200 and reponse.data["stockage"]["limite_go"] == 50
    assert reponse.data["stockage"]["utilise"] == depart + 200_000
    assert operateur.post(f"/api/v1/console/organisations/{org.pk}/stockage/", {"stockage_go": 0}, format="json").status_code == 400
    assert operateur.post(f"/api/v1/console/organisations/{org.pk}/stockage/", {"stockage_go": None}, format="json").data["stockage_go"] is None
    assert admin.post(f"/api/v1/console/organisations/{org.pk}/stockage/", {"stockage_go": 500}, format="json").status_code == 403
    with contexte.cles_de(org):
        default_storage.delete(nom)


def test_achat_de_stockage(deux_organisations, monkeypatch, settings):
    """Page Stockage : l'administrateur paie 2 × 10 Go par mobile money ; payé, l'espace grandit aussitôt, une seule fois."""
    from django.core import mail
    from django.core.cache import cache

    from . import paiement
    from .models import PaiementAbonnement
    from .test_paiement import CinetPaySimule

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.COURRIEL_ABONNEMENTS = "abonnements@expertise-id.com"
    settings.CINETPAY_API_KEY, settings.CINETPAY_API_PASSWORD = "sk_test_cle", "mot-de-passe"
    settings.ABONNEMENT_PRIX_TRANCHE, settings.ABONNEMENT_PRIX_TRANCHE_USD = 3000, 5
    simule = CinetPaySimule()
    monkeypatch.setattr(paiement, "_appel", simule)
    cache.clear()
    org_a, _ = deux_organisations
    Organisation.objects.using("central").filter(pk=org_a.pk).update(offre="STANDARD_25", stockage_go=None)

    admin = _client(org_a, _admin(org_a))
    page = admin.get("/api/v1/stockage/").data
    assert page["limite_go"] == 25 and page["offre_go"] == 25 and page["peut_acheter"] is True
    assert page["tarifs"]["tranche"] == 3000 and page["achats"] == []
    assert admin.post("/api/v1/stockage/achat/", {"tranches": 0, "mois": 1}, format="json").status_code == 400

    reponse = admin.post("/api/v1/stockage/achat/", {"tranches": 2, "mois": 3}, format="json")
    assert reponse.status_code == 200 and reponse.data["montant"] == 3 * 2 * 3000
    envoi = simule.appels[-1][2]
    assert envoi["success_url"].endswith(f"/stockage?paiement={reponse.data['paiement']}") and "+ 20 Go" in envoi["designation"]
    ref = reponse.data["paiement"]
    # Pas encore payé : rien ne change. L'autre organisation ne voit pas ce paiement.
    assert admin.get(f"/api/v1/stockage/paiement/{ref}/").data["statut"] == "EN_ATTENTE"
    simule.statut = "SUCCESS"
    for _ in range(2):  # retour sur la page puis notification de CinetPay : agrandi une seule fois
        admin.get(f"/api/v1/stockage/paiement/{ref}/")
    APIClient().post("/api/v1/public/inscription/paiement/notification/", {"merchant_transaction_id": ref, "notify_token": "nt-secret"}, format="json")
    assert Organisation.objects.using("central").get(pk=org_a.pk).stockage_go == 45
    assert PaiementAbonnement.objects.using("central").get(reference=ref).statut == "PAYE"
    assert [m.subject for m in mail.outbox] == [f"Stockage ajouté : {org_a.nom}"] and "de 25 à 45 Go" in mail.outbox[0].body
    page = admin.get("/api/v1/stockage/").data
    assert page["limite_go"] == 45 and len(page["achats"]) == 1
    # Le lien public d'un paiement d'abonnement ne donne rien sur un achat de stockage.
    assert APIClient().get(f"/api/v1/public/inscription/paiement/{ref}/").status_code == 400

    # Carte bancaire : demande transmise à Expertise-ID, montant en dollars ; espace inchangé.
    assert admin.post("/api/v1/stockage/achat/", {"tranches": 1, "mois": 12, "moyen": "carte"}, format="json").data == {"carte": True}
    assert mail.outbox[-1].subject == f"Stockage par carte demandé : {org_a.nom}" and "60 $ HT" in mail.outbox[-1].body
    assert Organisation.objects.using("central").get(pk=org_a.pk).stockage_go == 45
    Organisation.objects.using("central").filter(pk=org_a.pk).update(stockage_go=None)


def test_alertes_de_stockage(deux_organisations, monkeypatch, settings):
    """À 90 % puis à 100 % : les administrateurs sont prévenus une fois par seuil (cloche, courriel), Expertise-ID quand c'est plein."""
    from django.core import mail

    from apps.notifications.models import Notification

    from . import quota

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.COURRIEL_ABONNEMENTS = "abonnements@expertise-id.com"
    org_a, _ = deux_organisations
    Organisation.objects.using("central").filter(pk=org_a.pk).update(offre="STANDARD_25", stockage_go=None, stockage_alerte=0)
    occupe = {"octets": 10 * quota.GO}
    monkeypatch.setattr(quota, "utilise", lambda org: occupe["octets"])

    def notifications():
        with contexte.dans_organisation(org_a):
            return list(Notification.objects.filter(type="STOCKAGE").values_list("titre", "lien"))

    with contexte.dans_organisation(org_a):
        quota.alerter()
    assert notifications() == []
    occupe["octets"] = int(23 * quota.GO)  # 92 %
    for _ in range(2):  # une seule fois par seuil
        with contexte.dans_organisation(org_a):
            quota.alerter()
    assert notifications() == [("Espace de stockage presque plein", "/stockage")]
    assert mail.outbox[-1].to == ["admin@essai-iso-a.org"] and "23,0 Go sur 25 Go (90 %)" in mail.outbox[-1].body

    # Un fichier refusé : « plein », administrateurs et Expertise-ID prévenus.
    with contexte.dans_organisation(org_a):
        with pytest.raises(Exception):
            quota.verifier(3 * quota.GO)
    assert notifications()[0] == ("Espace de stockage plein", "/stockage")
    assert any(m.subject == f"Espace de stockage plein : {org_a.nom}" for m in mail.outbox)

    # Espace agrandi (achat ou console) : de nouveau sous les seuils, alertes à nouveau possibles.
    Organisation.objects.using("central").filter(pk=org_a.pk).update(stockage_go=50, stockage_alerte=0)
    with contexte.dans_organisation(org_a):
        quota.alerter()
        Notification.objects.filter(type="STOCKAGE").delete()
    assert Organisation.objects.using("central").get(pk=org_a.pk).stockage_alerte == 0
    Organisation.objects.using("central").filter(pk=org_a.pk).update(stockage_go=None)


def test_alerte_disque_commun(monkeypatch, settings):
    """Disque commun (Volume) : courriel à Expertise-ID près du plafond ou rempli à 90 %, une fois par jour."""
    import shutil
    from collections import namedtuple

    from django.core import mail
    from django.core.cache import cache

    from . import quota

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.COURRIEL_ABONNEMENTS = "abonnements@expertise-id.com"
    Usage = namedtuple("Usage", "total used free")
    disque = {"usage": Usage(60 * quota.GO, 6 * quota.GO, 54 * quota.GO)}
    monkeypatch.setattr(shutil, "disk_usage", lambda chemin: disque["usage"])
    with contexte.cles_de(None):
        cache.delete("alerte-disque")
    envoyes = len(mail.outbox)

    settings.VOLUME_PLAFOND_GO = 0  # sans plafond déclaré : pas de surveillance
    disque["usage"] = Usage(60 * quota.GO, 58 * quota.GO, 2 * quota.GO)
    quota.alerter_disque()
    settings.VOLUME_PLAFOND_GO = 1000
    disque["usage"] = Usage(60 * quota.GO, 6 * quota.GO, 54 * quota.GO)
    quota.alerter_disque()
    assert len(mail.outbox) == envoyes

    disque["usage"] = Usage(60 * quota.GO, 58 * quota.GO, 2 * quota.GO)  # 97 % : l'agrandissement n'a pas suivi
    quota.alerter_disque()
    quota.alerter_disque()  # une seule fois par jour
    assert [m.subject for m in mail.outbox[envoyes:]] == ["Disque des données rempli à 97 %"]
    assert mail.outbox[-1].to == ["abonnements@expertise-id.com"]

    with contexte.cles_de(None):
        cache.delete("alerte-disque")
    disque["usage"] = Usage(950 * quota.GO, 500 * quota.GO, 450 * quota.GO)
    quota.alerter_disque()
    assert mail.outbox[-1].subject == "Disque des données proche du plafond (950 Go sur 1000 Go)"
    with contexte.cles_de(None):
        cache.delete("alerte-disque")
