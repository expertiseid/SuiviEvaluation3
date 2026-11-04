"""
Corbeille des documents : supprimer un document ou un dossier le met à la corbeille, d'où on peut le
restaurer ou le supprimer définitivement (« vider »).

- Un dossier part avec tout son contenu (sous-dossiers, documents) : seuls le dossier et les éléments
  supprimés un par un apparaissent dans la corbeille ; le contenu revient ou disparaît avec son dossier.
- Restaurer : à sa place, ou à la racine si son dossier d'origine est lui-même à la corbeille.
- Vider : suppression définitive, fichiers compris. Les éléments supprimés à part qui se trouvaient dans
  le dossier vidé restent dans la corbeille (ramenés à la racine).
- Vidage automatique : ce qui est à la corbeille depuis plus de 30 jours est supprimé définitivement
  (purger(), lancé chaque heure par la tâche planifiée check_deadlines, dans chaque espace).
- Mêmes règles de visibilité que l'explorateur : on ne voit que la corbeille de ses projets et de la
  bibliothèque libre.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Document, DocumentVersion, Dossier

DUREE_CONSERVATION_JOURS = 30


def _visibles(user, modele, tous=False):
    from apps.projects.queryset_filters import visible_projets_ids

    ids = visible_projets_ids(user)
    gestionnaire = modele.tous if tous else modele.objects
    if modele is Dossier:
        return gestionnaire.filter(Q(projet__isnull=True) | Q(projet__id__in=ids))
    return gestionnaire.filter(
        Q(projet__isnull=True, activite__isnull=True, sous_activite__isnull=True)
        | Q(projet__id__in=ids)
        | Q(activite__projet__id__in=ids)
        | Q(sous_activite__activite__projet__id__in=ids)
    )


def elements(user):
    """Contenu de la corbeille (ce qui a été supprimé directement), du plus récent au plus ancien."""
    racines = dict(supprime_le__isnull=False, supprime_avec__isnull=True)
    return (_visibles(user, Dossier, tous=True).filter(**racines).select_related("supprime_par", "projet").order_by("-supprime_le"),
            _visibles(user, Document, tous=True).filter(**racines).select_related(
                "supprime_par", "projet", "activite__projet", "sous_activite__activite__projet").order_by("-supprime_le"))


def _sous_arbre(dossier, gestionnaire):
    """Identifiants des sous-dossiers de `dossier`, à toute profondeur (lui exclu)."""
    ids, niveau = [], [dossier.pk]
    while niveau:
        niveau = list(gestionnaire.filter(parent_id__in=niveau).values_list("pk", flat=True))
        ids += niveau
    return ids


@transaction.atomic
def jeter(user, dossiers=(), documents=()):
    """Met les dossiers (avec leur contenu) et les documents donnés à la corbeille. Renvoie le nombre jeté."""
    maintenant, nombre = timezone.now(), 0
    for dossier in dossiers:
        if dossier.supprime_le:  # déjà parti avec un dossier sélectionné lui aussi
            continue
        sous = _sous_arbre(dossier, Dossier.objects)
        marque = dict(supprime_le=maintenant, supprime_par=user)
        Dossier.objects.filter(pk__in=sous).update(supprime_avec=dossier, **marque)
        Document.objects.filter(dossier_id__in=[dossier.pk, *sous]).update(supprime_avec=dossier, **marque)
        Dossier.objects.filter(pk=dossier.pk).update(supprime_avec=None, **marque)
        nombre += 1
    nombre += Document.objects.filter(pk__in=[d.pk for d in documents]).update(
        supprime_le=maintenant, supprime_par=user, supprime_avec=None)
    return nombre


@transaction.atomic
def restaurer(dossiers=(), documents=()):
    nombre = 0
    for dossier in dossiers:
        Dossier.tous.filter(supprime_avec=dossier).update(supprime_le=None, supprime_par=None, supprime_avec=None)
        Document.tous.filter(supprime_avec=dossier).update(supprime_le=None, supprime_par=None, supprime_avec=None)
        parent_parti = dossier.parent_id and Dossier.tous.filter(pk=dossier.parent_id, supprime_le__isnull=False).exists()
        Dossier.tous.filter(pk=dossier.pk).update(supprime_le=None, supprime_par=None,
                                                  **({"parent": None} if parent_parti else {}))
        nombre += 1
    for document in documents:
        dossier_parti = document.dossier_id and Dossier.tous.filter(pk=document.dossier_id, supprime_le__isnull=False).exists()
        Document.tous.filter(pk=document.pk).update(supprime_le=None, supprime_par=None,
                                                    **({"dossier": None} if dossier_parti else {}))
        nombre += 1
    return nombre


def vider(dossiers=(), documents=()):
    """Suppression définitive (base et fichiers). Renvoie le nombre d'éléments supprimés."""
    with transaction.atomic():
        ids_documents = [d.pk for d in documents]
        for dossier in dossiers:
            # Le dossier et ce qui est parti avec lui (pas les sous-dossiers supprimés à part, qui restent).
            arbre = [dossier.pk, *_sous_arbre(dossier, Dossier.tous.filter(supprime_avec=dossier))]
            # Supprimés à part avant leur dossier : ils restent dans la corbeille, à la racine.
            Dossier.tous.filter(parent_id__in=arbre, supprime_avec__isnull=True, supprime_le__isnull=False).exclude(
                pk=dossier.pk).update(parent=None)
            Document.tous.filter(dossier_id__in=arbre, supprime_avec__isnull=True, supprime_le__isnull=False).update(dossier=None)
            ids_documents += list(Document.tous.filter(dossier_id__in=arbre).values_list("pk", flat=True))
        fichiers = [(v.fichier.storage, v.fichier.name) for v in DocumentVersion.objects.filter(document_id__in=ids_documents) if v.fichier]
        Document.tous.filter(pk__in=ids_documents).delete()
        Dossier.tous.filter(pk__in=[d.pk for d in dossiers]).delete()
    for stockage, nom in fichiers:  # après la validation : un échec n'efface aucun fichier encore utilisé
        try:
            stockage.delete(nom)
        except OSError:
            pass
    return len(dossiers) + len(documents)


