"""Droits précis par projet, document stratégique et élément (apps.projects.droits)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import (
    NIVEAU_ACCES_LECTURE_ECRITURE, NIVEAU_ACCES_LECTURE_SEULE, ROLE_ADMIN, ROLE_ANIMATEUR_TERRAIN, ROLE_CHARGE_SE,
)
from apps.accounts.models import User
from apps.core.models import EtatApprobation
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau
from apps.suivi.models import PointSuivi

from .droits import droits_document, droits_element, droits_projet
from .models import Activite, DroitObjet, Projet


def _client(user, jwt=False):
    client = APIClient()
    if jwt:  # vrai jeton : passe par le filtre des modules (ModulesMasquesMiddleware)
        from apps.accounts import double_auth

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {double_auth.jetons(user)['access']}")
    else:
        client.force_authenticate(user)
    return client


def _projet(code, **champs):
    return Projet.objects.create(nom=code, code=code, date_debut="2026-01-01", date_fin="2026-12-31", statut="EN_COURS", **champs)


@pytest.fixture
def projets(db):
    return _projet("DR-A"), _projet("DR-B")


def _creer_activite(client, projet):
    return client.post("/api/v1/activites/", {"projet": projet.id, "libelle": "Nouvelle"}, format="json")


@pytest.mark.django_db
def test_lecture_seule_globale_mais_ecriture_sur_un_projet(projets):
    a, b = projets
    lecteur = User.objects.create_user(username="lect", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_SEULE)
    DroitObjet.objects.create(utilisateur=lecteur, projet=a, acces="ECRITURE")
    for client in (_client(lecteur), _client(lecteur, jwt=True)):
        assert _creer_activite(client, a).status_code == 201
        assert _creer_activite(client, b).status_code == 403
    activite_b = Activite.objects.create(projet=b, libelle="B1")
    assert _client(lecteur).patch(f"/api/v1/activites/{activite_b.id}/", {"libelle": "X"}, format="json").status_code == 403
    assert _client(lecteur).get(f"/api/v1/projets/{a.id}/").data["mes_droits"] == {"ecriture": True, "approuver": False}


@pytest.mark.django_db
def test_ecriture_globale_mais_lecture_seule_sur_un_projet(projets):
    a, b = projets
    redacteur = User.objects.create_user(username="red", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    DroitObjet.objects.create(utilisateur=redacteur, projet=b, acces="LECTURE")
    client = _client(redacteur)
    assert _creer_activite(client, a).status_code == 201
    assert _creer_activite(client, b).status_code == 403
    activite_b = Activite.objects.create(projet=b, libelle="B1")
    assert client.patch(f"/api/v1/activites/{activite_b.id}/", {"libelle": "X"}, format="json").status_code == 403
    assert client.delete(f"/api/v1/activites/{activite_b.id}/").status_code == 403
    # Toutes les voies : un point de suivi (enregistrement contrôlé par le verrou du projet) est refusé aussi.
    reponse = client.post("/api/v1/points-suivi/", {"activite": activite_b.id, "periode_debut": "2026-01-01",
                                                    "periode_fin": "2026-01-31", "quantite_realisee": 2}, format="json")
    assert reponse.status_code == 403
    # « Ailleurs : lecture seule » : plus rien d'écrit hors des droits précis.
    redacteur.hors_droits_precis = "LECTURE"
    redacteur.save()
    assert _creer_activite(_client(User.objects.get(pk=redacteur.pk)), a).status_code == 403


@pytest.mark.django_db
def test_droit_precis_rend_le_projet_visible(projets):
    a, b = projets
    animateur = User.objects.create_user(username="anim", password="x", role=ROLE_ANIMATEUR_TERRAIN)
    DroitObjet.objects.create(utilisateur=animateur, projet=b, acces="LECTURE")
    codes = {p["code"] for p in _client(animateur).get("/api/v1/projets/").data["results"]}
    assert "DR-B" in codes and "DR-A" not in codes


@pytest.mark.django_db
def test_approuver_un_projet_seulement():
    a = _projet("DR-AP1", approbation_realisations=True)
    b = _projet("DR-AP2", approbation_realisations=True)
    saisie = User.objects.create_user(username="sais", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    approbateur = User.objects.create_user(username="appr", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_SEULE)
    DroitObjet.objects.create(utilisateur=approbateur, projet=a, acces="LECTURE", approuver=True)
    points = {}
    for projet in (a, b):
        activite = Activite.objects.create(projet=projet, libelle="X")
        assert _client(saisie).post("/api/v1/points-suivi/", {"activite": activite.id, "periode_debut": "2026-01-01",
                                                              "periode_fin": "2026-01-31", "quantite_realisee": 2},
                                    format="json").status_code == 201
        points[projet.code] = PointSuivi.tous.get(activite=activite)
    assert points["DR-AP1"].etat_approbation == EtatApprobation.EN_ATTENTE

    client = _client(approbateur)
    liste = client.get("/api/v1/approbations/").data
    assert liste["peut_approuver"] is True
    assert {s["projet_code"] for s in liste["saisies"] if s["approuvable"]} == {"DR-AP1"}
    # Il approuve dans A (avec la seule lecture : l'approbation n'est pas une modification), pas dans B.
    assert client.post(f"/api/v1/approbations/saisies/point/{points['DR-AP1'].id}/", {"approuver": True}, format="json").status_code == 200
    assert client.post(f"/api/v1/approbations/saisies/point/{points['DR-AP2'].id}/", {"approuver": True}, format="json").status_code == 403
    points["DR-AP1"].refresh_from_db()
    assert points["DR-AP1"].etat_approbation == EtatApprobation.APPROUVEE


@pytest.mark.django_db
def test_strategie_pilier_et_programme():
    redacteur = User.objects.create_user(username="strat", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    strategie = CadreStrategique.objects.create(nom="Stratégie")
    autre = CadreStrategique.objects.create(nom="Autre")
    pilier_niveau = TypeNiveau.objects.create(cadre_strategique=strategie, nom_niveau="Pilier", ordre=1)
    pilier1 = ElementStrategique.objects.create(type_niveau=pilier_niveau, nom="Pilier 1")
    pilier2 = ElementStrategique.objects.create(type_niveau=pilier_niveau, nom="Pilier 2")
    programme = CadreStrategique.objects.create(nom="Programme", document_parent=strategie)
    client = _client(redacteur)

    # Sans droit précis : comme avant, seul l'Administrateur modifie les stratégies.
    assert client.patch(f"/api/v1/cadres-strategiques/{strategie.id}/", {"nom": "S"}, format="json").status_code == 403

    DroitObjet.objects.create(utilisateur=redacteur, document=strategie, acces="ECRITURE")
    DroitObjet.objects.create(utilisateur=redacteur, element=pilier2, acces="LECTURE", approuver=True)
    redacteur = User.objects.get(pk=redacteur.pk)
    client = _client(redacteur)
    assert client.patch(f"/api/v1/cadres-strategiques/{strategie.id}/", {"nom": "S"}, format="json").status_code == 200
    assert client.patch(f"/api/v1/elements-strategiques/{pilier1.id}/", {"nom": "P1"}, format="json").status_code == 200
    assert client.patch(f"/api/v1/elements-strategiques/{pilier2.id}/", {"nom": "P2"}, format="json").status_code == 403
    assert client.post("/api/v1/elements-strategiques/", {"type_niveau": pilier_niveau.id, "nom": "Pilier 3"},
                       format="json").status_code == 201
    assert client.patch(f"/api/v1/cadres-strategiques/{autre.id}/", {"nom": "A"}, format="json").status_code == 403
    # Le programme rattaché à la stratégie suit son droit ; le pilier 2 a le sien (lecture, approbation).
    assert droits_document(redacteur, programme.id).ecriture is True
    assert droits_element(redacteur, pilier2.id).approuver is True and droits_element(redacteur, pilier1.id).approuver is False
    assert client.get(f"/api/v1/elements-strategiques/{pilier2.id}/").data["mes_droits"] == {"ecriture": False, "approuver": True}


@pytest.mark.django_db
def test_fiche_utilisateur_enregistre_les_droits(projets):
    a, b = projets
    admin = _client(User.objects.create_user(username="adm_dr", password="x", role=ROLE_ADMIN))
    cible = User.objects.create_user(username="cible", password="x", role=ROLE_CHARGE_SE, email="cible@exemple.org")
    strategie = CadreStrategique.objects.create(nom="S")
    reponse = admin.patch(f"/api/v1/utilisateurs/{cible.id}/", {
        "hors_droits_precis": "LECTURE",
        "droits_objets": [{"projet": a.id, "acces": "ECRITURE", "approuver": True}, {"document": strategie.id, "acces": "LECTURE"}],
    }, format="json")
    assert reponse.status_code == 200, reponse.data
    fiche = admin.get(f"/api/v1/utilisateurs/{cible.id}/").data
    assert fiche["hors_droits_precis"] == "LECTURE" and len(fiche["droits_objets"]) == 2
    cible = User.objects.get(pk=cible.pk)
    assert droits_projet(cible, a.id).approuver and not droits_projet(cible, b.id).ecriture
    doublon = admin.patch(f"/api/v1/utilisateurs/{cible.id}/", {"droits_objets": [{"projet": a.id}, {"projet": a.id}]}, format="json")
    assert doublon.status_code == 400
    deux_cibles = admin.patch(f"/api/v1/utilisateurs/{cible.id}/", {"droits_objets": [{"projet": a.id, "document": strategie.id}]},
                              format="json")
    assert deux_cibles.status_code == 400


@pytest.mark.django_db
def test_approbation_des_modifications_d_une_strategie():
    from apps.strategy.models import AppreciationStrategique

    from .models import DemandeModification

    strategie = CadreStrategique.objects.create(nom="Stratégie A", approbation_modifications=True)
    niveau = TypeNiveau.objects.create(cadre_strategique=strategie, nom_niveau="Pilier", ordre=1)
    pilier1 = ElementStrategique.objects.create(type_niveau=niveau, nom="Pilier 1")
    pilier2 = ElementStrategique.objects.create(type_niveau=niveau, nom="Pilier 2")
    redacteur = User.objects.create_user(username="red_s", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    approbateur_p1 = User.objects.create_user(username="app_p1", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_SEULE)
    approbateur_p2 = User.objects.create_user(username="app_p2", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_SEULE)
    DroitObjet.objects.create(utilisateur=redacteur, document=strategie, acces="ECRITURE")
    DroitObjet.objects.create(utilisateur=approbateur_p1, element=pilier1, acces="LECTURE", approuver=True)
    DroitObjet.objects.create(utilisateur=approbateur_p2, element=pilier2, acces="LECTURE", approuver=True)
    client = _client(redacteur)

    # Modification du pilier 1 : demande, rien n'est changé tant qu'elle n'est pas approuvée.
    reponse = client.patch(f"/api/v1/elements-strategiques/{pilier1.id}/", {"nom": "Pilier 1 révisé"}, format="json")
    assert reponse.status_code == 202
    pilier1.refresh_from_db()
    assert pilier1.nom == "Pilier 1"
    demande = DemandeModification.objects.get(pk=reponse.data["demande_approbation"])
    assert (demande.document_id, demande.element_id, demande.cible) == (strategie.id, pilier1.id, "element")

    # Seul celui qui peut approuver le pilier 1 la voit et la traite.
    assert not any(d["id"] == demande.id for d in _client(approbateur_p2).get("/api/v1/approbations/").data["demandes"])
    assert _client(approbateur_p2).post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": True}, format="json").status_code == 403
    liste = _client(approbateur_p1).get("/api/v1/approbations/").data
    assert [d["approuvable"] for d in liste["demandes"] if d["id"] == demande.id] == [True]
    assert _client(approbateur_p1).post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": True}, format="json").status_code == 200
    pilier1.refresh_from_db()
    assert pilier1.nom == "Pilier 1 révisé"

    # Ajout sous le pilier 2 et appréciation du pilier 2 : demandes, appliquées par l'approbateur du pilier 2.
    sous_niveau = TypeNiveau.objects.create(cadre_strategique=strategie, nom_niveau="Axe", ordre=2, niveau_parent=niveau)
    ajout = client.post("/api/v1/elements-strategiques/", {"type_niveau": sous_niveau.id, "element_parent": pilier2.id,
                                                           "nom": "Axe 2.1"}, format="json")
    appreciation = client.post("/api/v1/appreciations-strategiques/", {"element": pilier2.id, "periode_debut": "2026-01-01",
                                                                       "periode_fin": "2026-12-31", "etat": "BON"}, format="json")
    assert ajout.status_code == 202 and appreciation.status_code == 202, appreciation.data
    for reponse in (ajout, appreciation):
        assert _client(approbateur_p2).post(f"/api/v1/approbations/demandes/{reponse.data['demande_approbation']}/",
                                            {"approuver": True}, format="json").status_code == 200
    assert ElementStrategique.objects.filter(nom="Axe 2.1", element_parent=pilier2).exists()
    assert AppreciationStrategique.objects.get(element=pilier2).saisi_par == redacteur

    # Un approbateur modifie directement ; le réglage du circuit reste à l'Administrateur.
    DroitObjet.objects.create(utilisateur=approbateur_p1, document=strategie, acces="ECRITURE", approuver=True)
    approbateur_p1 = User.objects.get(pk=approbateur_p1.pk)
    assert _client(approbateur_p1).patch(f"/api/v1/cadres-strategiques/{strategie.id}/", {"nom": "Stratégie A2"},
                                         format="json").status_code == 200
    assert _client(approbateur_p1).patch(f"/api/v1/cadres-strategiques/{strategie.id}/", {"approbation_modifications": False},
                                         format="json").status_code == 400


@pytest.mark.django_db
def test_tout_ce_qu_il_saisit_doit_etre_approuve():
    from apps.accounts.models import Role

    from .models import DemandeModification

    projet = _projet("DR-SA")  # aucune approbation exigée par le projet
    Role.objects.update_or_create(code="APPROB_T", defaults={"libelle": "Approbateur", "peut_approuver": True, "visibilite_globale": True})
    agent = User.objects.create_user(username="agent_sa", password="x", role="APPROB_T", niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE,
                                     saisies_a_approuver=True)
    designe = User.objects.create_user(username="designe", password="x", role=ROLE_ANIMATEUR_TERRAIN, niveau_acces=NIVEAU_ACCES_LECTURE_SEULE)
    autre = User.objects.create_user(username="autre_appr", password="x", role="APPROB_T", niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    admin = User.objects.create_user(username="adm_sa", password="x", role=ROLE_ADMIN)
    agent.approbateurs.set([designe])
    activite = Activite.objects.create(projet=projet, libelle="A1")

    def saisir(quantite):
        mois = f"{quantite:02d}"  # une période par saisie (pas de chevauchement)
        reponse = _client(agent).post("/api/v1/points-suivi/", {"activite": activite.id, "periode_debut": f"2026-{mois}-01",
                                                                "periode_fin": f"2026-{mois}-28", "quantite_realisee": quantite},
                                      format="json")
        assert reponse.status_code == 201
        return PointSuivi.tous.get(pk=reponse.data["id"])

    # Sa saisie reste en attente, même s'il a lui-même le droit d'approuver (rôle) ; il ne peut pas se l'approuver.
    point = saisir(2)
    assert point.etat_approbation == EtatApprobation.EN_ATTENTE
    url = f"/api/v1/approbations/saisies/point/{point.id}/"
    assert _client(agent).post(url, {"approuver": True}, format="json").status_code == 403
    # Approbateur désigné : seul lui (avec l'Administrateur), même sans droit sur le projet.
    assert _client(autre).post(url, {"approuver": True}, format="json").status_code == 403
    liste = _client(designe).get("/api/v1/approbations/").data
    assert liste["peut_approuver"] and [s["approuvable"] for s in liste["saisies"] if s["id"] == point.id] == [True]
    assert _client(designe).post(url, {"approuver": True}, format="json").status_code == 200
    point.refresh_from_db()
    assert point.etat_approbation == EtatApprobation.APPROUVEE
    assert _client(admin).post(f"/api/v1/approbations/saisies/point/{saisir(3).id}/", {"approuver": True}, format="json").status_code == 200

    # Changement de planification : une demande, même si le projet n'en exige pas.
    reponse = _client(agent).patch(f"/api/v1/activites/{activite.id}/", {"libelle": "A1 révisée"}, format="json")
    assert reponse.status_code == 202
    demande = DemandeModification.objects.get(pk=reponse.data["demande_approbation"])
    assert _client(autre).post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": True}, format="json").status_code == 403
    assert _client(designe).post(f"/api/v1/approbations/demandes/{demande.id}/", {"approuver": True}, format="json").status_code == 200
    activite.refresh_from_db()
    assert activite.libelle == "A1 révisée"

    # Stratégie : ses modifications deviennent aussi des demandes.
    strategie = CadreStrategique.objects.create(nom="S-SA")
    niveau = TypeNiveau.objects.create(cadre_strategique=strategie, nom_niveau="Pilier", ordre=1)
    pilier = ElementStrategique.objects.create(type_niveau=niveau, nom="Pilier")
    DroitObjet.objects.create(utilisateur=agent, document=strategie, acces="ECRITURE")
    agent = User.objects.get(pk=agent.pk)
    assert _client(agent).patch(f"/api/v1/elements-strategiques/{pilier.id}/", {"nom": "P"}, format="json").status_code == 202

    # Sans approbateur désigné : toute personne ayant le droit d'approuver (ici par son rôle).
    agent.approbateurs.clear()
    point = saisir(4)
    assert _client(autre).post(f"/api/v1/approbations/saisies/point/{point.id}/", {"approuver": True}, format="json").status_code == 200
    # Une personne ne se désigne pas elle-même.
    refus = _client(admin).patch(f"/api/v1/utilisateurs/{agent.id}/", {"approbateurs": [agent.id]}, format="json")
    assert refus.status_code == 400
