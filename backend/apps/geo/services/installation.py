"""
Zones administratives installées automatiquement pour un pays : à l'inscription (pays de l'organisation), quand
un pays est ajouté aux pays de l'organisation (page Zones administratives) ou choisi pour un projet.

- Burkina Faso : référentiel national (17 régions, 47 provinces : referentiel_bf).
- Autres pays : limites ouvertes geoBoundaries (niveaux 1 à 3 s'ils existent) ; chaque zone est rattachée à la
  zone du niveau supérieur qui la contient (calcul sur les contours), et placée sur la carte.
- Un pays qui a déjà des niveaux administratifs n'est jamais modifié : ce qu'une organisation a saisi ou corrigé
  est gardé. Tout reste modifiable ensuite sur la page Zones administratives.
- Le téléchargement peut prendre une minute : il se fait en arrière-plan (installer_en_arriere_plan), et
  InstallationZones dit où il en est.
"""
import logging
import threading

from django.conf import settings
from django.db import IntegrityError, connections, transaction

from .limites import LimitesIndisponibles, telecharger

logger = logging.getLogger(__name__)

NIVEAUX = (1, 2, 3)
# Noms des niveaux donnés par geoBoundaries (en anglais) → français.
NOMS_NIVEAUX = {
    "region": "Région", "regions": "Région", "province": "Province", "provinces": "Province",
    "district": "District", "districts": "District", "department": "Département", "departments": "Département",
    "departement": "Département", "state": "État", "states": "État", "county": "Comté", "counties": "Comté",
    "municipality": "Commune", "municipalities": "Commune", "commune": "Commune", "communes": "Commune",
    "prefecture": "Préfecture", "prefectures": "Préfecture", "governorate": "Gouvernorat", "governorates": "Gouvernorat",
    "canton": "Canton", "cantons": "Canton", "sub-prefecture": "Sous-préfecture", "sub-prefectures": "Sous-préfecture",
    "subprefecture": "Sous-préfecture", "arrondissement": "Arrondissement", "arrondissements": "Arrondissement",
    "circle": "Cercle", "cercle": "Cercle", "cercles": "Cercle", "division": "Division", "divisions": "Division",
    "subdivision": "Subdivision", "sub-division": "Subdivision", "subdivisions": "Subdivision", "zone": "Zone",
    "zones": "Zone", "ward": "Quartier", "wards": "Quartier", "village": "Village", "villages": "Village",
    "local government area": "Zone de gouvernement local", "local government areas": "Zone de gouvernement local",
    "parish": "Paroisse", "parishes": "Paroisse", "city": "Ville", "cities": "Ville", "town": "Ville",
}


def nom_niveau(source: str, ordre: int) -> str:
    cle = (source or "").strip().lower()
    return NOMS_NIVEAUX.get(cle) or ((source or "").strip()[:150] or f"Niveau {ordre}")


def code_pays(nom: str) -> str:
    """Code ISO à deux lettres d'un pays donné par son nom (français ou anglais) ou son code ; « » si inconnu."""
    import unicodedata

    from ..noms_pays import NOMS_PAYS

    nom = (nom or "").strip()
    if len(nom) == 2 and nom.isalpha():
        return nom.upper()
    cle = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode().lower()
    return NOMS_PAYS.get(" ".join(cle.replace("’", " ").replace("'", " ").split()), "")


def installe(pays: str) -> bool:
    from ..models import NiveauAdministratif

    return NiveauAdministratif.objects.filter(pays=pays.upper()).exists()


def _depuis_geoboundaries(pays: str) -> int:
    from shapely.geometry import shape
    from shapely.strtree import STRtree

    from ..models import NiveauAdministratif, Zone

    total, niveau_parent, parents = 0, None, []  # parents : [(forme, zone)] du niveau précédent
    with transaction.atomic():
        for ordre in NIVEAUX:
            try:
                limite = telecharger(pays, ordre)
            except LimitesIndisponibles:
                if ordre == 1:
                    raise
                break  # niveau absent de la source : on s'arrête au précédent
            elements = []
            for entite in limite.geojson.get("features", []):
                nom = ((entite.get("properties") or {}).get("shapeName") or "").strip()[:150]
                try:
                    forme = shape(entite["geometry"])
                    point = forme.representative_point()
                except Exception:
                    continue
                if nom:
                    elements.append((forme, point, nom))
            if not elements:
                break
            niveau = NiveauAdministratif.objects.create(pays=pays, nom_niveau=nom_niveau(limite.nom_niveau, ordre),
                                                        ordre=ordre, niveau_parent=niveau_parent)
            arbre = STRtree([forme for forme, _ in parents]) if parents else None
            nouvelles = []
            for forme, point, nom in elements:
                parent = None
                if arbre is not None:
                    parent = next((parents[i][1] for i in arbre.query(point) if parents[i][0].contains(point)), None)
                    if parent is None:  # contours imparfaits : la zone la plus proche
                        parent = parents[int(arbre.nearest(point))][1]
                nouvelles.append((forme, Zone(niveau_administratif=niveau, parent=parent, nom=nom,
                                              latitude=round(point.y, 6), longitude=round(point.x, 6))))
            Zone.objects.bulk_create([zone for _, zone in nouvelles])
            total += len(nouvelles)
            niveau_parent, parents = niveau, nouvelles
    return total


