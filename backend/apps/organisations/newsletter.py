"""
Newsletter du site vitrine (base centrale).

- Inscription depuis le site (adresse courriel, langue du site, accord) : un courriel de confirmation est
  envoyé ; rien n'est reçu tant que le lien n'est pas ouvert (double confirmation). La réponse est la même
  que l'adresse soit nouvelle, déjà inscrite ou en attente : le site ne révèle pas qui est abonné.
- Chaque envoi porte un lien de désinscription (page newsletter.html du site, et en-tête List-Unsubscribe
  pour le bouton « Se désabonner » des messageries).
- Console Expertise-ID (EstOperateur) : abonnés (nombre, liste, export Excel, suppression) ; newsletters :
  rédiger en français avec traductions facultatives, s'envoyer un essai, puis envoyer une seule fois à tous
  les abonnés confirmés, chacun dans sa langue. L'envoi se fait en arrière-plan.
"""
import io
import logging
import secrets
import threading
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import connections
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import escape
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.core.vocabulaire import v

from .console import EstOperateur
from .models import LANGUES_SITE, AbonneNewsletter, EnvoiNewsletter

logger = logging.getLogger(__name__)
LANGUES = ("fr", *LANGUES_SITE)
PAUSE_ENTRE_ENVOIS = 0.2  # secondes : ménage le serveur de courriel


def _adresse_site() -> str:
    return settings.URL_SITE.rstrip("/")


def lien_confirmation(abonne) -> str:
    return f"{_adresse_site()}/newsletter.html?confirmer={abonne.jeton}&lang={abonne.langue}"


def lien_desinscription(abonne) -> str:
    return f"{_adresse_site()}/newsletter.html?desinscrire={abonne.jeton}&lang={abonne.langue}"


def _envoyer_confirmation(abonne):
    from apps.core.langues import en_langue

    with en_langue(abonne.langue):
        sujet = v("Confirmez votre inscription à la newsletter d'Expertise-ID Monitora")
        texte = (v("Bonjour,\n\nPour recevoir la newsletter d'Expertise-ID Monitora, confirmez votre inscription en "
                   "ouvrant ce lien :") + f"\n\n{lien_confirmation(abonne)}\n\n"
                 + v("Si vous n'avez pas demandé cette inscription, ignorez ce message : vous ne recevrez rien."))
    try:
        EmailMultiAlternatives(sujet, texte, settings.DEFAULT_FROM_EMAIL, [abonne.courriel]).send()
    except Exception as erreur:  # serveur de courriel injoignable : la réponse au site reste la même
        logger.warning("Confirmation de newsletter non envoyée : %s", type(erreur).__name__)


# --- Site vitrine (public) -------------------------------------------------------------------------

class LimiteNewsletter(AnonRateThrottle):
    scope = "newsletter"
    rate = "10/hour"


def _public(vue):
    return api_view(["POST"])(authentication_classes([])(permission_classes([AllowAny])(throttle_classes([LimiteNewsletter])(vue))))


@_public
def inscription(request):
    """{courriel, langue, accord: true} : envoie le lien de confirmation ; même réponse dans tous les cas."""
    from apps.core.courriel import adresse_fictive

    if request.data.get("site_web"):  # champ piège, invisible pour une personne
        raise ValidationError({"detail": "Envoi refusé."})
    courriel = str(request.data.get("courriel") or "").strip().lower()[:254]
    if "@" not in courriel or adresse_fictive(courriel):
        raise ValidationError({"courriel": v("Indiquez une adresse courriel valide.")})
    if request.data.get("accord") is not True:
        raise ValidationError({"accord": v("Votre accord est nécessaire pour recevoir la newsletter.")})
    langue = request.data.get("langue") if request.data.get("langue") in LANGUES else "fr"
    abonne = AbonneNewsletter.objects.filter(courriel=courriel).first()
    if abonne is None:
        abonne = AbonneNewsletter.objects.create(courriel=courriel, langue=langue, jeton=secrets.token_urlsafe(32))
    if abonne.statut != "ACTIF":
        abonne.langue = langue
        abonne.save(update_fields=["langue"])
        _envoyer_confirmation(abonne)
    return Response({"detail": v("Merci ! Un courriel de confirmation vient de vous être envoyé : ouvrez le lien qu'il "
                                 "contient pour recevoir la newsletter.")})


def _abonne_du_jeton(request):
    jeton = str(request.data.get("jeton") or request.query_params.get("jeton") or "")
    abonne = AbonneNewsletter.objects.filter(jeton=jeton).first() if jeton else None
    if abonne is None:
        raise ValidationError({"detail": v("Ce lien n'est plus valable.")})
    return abonne


