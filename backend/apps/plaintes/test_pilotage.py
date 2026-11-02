"""Lot 6 : indicateurs, masquage des petits effectifs confidentiels, vues personnalisables, exports,
actions correctives, encart projet (scénario 11)."""
import datetime
import io

import pytest
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE
from apps.accounts.models import User

from . import pilotage
from .models import ActionCorrective, ActionDossier, Categorie, Dossier, EtapeCircuit, Mecanisme, TypeRetour
from .reception import recevoir

URL = "/api/v1/plaintes/"
AUJ = timezone.localdate()


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_pil", password="x", role=ROLE_ADMIN)


@pytest.fixture
def point_focal(db):
    return User.objects.create_user(username="pf_pil", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def suivi_eval(db):
    """Responsable S&E : voit les indicateurs agrégés, aucun contenu de plainte confidentielle."""
    return User.objects.create_user(username="se_pil", password="x", role=ROLE_CHARGE_SE, niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def actif(admin, point_focal):
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200


def _dossier(categorie="Retard", jours=10, **champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "Récit.", "consentement": True,
               "categorie": Categorie.objects.get(nom=categorie).id, "nom": "Awa", "telephone": "70000000",
               "mode_reponse": "TELEPHONE", "date_reception": (AUJ - datetime.timedelta(days=jours)).isoformat()}
    donnees.update(champs)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("django.db.transaction.on_commit", lambda f, *a, **k: f())
        return recevoir(donnees, "TELEPHONE")[0]


def _clore(d, jours_apres, retour=True):
    Dossier.objects.filter(pk=d.pk).update(statut="CLOTURE", date_cloture=d.date_reception + datetime.timedelta(days=jours_apres),
                                           retour_donne=retour, issue="RESOLU")


def _element(resultat, code):
    return next(e for e in resultat["elements"] if e["code"] == code)


@pytest.mark.django_db
def test_indicateurs_de_base(actif, admin):
    Mecanisme.objects.filter(pk=1).update(accuse_reception_auto=False)  # accusés comptés à la main ci-dessous
    a, b, c = _dossier(jours=40), _dossier(jours=30), _dossier(jours=5)
    _clore(a, 10)                 # dans le délai (30 j)
    _clore(b, 25, retour=False)   # dans le délai, plaignant non informé
    Dossier.objects.filter(pk__in=[a.pk, b.pk]).update(echeance=AUJ)
    Dossier.objects.filter(pk=a.pk).update(echeance=a.date_reception + datetime.timedelta(days=5))  # finalement hors délai
    ActionDossier.objects.create(dossier=c, type="COMMUNICATION", sens="SORTANT", objet="ACCUSE_RECEPTION", canal="SMS")
    r = pilotage.calculer_vue("pilotage", admin)
    assert _element(r, "volume")["valeur"] == 3 and _element(r, "clotures")["valeur"] == 2
    dans = _element(r, "dans_delais")
    assert (dans["numerateur"], dans["denominateur"], dans["valeur"], dans["unite"]) == (1, 2, 50.0, "%")
    assert _element(r, "delai_moyen")["valeur"] == 17.5 and _element(r, "delai_median")["valeur"] == 17.5
    boucle = _element(r, "boucle")
    assert (boucle["numerateur"], boucle["denominateur"]) == (1, 2)
    assert all(e["definition"] for e in r["elements"] if e["nature"] == "chiffre")
    accuses = pilotage.Calcul(admin).calculer("accuses")
    assert (accuses["numerateur"], accuses["denominateur"]) == (1, 3)
    assert pilotage.Calcul(admin).calculer("attente_affectation")["valeur"] == 1
    # Satisfaction : affichée seulement à partir de 10 réponses.
    for i in range(9):
        ActionDossier.objects.create(dossier=a, type="COMMUNICATION", sens="ENTRANT", objet="SATISFACTION",
                                     canal="TELEPHONE", details={"satisfait": i % 3 != 0})
    assert pilotage.Calcul(admin).calculer("satisfaction")["valeur"] is None
    ActionDossier.objects.create(dossier=a, type="COMMUNICATION", sens="ENTRANT", objet="SATISFACTION", canal="SMS",
                                 details={"satisfait": True})
    assert pilotage.Calcul(admin).calculer("satisfaction")["valeur"] == 70.0


@pytest.mark.django_db
def test_masquage_et_scenario_11(actif, admin, suivi_eval, point_focal):
    """Le S&E voit des totaux, jamais un dossier confidentiel ; petites cases masquées ; seuil jamais < 5."""
    for _ in range(3):
        _dossier()
    sensibles = [_dossier(categorie="Fraude et corruption") for _ in range(2)]
    r = _client(suivi_eval).get(URL + "tableau-de-bord/?vue=pilotage").data
    assert _element(r, "volume")["valeur"] == 5  # les totaux comptent tout
    categories = _element(r, "par_categorie")
    assert "Fraude et corruption" not in categories["categories"]  # confidentiels seulement en total
    assert categories["confidentiels"] == "moins de 5"
    # Clic vers les dossiers : seulement ceux qu'il peut voir.
    liste = _client(suivi_eval).get(URL + "dossiers/").data
    assert liste["count"] == 3 and not any(d["sensible"] for d in liste["results"])
    assert _client(suivi_eval).get(URL + "tableau-de-bord/?vue=confidentielle").status_code == 403
    conf = _client(point_focal).get(URL + "tableau-de-bord/?vue=confidentielle").data
    assert _element(conf, "conf_recus")["valeur"] == "moins de 5" and all(
        "Récit" not in str(e) for e in conf["elements"])
    assert "seuil_masquage" in _client(admin).patch(URL + "mecanisme/", {"seuil_masquage": 3}, format="json").data
    _client(admin).patch(URL + "mecanisme/", {"seuil_masquage": 10}, format="json")
    for _ in range(4):
        _dossier(categorie="Fraude et corruption")
    assert _element(pilotage.calculer_vue("confidentielle", point_focal), "conf_recus")["valeur"] == "moins de 10"
    assert len(sensibles) == 2


@pytest.mark.django_db
def test_vues_personnalisees(actif, admin, suivi_eval, point_focal):
    c = _client(suivi_eval)
    assert c.get("/api/v1/plaintes-tableau/configuration/?vue=pilotage").data["source"] == "defaut"
    elements = [{"code": "volume"}, {"code": "par_canal", "graphique": "colonnes"}, {"code": "conf_recus"}, {"code": "inconnu"}]
    r = c.put("/api/v1/plaintes-tableau/configuration/", {"vue": "pilotage", "elements": elements}, format="json")
    assert r.data["source"] == "utilisateur" and [e["code"] for e in r.data["elements"]] == ["volume", "par_canal"]
    # Sa copie ne change rien pour les autres.
    assert pilotage.configuration("pilotage", point_focal)["source"] == "defaut"
    assert c.put("/api/v1/plaintes-tableau/configuration/", {"vue": "pilotage", "elements": elements, "portee": "organisation"},
                 format="json").status_code == 403
    _client(admin).put("/api/v1/plaintes-tableau/configuration/",
                       {"vue": "pilotage", "elements": [{"code": "boucle"}], "portee": "organisation"}, format="json")
    assert pilotage.configuration("pilotage", point_focal)["elements"] == [{"code": "boucle", "graphique": "barres"}]
    # « Revenir à la vue de l'organisation ».
    r = c.delete("/api/v1/plaintes-tableau/configuration/?vue=pilotage")
    assert r.data["source"] == "organisation" and r.data["elements"][0]["code"] == "boucle"


@pytest.mark.django_db
def test_exports(actif, admin, suivi_eval):
    _dossier(), _dossier(categorie="Fraude et corruption")
    for format_, signature in (("excel", b"PK"), ("pdf", b"%PDF")):
        r = _client(admin).get(f"{URL}tableau-de-bord/export/{format_}/?vue=pilotage")
        assert r.status_code == 200 and r.content[:len(signature)] == signature
    r = _client(suivi_eval).post(URL + "dossiers/exporter-liste/", {"coordonnees": True}, format="json")
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.max_row == 2 and "Téléphone" not in [c.value for c in ws[1]]  # pas de confidentiel, pas de coordonnées
    assert ActionDossier.objects.filter(type="EXPORT", auteur=suivi_eval).count() == 1
    r = _client(admin).post(URL + "dossiers/exporter-liste/", {"coordonnees": True}, format="json")
    assert "Téléphone" in [c.value for c in load_workbook(io.BytesIO(r.content)).active[1]]


@pytest.mark.django_db
def test_actions_correctives_et_encart_projet(actif, admin, suivi_eval):
    d = _dossier()
    s = _dossier(categorie="Fraude et corruption")
    c = _client(suivi_eval)
    assert c.post(URL + "actions-correctives/", {"titre": "Réparer la pompe", "dossiers": [s.id]}, format="json").status_code == 400
    r = c.post(URL + "actions-correctives/", {"titre": "Réparer la pompe", "dossiers": [d.id], "responsable": suivi_eval.id,
                                              "echeance": (AUJ + datetime.timedelta(days=10)).isoformat()}, format="json")
    assert r.status_code == 201 and r.data["dossiers_lies"] == [{"id": d.id, "numero": d.numero}]
    assert d.actions.filter(type="ACTION_CORRECTIVE").exists()
    action = ActionCorrective.objects.get()
    action.dossiers.add(s)  # lien posé par un point focal habilité
    r = c.patch(f"{URL}actions-correctives/{action.id}/", {"dossiers": [d.id], "statut": "REALISEE"}, format="json")
    assert r.data["dossiers_lies"] == [{"id": d.id, "numero": d.numero}]
    assert set(action.dossiers.values_list("pk", flat=True)) == {d.pk, s.pk}  # lien invisible conservé
    assert ActionCorrective.objects.get().date_realisation == AUJ
    from apps.projects.models import Projet
    projet = Projet.objects.create(nom="P", code="P-1", date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2027, 1, 1))
    Dossier.objects.filter(pk=d.pk).update(projet=projet)
    encart = c.get(f"{URL}projets/{projet.id}/retours/").data
    assert _element(encart, "volume")["valeur"] == 1
