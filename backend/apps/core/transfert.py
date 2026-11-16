"""
Sauvegarde complète d'un espace dans un seul fichier zip, et sa reprise dans un autre espace (même
plateforme ou autre installation) : on y retrouve tout ce que l'on voyait avant.

Contenu du zip :
- manifeste.json : format, date, organisation d'origine, migrations appliquées, nombre d'objets ;
- donnees.json : toutes les données de l'espace, au format de manage.py dumpdata (éléments de la
  corbeille compris) ; les types de contenu et les permissions, dont les numéros diffèrent d'une base
  à l'autre, y sont désignés par leur nom (clé naturelle), tout le reste par son numéro ;
- fichiers/ : les fichiers téléversés (documents, logos, photos…) ;
- prive/ : les pièces jointes des plaintes, EN CLAIR. Sur le serveur elles sont chiffrées avec la clé
  de l'organisation, illisible ailleurs : on les déchiffre à l'export et on les rechiffre à l'import.
  Les champs chiffrés de la base (récits, coordonnées) sont exportés en clair pour la même raison.
Le fichier contient donc des données personnelles en clair : réservé à l'administrateur, journalisé,
à garder en lieu sûr.

Reprise, en une seule transaction (en cas d'erreur, rien n'est changé), de deux façons :
- « remplacer » : tout le contenu de l'espace est remplacé par celui de la sauvegarde. Le compte de
  l'administrateur qui fait la reprise est gardé s'il n'existe pas dans la sauvegarde ;
- « ajouter » (fusion) : le contenu de la sauvegarde s'ajoute à celui de l'espace, qui garde tout ce
  qu'il avait. Chaque élément repris reçoit un nouveau numéro et ses liens suivent. Ce qui existe déjà
  n'est pas dupliqué mais réutilisé : référentiels (zones, catégories, types…), comptes (même
  identifiant ou même adresse courriel), bailleurs et partenaires (même nom), réglages de l'espace.
  Un projet ou un dossier de plainte dont le code existe déjà est repris sous un code suffixé (« -R1 »).
  Un fichier du même nom qu'un fichier existant mais différent est enregistré sous un autre nom.
  L'historique des modifications des éléments repris n'est pas recopié.
Dans les deux cas, le journal d'audit, qui ne s'efface jamais, est gardé : les événements de l'espace
d'origine y sont ajoutés.
"""
import json
import os
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.conf import settings
from itertools import chain

from django.core import serializers
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder

from apps.organisations import contexte

FORMAT = 1
# Jamais exportés ni effacés : propres à chaque base (types de contenu, permissions, sessions…) ou à
# la base centrale (registre des organisations).
EXCLUS = ("contenttypes", "auth.permission", "sessions", "admin.logentry", "token_blacklist")
AUDIT = "core.evenementaudit"


class TransfertRefuse(Exception):
    """Fichier invalide ou incompatible : le message est montré tel quel."""


def _modeles():
    """Modèles de l'espace (exportés et remplacés), tables intermédiaires comprises."""
    for modele in apps.get_models(include_auto_created=True):
        meta = modele._meta
        label = f"{meta.app_label}.{meta.model_name}"
        if meta.app_label in EXCLUS or label in EXCLUS or contexte.est_central(meta.app_label, meta.model_name):
            continue
        if not meta.managed or meta.proxy:
            continue
        yield modele


# Seules références écrites par leur nom : les numéros des comptes, eux, sont gardés tels quels (et
# l'historique des modifications peut désigner un compte supprimé depuis, sans clé naturelle possible).
NATURELS = {"contenttypes.ContentType", "auth.Permission"}


class _Serialiseur(serializers.get_serializer("json")):
    def _naturel(self, field):
        return self.use_natural_foreign_keys and field.remote_field.model._meta.label in NATURELS

    def handle_fk_field(self, obj, field):
        self.use_natural_foreign_keys, garde = self._naturel(field), self.use_natural_foreign_keys
        try:
            super().handle_fk_field(obj, field)
        finally:
            self.use_natural_foreign_keys = garde

    def handle_m2m_field(self, obj, field):
        self.use_natural_foreign_keys, garde = self._naturel(field), self.use_natural_foreign_keys
        try:
            super().handle_m2m_field(obj, field)
        finally:
            self.use_natural_foreign_keys = garde


def _ecrire_donnees(chemin, selection=None) -> int:
    """
    Les lignes de l'espace (toutes, ou celles de `selection` : {modèle: numéros}), modèles dans l'ordre
    de leurs dépendances ; renvoie leur nombre.
    """
    exportes = {m for m in _modeles() if not m._meta.auto_created}
    ordre = serializers.sort_dependencies([(config, None) for config in apps.get_app_configs()])
    modeles = [m for m in ordre if m in exportes and (selection is None or selection.get(m))]

    def lignes(m):
        qs = m._base_manager.order_by("pk")
        return qs if selection is None else qs.filter(pk__in=selection[m])

    nombre = sum(lignes(m).count() for m in modeles)
    objets = chain.from_iterable(lignes(m).iterator(chunk_size=2000) for m in modeles)
    with open(chemin, "w", encoding="utf-8") as f:
        _Serialiseur().serialize(objets, stream=f, use_natural_foreign_keys=True)
    return nombre


