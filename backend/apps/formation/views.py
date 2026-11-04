"""
Cours en ligne : réservé aux organisations abonnées (pas à la démonstration). Chaque utilisateur suit
sa progression : leçons terminées, quiz (corrigés ici, jamais dans le navigateur), attestation PDF une
fois tous les quiz réussis.
"""
import secrets
from html import escape

from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.vocabulaire import v

from .contenu import CHAPITRES, MODULES, PAR_CODE, SEUIL_REUSSITE
from .models import Attestation, LeconTerminee, TentativeQuiz


def acces_ouvert() -> bool:
    """Ouvert aux organisations abonnées : fermé dans la démonstration (espace ou installation)."""
    from apps.accounts.demo import actif

    return not actif()


def _verifier_acces():
    if not acces_ouvert():
        raise PermissionDenied({"detail": v("La formation est réservée aux organisations abonnées."), "code": "formation_reservee"})


def _module(code):
    module = PAR_CODE.get(code)
    if module is None:
        raise NotFound(v("Module introuvable."))
    return module


def _lecon(module, code):
    for lecon in module["lecons"]:
        if lecon["code"] == code:
            return lecon
    raise NotFound(v("Leçon introuvable."))


def _cle(module, lecon):
    return f"{module['code']}/{lecon['code']}"


