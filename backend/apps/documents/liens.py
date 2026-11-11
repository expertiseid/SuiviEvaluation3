"""
Liens signés vers les fichiers des documents (GED).

Les fichiers ne sont jamais servis directement par une adresse publique (/media/) : l'API remet, à qui
peut voir le document, une adresse signée valable une heure (assez pour consulter la page et ses
miniatures). Au téléchargement, l'accès de la personne est vérifié de nouveau.
"""
import mimetypes
import os
from urllib.parse import quote

from django.core import signing
from django.db.models import Q
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from apps.organisations.contexte import sel

from .models import Document, DocumentVersion

SEL = "documents.fichier"
DUREE_S = 3600
# Ouverts dans le navigateur (aperçu) ; les autres sont proposés au téléchargement.
APERCU = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4", "video/webm", "text/plain"}


def documents_visibles(user):
    from apps.projects.queryset_filters import visible_projets_ids

    from apps.core.masquage import activites_masquees

    ids = visible_projets_ids(user)
    masquees = activites_masquees(user)  # documents rattachés à un élément masqué à cet utilisateur : exclus
    return Document.objects.filter(
        Q(projet__isnull=True, activite__isnull=True, sous_activite__isnull=True)
        | Q(projet__id__in=ids)
        | Q(activite__projet__id__in=ids)
        | Q(sous_activite__activite__projet__id__in=ids)
    ).exclude(Q(activite_id__in=masquees) | Q(sous_activite__activite_id__in=masquees))


def adresse(request, version):
    from apps.organisations.contexte import parametre_org

    jeton = signing.dumps({"v": version.pk, "u": request.user.pk}, salt=sel(SEL))
    org = parametre_org()  # lien ouvert hors de l'interface (nouvel onglet) : l'organisation est dans l'adresse
    return request.build_absolute_uri(f"/api/v1/fichiers-documents/{jeton}/" + (f"?{org}" if org else ""))


@require_GET
def telecharger(request, jeton):
    from apps.accounts.models import User

    try:
        contenu = signing.loads(jeton, salt=sel(SEL), max_age=DUREE_S)
    except signing.BadSignature:
        raise Http404
    utilisateur = User.objects.filter(pk=contenu.get("u"), is_active=True).first()
    version = DocumentVersion.objects.select_related("document").filter(pk=contenu.get("v")).first()
    if utilisateur is None or version is None or not documents_visibles(utilisateur).filter(pk=version.document_id).exists():
        raise Http404
    if not version.fichier.storage.exists(version.fichier.name):
        raise Http404
    type_mime = mimetypes.guess_type(version.fichier.name)[0] or "application/octet-stream"
    extension = os.path.splitext(version.fichier.name)[1]
    nom = version.document.nom if version.document.nom.lower().endswith(extension.lower()) else f"{version.document.nom}{extension}"
    reponse = FileResponse(version.fichier.open("rb"), content_type=type_mime)
    disposition = "inline" if type_mime in APERCU else "attachment"
    reponse["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(nom)}"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Cache-Control"] = "private, max-age=3600"
    return reponse