def _migrations() -> dict:
    appliquees = {}
    for app, nom in MigrationRecorder(connection).applied_migrations():
        appliquees.setdefault(app, []).append(nom)
    return {app: sorted(noms) for app, noms in appliquees.items()}


def _racine(reglage) -> Path:
    from apps.organisations.stockage import racine_fichiers

    return Path(racine_fichiers(str(reglage)))


def _fichiers(racine: Path):
    """Fichiers sous `racine` ; hors organisation, sans les dossiers des organisations."""
    if not racine.is_dir():
        return
    for dossier, sous, noms in os.walk(racine):
        if contexte.courante() is None and Path(dossier) == racine and "organisations" in sous:
            sous.remove("organisations")
        for nom in noms:
            chemin = Path(dossier) / nom
            yield chemin, chemin.relative_to(racine).as_posix()


# Réglages de l'espace (une seule ligne) : ceux de l'espace d'arrivée sont gardés.
SINGLETONS = {"dashboard.configurationtableaudebord", "dashboard.configurationmenu", "projects.parametrescalcul",
              "projects.parametresrapportage", "indicators.parametresalerte", "plaintes.mecanisme",
              "core.identiteorganisation"}
# Éléments sans champ unique, reconnus par ces champs pour ne pas les dupliquer.
CORRESPONDANCES = {"geo.niveauadministratif": ("pays", "ordre"), "geo.zone": ("niveau_administratif", "parent", "nom"),
                   "geo.localite": ("pays", "nom", "commune", "latitude", "longitude"),
                   "partners.bailleur": ("nom",), "partners.partenaire": ("nom",),
                   "strategy.typedocument": ("ordre",), "strategy.cadrestrategique": ("type_document", "nom"),
                   "strategy.typeniveau": ("cadre_strategique", "ordre"),
                   "strategy.elementstrategique": ("type_niveau", "element_parent", "nom")}
# Code unique déjà pris : l'élément est repris comme nouveau, sous un code suffixé.
RENOMMER = {"projects.projet": "code", "plaintes.dossier": "numero"}



# --- Sélection : quelques projets ou cadres stratégiques, avec tout ce qui leur appartient ----------

# Jamais repris en descendant d'un élément sélectionné (référentiels et éléments partagés) : ils ne sont
# exportés que s'ils sont désignés par un élément exporté (ex. une zone, un bailleur, un bénéficiaire).
PARTAGES = {"accounts.user", "accounts.role", "geo.zone", "geo.niveauadministratif", "partners.bailleur",
            "partners.partenaire", "partners.structureorganisation", "partners.partieprenante",
            "partners.categoriepartieprenante", "beneficiaries.beneficiaire", "strategy.typedocument", AUDIT} | SINGLETONS


# Jamais exportés seulement parce qu'un autre élément les désigne : un projet (ou son contenu) vient
# entier ou pas du tout. Ce qui dépend obligatoirement d'un projet non exporté est laissé de côté.
# Une plainte non plus : une action corrective commune à deux projets n'emporte pas la plainte de l'autre.
NON_CITES = {"projects.projet", "projects.activite", "projects.sousactivite", "plaintes.dossier"}


def _descendre_vers(depuis, vers) -> bool:
    """Peut-on reprendre les éléments de `vers` qui désignent un élément exporté de `depuis` ?"""
    if vers._meta.label_lower in PARTAGES or vers.__name__.startswith("Historical"):
        return False
    if depuis._meta.app_label == "strategy":
        # Un cadre emporte sa structure, ses programmes et ses indicateurs stratégiques, pas les projets
        # (ils ne viennent que si on les demande : avec_projets).
        return vers._meta.app_label == "strategy" or vers._meta.label_lower == "indicators.indicateurelement"
    # Un projet (et ce qui lui appartient) n'emporte ni d'autres projets ni la stratégie.
    return vers._meta.app_label != "strategy" and vers._meta.label_lower != "projects.projet"


def racines(projets=(), cadres=(), avec_projets=True) -> tuple[set, set]:
    """Cadres choisis avec leurs programmes (et maillons suivants), et projets choisis ou rattachés à ces cadres."""
    from apps.projects.models import Projet
    from apps.strategy.models import CadreStrategique

    cadres = set(CadreStrategique.objects.filter(pk__in=cadres).values_list("pk", flat=True))
    frontiere = set(cadres)
    while frontiere:
        frontiere = set(CadreStrategique.objects.filter(document_parent__in=frontiere).values_list("pk", flat=True)) - cadres
        cadres |= frontiere
    projets = set(Projet.objects.filter(pk__in=projets).values_list("pk", flat=True))
    if avec_projets and cadres:
        projets |= set(Projet.objects.filter(cadre_strategique__in=cadres).values_list("pk", flat=True))
    return cadres, projets