@_public
def confirmer(request):
    abonne = _abonne_du_jeton(request)
    abonne.confirme_le = abonne.confirme_le if abonne.confirme_le and not abonne.desinscrit_le else timezone.now()
    abonne.desinscrit_le = None
    abonne.save(update_fields=["confirme_le", "desinscrit_le"])
    return Response({"detail": v("Votre inscription est confirmée : vous recevrez la newsletter d'Expertise-ID Monitora.")})


@_public
def desinscrire(request):
    """Lien de chaque envoi (page du site), ou bouton « Se désabonner » de la messagerie (POST, jeton dans l'adresse)."""
    abonne = _abonne_du_jeton(request)
    if not abonne.desinscrit_le:
        abonne.desinscrit_le = timezone.now()
        abonne.save(update_fields=["desinscrit_le"])
    return Response({"detail": v("Vous êtes désinscrit : vous ne recevrez plus la newsletter.")})


# --- Console Expertise-ID --------------------------------------------------------------------------

class AbonneSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbonneNewsletter
        fields = ("id", "courriel", "langue", "statut", "cree_le", "confirme_le", "desinscrit_le")
        read_only_fields = fields


class EnvoiSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvoiNewsletter
        fields = ("id", "sujet", "contenu", "traductions", "statut", "destinataires", "envoyes", "echecs", "envoye_par",
                  "envoye_le", "cree_le", "modifie_le")
        read_only_fields = ("statut", "destinataires", "envoyes", "echecs", "envoye_par", "envoye_le", "cree_le", "modifie_le")

    def validate_traductions(self, valeur):
        if not isinstance(valeur, dict):
            return {}
        return {langue: {c: str(t.get(c, ""))[:20000] for c in ("sujet", "contenu") if str(t.get(c, "")).strip()}
                for langue, t in valeur.items() if langue in LANGUES_SITE and isinstance(t, dict)}

    def validate(self, donnees):
        if self.instance and self.instance.statut != EnvoiNewsletter.Statut.BROUILLON:
            raise ValidationError({"detail": v("Cette newsletter est déjà envoyée : elle ne peut plus être modifiée.")})
        return donnees


def abonnes_actifs():
    return AbonneNewsletter.objects.filter(confirme_le__isnull=False, desinscrit_le__isnull=True)


class AbonneConsoleViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = (EstOperateur,)
    serializer_class = AbonneSerializer
    queryset = AbonneNewsletter.objects.all()
    pagination_class = None

    @action(detail=False, methods=["get"])
    def exporter(self, request):
        from openpyxl import Workbook

        classeur = Workbook()
        feuille = classeur.active
        feuille.title = "Abonnés"
        feuille.append(["Adresse courriel", "Langue", "Statut", "Inscrit le", "Confirmé le", "Désinscrit le"])
        libelles = {"ACTIF": "Actif", "EN_ATTENTE": "En attente de confirmation", "DESINSCRIT": "Désinscrit"}
        jour = lambda d: timezone.localtime(d).strftime("%d/%m/%Y %H:%M") if d else ""
        for a in AbonneNewsletter.objects.all():
            feuille.append([a.courriel, a.langue, libelles[a.statut], jour(a.cree_le), jour(a.confirme_le), jour(a.desinscrit_le)])
        for colonne, largeur in zip("ABCDEF", (38, 8, 26, 18, 18, 18)):
            feuille.column_dimensions[colonne].width = largeur
        sortie = io.BytesIO()
        classeur.save(sortie)
        reponse = HttpResponse(sortie.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        reponse["Content-Disposition"] = "attachment; filename=abonnes-newsletter.xlsx"
        return reponse


def _message(envoi, abonne, connexion=None):
    """Courriel d'une newsletter pour un abonné : dans sa langue, avec le lien de désinscription."""
    from apps.core.langues import en_langue

    traduction = (envoi.traductions or {}).get(abonne.langue) or {}
    sujet = traduction.get("sujet") or envoi.sujet
    contenu = traduction.get("contenu") or envoi.contenu
    lien = lien_desinscription(abonne)
    with en_langue(abonne.langue):
        pied = v("Vous recevez ce courriel parce que vous êtes inscrit à la newsletter d'Expertise-ID Monitora. "
                 "Pour vous désinscrire :")
    texte = f"{contenu}\n\n—\n{pied} {lien}"
    paragraphes = "".join(f"<p>{escape(p).replace(chr(10), '<br>')}</p>" for p in contenu.split("\n\n") if p.strip())
    html = (f'<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#1c2420;max-width:640px">'
            f"{paragraphes}<hr style=\"border:none;border-top:1px solid #dde2dc;margin:28px 0 12px\">"
            f'<p style="font-size:12px;color:#5d6862">{escape(pied)} <a href="{escape(lien)}">{escape(lien)}</a></p></div>')
    api = f"{settings.PLAINTES_URL_PUBLIQUE.rstrip('/')}/api/v1/public/site/newsletter/desinscrire/?jeton={abonne.jeton}"
    message = EmailMultiAlternatives(sujet, texte, settings.DEFAULT_FROM_EMAIL, [abonne.courriel], connection=connexion,
                                     headers={"List-Unsubscribe": f"<{api}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})
    message.attach_alternative(html, "text/html")
    return message


def diffuser(envoi_id):
    """Envoie la newsletter à tous les abonnés confirmés (une seule fois) ; compte les envois et les échecs."""
    envoi = EnvoiNewsletter.objects.get(pk=envoi_id)
    abonnes = list(abonnes_actifs())
    EnvoiNewsletter.objects.filter(pk=envoi.pk).update(destinataires=len(abonnes))
    envoyes = echecs = 0
    with get_connection() as connexion:
        for abonne in abonnes:
            try:
                envoyes += _message(envoi, abonne, connexion).send()
            except Exception as erreur:
                echecs += 1
                logger.warning("Newsletter %s non envoyée à un abonné : %s", envoi.pk, type(erreur).__name__)
            EnvoiNewsletter.objects.filter(pk=envoi.pk).update(envoyes=envoyes, echecs=echecs)
            time.sleep(PAUSE_ENTRE_ENVOIS)
    EnvoiNewsletter.objects.filter(pk=envoi.pk).update(statut=EnvoiNewsletter.Statut.ENVOYE, envoye_le=timezone.now())


def lancer(envoi, en_arriere_plan=True):
    def travail():
        try:
            diffuser(envoi.pk)
        except Exception:
            logger.exception("Envoi de la newsletter %s interrompu.", envoi.pk)
        finally:
            if en_arriere_plan:
                connections.close_all()

    if en_arriere_plan:
        threading.Thread(target=travail, name=f"newsletter-{envoi.pk}", daemon=True).start()
    else:
        travail()


class EnvoiConsoleViewSet(viewsets.ModelViewSet):
    permission_classes = (EstOperateur,)
    serializer_class = EnvoiSerializer
    queryset = EnvoiNewsletter.objects.all()
    pagination_class = None

    def perform_destroy(self, instance):
        if instance.statut == EnvoiNewsletter.Statut.EN_COURS:
            raise ValidationError({"detail": v("Envoi en cours : attendez qu'il soit terminé.")})
        instance.delete()

    @action(detail=True, methods=["post"])
    def essai(self, request, pk=None):
        """Envoie la newsletter à l'adresse de l'opérateur connecté, dans la langue demandée, sans rien enregistrer."""
        envoi = self.get_object()
        langue = request.data.get("langue") if request.data.get("langue") in LANGUES else "fr"
        if not request.user.email:
            raise ValidationError({"detail": v("Votre compte n'a pas d'adresse courriel.")})
        temoin = AbonneNewsletter(courriel=request.user.email, langue=langue, jeton="essai")
        _message(envoi, temoin).send()
        return Response({"detail": v(f"Essai envoyé à {request.user.email}.")})

    @action(detail=True, methods=["post"])
    def envoyer(self, request, pk=None):
        """Envoi définitif à tous les abonnés confirmés ; une seule fois."""
        nombre = abonnes_actifs().count()
        lignes = EnvoiNewsletter.objects.filter(pk=pk, statut=EnvoiNewsletter.Statut.BROUILLON).update(
            statut=EnvoiNewsletter.Statut.EN_COURS, envoye_par=request.user.email or request.user.username, destinataires=nombre)
        if not lignes:
            raise ValidationError({"detail": v("Cette newsletter est déjà envoyée.")})
        if not nombre:
            EnvoiNewsletter.objects.filter(pk=pk).update(statut=EnvoiNewsletter.Statut.BROUILLON, envoye_par="")
            raise ValidationError({"detail": v("Aucun abonné confirmé pour le moment.")})
        envoi = EnvoiNewsletter.objects.get(pk=pk)
        lancer(envoi)
        return Response(EnvoiSerializer(envoi).data)

    @action(detail=False, methods=["get"])
    def resume(self, request):
        tous = AbonneNewsletter.objects.all()
        return Response({"actifs": abonnes_actifs().count(), "en_attente": tous.filter(confirme_le__isnull=True, desinscrit_le__isnull=True).count(),
                         "desinscrits": tous.filter(desinscrit_le__isnull=False).count()})