def _etat(utilisateur):
    terminees = set(LeconTerminee.objects.filter(utilisateur=utilisateur).values_list("lecon", flat=True))
    reussis = set(TentativeQuiz.objects.filter(utilisateur=utilisateur, reussi=True).values_list("module", flat=True))
    meilleurs = {}
    for t in TentativeQuiz.objects.filter(utilisateur=utilisateur):
        meilleurs[t.module] = max(meilleurs.get(t.module, 0), t.score)
    return terminees, reussis, meilleurs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sommaire(request):
    """Les modules et la progression de l'utilisateur ; acces=False dans la démonstration."""
    if not acces_ouvert():
        return Response({"acces": False, "modules": [{"code": m["code"], "titre": m["titre"], "description": m["description"],
                                                      "icone": m["icone"], "lecons": len(m["lecons"])} for m in MODULES]})
    terminees, reussis, meilleurs = _etat(request.user)
    modules = []
    for m in MODULES:
        lecons = [{"code": le["code"], "titre": le["titre"], "duree": le["duree"], "terminee": _cle(m, le) in terminees} for le in m["lecons"]]
        modules.append({
            "code": m["code"], "titre": m["titre"], "description": m["description"], "icone": m["icone"], "lecons": lecons,
            "quiz": {"questions": len(m["quiz"]), "seuil": SEUIL_REUSSITE, "reussi": m["code"] in reussis, "meilleur": meilleurs.get(m["code"])},
        })
    total = sum(len(m["lecons"]) for m in MODULES) + len(MODULES)
    faits = len(terminees & {_cle(m, le) for m in MODULES for le in m["lecons"]}) + len(reussis & set(PAR_CODE))
    attestation = Attestation.objects.filter(utilisateur=request.user).first()
    return Response({
        "acces": True, "modules": modules, "progression": round(100 * faits / total) if total else 0,
        "attestation": {"numero": attestation.numero, "date": attestation.delivree_le} if attestation else None,
        "attestation_possible": reussis >= set(PAR_CODE),
    })


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def lecon(request, module, code):
    """GET : contenu de la leçon ; POST : la marquer terminée ; DELETE : la remettre à faire."""
    _verifier_acces()
    m = _module(module)
    le = _lecon(m, code)
    cle = _cle(m, le)
    if request.method == "POST":
        try:
            LeconTerminee.objects.get_or_create(utilisateur=request.user, lecon=cle)
        except IntegrityError:
            pass
    elif request.method == "DELETE":
        LeconTerminee.objects.filter(utilisateur=request.user, lecon=cle).delete()
    rang = m["lecons"].index(le)
    blocs = [{**b, "debut": CHAPITRES[b["chapitre"]][0], "fin": CHAPITRES[b["chapitre"]][1]} if b["type"] == "video" else b
             for b in le["blocs"]]
    return Response({
        "module": {"code": m["code"], "titre": m["titre"]}, "code": le["code"], "titre": le["titre"], "duree": le["duree"],
        "objectif": le["objectif"], "blocs": blocs,
        "terminee": LeconTerminee.objects.filter(utilisateur=request.user, lecon=cle).exists(),
        "precedente": m["lecons"][rang - 1]["code"] if rang > 0 else None,
        "suivante": m["lecons"][rang + 1]["code"] if rang + 1 < len(m["lecons"]) else None,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def quiz(request, module):
    """GET : les questions (sans les réponses) ; POST {reponses: [indices]} : correction et résultat."""
    _verifier_acces()
    m = _module(module)
    questions = m["quiz"]
    if request.method == "GET":
        return Response({"module": {"code": m["code"], "titre": m["titre"]}, "seuil": SEUIL_REUSSITE,
                         "questions": [{"question": q["question"], "choix": q["choix"]} for q in questions]})
    reponses = request.data.get("reponses")
    if not isinstance(reponses, list) or len(reponses) != len(questions):
        raise ValidationError({"reponses": v("Répondez à toutes les questions.")})
    corrections, score = [], 0
    for q, r in zip(questions, reponses):
        juste = r == q["bonne"]
        score += juste
        corrections.append({"juste": juste, "bonne": q["bonne"], "explication": q["explication"]})
    reussi = score >= SEUIL_REUSSITE
    TentativeQuiz.objects.create(utilisateur=request.user, module=m["code"], score=score, total=len(questions), reussi=reussi, reponses=reponses)
    return Response({"score": score, "total": len(questions), "reussi": reussi, "seuil": SEUIL_REUSSITE, "corrections": corrections})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def attestation(request):
    """Attestation PDF, une fois tous les quiz réussis (délivrée une fois, téléchargeable à nouveau)."""
    from weasyprint import HTML

    from apps.core.models import IdentiteOrganisation

    _verifier_acces()
    _, reussis, _ = _etat(request.user)
    if not reussis >= set(PAR_CODE):
        raise PermissionDenied(v("Réussissez d'abord le quiz de chaque module."))
    attestation = Attestation.objects.filter(utilisateur=request.user).first()
    if attestation is None:
        attestation = Attestation.objects.create(utilisateur=request.user, numero=f"EIM-{timezone.now():%Y}-{secrets.token_hex(3).upper()}")
    nom = escape(request.user.get_full_name() or request.user.username)
    organisation = escape(IdentiteOrganisation.courante().nom or "")
    date = attestation.delivree_le.strftime("%d/%m/%Y")
    modules = "".join(f"<li>{escape(m['titre'])}</li>" for m in MODULES)
    html = f"""<html><head><meta charset="utf-8"><style>
      @page {{ size: A4 landscape; margin: 0; }}
      body {{ font-family: Helvetica, Arial, sans-serif; margin: 0; color: #1f2a4a; }}
      .cadre {{ position: absolute; inset: 14mm; border: 3px solid #1ea7e1; border-radius: 10mm; padding: 16mm 22mm; }}
      .haut {{ color: #1ea7e1; letter-spacing: .25em; font-size: 11pt; font-weight: bold; }}
      h1 {{ font-size: 34pt; margin: 6mm 0 2mm; }}
      .nom {{ font-size: 26pt; font-weight: bold; color: #0b7a5c; margin: 8mm 0 2mm; }}
      p {{ font-size: 12.5pt; line-height: 1.5; margin: 2mm 0; }}
      ul {{ columns: 2; font-size: 11pt; margin: 4mm 0; }}
      .bas {{ position: absolute; bottom: 14mm; left: 22mm; right: 22mm; font-size: 10pt; color: #5d6b7a; display: flex; justify-content: space-between; }}
    </style></head><body><div class="cadre">
      <div class="haut">EXPERTISE-ID MONITORA</div>
      <h1>Attestation de formation</h1>
      <p>Expertise-ID atteste que</p>
      <div class="nom">{nom}</div>
      <p>{('de l\'organisation <b>' + organisation + '</b>, ') if organisation else ''}a suivi le cours en ligne de la plateforme
      Expertise-ID Monitora et réussi le quiz de chacun de ses {len(MODULES)} modules :</p>
      <ul>{modules}</ul>
      <div class="bas"><span>Délivrée le {date}</span><span>N° {attestation.numero}</span><span>Expertise-ID · www.expertise-id.com</span></div>
    </div></body></html>"""
    reponse = HttpResponse(HTML(string=html).write_pdf(), content_type="application/pdf")
    reponse["Content-Disposition"] = f'attachment; filename="attestation_{attestation.numero}.pdf"'
    return reponse
