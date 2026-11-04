"""Lot 3 du mécanisme de plaintes : traitement des dossiers (scénario 3, transitions interdites, recours…)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import NIVEAU_ACCES_LECTURE_ECRITURE, ROLE_ADMIN, ROLE_CHARGE_SE, ROLE_CHEF_PROJET
from apps.accounts.models import User

from .habilitations import habiliter_d_office
from .models import ActionDossier, Categorie, Dossier, EtapeCircuit, Mecanisme, TypeRetour
from .reception import recevoir

URL = "/api/v1/plaintes/"


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="adm_trait", password="x", role=ROLE_ADMIN)


@pytest.fixture
def gestionnaire(db):
    return User.objects.create_user(username="gest_trait", password="x", role=ROLE_CHEF_PROJET,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def second(db):
    return User.objects.create_user(username="gest2_trait", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def point_focal(db):
    return User.objects.create_user(username="pf_trait", password="x", role=ROLE_CHARGE_SE,
                                    niveau_acces=NIVEAU_ACCES_LECTURE_ECRITURE)


@pytest.fixture
def actif(admin, point_focal):
    assert _client(admin).post(URL + "modeles/", {"modele": "standard"}, format="json").status_code == 200
    Mecanisme.objects.filter(pk=1).update(conservation_ordinaire_mois=60, conservation_sensible_mois=120)
    EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
    habiliter_d_office(point_focal)
    assert _client(admin).post(URL + "mecanisme/activer/").status_code == 200


def _dossier(**champs):
    donnees = {"type_retour": TypeRetour.objects.get(nom="Plainte").id, "description": "La pompe est en panne.",
               "consentement": True, "telephone": "70000000", "mode_reponse": "TELEPHONE",
               "categorie": Categorie.objects.get(nom="Retard").id}
    donnees.update(champs)
    return recevoir(donnees, "FORMULAIRE", public=True)[0]


def _agir(user, dossier, action, donnees=None):
    return _client(user).post(f"{URL}dossiers/{dossier.id}/{action}/", donnees or {}, format="json")


@pytest.mark.django_db
def test_plainte_ordinaire_jusqu_a_la_cloture(actif, admin, gestionnaire):
    """Scénario 3 : numéro, classification, affectation, traitement, décision, réponse, clôture."""
    d = _dossier()
    assert d.actions.get().type == "RECEPTION"
    r = _agir(admin, d, "classer", {"priorite": d.__class__._meta.get_field("priorite").related_model.objects.get(nom="Élevée").id})
    assert r.status_code == 200 and r.data["priorite_nom"] == "Élevée" and r.data["statut"] == "RECU"
    r = _agir(admin, d, "affecter", {"responsable": gestionnaire.id})
    assert r.data["responsable_nom"] == "gest_trait" and r.data["statut"] == "EN_COURS"
    traitement_ = EtapeCircuit.objects.get(circuit=d.circuit, nom="Traitement")
    assert _agir(gestionnaire, d, "etape", {"etape": traitement_.id, "commentaire": "Visite du site"}).data["etape_nom"] == "Traitement"
    assert _agir(gestionnaire, d, "noter", {"texte": "Pièce commandée", "corrective": True}).status_code == 200
    # Communiquer la décision avant de l'avoir prise : refusé.
    communication = {"sens": "SORTANT", "canal": "TELEPHONE", "objet": "DECISION", "texte": "Appel au plaignant."}
    assert "objet" in _agir(gestionnaire, d, "communiquer", communication).data
    assert _agir(gestionnaire, d, "decider", {"decision": "La pompe sera réparée sous 7 jours."}).status_code == 200
    r = _agir(gestionnaire, d, "communiquer", communication)
    assert r.data["statut"] == "REPONDU" and r.data["date_reponse"]
    # Clôture : motif, retour au plaignant et issue exigés.
    erreurs = _agir(gestionnaire, d, "cloturer", {}).data
    assert {"issue", "motif", "retour_donne"} <= set(erreurs)
    assert "raison_sans_retour" in _agir(gestionnaire, d, "cloturer", {"issue": "RESOLU", "motif": "Réparée", "retour_donne": False}).data
    r = _agir(gestionnaire, d, "cloturer", {"issue": "RESOLU", "motif": "Pompe réparée", "retour_donne": True})
    assert r.data["statut"] == "CLOTURE" and r.data["etape_nom"] == "Clôture" and r.data["date_cloture"]
    types = list(ActionDossier.objects.filter(dossier=d).order_by("id").values_list("type", flat=True))
    assert types == ["RECEPTION", "CLASSIFICATION", "AFFECTATION", "ETAPE", "ACTION_CORRECTIVE", "DECISION", "COMMUNICATION", "CLOTURE"]
    # Dossier clôturé : plus de traitement, mais une note reste possible.
    assert _agir(gestionnaire, d, "etape", {"etape": traitement_.id}).status_code == 400
    assert _agir(gestionnaire, d, "noter", {"texte": "Plaignant satisfait"}).status_code == 200
    # Le suivi public reflète l'état.
    assert Dossier.objects.get(pk=d.pk).statut == "CLOTURE"


@pytest.mark.django_db
def test_transitions_interdites(actif, admin, gestionnaire, second):
    d = _dossier()
    cloture = EtapeCircuit.objects.get(circuit=d.circuit, est_cloture=True)
    assert "etape" in _agir(admin, d, "etape", {"etape": cloture.id}).data  # passer par « Clôturer »
    assert _agir(admin, d, "recours", {"motif": "x"}).status_code == 400  # pas encore de réponse
    assert _agir(admin, d, "rouvrir", {"motif": "x"}).status_code == 400  # pas clôturé
    _agir(admin, d, "affecter", {"responsable": gestionnaire.id})
    assert _agir(second, d, "recuser", {"motif": "x"}).status_code == 400  # pas son dossier
    assert _agir(gestionnaire, d, "recuser", {"motif": "Lien de parenté avec le plaignant"}).data["responsable"] is None
    # Référée : acteur externe et consentement exigés.
    donnees = {"issue": "REFERE", "motif": "Relève de la mairie", "retour_donne": True, "decision": "Orienté"}
    erreurs = _agir(admin, d, "cloturer", donnees).data
    assert {"oriente_vers", "consentement_reference"} <= set(erreurs)
    r = _agir(admin, d, "cloturer", {**donnees, "oriente_vers": "Mairie de Kaya", "consentement_reference": True})
    assert r.data["issue"] == "REFERE" and r.data["decision"] == "Orienté"
    # Réouverture réservée aux rôles autorisés et motivée.
    assert _agir(gestionnaire, d, "rouvrir", {"motif": "x"}).status_code == 400
    assert "motif" in _agir(admin, d, "rouvrir", {}).data
    r = _agir(admin, d, "rouvrir", {"motif": "Nouvel élément"})
    assert r.data["statut"] == "EN_COURS" and r.data["issue"] == "" and r.data["etape_nom"] != "Clôture"


@pytest.mark.django_db
def test_recours_reexamine_par_une_autre_personne(actif, admin, gestionnaire, second):
    d = _dossier()
    _agir(admin, d, "affecter", {"responsable": gestionnaire.id})
    _agir(gestionnaire, d, "decider", {"decision": "Refus"})
    _agir(gestionnaire, d, "cloturer", {"issue": "NON_FONDE", "motif": "Critères non remplis", "retour_donne": True})
    r = _agir(admin, d, "recours", {"motif": "Le plaignant conteste les critères."})
    assert r.data["en_recours"] and r.data["responsable"] is None and r.data["statut"] == "EN_COURS"
    assert r.data["gestionnaire_initial_nom"] == "gest_trait"
    assert "responsable" in _agir(admin, d, "affecter", {"responsable": gestionnaire.id}).data
    possibles = [p["id"] for p in _client(admin).get(f"{URL}dossiers/{d.id}/responsables-possibles/").data]
    assert gestionnaire.id not in possibles and second.id in possibles
    assert _agir(admin, d, "affecter", {"responsable": second.id}).status_code == 200


@pytest.mark.django_db
def test_classement_sensible_et_confidentialite(actif, admin, gestionnaire, point_focal):
    d = _dossier()
    _agir(admin, d, "affecter", {"responsable": gestionnaire.id})
    eas = Categorie.objects.get(nom="Exploitation et abus sexuels")
    # Le gestionnaire reclasse : le dossier part au circuit confidentiel et il en perd l'accès.
    r = _agir(gestionnaire, d, "classer", {"categorie": eas.id})
    assert r.status_code == 200 and r.data == {"numero": d.numero, "visible": False}
    d.refresh_from_db()
    assert d.sensible and d.circuit.sensible and d.responsable is None
    assert _client(gestionnaire).get(f"{URL}dossiers/{d.id}/").status_code == 404
    # Seuls les points focaux du circuit (et l'Administrateur) peuvent le recevoir.
    assert "responsable" in _agir(admin, d, "affecter", {"responsable": gestionnaire.id}).data
    assert _agir(admin, d, "affecter", {"responsable": point_focal.id}).status_code == 200
    # Reclasser vers une catégorie ordinaire ne lève jamais la sensibilité automatiquement.
    _agir(point_focal, d, "classer", {"categorie": Categorie.objects.get(nom="Retard").id})
    assert Dossier.objects.get(pk=d.pk).sensible


@pytest.mark.django_db
def test_vues_liens_et_vues_enregistrees(actif, admin, gestionnaire, point_focal):
    a, b = _dossier(), _dossier()
    sensible = _dossier(categorie=Categorie.objects.get(nom="Fraude et corruption").id)
    _agir(admin, a, "affecter", {"responsable": gestionnaire.id})
    c = _client(gestionnaire)
    assert [d["numero"] for d in c.get(URL + "dossiers/?vue=mes_dossiers").data["results"]] == [a.numero]
    assert c.get(URL + "dossiers/?vue=sans_responsable").data["count"] == 1  # b ; le dossier confidentiel n'est pas compté
    # Dossiers possiblement liés : même projet et même catégorie, dates proches.
    from apps.projects.models import Projet
    import datetime
    projet = Projet.objects.create(nom="Projet test", code="PT-1", date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2027, 12, 31))
    Dossier.objects.filter(pk__in=[a.pk, b.pk]).update(projet=projet)
    assert [d["numero"] for d in c.get(f"{URL}dossiers/{a.id}/possiblement-lies/").data] == [b.numero]
    assert c.post(f"{URL}dossiers/{a.id}/lier/", {"numero": sensible.numero}, format="json").status_code == 400  # invisible
    r = c.post(f"{URL}dossiers/{a.id}/lier/", {"numero": b.numero}, format="json")
    assert [x["numero"] for x in r.data["dossiers_lies"]] == [b.numero]
    assert c.get(f"{URL}dossiers/{a.id}/possiblement-lies/").data == []
    # Vues enregistrées : propres à chacun.
    assert c.post("/api/v1/plaintes-vues/", {"nom": "Mes urgences", "filtres": {"vue": "urgents"}}, format="json").status_code == 201
    assert c.post("/api/v1/plaintes-vues/", {"nom": "mes urgences", "filtres": {}}, format="json").status_code == 400
    assert _client(point_focal).get("/api/v1/plaintes-vues/").data == []


@pytest.mark.django_db
def test_commande_de_demonstration(admin):
    """La démonstration passe par les vraies opérations : journaux et dates cohérents."""
    from django.core.management import call_command

    User.objects.create_user(username="admin", password="x", role=ROLE_ADMIN)
    call_command("seed_demo_plaintes")
    clos = Dossier.objects.filter(statut="CLOTURE")
    assert Dossier.objects.count() == 43 and clos.exists() and Dossier.objects.filter(en_recours=True).count() == 1
    # Lot 5 : un dossier visant le point focal suit le circuit alternatif ; assistance et suspension légale.
    vise = Dossier.objects.get(mis_en_cause_utilisateurs__username="pf_psea")
    assert vise.circuit == Mecanisme.courant().circuit_alternatif
    assert Dossier.objects.filter(referencements__isnull=False).exists() and Dossier.objects.filter(suspension_legale=True).exists()
    for d in clos:
        assert d.actions.filter(type="CLOTURE").exists() and d.decision
        assert d.date_reception <= d.date_decision <= d.date_cloture
    assert not Dossier.objects.filter(actions__isnull=True).exists()


def test_correction_du_plaignant_tracee(actif, admin, gestionnaire):
    """Informations du plaignant corrigées ; ancienne et nouvelle valeur au journal, chiffrées, pas dans les détails."""
    d = _dossier(nom="Lexi")
    # Mode de réponse incohérent avec les coordonnées : refusé, rien n'est changé.
    assert "courriel" in _agir(gestionnaire, d, "plaignant", {"mode_reponse": "COURRIEL"}).data
    r = _agir(gestionnaire, d, "plaignant", {"telephone": "77364628", "courriel": "lexi@exemple.org", "mode_reponse": "COURRIEL"})
    assert r.status_code == 200 and r.data["telephone"] == "77364628" and r.data["mode_reponse"] == "COURRIEL"
    action = d.actions.get(type="PLAIGNANT")
    assert action.auteur == gestionnaire and action.details == {"champs": ["telephone", "courriel", "mode_reponse"]}
    assert "Téléphone : 70000000 → 77364628" in action.texte and "Courriel : — → lexi@exemple.org" in action.texte
    # Rien de changé : pas de nouvelle trace.
    _agir(gestionnaire, d, "plaignant", {"telephone": "77364628"})
    assert d.actions.filter(type="PLAIGNANT").count() == 1
    # Dossier anonyme : l'identité ne peut pas être ajoutée, seul le consentement se corrige.
    anonyme = _dossier(anonyme=True, telephone="", mode_reponse="AUCUN")
    r = _agir(admin, anonyme, "plaignant", {"nom": "Quelqu'un", "consentement": False})
    assert r.status_code == 200 and r.data["nom"] == "" and r.data["consentement"] is False


@pytest.mark.django_db
def test_compteurs_des_vues(actif, admin):
    """Colonne des vues : un nombre par vue prête, calculé sur les seuls dossiers visibles."""
    reponse = APIClient()
    reponse.force_authenticate(admin)
    compteurs = reponse.get(URL + "dossiers/compteurs/").data
    assert set(compteurs) >= {"tous", "mes_dossiers", "urgents", "en_retard", "confidentiels", "a_anonymiser"}
    assert compteurs["tous"] == Dossier.objects.count()