def retirer(choix) -> dict:
    """
    Supprime de l'espace ce qu'un extrait vient d'emporter (`choix`, comme pour exporter) : les projets
    avec tout ce qui leur appartient, puis les cadres, des programmes vers leur cadre. Tout ou rien.
    Ce qui n'est que cité (comptes, zones, bailleurs, bénéficiaires…) reste : d'autres projets s'en servent.
    """
    from django.db.models.deletion import ProtectedError

    from apps.projects.models import Projet
    from apps.projects.services import supprimer_projet_cascade
    from apps.strategy.models import CadreStrategique
    from apps.strategy.services import supprimer_cadre_strategique_cascade

    cadres, projets = racines(**choix)
    restants = Projet.objects.filter(cadre_strategique__in=cadres).exclude(pk__in=projets)
    if restants.exists():
        raise TransfertRefuse(f"{restants.count()} projet(s) rattaché(s) à ces cadres resteraient sans cadre : "
                              "exportez les cadres avec leurs projets pour pouvoir les retirer.")
    noms = list(Projet.objects.filter(pk__in=projets).values_list("code", flat=True)) \
        + list(CadreStrategique.objects.filter(pk__in=cadres).values_list("nom", flat=True))
    try:
        with transaction.atomic():
            for projet in Projet.objects.filter(pk__in=projets):
                supprimer_projet_cascade(projet)
            a_supprimer = {c.pk: c for c in CadreStrategique.objects.filter(pk__in=cadres)}
            while a_supprimer:
                parents = {c.document_parent_id for c in a_supprimer.values()}
                feuilles = [pk for pk in a_supprimer if pk not in parents]
                for pk in feuilles:
                    supprimer_cadre_strategique_cascade(a_supprimer.pop(pk))
    except ProtectedError as erreur:
        modeles = sorted({o._meta.verbose_name for o in erreur.protected_objects})
        raise TransfertRefuse("Rien n'a été retiré : des éléments d'ailleurs en dépendent encore "
                              f"({', '.join(map(str, modeles))}).") from erreur
    return {"projets": len(projets), "cadres": len(cadres), "noms": noms}


def selection(projets=(), cadres=(), avec_projets=True) -> dict:
    """
    Éléments à exporter pour ces projets et ces cadres (programmes rattachés compris) : {modèle: numéros}.
    - « possédés » : la racine et, de proche en proche, ce qui la désigne (activités, suivis, documents,
      plaintes, inscriptions des bénéficiaires…) ;
    - « cités » : ce que désigne un élément exporté (comptes, zones, bailleurs, bénéficiaires, élément
      de stratégie de rattachement…), sans ce qui leur appartient.
    """
    from apps.indicators.models import Indicateur
    from apps.projects.models import Projet
    from apps.strategy.models import CadreStrategique

    possedes = defaultdict(set)
    a_traiter = []

    def posseder(modele, numeros):
        nouveaux = set(numeros) - possedes[modele]
        if nouveaux:
            possedes[modele] |= nouveaux
            a_traiter.append((modele, nouveaux))

    cadres, projets = racines(projets, cadres, avec_projets)
    posseder(CadreStrategique, cadres)
    posseder(Projet, projets)

    while a_traiter:
        modele, numeros = a_traiter.pop()
        for relation in modele._meta.related_objects:
            if not hasattr(relation, "field"):
                continue
            enfant = relation.related_model
            if not _descendre_vers(modele, enfant):
                continue
            if relation.many_to_many:
                # Élément rattaché par une liste (ex. action corrective commune à plusieurs dossiers de plainte) ;
                # jamais depuis la stratégie : un cadre n'emporte pas ce qui le cite en complément.
                if modele._meta.app_label != "strategy":
                    posseder(enfant, enfant._base_manager.filter(**{f"{relation.field.name}__in": numeros}).values_list("pk", flat=True))
                continue
            posseder(enfant, enfant._base_manager.filter(**{f"{relation.field.attname}__in": numeros}).values_list("pk", flat=True))

    # Ce que désignent les éléments exportés (de proche en proche, sans leurs propres « enfants »).
    tout = defaultdict(set, {m: set(n) for m, n in possedes.items()})
    a_citer = list(tout.items())
    while a_citer:
        modele, numeros = a_citer.pop()
        liens = [f for f in modele._meta.concrete_fields if f.is_relation and f.related_model is not None]
        plusieurs = [f for f in modele._meta.many_to_many if f.related_model is not None]
        for champ in liens + plusieurs:
            visee = champ.related_model
            if visee._meta.app_label in ("contenttypes", "auth") or contexte.est_central(visee._meta.app_label, visee._meta.model_name):
                continue
            if visee._meta.label_lower in NON_CITES:
                continue
            if champ.many_to_many:
                cibles = set(modele._base_manager.filter(pk__in=numeros).values_list(champ.name, flat=True)) - {None}
            else:
                cibles = set(modele._base_manager.filter(pk__in=numeros).values_list(champ.attname, flat=True)) - {None}
            nouveaux = cibles - tout[visee]
            if nouveaux:
                tout[visee] |= nouveaux
                a_citer.append((visee, nouveaux))
    # Indicateurs stratégiques (sans projet) cités par un cadre exporté : leurs valeurs viennent avec eux.
    strategiques = Indicateur.objects.filter(pk__in=tout.get(Indicateur, ()), projet__isnull=True, activite__isnull=True)
    for ind in strategiques.values_list("pk", flat=True):
        for relation in Indicateur._meta.related_objects:
            if relation.many_to_many or not hasattr(relation, "field") or not _descendre_vers(Indicateur, relation.related_model):
                continue
            enfant = relation.related_model
            tout[enfant] |= set(enfant._base_manager.filter(**{relation.field.attname: ind}).values_list("pk", flat=True))
    _retirer_orphelins(tout)
    return {m: n for m, n in tout.items() if n and not m.__name__.startswith("Historical")}