def _verrouiller(pays: str):
    """Verrou PostgreSQL propre au pays, libéré à la fin de la transaction."""
    import zlib

    from django.db import connection

    with connection.cursor() as curseur:
        curseur.execute("SELECT pg_advisory_xact_lock(%s)", [zlib.crc32(f"zones-{pays}".encode())])


def installer_pays(pays: str) -> int:
    """
    Installe les zones d'un pays (rien si le pays a déjà des niveaux) ; renvoie le nombre de zones créées. Un verrou
    par pays (base de données) empêche deux installations simultanées de se mêler.
    """
    from ..models import InstallationZones, NiveauAdministratif, Zone

    pays = (pays or "").upper()[:2]
    if len(pays) != 2:
        return 0
    if _mode() == "desactivee" and pays != "BF":  # le référentiel du Burkina Faso est local : toujours possible
        return 0
    if installe(pays):
        InstallationZones.objects.update_or_create(pays=pays, defaults={"statut": InstallationZones.Statut.TERMINE})
        return 0
    InstallationZones.objects.update_or_create(pays=pays, defaults={"statut": InstallationZones.Statut.EN_COURS, "message": ""})
    try:
        with transaction.atomic():
            _verrouiller(pays)
            if installe(pays):  # installé pendant l'attente du verrou
                total, source = 0, ""
            elif pays == "BF":
                from ..referentiel_bf import charger_zones_bf

                total, source = charger_zones_bf(NiveauAdministratif, Zone), "référentiel national"
            else:
                total, source = _depuis_geoboundaries(pays), "geoBoundaries"
    except Exception as exc:
        if installe(pays):  # installées entre-temps par une autre demande : rien à signaler
            InstallationZones.objects.filter(pays=pays).update(statut=InstallationZones.Statut.TERMINE, message="")
            return 0
        logger.warning("Zones administratives de %s non installées : %s", pays, exc)
        InstallationZones.objects.filter(pays=pays).update(statut=InstallationZones.Statut.ECHEC, message=str(exc)[:500])
        return 0
    if source:
        InstallationZones.objects.filter(pays=pays).update(statut=InstallationZones.Statut.TERMINE, zones=total, source=source)
    else:
        InstallationZones.objects.filter(pays=pays).update(statut=InstallationZones.Statut.TERMINE)
    return total


def _mode() -> str:
    return getattr(settings, "ZONES_INSTALLATION", "arriere-plan")


def installer_en_arriere_plan(pays_liste):
    """Lance l'installation des pays qui n'ont pas encore de zones, sans faire attendre la requête."""
    from apps.organisations import contexte

    from ..models import InstallationZones

    if _mode() == "desactivee":
        return []
    a_faire = []
    for pays in {(p or "").upper()[:2] for p in pays_liste}:
        if len(pays) != 2 or installe(pays):
            continue
        # Réservation en base : une seule installation par pays, même si plusieurs demandes arrivent ensemble.
        try:
            with transaction.atomic():
                _, creee = InstallationZones.objects.get_or_create(pays=pays, defaults={"statut": InstallationZones.Statut.EN_COURS})
        except IntegrityError:
            continue
        if not creee and not InstallationZones.objects.filter(pays=pays).exclude(
                statut=InstallationZones.Statut.EN_COURS).update(statut=InstallationZones.Statut.EN_COURS, message=""):
            continue  # déjà en cours
        a_faire.append(pays)
    if not a_faire:
        return []
    org = contexte.courante()

    def travail():
        try:
            if org is not None:
                with contexte.dans_organisation(org):
                    for pays in a_faire:
                        installer_pays(pays)
            else:
                for pays in a_faire:
                    installer_pays(pays)
        finally:
            connections.close_all()

    if _mode() == "synchrone":
        for pays in a_faire:
            installer_pays(pays)
        return a_faire
    threading.Thread(target=travail, daemon=True).start()
    return a_faire
