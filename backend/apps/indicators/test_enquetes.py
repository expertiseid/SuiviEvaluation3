"""Données d'enquête : import, estimations pondérées et marges d'erreur (apps.indicators.enquetes)."""
import io
import math
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .enquetes import EnqueteInvalide, a_ecarter, estimer, lire, quantile_student
from .formules import evaluer
from .models import Enquete


def _enquete(colonnes, lignes, **plan):
    return Enquete(titre="E", colonnes=[{"nom": n, "type": t} for n, t in colonnes], donnees=lignes, nombre_reponses=len(lignes), **plan)


@pytest.mark.django_db  # libellés au vocabulaire de l'organisation
def test_proportion_sondage_aleatoire_simple():
    # 40 « Oui » sur 100 : p = 40 %, erreur type = racine(p(1 − p) / (n − 1)).
    e = _enquete([("eau", "TEXTE")], [["Oui"]] * 40 + [["Non"]] * 60)
    r = estimer(e, "proportion", "eau", ["Oui"])["resultats"][0]
    erreur = math.sqrt(0.4 * 0.6 / 99) * 100
    assert r["estimation"] == 40.0 and r["n"] == 100 and abs(r["erreur_type"] - erreur) < 1e-3
    assert abs(r["marge"] - quantile_student(99) * erreur) < 1e-3 and quantile_student(99) == 2.0
    assert abs(r["deff"] - 1.0) < 1e-6  # sans pondération ni grappe : pas d'effet de plan
    assert r["ic_bas"] < 40 < r["ic_haut"] and not r["effectif_faible"]


@pytest.mark.django_db  # libellés au vocabulaire de l'organisation
def test_moyenne_ponderee_ventilee_et_grappes():
    # Moyenne pondérée : (1×10 + 3×20) / 4 = 17,5.
    e = _enquete([("revenu", "NOMBRE"), ("poids", "NOMBRE"), ("sexe", "TEXTE")],
                 [[10, 1, "F"], [20, 3, "M"], [None, 5, "F"]], colonne_poids="poids")
    r = estimer(e, "moyenne", "revenu")
    assert r["resultats"][0]["estimation"] == 17.5 and r["resultats"][0]["n"] == 2 and "pondéré" in r["plan"]
    par_sexe = {x["groupe"]: x for x in estimer(e, "moyenne", "revenu", par="sexe")["resultats"]}
    assert par_sexe["F"]["estimation"] == 10 and par_sexe["M"]["estimation"] == 20 and par_sexe["F"]["effectif_faible"]
    # Total estimé : 1×10 + 3×20 = 70 ; nombre estimé de femmes : poids 1 + 5 = 6.
    assert estimer(e, "total", "revenu")["resultats"][0]["estimation"] == 70
    assert estimer(e, "total", "sexe", ["F"])["resultats"][0]["estimation"] == 6

    # Grappes : 2 villages identiques en interne (tout Oui / tout Non) → toute la variance vient des villages.
    villages = _enquete([("eau", "TEXTE"), ("village", "TEXTE")],
                        [["Oui", "V1"]] * 10 + [["Non", "V2"]] * 10, colonne_grappe="village")
    g = estimer(villages, "proportion", "eau", ["Oui"])["resultats"][0]
    # z par village : ±10 × 0,5 / 20 = ±0,25 ; variance = 2/1 × (0,25² × 2) = 0,25 → erreur type 0,5 (50 points).
    assert g["estimation"] == 50 and abs(g["erreur_type"] - 50) < 1e-6 and g["deff"] > 10
    assert g["ic_bas"] == 0 and g["ic_haut"] == 100  # bornées à 0 et 100 %

    with pytest.raises(EnqueteInvalide):
        estimer(e, "moyenne", "sexe")
    with pytest.raises(EnqueteInvalide):
        estimer(e, "proportion", "inconnue", ["x"])


@pytest.mark.django_db
def test_import_api_et_formule():
    assert a_ecarter("Nom du chef de ménage") and a_ecarter("groupe/telephone") and a_ecarter("_uuid") and a_ecarter("_gps_latitude")
    assert not a_ecarter("nombre_enfants") and not a_ecarter("Âge")
    contenu = "nom;telephone;_uuid;age;acces_eau;poids_menage\n" + "\n".join(
        f"P{i};7000{i};u{i};{20 + i};{'Oui' if i % 4 == 0 else 'Non'};{'2,5' if i % 2 else '1'}" for i in range(40))
    lu = lire(SimpleUploadedFile("menages.csv", contenu.encode("utf-8")))
    assert [c["nom"] for c in lu["colonnes"]] == ["age", "acces_eau", "poids_menage"]
    assert lu["colonnes_ecartees"] == ["nom", "telephone", "_uuid"] and lu["colonne_poids"] == "poids_menage"
    assert lu["colonnes"][0]["type"] == "NOMBRE" and lu["donnees"][1] == [21.0, "Non", 2.5]
    with pytest.raises(EnqueteInvalide):
        lire(SimpleUploadedFile("vide.csv", b"a;b\n"))

    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_enquetes", password="x", role=ROLE_ADMIN))
    cree = client.post("/api/v1/enquetes/", {"fichier": SimpleUploadedFile("menages.csv", contenu.encode("utf-8")),
                                            "titre": "Enquête ménages"}, format="multipart")
    assert cree.status_code == 201 and cree.data["nombre_reponses"] == 40 and "donnees" not in cree.data
    numero = cree.data["id"]
    assert client.patch(f"/api/v1/enquetes/{numero}/", {"colonne_poids": "acces_eau"}, format="json").status_code == 400
    modalites = client.get(f"/api/v1/enquetes/{numero}/modalites/", {"colonne": "acces_eau"}).data
    assert modalites == [{"valeur": "Non", "nombre": 30}, {"valeur": "Oui", "nombre": 10}]
    calcul = client.get(f"/api/v1/enquetes/{numero}/calcul/", {"calcul": "proportion", "colonne": "acces_eau", "valeurs": ["Oui"]}).data
    # « Oui » : i multiple de 4, donc pair, poids 1 ; 10 × 1 / (20 × 1 + 20 × 2,5) = 14,29 %.
    assert abs(calcul["resultats"][0]["estimation"] - 1000 / 70) < 1e-3

    # Résultat d'enquête dans un indicateur calculé, avec sa marge d'erreur.
    formule = {"termes": [{"mesure": "enquete", "filtres": {"enquete": numero, "calcul_enquete": "proportion",
                                                           "colonne": "acces_eau", "valeurs": "Oui"}}], "expression": "A"}
    r = evaluer(formule, [])
    assert r["valeur"] == Decimal("14.29") and r["marges"]["A"] > 0
