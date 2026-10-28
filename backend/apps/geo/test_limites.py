"""Limites administratives et carte des bénéficiaires (sans accès Internet : contours fabriqués)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import User

from .models import LimiteAdministrative, NiveauAdministratif, Zone
from .services.limites import completer_par_les_enfants, placer_zones


def _carre(nom, lng, lat, cote=1.0):
    return {
        "type": "Feature",
        "properties": {"shapeName": nom},
        "geometry": {"type": "Polygon", "coordinates": [[
            [lng, lat], [lng + cote, lat], [lng + cote, lat + cote], [lng, lat + cote], [lng, lat],
        ]]},
    }


@pytest.mark.django_db
def test_placement_des_zones_et_carte():
    region = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Région", ordre=1)
    province = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Province", ordre=2, niveau_parent=region)
    commune = NiveauAdministratif.objects.create(pays="ZZ", nom_niveau="Commune", ordre=3, niveau_parent=province)
    nord = Zone.objects.create(nom="Nouvelle Région", niveau_administratif=region)  # absente de la source
    houet = Zone.objects.create(nom="Houet", niveau_administratif=province, parent=nord)
    kouritenga = Zone.objects.create(nom="Kouritenga", niveau_administratif=province, parent=nord)
    bobo = Zone.objects.create(nom="Bobo", niveau_administratif=commune, parent=houet)
    faux = Zone.objects.create(nom="Koudougou", niveau_administratif=commune, parent=houet)

    LimiteAdministrative.objects.create(pays="ZZ", niveau=2, geojson={"type": "FeatureCollection", "features": [
        _carre("Houet", -5, 11), _carre("Kourittenga", 0, 12),  # orthographe voisine
    ]})
    niveau3 = LimiteAdministrative.objects.create(pays="ZZ", niveau=3, geojson={"type": "FeatureCollection", "features": [
        _carre("Bobo", -4.5, 11.2, 0.2),
        _carre("Koudougou", -1, 14, 0.2),  # contour mal nommé dans la source : hors de sa province
    ]})
    assert placer_zones(LimiteAdministrative.objects.get(niveau=2)) == 2
    assert placer_zones(niveau3) == 1
    faux.refresh_from_db()
    assert faux.latitude is None  # rejeté : pas dans le contour de sa province
    assert completer_par_les_enfants("ZZ") == 1  # la région prend le centre de ses provinces
    nord.refresh_from_db()
    houet.refresh_from_db()
    assert round(float(houet.latitude), 1) == 11.5 and nord.latitude is not None

    # Carte : GPS en points, sinon au centre de la localité (ou de la zone parente placée).
    from apps.beneficiaries.models import Beneficiaire

    Beneficiaire.objects.create(nom="A", prenom="a", sexe="F", zone=bobo)
    Beneficiaire.objects.create(nom="B", prenom="b", sexe="M", zone=faux)  # placé sur Houet
    Beneficiaire.objects.create(nom="C", prenom="c", sexe="F", latitude="11.3", longitude="-4.4")
    Beneficiaire.objects.create(nom="D", prenom="d", sexe="M")
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="adm_carte", password="x", role=ROLE_ADMIN))
    carte = client.get("/api/v1/beneficiaires/carte/").data
    assert carte["total"] == 4 and carte["non_localises"] == 1
    assert [(p["nom"], p["lat"]) for p in carte["points"]] == [("C c", 11.3)]
    assert sorted((z["nom"], z["nombre"]) for z in carte["zones"]) == [("Bobo", 1), ("Houet", 1)]

    # Contours servis depuis le cache.
    r = client.get("/api/v1/limites-administratives/", {"pays": "ZZ", "niveau": 2})
    assert r.status_code == 200 and len(r.data["geojson"]["features"]) == 2