def _retirer_orphelins(tout):
    """Retire les éléments cités qui dépendent d'un projet, d'une activité… non exportés (indicateur d'un autre projet…)."""
    change = True
    while change:
        change = False
        for modele in list(tout):
            numeros = tout[modele]
            if not numeros:
                continue
            for champ in modele._meta.concrete_fields:
                if not champ.is_relation or champ.related_model is None:
                    continue
                visee = champ.related_model
                label = visee._meta.label_lower
                if label not in NON_CITES and visee not in tout:
                    continue
                gardes = tout.get(visee, set())
                exclus = set(modele._base_manager.filter(pk__in=numeros).exclude(**{f"{champ.attname}__isnull": True})
                             .exclude(**{f"{champ.attname}__in": gardes}).values_list("pk", flat=True))
                if exclus:
                    tout[modele] = numeros - exclus
                    numeros = tout[modele]
                    change = True


def exporter(destination: str, choix=None) -> dict:
    """
    Écrit dans `destination` la sauvegarde de l'espace courant : complète, ou limitée à `choix`
    ({"projets": [...], "cadres": [...], "avec_projets": bool}) ; renvoie le manifeste.
    """
    from apps.plaintes.chiffrement import _fernet

    elements = selection(**choix) if choix else None
    with tempfile.TemporaryDirectory() as travail:
        donnees = os.path.join(travail, "donnees.json")
        nombre = _ecrire_donnees(donnees, elements)
        org = contexte.courante()
        manifeste = {
            "format": FORMAT,
            "date": datetime.now().isoformat(timespec="seconds"),
            "organisation": org.nom if org else "",
            "identifiant": org.sous_domaine if org else "",
            "migrations": _migrations(),
            "objets": nombre,
            "selection": bool(choix),
        }
        illisibles = 0
        racine = _racine(settings.MEDIA_ROOT)
        racine_privee = _racine(settings.PLAINTES_STOCKAGE_PRIVE)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.write(donnees, "donnees.json")
            fichiers = _fichiers(racine) if elements is None else _fichiers_selection(elements, racine)
            for chemin, relatif in fichiers:
                archive.write(chemin, f"fichiers/{relatif}")
            fernet = _fernet()
            pieces = _fichiers(racine_privee) if elements is None else _pieces_selection(elements, racine_privee)
            for chemin, relatif in pieces:
                try:
                    archive.writestr(f"prive/{relatif}", fernet.decrypt(chemin.read_bytes()))
                except Exception:
                    illisibles += 1
            manifeste["pieces_illisibles"] = illisibles
            archive.writestr("manifeste.json", json.dumps(manifeste, ensure_ascii=False, indent=2))
    return manifeste


def _fichiers_selection(elements, racine: Path):
    """Fichiers des éléments sélectionnés (documents, pièces justificatives…)."""
    for modele, numeros in elements.items():
        champs = [f for f in modele._meta.concrete_fields if f.get_internal_type() in ("FileField", "ImageField")]
        for champ in champs:
            for nom in modele._base_manager.filter(pk__in=numeros).values_list(champ.attname, flat=True):
                chemin = racine / str(nom or "")
                if nom and chemin.is_file():
                    yield chemin, Path(nom).as_posix()


def _pieces_selection(elements, racine: Path):
    """Pièces jointes des dossiers de plaintes sélectionnés."""
    from apps.plaintes.models import PieceJointe

    for dossier_uid, uid in PieceJointe.objects.filter(pk__in=elements.get(PieceJointe, ())).values_list("dossier__uid", "uid"):
        chemin = racine / str(dossier_uid) / f"{uid}.bin"
        if chemin.is_file():
            yield chemin, chemin.relative_to(racine).as_posix()


def lire_manifeste(archive: zipfile.ZipFile) -> dict:
    noms = set(archive.namelist())
    if "manifeste.json" not in noms or "donnees.json" not in noms:
        raise TransfertRefuse("Ce fichier n'est pas une sauvegarde complète de la plateforme.")
    try:
        manifeste = json.loads(archive.read("manifeste.json"))
    except ValueError:
        raise TransfertRefuse("Le manifeste de la sauvegarde est illisible.")
    if manifeste.get("format") != FORMAT:
        raise TransfertRefuse("Format de sauvegarde inconnu : mettez d'abord la plateforme à jour.")
    # La sauvegarde ne doit pas venir d'une version plus récente que celle-ci.
    ici = _migrations()
    manquantes = [f"{app}.{nom}" for app, noms in manifeste.get("migrations", {}).items()
                  for nom in noms if nom not in ici.get(app, ())]
    if manquantes:
        raise TransfertRefuse("Cette sauvegarde vient d'une version plus récente de la plateforme : "
                              "mettez d'abord cette plateforme à jour.")
    for nom in noms:
        if nom.startswith("/") or ".." in Path(nom).parts:
            raise TransfertRefuse("Ce fichier contient des chemins non autorisés.")
    return manifeste


def _vider_espace():
    """Efface toutes les données de l'espace, sauf le journal d'audit (ajout uniquement)."""
    # DELETE plutôt que TRUNCATE : possible même dans une transaction déjà commencée ; les liens entre
    # tables ne sont vérifiés qu'à la fin (contraintes différées), une fois la sauvegarde chargée.
    tables = [m._meta.db_table for m in _modeles() if f"{m._meta.app_label}.{m._meta.model_name}" != AUDIT]
    with connection.cursor() as curseur:
        curseur.execute("SET CONSTRAINTS ALL DEFERRED")
        for table in tables:
            curseur.execute(f"DELETE FROM {connection.ops.quote_name(table)}")


