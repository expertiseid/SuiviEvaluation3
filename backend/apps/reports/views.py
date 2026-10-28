import datetime

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import HasGlobalVisibilityOrAssigned
from apps.core.vocabulaire import v
from apps.projects.models import Projet
from apps.projects.queryset_filters import visible_projets_ids

from .financier import SECTIONS, donnees_financieres, excel_rapport_financier, html_rapport_financier


def _projet_visible(request, projet_id):
    return Projet.objects.filter(id__in=visible_projets_ids(request.user), id=projet_id).first()


def _date(texte):
    try:
        return datetime.date.fromisoformat(texte) if texte else None
    except ValueError:
        return None


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def rapport_financier(request, projet_id):
    """
    Rapport financier seul : ?fichier=pdf|docx|xlsx&sections=sources,rallonges,…&debut=AAAA-MM-JJ&fin=…
    (toutes les sections et toute la durée par défaut).
    """
    projet = _projet_visible(request, projet_id)
    if projet is None:
        return Response({"detail": v("Projet introuvable ou non accessible.")}, status=404)
    sections = [s for s in (request.query_params.get("sections") or ",".join(SECTIONS)).split(",") if s in SECTIONS]
    if not sections:
        return Response({"detail": "Choisissez au moins une section."}, status=400)
    donnees = donnees_financieres(projet, _date(request.query_params.get("debut")), _date(request.query_params.get("fin")))
    nom = f"rapport_financier_{projet.code}"
    format_ = request.query_params.get("fichier", "pdf")  # « format » est réservé par DRF
    if format_ == "docx":
        from .word import reponse_docx

        return reponse_docx(html_rapport_financier(donnees, sections), nom)
    if format_ == "xlsx":
        response = HttpResponse(
            excel_rapport_financier(donnees, sections),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={nom}.xlsx"
        return response
    from weasyprint import HTML

    response = HttpResponse(HTML(string=html_rapport_financier(donnees, sections)).write_pdf(), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={nom}.pdf"
    return response


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def cadre_logique(request, projet_id):
    """Cadre logique du projet (JSON pour l'écran), ou ?fichier=pdf|docx pour l'exporter."""
    from .cadre_logique import construire_cadre_logique, html_cadre_logique

    projet = _projet_visible(request, projet_id)
    if projet is None:
        return Response({"detail": v("Projet introuvable ou non accessible.")}, status=404)
    data = construire_cadre_logique(projet)
    fichier = request.query_params.get("fichier")
    if fichier == "docx":
        from .word import reponse_docx

        return reponse_docx(html_cadre_logique(data), f"cadre_logique_{projet.code}")
    if fichier == "pdf":
        from weasyprint import HTML

        response = HttpResponse(HTML(string=html_cadre_logique(data)).write_pdf(), content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename=cadre_logique_{projet.code}.pdf"
        return response
    return Response(data)


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def registre_risques(request, projet_id):
    """Registre des risques du projet : ?fichier=pdf (défaut) ou docx."""
    from .risques import html_registre_risques

    projet = _projet_visible(request, projet_id)
    if projet is None:
        return Response({"detail": v("Projet introuvable ou non accessible.")}, status=404)
    html = html_registre_risques(projet)
    if request.query_params.get("fichier") == "docx":
        from .word import reponse_docx

        return reponse_docx(html, f"risques_{projet.code}")
    from weasyprint import HTML

    response = HttpResponse(HTML(string=html).write_pdf(), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=risques_{projet.code}.pdf"
    return response


@api_view(["GET"])
@permission_classes([HasGlobalVisibilityOrAssigned])
def rapport_suivi_strategique(request, cadre_id):
    """Rapport de suivi d'un document stratégique : ?fichier=pdf (défaut) ou docx."""
    from apps.strategy.models import CadreStrategique

    from .suivi_strategique import html_suivi_strategique

    cadre = CadreStrategique.objects.filter(id=cadre_id).first()
    if cadre is None:
        return Response({"detail": "Document stratégique introuvable."}, status=404)
    html = html_suivi_strategique(cadre, list(visible_projets_ids(request.user)))
    nom = f"suivi_strategique_{cadre.id}"
    if request.query_params.get("fichier") == "docx":
        from .word import reponse_docx

        return reponse_docx(html, nom)
    from weasyprint import HTML

    response = HttpResponse(HTML(string=html).write_pdf(), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={nom}.pdf"
    return response
