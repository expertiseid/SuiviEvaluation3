import pytest

from .models import Beneficiaire
from .services.duplicate_detection import rechercher_doublons


@pytest.mark.django_db
def test_doublon_detecte_par_piece_identite_exacte():
    b1 = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F", numero_piece_identite="CNIB123")
    b2 = Beneficiaire.objects.create(nom="Traore", prenom="Awa", sexe="F", numero_piece_identite="CNIB123")

    resultats = rechercher_doublons(b2)

    assert any(r["candidat"].pk == b1.pk and r["methode"] == "PIECE_IDENTITE" for r in resultats)


@pytest.mark.django_db
def test_beneficiaires_distincts_ne_sont_pas_signales():
    Beneficiaire.objects.create(nom="Sawadogo", prenom="Issa", sexe="M", numero_piece_identite="CNIB999")
    autre = Beneficiaire.objects.create(nom="Ouedraogo", prenom="Fatou", sexe="F", numero_piece_identite="CNIB111")

    resultats = rechercher_doublons(autre)

    assert resultats == []


@pytest.mark.django_db
def test_seuls_les_vrais_doublons_sont_signales():
    import datetime

    base = dict(nom="OUÉDRAOGO", prenom="Awa", sexe="F", telephone="+226 70 11 22 33", date_naissance=datetime.date(1990, 5, 1))
    awa = Beneficiaire.objects.create(**base)
    # Même nom courant, mais rien d'autre en commun : pas un doublon.
    Beneficiaire.objects.create(nom="Ouedraogo", prenom="Awa", sexe="F", telephone="76 00 00 00")
    # Homonyme de sexe différent, ou né une autre année : jamais signalé.
    Beneficiaire.objects.create(nom="Ouedraogo", prenom="Awa", sexe="M", telephone="70112233")
    Beneficiaire.objects.create(nom="Ouedraogo", prenom="Awa", sexe="F", telephone="70112233", date_naissance=datetime.date(1985, 1, 1))
    # Pièces d'identité différentes : deux personnes.
    Beneficiaire.objects.filter(pk=awa.pk).update(numero_piece_identite="B 123")
    Beneficiaire.objects.create(nom="Ouedraogo", prenom="Awa", sexe="F", telephone="70112233", numero_piece_identite="B999")
    # Vrai doublon : orthographe proche, même téléphone (sans indicatif).
    vrai = Beneficiaire.objects.create(nom="Ouedraogo", prenom="Awa", sexe="F", telephone="70112233")
    # Nom et prénom inversés, même date de naissance.
    inverse = Beneficiaire.objects.create(nom="Awa", prenom="Ouédraogo", sexe="F", date_naissance=datetime.date(1990, 5, 1))
    # Même pièce d'identité écrite autrement.
    piece = Beneficiaire.objects.create(nom="X", prenom="Y", sexe="F", numero_piece_identite="b-123")

    awa.refresh_from_db()
    trouves = {r["candidat"].pk: r for r in rechercher_doublons(awa)}
    assert set(trouves) == {vrai.pk, inverse.pk, piece.pk}
    assert trouves[vrai.pk]["motifs"] == ["Nom et prénom identiques", "Même téléphone"]
    assert "Nom et prénom inversés" in trouves[inverse.pk]["motifs"]
    assert trouves[piece.pk]["methode"] == "PIECE_IDENTITE"


@pytest.mark.django_db
def test_reverifier_retire_les_anciens_faux_positifs():
    from .models import SignalementDoublon
    from .services.duplicate_detection import reverifier_signalements

    a = Beneficiaire.objects.create(nom="Sawadogo", prenom="Issa", sexe="M")
    b = Beneficiaire.objects.create(nom="Sawadogo", prenom="Issa", sexe="M", telephone="70000000")
    c = Beneficiaire.objects.create(nom="Sawadogo", prenom="Issa", sexe="M", telephone="70000000")
    SignalementDoublon.objects.create(beneficiaire_1=a, beneficiaire_2=b, methode="SIMILARITE")  # ancien faux positif
    SignalementDoublon.objects.create(beneficiaire_1=b, beneficiaire_2=c, methode="SIMILARITE")
    assert reverifier_signalements() == {"retires": 1, "maintenus": 1}
    assert SignalementDoublon.objects.get().motifs == ["Nom et prénom identiques", "Même téléphone"]


