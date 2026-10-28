"""Lot 5 : registre des risques et suivi par réévaluations."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from apps.intervenants.models import Intervenant

from .models import Activite, Projet, Risque


@pytest.mark.django_db
def test_registre_et_suivi_des_risques():
    client = APIClient()
    admin = User.objects.create_user(username="adm_risque", password="x", role=ROLE_ADMIN)
    client.force_authenticate(admin)
    projet = Projet.objects.create(nom="P", code="RSQ-1", date_debut="2026-01-01", date_fin="2026-12-31")
    autre = Projet.objects.create(nom="Q", code="RSQ-2", date_debut="2026-01-01", date_fin="2026-12-31")
    element = Activite.objects.create(projet=projet, libelle="Forages")

    r = client.post("/api/v1/risques/", {
        "projet": projet.id, "libelle": "Insécurité dans la zone", "nature": "EXTERNE", "categorie": "Sécuritaire",
        "element": element.id, "probabilite": 4, "impact": 5, "mesures_attenuation": "Coordination avec les autorités",
        "responsable": Intervenant.objects.create(nom="Sawadogo", prenom="Ali").id,
    }, format="json")
    assert r.status_code == 201, r.data
    assert r.data["code"] == "R1" and r.data["criticite"] == 20 and r.data["niveau"] == "CRITIQUE"
    assert r.data["responsable_nom"] == "Sawadogo Ali"
    risque_id = r.data["id"]
    # Cotation hors 1-5 et élément d'un autre projet refusés.
    assert client.post("/api/v1/risques/", {"projet": projet.id, "libelle": "x", "probabilite": 6}, format="json").status_code == 400
    autre_element = Activite.objects.create(projet=autre, libelle="Autre")
    assert client.post("/api/v1/risques/", {"projet": projet.id, "libelle": "x", "element": autre_element.id}, format="json").status_code == 400

    # Réévaluation : devient la cotation courante ; la supprimer rétablit la précédente.
    e1 = client.post("/api/v1/evaluations-risques/", {
        "risque": risque_id, "date": "2026-03-01", "probabilite": 2, "impact": 5, "statut": "MAITRISE", "actions_menees": "Escorte",
    }, format="json")
    assert e1.status_code == 201 and e1.data["niveau"] == "ELEVE" and e1.data["saisi_par_nom"] == "adm_risque"
    client.post("/api/v1/evaluations-risques/", {"risque": risque_id, "date": "2026-01-15", "probabilite": 3, "impact": 5, "statut": "ACTIF"}, format="json")
    risque = Risque.objects.get(id=risque_id)
    assert (risque.probabilite, risque.statut) == (2, "MAITRISE")  # la plus récente par date
    client.delete(f"/api/v1/evaluations-risques/{e1.data['id']}/")
    risque.refresh_from_db()
    assert (risque.probabilite, risque.statut) == (3, "ACTIF")
    assert len(client.get(f"/api/v1/risques/{risque_id}/").data["evaluations"]) == 1

    # Numérotation sans doublon après une suppression au milieu.
    r2 = client.post("/api/v1/risques/", {"projet": projet.id, "libelle": "Retard de décaissement", "nature": "INTERNE"}, format="json").data
    client.post("/api/v1/risques/", {"projet": projet.id, "libelle": "Hausse des prix"}, format="json")
    client.delete(f"/api/v1/risques/{r2['id']}/")
    assert client.post("/api/v1/risques/", {"projet": projet.id, "libelle": "Pluies tardives"}, format="json").data["code"] == "R4"

    # Registre exporté.
    for fichier, debut in (("pdf", b"%PDF"), ("docx", b"PK")):
        reponse = client.get(f"/api/v1/rapports/risques/{projet.id}/", {"fichier": fichier})
        assert reponse.status_code == 200 and reponse.content.startswith(debut)

    # Projet clôturé : registre en lecture seule.
    Projet.objects.filter(id=projet.id).update(statut=Projet.Statut.CLOTURE)
    assert client.post("/api/v1/evaluations-risques/", {"risque": risque_id, "probabilite": 1, "impact": 1, "statut": "CLOS"}, format="json").status_code == 403