# Vider l'espace après sa sauvegarde complète : les données partent, l'espace reste prêt à resservir avec
# ses comptes, ses réglages et ses référentiels (zones, listes de choix, circuits de plaintes…).
GARDES_APPS = {"auth", "accounts", "geo", "formation"}
GARDES = {AUDIT, "core.identiteorganisation", "core.traductioncorrigee", "strategy.typedocument",
          "indicators.palieralerte", "beneficiaries.statutparticulier", "beneficiaries.typeactivitebeneficiaire",
          "beneficiaries.variablebeneficiaire", "partners.structureorganisation", "partners.categoriepartieprenante",
          "plaintes.typeretour", "plaintes.priorite", "plaintes.circuit", "plaintes.etapecircuit", "plaintes.categorie",
          "plaintes.modelemessage", "plaintes.jourferie", "plaintes.prestataire", "plaintes.habilitationsensible",
          "plaintes.compteurdossiers", "plaintes.tableauplaintes", "plaintes.vuedossiers"} | SINGLETONS


def _garde(modele, historiques) -> bool:
    if modele in historiques:
        return historiques[modele]
    if modele._meta.auto_created:
        # Table d'une liste (ex. projets d'un mécanisme) : vidée dès qu'un de ses deux côtés part.
        return all(_garde(f.related_model, historiques) for f in modele._meta.concrete_fields if f.is_relation)
    return modele._meta.app_label in GARDES_APPS or modele._meta.label_lower in GARDES


def vider_donnees() -> dict:
    """
    Efface les données de l'espace (stratégies, projets, bénéficiaires, documents, plaintes, partenaires,
    notifications, et leurs fichiers), en une transaction. Restent : les comptes, les réglages, le logo,
    les zones et les listes de référence, le journal d'audit.
    """
    from django.db.models import Q

    from apps.accounts.models import User
    from apps.indicators.models import PalierAlerte

    modeles = list(_modeles())
    # Historique des modifications : suit le sort de l'élément dont il garde les copies.
    historiques = {m.history.model: _garde(m, {}) for m in modeles if hasattr(m, "history")}
    a_vider = [m for m in modeles if not _garde(m, historiques)]
    objets = sum(m._base_manager.count() for m in a_vider if not m._meta.auto_created and m not in historiques)
    with transaction.atomic():
        User._base_manager.update(partenaire=None, partie_prenante=None)
        PalierAlerte._base_manager.filter(Q(projet__isnull=False) | Q(indicateur__isnull=False)
                                          | Q(activite__isnull=False)).delete()
        with connection.cursor() as curseur:
            curseur.execute("SET CONSTRAINTS ALL DEFERRED")
            for modele in a_vider:
                curseur.execute(f"DELETE FROM {connection.ops.quote_name(modele._meta.db_table)}")
        transaction.on_commit(lambda: _effacer_fichiers_orphelins([m for m in modeles if _garde(m, historiques)]))
    return {"objets": objets}


def _effacer_fichiers_orphelins(gardes):
    """Retire du stockage les fichiers que plus rien n'utilise (le logo reste), et toutes les pièces des plaintes."""
    from django.db import models

    utilises = set()
    for modele in gardes:
        for champ in modele._meta.concrete_fields:
            if isinstance(champ, models.FileField):
                utilises |= set(modele._base_manager.exclude(**{champ.attname: ""}).values_list(champ.attname, flat=True))
    for chemin, relatif in list(_fichiers(_racine(settings.MEDIA_ROOT))):
        if relatif not in utilises:
            chemin.unlink(missing_ok=True)
    for chemin, _relatif in list(_fichiers(_racine(settings.PLAINTES_STOCKAGE_PRIVE))):
        chemin.unlink(missing_ok=True)


def _remplacer_dossier(racine: Path, archive: zipfile.ZipFile, prefixe: str, transformer=None):
    """Remplace le contenu de `racine` par les fichiers `prefixe`… de l'archive (l'ancien est mis de côté)."""
    mis_de_cote = None
    if racine.exists() and any(racine.iterdir()):
        mis_de_cote = racine.with_name(f"{racine.name}.avant-reprise-{datetime.now():%Y%m%d-%H%M%S}")
        if contexte.courante() is None:
            # Installation unique : les dossiers des organisations restent en place.
            mis_de_cote.mkdir(parents=True)
            for element in racine.iterdir():
                if element.name != "organisations":
                    shutil.move(str(element), mis_de_cote / element.name)
        else:
            shutil.move(str(racine), mis_de_cote)
    racine.mkdir(parents=True, exist_ok=True)
    for nom in archive.namelist():
        if not nom.startswith(prefixe) or nom.endswith("/"):
            continue
        cible = racine / nom[len(prefixe):]
        cible.parent.mkdir(parents=True, exist_ok=True)
        contenu = archive.read(nom)
        cible.write_bytes(transformer(contenu) if transformer else contenu)
        if transformer:
            os.chmod(cible, 0o600)
    return mis_de_cote


