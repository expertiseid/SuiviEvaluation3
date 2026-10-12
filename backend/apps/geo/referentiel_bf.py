"""
Chargement du référentiel administratif du Burkina Faso (niveaux Région >
Province > Commune, 17 régions et 47 provinces) — partagé entre la commande
`seed_zones_bfa` et la migration 0007 (d'où les modèles passés en paramètre :
la migration utilise ses modèles « historiques »).

Réutilise ce qui existe déjà plutôt que de dupliquer : un niveau saisi à la
main sous un autre libellé (« REGION », « region »...) est reconnu et
renommé, et une zone saisie à la main est reconnue par son code ou par son
nom, même avec une orthographe proche (« BANKUY » pour « Bankui ») — elle
garde alors son identifiant, donc les projets/bénéficiaires qui y sont
rattachés le restent.
"""
import difflib
import json
import unicodedata
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "bfa_regions_provinces.json"

# Ressemblance minimale (0-1) pour reconnaître une zone saisie à la main.
SEUIL_RESSEMBLANCE = 0.8


def _normaliser(texte: str) -> str:
    sans_accents = "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn")
    return "".join(c for c in sans_accents.lower() if c.isalnum())


def _niveau(NiveauAdministratif, nom, ordre, parent):
    existant = next(
        (n for n in NiveauAdministratif.objects.filter(pays="BF") if _normaliser(n.nom_niveau) == _normaliser(nom)),
        None,
    )
    if existant is None:
        return NiveauAdministratif.objects.create(pays="BF", nom_niveau=nom, ordre=ordre, niveau_parent=parent)
    existant.nom_niveau = nom
    existant.niveau_parent = parent
    existant.save(update_fields=["nom_niveau", "niveau_parent"])
    return existant


def _charger_niveau_zones(Zone, niveau, lignes, parent_de):
    """`lignes` : (code, nom officiel, ...) ; `parent_de(ligne)` : zone parente ou None."""
    restantes = list(Zone.objects.filter(niveau_administratif=niveau))
    par_code = {}
    crees = 0
    for ligne in lignes:
        code, nom = ligne[0], ligne[1]
        zone = next((z for z in restantes if z.code == code), None)
        if zone is None:
            zone = next((z for z in restantes if _normaliser(z.nom) == _normaliser(nom)), None)
        if zone is None:
            candidates = [z for z in restantes if not z.code]
            scores = [(difflib.SequenceMatcher(None, _normaliser(z.nom), _normaliser(nom)).ratio(), z) for z in candidates]
            meilleur = max(scores, key=lambda s: s[0], default=None)
            if meilleur and meilleur[0] >= SEUIL_RESSEMBLANCE:
                zone = meilleur[1]

        if zone is None:
            zone = Zone.objects.create(code=code, nom=nom, niveau_administratif=niveau, parent=parent_de(ligne))
            crees += 1
        else:
            restantes.remove(zone)
            zone.code = code
            zone.nom = nom
            zone.parent = parent_de(ligne)
            zone.save(update_fields=["code", "nom", "parent"])
        par_code[code] = zone
    return par_code, crees


def charger_zones_bf(NiveauAdministratif, Zone) -> int:
    """Charge (ou complète) le référentiel BF. Renvoie le nombre de zones créées."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    niveau_region = _niveau(NiveauAdministratif, "Région", 1, None)
    niveau_province = _niveau(NiveauAdministratif, "Province", 2, niveau_region)
    _niveau(NiveauAdministratif, "Commune", 3, niveau_province)

    regions, crees_regions = _charger_niveau_zones(Zone, niveau_region, data["regions"], lambda ligne: None)
    _, crees_provinces = _charger_niveau_zones(
        Zone, niveau_province, data["provinces"], lambda ligne: regions[ligne[2]]
    )
    return crees_regions + crees_provinces
