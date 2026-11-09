"""Réponses d'erreur de l'API (REST_FRAMEWORK["EXCEPTION_HANDLER"]).

Supprimer une fiche encore utilisée ailleurs (une région qui contient des provinces, un bailleur
rattaché à des financements…) lève ProtectedError : sans ce traitement, le serveur répondait par une
erreur 500. L'utilisateur reçoit à la place un message clair (409, conflit).
"""

from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.vocabulaire import v


def gestionnaire_erreurs(exc, context):
    if isinstance(exc, (ProtectedError, RestrictedError)):
        return Response(
            {"detail": v("Suppression impossible : cet élément est encore utilisé ailleurs dans la plateforme. Retirez d'abord ce qui s'y rattache.")},
            status=status.HTTP_409_CONFLICT,
        )
    return exception_handler(exc, context)