# --- Fusion (mode « ajouter ») ------------------------------------------------------------------

def _verifications(modele, label):
    """Groupes de champs qui désignent un élément existant (champs uniques, unicités composées…)."""
    # (champs, condition) : une unicité partielle (ex. une seule habilitation en cours par personne) ne
    # vaut que pour les éléments qui remplissent sa condition.
    groupes = [((f.name,), None) for f in modele._meta.concrete_fields if f.unique and not f.primary_key]
    groupes += [(tuple(u), None) for u in modele._meta.unique_together]
    groupes += [(tuple(c.fields), getattr(c, "condition", None)) for c in modele._meta.constraints if getattr(c, "fields", None)]
    if label in CORRESPONDANCES:
        groupes.append((CORRESPONDANCES[label], None))
    if label in RENOMMER:
        groupes = [g for g in groupes if g[0] != (RENOMMER[label],)]
    return groupes


class _Index:
    """
    Éléments déjà présents, par groupe de champs qui les désigne : lus en une requête par groupe (au premier
    besoin), puis complétés au fil des créations — au lieu d'une requête par élément de la sauvegarde.
    """

    def __init__(self):
        self.groupes = {}  # (modèle, groupe, condition) -> {valeurs: numéro}

    @staticmethod
    def _noms(modele, groupe):
        return tuple(modele._meta.get_field(nom).attname for nom in groupe)

    def _table(self, modele, groupe, condition):
        cle = (modele, groupe, condition)
        if cle not in self.groupes:
            existants = modele._base_manager.all()
            if condition is not None:
                existants = existants.filter(condition)
            table = {}
            for *valeurs, numero in existants.order_by("-pk").values_list(*self._noms(modele, groupe), "pk"):
                table[tuple(valeurs)] = numero  # du plus récent au plus ancien : le plus ancien reste
            self.groupes[cle] = table
        return self.groupes[cle]

    def chercher(self, objet, label, en_attente=()):
        """Numéro de l'élément déjà présent qui correspond (les champs dont le lien est en attente ne comptent pas)."""
        modele = type(objet)
        for groupe, condition in _verifications(modele, label):
            if any(nom in en_attente for nom in groupe):
                continue
            valeurs = tuple(getattr(objet, attname) for attname in self._noms(modele, groupe))
            if len(groupe) == 1 and valeurs[0] in (None, ""):
                continue
            numero = self._table(modele, groupe, condition).get(valeurs)
            if numero is not None:
                return numero
        if label == "accounts.user" and objet.email:
            return modele._base_manager.filter(email__iexact=objet.email).values_list("pk", flat=True).first()
        return None

    def ajouter(self, objet, label):
        """Élément créé : désormais trouvé par les suivants (une unicité partielle seulement s'il en remplit la condition)."""
        modele = type(objet)
        for groupe, condition in _verifications(modele, label):
            cle = (modele, groupe, condition)
            if cle not in self.groupes:
                continue
            if condition is not None and not modele._base_manager.filter(condition, pk=objet.pk).exists():
                continue
            self.groupes[cle].setdefault(tuple(getattr(objet, a) for a in self._noms(modele, groupe)), objet.pk)


def _code_libre(objet, champ_nom):
    champ = type(objet)._meta.get_field(champ_nom)
    base = getattr(objet, champ_nom)
    n = 1
    while True:
        suffixe = f"-R{n}"
        candidat = f"{base[: champ.max_length - len(suffixe)]}{suffixe}" if champ.max_length else f"{base}{suffixe}"
        if not type(objet)._base_manager.filter(**{champ_nom: candidat}).exists():
            setattr(objet, champ_nom, candidat)
            return
        n += 1


def _nom_libre(racine: Path, nom: str) -> str:
    chemin = Path(nom)
    n = 1
    while True:
        candidat = chemin.with_name(f"{chemin.stem}-reprise{n}{chemin.suffix}").as_posix()
        if not (racine / candidat).exists():
            return candidat
        n += 1


def _fichiers_de(objet, archive, racine: Path, noms_archive: set):
    """Fichiers de l'élément : copiés s'ils manquent ; renommés s'ils diffèrent d'un fichier existant."""
    for champ in objet._meta.concrete_fields:
        if champ.get_internal_type() not in ("FileField", "ImageField"):
            continue
        nom = str(getattr(objet, champ.attname) or "")
        if not nom or f"fichiers/{nom}" not in noms_archive:
            continue
        contenu = archive.read(f"fichiers/{nom}")
        cible = racine / nom
        if cible.exists() and cible.read_bytes() != contenu:
            nom = _nom_libre(racine, nom)
            setattr(objet, champ.attname, nom)
            cible = racine / nom
        if not cible.exists():
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(contenu)


def _ordre_des_modeles(labels) -> list:
    """Modèles dans l'ordre de leurs liens (un élément après ceux qu'il désigne) ; un cycle est rompu au plus simple."""
    dependances, obligatoires = {}, {}
    for label in labels:
        try:
            modele = apps.get_model(label)
        except LookupError:
            continue
        liens = [f for f in modele._meta.concrete_fields if f.is_relation and f.related_model is not None]
        dependances[label] = {f.related_model._meta.label_lower for f in liens} & labels - {label}
        obligatoires[label] = {f.related_model._meta.label_lower for f in liens if not f.null}
    ordre = []
    while dependances:
        prets = sorted(l for l, d in dependances.items() if not d)
        if not prets:
            # Dépendance circulaire : passe d'abord un modèle dont les liens en attente peuvent rester vides
            # (ex. la version courante d'un document), puis celui qui attend le moins d'autres modèles.
            prets = [min(dependances, key=lambda l: (len(dependances[l] & obligatoires[l]), len(dependances[l]), l))]
        for label in prets:
            ordre.append(label)
            del dependances[label]
        for d in dependances.values():
            d.difference_update(prets)
    return ordre


