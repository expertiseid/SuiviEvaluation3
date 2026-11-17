"""Bénéficiaires et territoires (apps.beneficiaries.territoires)."""
import pytest

from apps.geo.models import NiveauAdministratif, Zone
from apps.projects.models import Projet

from .models import Beneficiaire, ParticipationProjet
from .territoires import beneficiaires_territoires, coordonnees_valides


@pytest.mark.django_db
def test_beneficiaires_et_territoires():
    region = NiveauAdministratif.objects.create(pays="BF", nom_niveau="Région", ordre=1)
    commune = NiveauAdministratif.objects.create(pays="BF", nom_niveau="Commune", ordre=2, niveau_parent=region)
    nord = Zone.objects.create(nom="Nord", niveau_administratif=region)
    sud = Zone.objects.create(nom="Sud", niveau_administratif=region, population=2000)
    # La population du Nord vient de ses communes.
    ouahigouya = Zone.objects.create(nom="Ouahigouya", niveau_administratif=commune, parent=nord, population=1000)
    seguenega = Zone.objects.create(nom="Séguénéga", niveau_administratif=commune, parent=nord, population=3000)
    projet = Projet.objects.create(nom="P", code="TE-1", date_debut="2026-01-01", date_fin="2026-12-31", cible_totale=8)
    projet.zones.set([ouahigouya, seguenega])  # Séguénéga ciblée, mais personne n'y est inscrit

    def inscrire(nom, sexe, zone, statut="EN_COURS", satisfaction=None, taille=None):
        b = Beneficiaire.objects.create(nom=nom, prenom=nom, sexe=sexe, zone=zone, taille_menage=taille)
        ParticipationProjet.objects.create(beneficiaire=b, projet=projet, date_inscription="2026-02-01", statut=statut,
                                           satisfaction=satisfaction)
        return b

    a = inscrire("a", "F", ouahigouya, "TERMINE", 5, taille=6)
    inscrire("b", "M", ouahigouya, "ABANDON", 2, taille=4)
    inscrire("c", "F", sud)  # hors des zones du projet
    inscrire("d", "F", nord, "TERMINE")  # inscrit à la région seulement : pas « hors zone »
    # Deuxième activité de « a », encore en cours : son parcours n'est plus complet.
    ParticipationProjet.objects.create(beneficiaire=a, projet=projet, date_inscription="2026-03-01")

    t = beneficiaires_territoires([projet.id])
    assert (t["directs"], t["menages"], t["personnes_des_menages"]) == (4, 2, 10)
    assert (t["indirects"], t["source_indirects"]) == (8, "menages")  # (6 − 1) + (4 − 1)
    assert (t["cible"], t["couverture_cible"]) == (8, 50.0)
    assert (t["parcours"], t["taux_abandon"], t["taux_maintien"], t["taux_paquet_complet"]) == (4, 25.0, 75.0, 25.0)
    assert (t["satisfaction_moyenne"], t["satisfaction_reponses"], t["part_satisfaits"]) == (3.5, 2, 50.0)
    par_zone = {x["zone"]: x for x in t["territoires"]}
    assert par_zone["Nord"]["beneficiaires"] == 3 and par_zone["Nord"]["population"] == 4000
    assert par_zone["Nord"]["pour_1000_habitants"] == 0.75 and par_zone["Sud"]["pour_1000_habitants"] == 0.5
    assert t["ecart_couverture"]["plus_haut"] == "Nord" and t["ecart_couverture"]["rapport"] == 1.5
    assert (t["zones_ciblees"], t["zones_sans_beneficiaire"]) == (2, 1)
    assert t["zones_sans_beneficiaire_exemples"] == [{"projet": "TE-1", "zone": "Séguénéga", "niveau": "Commune"}]
    assert t["hors_zone"] == 1 and t["hors_zone_exemples"] == [{"projet": "TE-1", "zone": "Sud", "beneficiaires": 1}]
    assert (t["plaintes"], t["plaintes_pour_1000"]) == (0, 0.0)

    # Bénéficiaires indirects saisis au projet : ils priment sur l'estimation par les ménages.
    Projet.objects.filter(pk=projet.pk).update(beneficiaires_indirects=50)
    assert beneficiaires_territoires([projet.id])["indirects"] == 50
    # Aucun statut saisi : maintien et abandon inconnus (et non 100 % / 0 %).
    ParticipationProjet.objects.update(statut="EN_COURS")
    vide = beneficiaires_territoires([projet.id])
    assert vide["taux_abandon"] is None and vide["taux_maintien"] is None


def test_coordonnees_valides():
    burkina = [-5.5, 9.4, 2.4, 15.1]
    assert coordonnees_valides(12.37, -1.52, burkina)
    assert not coordonnees_valides(0, 0)
    assert not coordonnees_valides(95, 10)
    assert not coordonnees_valides(48.85, 2.35, burkina)  # Paris, pas au Burkina
    assert coordonnees_valides(None, None)
