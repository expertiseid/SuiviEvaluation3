from django.http import HttpResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.langues import dans_la_langue_demandee
from apps.core.permissions import HasGlobalVisibilityOrAssigned

from .services import generer_modele_import_complet, importer_planification_complete


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@dans_la_langue_demandee
def modele_import_complet(request):
    contenu = generer_modele_import_complet()
    response = HttpResponse(
        contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=modele_planification_complete.xlsx"
    return response


@api_view(["POST"])
@permission_classes([HasGlobalVisibilityOrAssigned])
@parser_classes([MultiPartParser, FormParser])
def importer_complet(request):
    fichier = request.data.get("fichier")
    if not fichier:
        raise ValidationError({"fichier": "Un fichier Excel (.xlsx) est requis."})
    try:
        resultat = importer_planification_complete(fichier, request.user)
    except Exception as exc:  # fichier corrompu, mauvais format, etc.
        raise ValidationError({"fichier": f"Impossible de lire ce fichier : {exc}"})
    return Response(resultat)