def _fusionner(chemin_donnees, archive, comptes_desactives=False) -> Counter:
    """Ajoute les éléments de la sauvegarde à ceux de l'espace ; renvoie les nombres créés et réutilisés."""
    from django.core import serializers
    from django.db import models

    racine = _racine(settings.MEDIA_ROOT)
    noms_archive = set(archive.namelist())
    correspondance = defaultdict(dict)  # modèle -> {ancien numéro: nouveau}
    with open(chemin_donnees, encoding="utf-8") as f:
        par_modele = defaultdict(list)
        for o in json.load(f):
            par_modele[o["model"]].append(o)
    presents = set(par_modele)
    a_corriger = []  # (modèle, champ, modèle visé, ancien numéro visé, numéro de l'élément créé)
    plusieurs = []  # liens multiples, posés à la fin
    bilan = Counter()
    index = _Index()
    with connection.cursor() as curseur:
        curseur.execute("SET CONSTRAINTS ALL DEFERRED")
    for label_modele in _ordre_des_modeles(presents):
        for desserialise in serializers.deserialize("python", par_modele.pop(label_modele), ignorenonexistent=True):
            objet = desserialise.object
            modele = type(objet)
            label = modele._meta.label_lower
            if modele.__name__.startswith("Historical"):
                continue
            ancien = objet.pk
            if label in SINGLETONS and modele._base_manager.exists():
                correspondance[label][ancien] = modele._base_manager.order_by("pk").first().pk
                bilan["reutilises"] += 1
                continue
            en_attente = []  # liens vers un élément pas encore repris (plus loin dans le fichier)
            for champ in modele._meta.concrete_fields:
                if not champ.is_relation or champ.related_model is None:
                    continue
                visee = champ.related_model._meta.label_lower
                valeur = getattr(objet, champ.attname)
                if valeur is None or champ.related_model._meta.app_label in ("contenttypes", "auth"):
                    continue
                if visee not in presents:
                    # Élément désigné absent de la sauvegarde (extrait) : le lien est vidé, ou l'élément ignoré.
                    if champ.null:
                        setattr(objet, champ.attname, None)
                        continue
                    objet = None
                    break
                if valeur in correspondance[visee]:
                    setattr(objet, champ.attname, correspondance[visee][valeur])
                else:
                    # Lien vers un élément repris plus loin (même modèle ou dépendance circulaire) : vide pour
                    # l'instant si possible, sinon gardé tel quel (contraintes différées), puis corrigé à la fin.
                    en_attente.append((champ, visee, valeur))
                    if champ.null:
                        setattr(objet, champ.attname, None)
            if objet is None:
                bilan["ignores"] += 1
                continue
            if label == AUDIT:
                objet.utilisateur_id = correspondance["accounts.user"].get(objet.utilisateur_id)
            existant = None if label == AUDIT else index.chercher(objet, label, {c.name for c, _, _ in en_attente})
            if existant is not None:
                correspondance[label][ancien] = existant
                bilan["reutilises"] += 1
                continue
            if label in RENOMMER and modele._base_manager.filter(**{RENOMMER[label]: getattr(objet, RENOMMER[label])}).exists():
                _code_libre(objet, RENOMMER[label])
                bilan["renommes"] += 1
            _fichiers_de(objet, archive, racine, noms_archive)
            if comptes_desactives and label == "accounts.user":
                objet.is_active = False  # compte cité par une sélection : l'administrateur l'active s'il le souhaite
                bilan["comptes_desactives"] += 1
            objet.pk = None
            models.Model.save_base(objet, raw=True, force_insert=True)
            if label != AUDIT:
                index.ajouter(objet, label)
            correspondance[label][ancien] = objet.pk
            bilan["crees"] += 1
            a_corriger += [(modele, champ, visee, valeur, objet.pk) for champ, visee, valeur in en_attente]
            if desserialise.m2m_data:
                plusieurs.append((objet, desserialise.m2m_data))

    for modele, champ, visee, ancien, numero in a_corriger:
        nouveau = correspondance[visee].get(ancien)
        if nouveau is not None:
            modele._base_manager.filter(pk=numero).update(**{champ.attname: nouveau})
        elif not champ.null:
            modele._base_manager.filter(pk=numero).delete()  # lien vers un élément absent de la sauvegarde
    for objet, liens in plusieurs:
        for nom, anciens in liens.items():
            champ = type(objet)._meta.get_field(nom)
            visee = champ.related_model._meta.label_lower
            # Types de contenu et permissions : numéros déjà ceux de cette base (clés naturelles).
            garder = champ.related_model._meta.app_label in ("contenttypes", "auth")
            ids = [correspondance[visee].get(a, a if garder else None) for a in anciens]
            getattr(objet, nom).add(*[i for i in ids if i is not None])
    # Demandes de modification : leur cible est un numéro d'élément de la planification.
    from apps.projects.models import DemandeModification

    nouvelles = correspondance["projects.demandemodification"].values()
    for demande in DemandeModification.objects.filter(pk__in=list(nouvelles), cible_id__isnull=False):
        visee = "projects.sousactivite" if demande.cible == DemandeModification.Cible.SOUS_ACTIVITE else "projects.activite"
        DemandeModification.objects.filter(pk=demande.pk).update(cible_id=correspondance[visee].get(demande.cible_id))
    # Fichiers sans élément (ex. couches de carte importées) : copiés s'ils manquent.
    for nom in noms_archive:
        if nom.startswith("fichiers/") and not nom.endswith("/") and not (racine / nom[len("fichiers/"):]).exists():
            cible = racine / nom[len("fichiers/"):]
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(archive.read(nom))
    return bilan