@pytest.mark.django_db
def test_export_beneficiaires_par_projet_et_global():
    import datetime
    import io

    from openpyxl import load_workbook
    from rest_framework.test import APIClient

    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User
    from apps.projects.models import Projet

    from .models import ParticipationProjet

    admin = User.objects.create_user(username="admin_export_benef", password="x", role=ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    projet_a = Projet.objects.create(nom="Projet A", code="PA", date_debut="2026-01-01", date_fin="2026-12-31")
    projet_b = Projet.objects.create(nom="Projet B", code="PB", date_debut="2026-01-01", date_fin="2026-12-31")
    awa = Beneficiaire.objects.create(nom="OUEDRAOGO", prenom="Awa", sexe="F")
    Beneficiaire.objects.create(nom="SAWADOGO", prenom="Issa", sexe="M")
    for projet in (projet_a, projet_b):
        ParticipationProjet.objects.create(beneficiaire=awa, projet=projet, date_inscription=datetime.date(2026, 3, 1))

    reponse = client.get("/api/v1/beneficiaires/exporter/", {"projets": str(projet_a.id)})
    assert reponse.status_code == 200
    wb = load_workbook(io.BytesIO(reponse.content))
    assert wb.sheetnames == ["PA"]
    entetes = [c.value for c in wb["PA"][1]]
    assert [r[entetes.index("Nom")] for r in wb["PA"].iter_rows(min_row=2, values_only=True)] == ["OUEDRAOGO"]

    wb = load_workbook(io.BytesIO(client.get("/api/v1/beneficiaires/exporter/").content))
    assert wb.sheetnames == ["Tous les bénéficiaires", "PA", "PB", "Sans projet"]
    lignes = list(wb["Tous les bénéficiaires"].iter_rows(min_row=2, values_only=True))
    entetes = [c.value for c in wb["Tous les bénéficiaires"][1]]
    assert len(lignes) == 2
    assert lignes[0][entetes.index("Projets (codes)")] == "PA; PB"

    wb = load_workbook(io.BytesIO(client.get("/api/v1/beneficiaires/exporter/", {"projets": f"{projet_a.id},{projet_b.id}"}).content))
    assert wb.sheetnames == ["Tous les bénéficiaires", "PA", "PB"]  # sans « Sans projet »
    assert len(list(wb["Tous les bénéficiaires"].iter_rows(min_row=2))) == 1

    pdf = client.get("/api/v1/beneficiaires/exporter/", {"projets": str(projet_a.id), "fichier": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_identifiant_qr_et_cartes():
    import datetime

    from rest_framework.test import APIClient

    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User
    from apps.projects.models import Projet

    from .models import ParticipationProjet

    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_qr", password="x", role=ROLE_ADMIN))
    b = client.post("/api/v1/beneficiaires/", {"nom": "Kaboré", "prenom": "Rasmata", "sexe": "F"}, format="json").data
    assert b["identifiant"] == f"BEN-{b['id']:06d}"
    # Non modifiable, et retrouvable par l'identifiant (lien du QR code) ou par la recherche.
    client.patch(f"/api/v1/beneficiaires/{b['id']}/", {"identifiant": "AUTRE"}, format="json")
    assert client.get(f"/api/v1/beneficiaires/identifiant/{b['identifiant'].lower()}/").data == {"id": b["id"]}
    assert client.get("/api/v1/beneficiaires/identifiant/BEN-999999/").status_code == 404
    assert client.get("/api/v1/beneficiaires/", {"search": b["identifiant"]}).data["count"] == 1

    qr = client.get(f"/api/v1/beneficiaires/{b['id']}/qr/", {"origine": "https://plateforme.exemple"})
    assert qr["Content-Type"] == "image/svg+xml" and b"<svg" in qr.content

    projet = Projet.objects.create(nom="P", code="QR-1", date_debut="2026-01-01", date_fin="2026-12-31")
    ParticipationProjet.objects.create(beneficiaire_id=b["id"], projet=projet, date_inscription=datetime.date(2026, 1, 5))
    for params in ({"ids": str(b["id"])}, {"projet": projet.id}):
        pdf = client.get("/api/v1/beneficiaires/cartes/", params)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get("/api/v1/beneficiaires/cartes/").status_code == 400

    # Position GPS contrôlée.
    r = client.patch(f"/api/v1/beneficiaires/{b['id']}/", {"latitude": 95}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_localisation_aux_niveaux_du_pays_et_aller_retour_excel():
    import io

    from openpyxl import load_workbook

    from apps.accounts.constants import ROLE_ADMIN
    from apps.accounts.models import User
    from apps.geo.models import NiveauAdministratif, Zone

    from .services.export_excel import exporter_beneficiaires
    from .services.import_excel import generer_modele_import, importer_beneficiaires_depuis_feuille

    # Un pays avec ses propres niveaux : le modèle les reprend comme colonnes.
    cercle = NiveauAdministratif.objects.create(pays="ML", nom_niveau="Région", ordre=1)
    NiveauAdministratif.objects.create(pays="ML", nom_niveau="Cercle", ordre=2, niveau_parent=cercle)
    niveau_commune = NiveauAdministratif.objects.create(pays="ML", nom_niveau="Commune", ordre=3)
    sikasso = Zone.objects.create(nom="Sikasso", niveau_administratif=cercle)
    Zone.objects.create(nom="Koutiala", niveau_administratif=NiveauAdministratif.objects.get(nom_niveau="Cercle"), parent=sikasso)
    wb = load_workbook(io.BytesIO(generer_modele_import("ML")))
    entetes = [c.value for c in wb["Bénéficiaires"][1]]
    assert entetes[:5] == ["Pays (code ISO, ex : BF)", "Région", "Cercle", "Commune", "Nom"]
    assert "Latitude" in entetes and "Longitude" in entetes

    feuille = wb["Bénéficiaires"]
    feuille.delete_rows(2, feuille.max_row)
    ligne = {"Pays (code ISO, ex : BF)": "ML", "Région": "Sikasso", "Cercle": "Koutiala", "Commune": "Zangasso",
             "Nom": "Diarra", "Prénom": "Mariam", "Sexe (F/M)": "F", "Latitude": "12,1615", "Longitude": -5.4605,
             "Consentement (Oui/Non)": "oui", "Date du consentement (AAAA-MM-JJ)": "2026-03-02"}
    feuille.append([ligne.get(e, "") for e in entetes])
    utilisateur = User.objects.create_user(username="adm_loc", password="x", role=ROLE_ADMIN)
    resultat = importer_beneficiaires_depuis_feuille(feuille, utilisateur)
    assert resultat["crees"] == 1 and resultat["avertissements"] == []
    b = Beneficiaire.objects.get(nom="Diarra")
    assert b.zone.nom == "Zangasso" and b.zone.niveau_administratif == niveau_commune and b.zone.parent.nom == "Koutiala"
    assert float(b.latitude) == 12.1615
    assert b.consentement is True and str(b.date_consentement) == "2026-03-02"

    # Export (localisation sur les bonnes colonnes, identifiant), puis réimport à l'identique.
    wb = load_workbook(io.BytesIO(exporter_beneficiaires(Beneficiaire.objects.all(), [], inclure_sans_projet=True)))
    export = wb["Sans projet"]
    entetes = [c.value for c in export[1]]
    valeurs = dict(zip(entetes, next(export.iter_rows(min_row=2, values_only=True))))
    assert (valeurs["Région"], valeurs["Cercle"], valeurs["Commune"], valeurs["Nom"]) == ("Sikasso", "Koutiala", "Zangasso", "Diarra")
    assert valeurs["Identifiant"] == b.identifiant
    assert valeurs["Consentement (Oui/Non)"] == "Oui"
    Beneficiaire.objects.all().delete()
    assert importer_beneficiaires_depuis_feuille(export, utilisateur)["crees"] == 1
    assert Beneficiaire.objects.get().zone == b.zone
    assert Beneficiaire.objects.get().consentement is True


@pytest.mark.django_db
def test_variables_personnalisees_par_projet_avec_na():
    import datetime
    import io

    from openpyxl import load_workbook
    from rest_framework.test import APIClient

    from apps.accounts.constants import ROLE_ADMIN, ROLE_CHARGE_SE
    from apps.accounts.models import User
    from apps.projects.models import Projet

    from .models import ParticipationProjet
    from .services.export_excel import exporter_beneficiaires
    from .services.import_excel import generer_modele_import, importer_beneficiaires_depuis_feuille

    admin = APIClient()
    admin.force_authenticate(User.objects.create_user(username="adm_var", password="x", role=ROLE_ADMIN))
    charge = APIClient()
    charge.force_authenticate(User.objects.create_user(username="se_var", password="x", role=ROLE_CHARGE_SE))
    eau = Projet.objects.create(nom="Eau", code="EAU", date_debut="2026-01-01", date_fin="2026-12-31")
    agri = Projet.objects.create(nom="Agri", code="AGRI", date_debut="2026-01-01", date_fin="2026-12-31")

    menage = admin.post("/api/v1/variables-beneficiaires/", {"libelle": "Taille du ménage", "type": "NOMBRE", "unite": "personnes"}, format="json").data
    semence = admin.post(
        "/api/v1/variables-beneficiaires/",
        {"libelle": "Semence reçue", "type": "CHOIX", "choix": ["Maïs", "Sorgho"], "tous_les_projets": False, "projets": [agri.id]},
        format="json",
    ).data
    assert semence["projets_codes"] == ["AGRI"]
    # Paramétrage réservé à l'administrateur ; un choix demande au moins deux réponses.
    assert charge.post("/api/v1/variables-beneficiaires/", {"libelle": "X"}, format="json").status_code == 403
    assert admin.post("/api/v1/variables-beneficiaires/", {"libelle": "Y", "type": "CHOIX", "choix": ["A"]}, format="json").status_code == 400

    # Réponses contrôlées selon le type.
    b = admin.post("/api/v1/beneficiaires/", {"nom": "Zongo", "prenom": "Ali", "sexe": "M"}, format="json").data
    r = admin.patch(f"/api/v1/beneficiaires/{b['id']}/", {"reponses": {menage["id"]: "abc"}}, format="json")
    assert r.status_code == 400 and "nombre" in str(r.data)
    r = admin.patch(f"/api/v1/beneficiaires/{b['id']}/", {"reponses": {menage["id"]: "6", semence["id"]: "maïs"}}, format="json")
    assert r.data["reponses"] == {str(menage["id"]): 6.0, str(semence["id"]): "Maïs"}
    ParticipationProjet.objects.create(beneficiaire_id=b["id"], projet=eau, date_inscription=datetime.date(2026, 1, 1))

    # Export du projet Eau : la semence ne le concerne pas → NA.
    wb = load_workbook(io.BytesIO(exporter_beneficiaires(Beneficiaire.objects.all(), [eau])))
    entetes = [c.value for c in wb["EAU"][1]]
    ligne = dict(zip(entetes, next(wb["EAU"].iter_rows(min_row=2, values_only=True))))
    assert ligne["Taille du ménage"] == 6 and ligne["Semence reçue"] == "NA"

    # Modèle d'import d'un projet : seulement ses variables ; import avec NA et réponse invalide.
    modele = load_workbook(io.BytesIO(generer_modele_import("BF", projet=eau)))["Bénéficiaires"]
    entetes = [c.value for c in modele[1]]
    assert "Taille du ménage" in entetes and "Semence reçue" not in entetes
    modele = load_workbook(io.BytesIO(generer_modele_import("BF", projet=agri)))["Bénéficiaires"]
    entetes = [c.value for c in modele[1]]
    modele.delete_rows(2, modele.max_row)
    for nom, menage_valeur, semence_valeur in (("Sanou", 4, "Sorgho"), ("Barry", "NA", "Riz")):
        valeurs = {"Nom": nom, "Prénom": "A", "Sexe (F/M)": "F", "Taille du ménage": menage_valeur, "Semence reçue": semence_valeur}
        modele.append([valeurs.get(e, "") for e in entetes])
    resultat = importer_beneficiaires_depuis_feuille(modele, User.objects.get(username="adm_var"), projet=agri)
    assert resultat["crees"] == 2
    assert Beneficiaire.objects.get(nom="Sanou").reponses == {str(menage["id"]): 4.0, str(semence["id"]): "Sorgho"}
    assert Beneficiaire.objects.get(nom="Barry").reponses == {}
    assert any("Riz" in a["message"] for a in resultat["avertissements"])

    # Supprimer une variable retire ses réponses des fiches.
    admin.delete(f"/api/v1/variables-beneficiaires/{semence['id']}/")
    assert str(semence["id"]) not in Beneficiaire.objects.get(nom="Sanou").reponses
