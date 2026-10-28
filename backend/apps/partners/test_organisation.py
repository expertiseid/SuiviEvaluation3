"""Lot 3 : structure de l'organisation, parties prenantes, rôles des partenaires, liens multiples entre niveaux."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User
from apps.projects.models import Activite, Projet
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau

from .models import Partenaire, StructureOrganisation


@pytest.fixture
def clients(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_org", password="x", role=ROLE_ADMIN))
    charge = APIClient()
    charge.force_authenticate(
        User.objects.create_user(username="se_org", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)
    )
    return admin, charge


@pytest.fixture
def projet(db):
    return Projet.objects.create(nom="P", code="ORG-1", date_debut="2026-01-01", date_fin="2026-12-31")


@pytest.mark.django_db
def test_structure_de_l_organisation(clients, projet):
    admin, charge = clients
    direction = admin.post("/api/v1/structures-organisation/", {"nom": "Direction des programmes", "type": "Direction"}).data
    service = admin.post(
        "/api/v1/structures-organisation/", {"nom": "Service S&E", "sigle": "SSE", "type": "Service", "parent": direction["id"]}
    ).data
    # Paramétrée par l'administrateur seulement ; pas de boucle.
    assert charge.post("/api/v1/structures-organisation/", {"nom": "X"}).status_code == 403
    r = admin.patch(f"/api/v1/structures-organisation/{direction['id']}/", {"parent": service["id"]}, format="json")
    assert r.status_code == 400

    # Projet et partie de projet affectés à un ou plusieurs services.
    activite = Activite.objects.create(projet=projet, libelle="Forages")
    assert charge.patch(f"/api/v1/projets/{projet.id}/", {"structures": [direction["id"], service["id"]]}, format="json").status_code == 200
    r = charge.patch(f"/api/v1/activites/{activite.id}/", {"structures": [service["id"]]}, format="json")
    assert r.status_code == 200 and r.data["structures_noms"] == ["SSE — Service S&E"]
    assert sorted(charge.get(f"/api/v1/projets/{projet.id}/").data["structures_noms"]) == ["Direction des programmes", "SSE — Service S&E"]


@pytest.mark.django_db
def test_parties_prenantes(clients, projet):
    admin, charge = clients
    categorie = admin.post("/api/v1/categories-parties-prenantes/", {"nom": "Collectivité"}).data
    # Créable à la volée par un utilisateur qui peut écrire, modifiable par l'administrateur seulement.
    pp = charge.post("/api/v1/parties-prenantes/", {"nom": "Mairie de Goulmou", "categorie": categorie["id"]}).data
    assert pp["categorie_nom"] == "Collectivité"
    assert charge.patch(f"/api/v1/parties-prenantes/{pp['id']}/", {"nom": "Y"}, format="json").status_code == 403
    charge.patch(f"/api/v1/projets/{projet.id}/", {"parties_prenantes": [pp["id"]]}, format="json")
    assert charge.get(f"/api/v1/projets/{projet.id}/").data["parties_prenantes_noms"] == ["Mairie de Goulmou"]


@pytest.mark.django_db
def test_role_des_partenaires_dans_le_projet(clients, projet):
    _, charge = clients
    ong = Partenaire.objects.create(nom="ONG Eau", type="MISE_EN_OEUVRE")
    objectif = Activite.objects.create(projet=projet, libelle="Objectif 1")
    autre = Activite.objects.create(projet=Projet.objects.create(nom="Q", code="ORG-2", date_debut="2026-01-01", date_fin="2026-12-31"), libelle="Ailleurs")

    donnees = {"projet": projet.id, "partenaire": ong.id, "nature": "CONSORTIUM", "role": "Construit les forages", "elements": [objectif.id]}
    r = charge.post("/api/v1/partenaires-projet/", donnees, format="json")
    assert r.status_code == 201 and r.data["elements_libelles"] == ["Objectif 1"]
    projet.refresh_from_db()
    assert list(projet.partenaires_consortium.all()) == [ong]  # ajouté au consortium du projet
    assert charge.get(f"/api/v1/activites/{objectif.id}/").data["partenaires_charges_noms"] == ["ONG Eau"]

    # Éléments d'un autre projet refusés ; un partenaire une seule fois par projet.
    r = charge.patch(f"/api/v1/partenaires-projet/{r.data['id']}/", {"elements": [autre.id]}, format="json")
    assert r.status_code == 400
    assert charge.post("/api/v1/partenaires-projet/", donnees, format="json").status_code == 400


@pytest.mark.django_db
def test_liens_multiples_entre_niveaux(clients, projet):
    admin, charge = clients
    cadre = CadreStrategique.objects.create(nom="Stratégie pays")
    n1 = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Axe", ordre=1)
    n2 = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Programme", ordre=2, niveau_parent=n1)
    axe1 = ElementStrategique.objects.create(type_niveau=n1, nom="Eau")
    axe2 = ElementStrategique.objects.create(type_niveau=n1, nom="Santé")
    prog = ElementStrategique.objects.create(type_niveau=n2, nom="Programme WASH", element_parent=axe1)
    prog2 = ElementStrategique.objects.create(type_niveau=n2, nom="Programme 2", element_parent=axe2)

    r = admin.patch(f"/api/v1/elements-strategiques/{prog.id}/", {"parents_secondaires": [axe2.id]}, format="json")
    assert r.status_code == 200 and r.data["parents_secondaires_noms"] == ["Santé"]
    # Seulement vers un niveau supérieur, jamais le parent principal.
    assert admin.patch(f"/api/v1/elements-strategiques/{prog.id}/", {"parents_secondaires": [prog2.id]}, format="json").status_code == 400
    assert admin.patch(f"/api/v1/elements-strategiques/{prog.id}/", {"parents_secondaires": [axe1.id]}, format="json").status_code == 400

    # Projet : un élément principal (compté) et d'autres liens (informatifs).
    r = charge.patch(
        f"/api/v1/projets/{projet.id}/",
        {"element_strategique": prog.id, "elements_strategiques_secondaires": [prog2.id]},
        format="json",
    )
    assert r.status_code == 200
    assert charge.get(f"/api/v1/projets/{projet.id}/").data["elements_strategiques_secondaires_noms"] == ["Programme 2"]
    r = charge.patch(f"/api/v1/projets/{projet.id}/", {"elements_strategiques_secondaires": [prog.id]}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_structure_des_utilisateurs(clients):
    admin, _ = clients
    service = StructureOrganisation.objects.create(nom="Service S&E")
    ong = Partenaire.objects.create(nom="ONG Eau", type="MISE_EN_OEUVRE")
    u = User.objects.create_user(username="zz_struct", password="x", role=ROLE_CHARGE_SE)

    r = admin.patch(f"/api/v1/utilisateurs/{u.id}/", {"type_structure": "CONSORTIUM", "partenaire": ong.id}, format="json")
    assert r.status_code == 200
    assert admin.get(f"/api/v1/utilisateurs/{u.id}/").data["structure_libelle"] == "Partenaire de consortium — ONG Eau"
    # Changer de type ne garde que le lien correspondant.
    admin.patch(f"/api/v1/utilisateurs/{u.id}/", {"type_structure": "INTERNE", "structure_interne": service.id}, format="json")
    u.refresh_from_db()
    assert u.partenaire is None and u.structure_interne == service


@pytest.mark.django_db
def test_affecter_projets_et_utilisateurs_depuis_la_structure(clients, projet):
    admin, charge = clients
    service = StructureOrganisation.objects.create(nom="Service S&E")
    autre = Projet.objects.create(nom="Q", code="ORG-3", date_debut="2026-01-01", date_fin="2026-12-31")
    u = User.objects.create_user(username="zz_aff", password="x", role=ROLE_CHARGE_SE, partenaire=Partenaire.objects.create(nom="ONG", type="MISE_EN_OEUVRE"), type_structure="CONSORTIUM")
    url = f"/api/v1/structures-organisation/{service.id}/affectations/"

    r = admin.post(url, {"projets": [projet.id, autre.id], "utilisateurs": [u.id]}, format="json")
    assert sorted(r.data["projets"]) == sorted([projet.id, autre.id]) and r.data["utilisateurs"] == [u.id]
    u.refresh_from_db()
    assert u.type_structure == "INTERNE" and u.structure_interne == service and u.partenaire is None
    assert admin.get("/api/v1/structures-organisation/").data[0]["nb_projets"] == 2

    # La liste remplace l'existante ; réservé à l'administrateur.
    r = admin.post(url, {"projets": [autre.id], "utilisateurs": []}, format="json")
    assert r.data == {"projets": [autre.id], "utilisateurs": []}
    assert not projet.structures.exists()
    assert charge.post(url, {"projets": []}, format="json").status_code == 403