def _ajouter_pieces(archive):
    """Pièces jointes des plaintes : rechiffrées avec la clé de cet espace, sans écraser l'existant."""
    from apps.plaintes.chiffrement import _fernet

    racine = _racine(settings.PLAINTES_STOCKAGE_PRIVE)
    fernet = _fernet()
    for nom in archive.namelist():
        if not nom.startswith("prive/") or nom.endswith("/"):
            continue
        cible = racine / nom[len("prive/"):]
        if cible.exists():
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(fernet.encrypt(archive.read(nom)))
        os.chmod(cible, 0o600)


def importer(chemin_zip: str, administrateur, mode: str = "remplacer") -> dict:
    """Reprend la sauvegarde dans l'espace courant (« remplacer » ou « ajouter ») ; renvoie un compte rendu."""
    from apps.accounts.models import User
    from apps.organisations import comptes, quota
    from apps.plaintes.chiffrement import _fernet

    if mode not in ("remplacer", "ajouter"):
        raise TransfertRefuse("Mode de reprise inconnu.")
    with zipfile.ZipFile(chemin_zip) as archive:
        manifeste = lire_manifeste(archive)
        if manifeste.get("selection") and mode != "ajouter":
            raise TransfertRefuse("Ce fichier ne contient qu'une partie d'un espace : il ne peut être repris qu'en mode « Ajouter ».")
        if mode == "ajouter":
            with tempfile.TemporaryDirectory() as travail:
                donnees = os.path.join(travail, "donnees.json")
                with open(donnees, "wb") as f:
                    f.write(archive.read("donnees.json"))
                with transaction.atomic():
                    bilan = _fusionner(donnees, archive, comptes_desactives=bool(manifeste.get("selection")))
            _ajouter_pieces(archive)
            org = contexte.courante()
            if contexte.actif() and org is not None:
                for utilisateur in User.objects.all():
                    comptes.synchroniser(utilisateur, org)
            quota.oublier()
            return {
                "mode": mode, "objets": manifeste.get("objets", 0), "origine": manifeste.get("organisation", ""),
                "date_sauvegarde": manifeste.get("date", ""), "crees": bilan["crees"], "reutilises": bilan["reutilises"],
                "renommes": bilan["renommes"], "comptes_desactives": bilan["comptes_desactives"],
                "selection": bool(manifeste.get("selection")), "compte_garde": True, "anciens_fichiers": [],
            }
        with tempfile.TemporaryDirectory() as travail:
            donnees = os.path.join(travail, "donnees.json")
            objets = json.loads(archive.read("donnees.json"))
            # Journal d'audit : les événements d'origine s'ajoutent à la suite (nouveaux numéros).
            for objet in objets:
                if objet.get("model") == AUDIT:
                    objet["pk"] = None
            with open(donnees, "w", encoding="utf-8") as f:
                json.dump(objets, f)
            nombre = len(objets)
            del objets

            garde = {
                "username": administrateur.username, "email": administrateur.email, "password": administrateur.password,
                "first_name": administrateur.first_name, "last_name": administrateur.last_name,
                "role": administrateur.role,
            }
            with transaction.atomic():
                _vider_espace()
                call_command("loaddata", donnees, verbosity=0)
                garde_compte = not User.objects.filter(email__iexact=garde["email"]).exists() if garde["email"] else False
                if garde_compte:
                    if User.objects.filter(username=garde["username"]).exists():
                        garde["username"] = f"{garde['username']}-reprise"
                    User.objects.create(**garde)

        fichiers = _remplacer_dossier(_racine(settings.MEDIA_ROOT), archive, "fichiers/")
        fernet = _fernet()
        prive = _remplacer_dossier(_racine(settings.PLAINTES_STOCKAGE_PRIVE), archive, "prive/", fernet.encrypt)

    org = contexte.courante()
    if contexte.actif() and org is not None:
        # Index des comptes (connexion par courriel) : celui des comptes repris.
        from apps.organisations.models import CompteOrganisation

        CompteOrganisation.objects.using("central").filter(organisation=org).delete()
        for utilisateur in User.objects.all():
            comptes.synchroniser(utilisateur, org)
    quota.oublier()
    return {
        "mode": mode,
        "objets": nombre,
        "origine": manifeste.get("organisation", ""),
        "date_sauvegarde": manifeste.get("date", ""),
        "compte_garde": garde_compte,
        "anciens_fichiers": [str(p) for p in (fichiers, prive) if p],
    }
