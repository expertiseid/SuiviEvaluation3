"""Lot 2 du mécanisme de plaintes : réception (formulaire public, saisie agent, suivi par code)."""
import re

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User

from .models import Categorie, Dossier, EtapeCircuit, Mecanisme, TypeRetour

URL = "/api/v1/plaintes/"
PUBLIC = "/api/v1/public/plaintes/"


@pytest.fixture(autouse=True)
def _cache_vide():
    cache.clear()  # compteurs de la limitation des envois
    yield
    cache.clear()


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_recep", password="x", role=ROLE_ADMIN)


@pytest.fixture
def point_focal(db):
    return User.objects.create_user(username="pf_recep", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def agent(db):
    return User.objects.create_user(username="agent_recep", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


def _client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


@pytest.fixture
def actif(admin, point_focal):
    """Mécanisme standard activé ; le circuit confidentiel est confié au point focal."""
    c = _client(admin)
    assert c.post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    assert c.post(URL + "mecanisme/activer/").status_code == 200
    return Mecanisme.courant()


def _depot(**champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "La pompe est en panne.",
               "consentement": True}
    donnees.update(champs)
    return _client().post(PUBLIC + "deposer/", donnees, format="json")


@pytest.mark.django_db
def test_formulaire_ferme_tant_que_le_mecanisme_est_inactif(admin):
    assert _client().get(PUBLIC + "formulaire/").data["disponible"] is False
    assert _client().post(PUBLIC + "deposer/", {"description": "x"}, format="json").status_code == 400


@pytest.mark.django_db
def test_plainte_anonyme_et_suivi_par_code(actif):
    """Scénario 4 : aucune coordonnée exigée ni conservée ; le code de suivi donne l'état général seul."""
    formulaire = _client().get(PUBLIC + "formulaire/").data
    assert formulaire["disponible"] and formulaire["anonymat_autorise"] and formulaire["types"]
    r = _depot(anonyme=True, nom="Ne doit pas rester", telephone="70000000", mode_reponse="TELEPHONE")
    assert r.status_code == 201, r.data
    dossier = Dossier.objects.get(numero=r.data["numero"])
    assert dossier.anonyme and not (dossier.nom or dossier.telephone or dossier.courriel)
    assert dossier.mode_reponse == "AUCUN" and dossier.canal == "FORMULAIRE" and dossier.saisi_par is None
    assert dossier.statut == "RECU" and dossier.circuit.nom == "Circuit standard" and dossier.etape.nom == "Réception"
    # Numéro lisible sans donnée personnelle ; code aléatoire conservé seulement sous forme d'empreinte.
    assert re.fullmatch(r"MGP-\d{4}-00001", dossier.numero)
    code = r.data["code_suivi"]
    assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code)
    assert code.replace("-", "") not in dossier.empreinte_code_suivi
    suivi = _client().post(PUBLIC + "suivi/", {"code": code.lower().replace("-", " ")}, format="json")
    assert suivi.status_code == 200 and set(suivi.data) == {"numero", "date_reception", "statut", "complement_possible", "pieces"}
    assert _client().post(PUBLIC + "suivi/", {"code": "AAAA-BBBB-CCCC"}, format="json").status_code == 404
    # Second dossier : la séquence continue.
    assert _depot().data["numero"].endswith("-00002")


@pytest.mark.django_db
def test_regles_du_formulaire_public(actif):
    assert "consentement" in _depot(consentement=False).data
    assert "description" in _depot(description="  ").data
    assert "courriel" in _depot(mode_reponse="COURRIEL").data
    assert _depot(site_web="http://robot").status_code == 400  # champ piège
    Mecanisme.objects.filter(pk=1).update(anonymat_autorise=False)
    assert "anonyme" in _depot(anonyme=True).data
    assert "nom" in _depot().data
    assert _depot(nom="Awa").status_code == 201


@pytest.mark.django_db
def test_limitation_des_envois(actif):
    for _ in range(10):
        assert _depot().status_code == 201
    assert _depot().status_code == 429
    assert Dossier.objects.count() == 10


@pytest.mark.django_db
def test_sensible_transmis_au_circuit_confidentiel(actif, admin, agent, point_focal):
    """Scénario 13 : l'agent ne garde que le numéro ; le point focal du circuit et l'Administrateur voient le dossier."""
    eas = Categorie.objects.get(nom="Exploitation et abus sexuels")
    r = _client(agent).post(URL + "dossiers/", {
        "canal": "TELEPHONE", "date_reception": "2026-01-15", "recueilli_directement": True,
        "type_retour": TypeRetour.objects.get(nom="Signalement").id, "categorie": eas.id, "description": "Récit.",
    }, format="json")
    assert r.status_code == 201, r.data
    assert r.data["sensible"] is True and r.data["visible"] is False and "dossier" not in r.data
    dossier = Dossier.objects.get(numero=r.data["numero"])
    assert dossier.circuit.sensible and str(dossier.date_reception) == "2026-01-15"
    for personne, voit in ((agent, False), (admin, True), (point_focal, True)):
        c = _client(personne)
        assert (c.get(URL + "dossiers/").data["count"] == 1) is voit
        assert c.get(f"{URL}dossiers/{dossier.id}/").status_code == (200 if voit else 404)
    # Question système : un retour visant le personnel est sensible, même sans catégorie sensible.
    r = _depot(concerne_personnel=True)
    assert Dossier.objects.get(numero=r.data["numero"]).sensible is True
    # Un dossier ordinaire saisi par l'agent reste visible et complet.
    r = _client(agent).post(URL + "dossiers/", {
        "canal": "BOITE", "type_retour": TypeRetour.objects.get(nom="Suggestion").id, "description": "Idée.",
    }, format="json")
    assert r.data["visible"] is True and r.data["dossier"]["canal"] == "BOITE"
    assert _client(agent).post(URL + "dossiers/", {"canal": "FORMULAIRE", "description": "x"}, format="json").status_code == 400


@pytest.mark.django_db
def test_module_cache_refuse_meme_en_lecture(actif, agent):
    _depot()
    agent.acces_modules = {"/plaintes": "MASQUE"}
    agent.save()
    from rest_framework_simplejwt.tokens import RefreshToken

    c = APIClient()  # vrai jeton : le contrôle des modules se fait avant l'authentification DRF
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(agent).access_token}")
    assert c.get(URL + "dossiers/").status_code == 403