def purger(jours=DUREE_CONSERVATION_JOURS) -> int:
    """Supprime définitivement ce qui est à la corbeille depuis plus de `jours` jours."""
    from datetime import timedelta

    limite = dict(supprime_le__lt=timezone.now() - timedelta(days=jours), supprime_avec__isnull=True)
    return vider(list(Dossier.tous.filter(**limite)), list(Document.tous.filter(**limite)))


PLAFOND_ARCHIVE = 500 * 1024 * 1024  # octets avant compression


def archive(dossiers=(), documents=()):
    """Fichier zip temporaire : dernière version de chaque document, dossiers avec leur arborescence."""
    import os
    import tempfile
    import zipfile

    entrees = [("", doc) for doc in documents]

    def parcourir(dossier, chemin):
        chemin = f"{chemin}{dossier.nom.replace('/', '-')}/"
        entrees.append((chemin, None))
        for doc in Document.objects.filter(dossier=dossier):
            entrees.append((chemin, doc))
        for sous in Dossier.objects.filter(parent=dossier):
            parcourir(sous, chemin)

    for dossier in dossiers:
        parcourir(dossier, "")
    taille, pris = 0, set()
    sortie = tempfile.TemporaryFile()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as zip_:
        for chemin, doc in entrees:
            if doc is None:
                zip_.writestr(chemin, "")
                continue
            version = doc.derniere_version
            if version is None or not version.fichier or not version.fichier.storage.exists(version.fichier.name):
                continue
            taille += version.fichier.size
            if taille > PLAFOND_ARCHIVE:
                sortie.close()
                raise ValueError("trop_volumineux")
            extension = os.path.splitext(version.fichier.name)[1]
            base = doc.nom.replace("/", "-")
            if extension and not base.lower().endswith(extension.lower()):
                base += extension
            nom, numero = f"{chemin}{base}", 2
            while nom in pris:  # deux documents du même nom dans le même dossier
                racine, ext = os.path.splitext(base)
                nom, numero = f"{chemin}{racine} ({numero}){ext}", numero + 1
            pris.add(nom)
            with version.fichier.open("rb") as source:
                zip_.writestr(nom, source.read())
    sortie.seek(0)
    return sortie
