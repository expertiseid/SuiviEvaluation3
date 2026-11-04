"""
Messages au plaignant (lot 7) — partie 6.7 du cahier des charges.

- Modèles par objet (accusé de réception, prise en charge, demande de complément, décision, clôture,
  enquête de satisfaction) et par langue, avec une version courriel et une version SMS, modifiables
  par l'organisation (paramétrage, onglet « Messages »).
- Le message est rédigé dans la langue du plaignant (celle de son dépôt), sinon en français.
- Variables : {numero}, {nom}, {mecanisme}, {date_reception}, {lien_suivi}, {decision}, {signature}.
  Pour un dossier confidentiel, {decision} n'est jamais remplacée par la décision : les messages ne
  révèlent aucun détail confidentiel.
- Envoi : courriel par le serveur de courriel de la plateforme ; SMS par une passerelle HTTP à
  configurer (PLAINTES_SMS_URL, PLAINTES_SMS_JETON, PLAINTES_SMS_EXPEDITEUR). Sans passerelle (ou
  avec le courriel en mode console), l'envoi est simulé et le journal l'indique (« SIMULE »).
- Chaque message est inscrit au journal du dossier avec son statut d'envoi (ENVOYE, ECHEC, SIMULE).
- Accusé de réception automatique à la réception, si le mécanisme le prévoit et que le plaignant a
  demandé une réponse par courriel, SMS ou téléphone.
"""
import json
import logging
import re
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.vocabulaire import v

from .models import ActionDossier, Mecanisme, ModeleMessage, ModeReponse

logger = logging.getLogger(__name__)

SMS, COURRIEL = "SMS", "COURRIEL"

# (objet) → {langue: (sujet, courriel, sms)}
MODELES = {
    "ACCUSE_RECEPTION": {
        "fr": ("Votre retour {numero} a bien été reçu",
               "Bonjour {nom},\n\nNous avons bien reçu votre retour, enregistré sous le numéro {numero} le {date_reception}. "
               "Il sera traité dans les délais annoncés.\n\nVous pouvez suivre son avancement avec votre code de suivi : "
               "{lien_suivi}\n\n{signature}",
               "{mecanisme} : votre retour {numero} a bien été reçu. Suivi avec votre code : {lien_suivi}"),
        "en": ("Your feedback {numero} has been received",
               "Hello {nom},\n\nWe have received your feedback, recorded under number {numero} on {date_reception}. "
               "It will be handled within the announced deadlines.\n\nYou can follow its progress with your tracking "
               "code: {lien_suivi}\n\n{signature}",
               "{mecanisme}: your feedback {numero} has been received. Track it with your code: {lien_suivi}"),
        "es": ("Hemos recibido su comentario {numero}",
               "Hola {nom},\n\nHemos recibido su comentario, registrado con el número {numero} el {date_reception}. "
               "Se tratará en los plazos anunciados.\n\nPuede seguir su avance con su código de seguimiento: "
               "{lien_suivi}\n\n{signature}",
               "{mecanisme}: hemos recibido su comentario {numero}. Seguimiento con su código: {lien_suivi}"),
        "de": ("Ihre Rückmeldung {numero} ist eingegangen",
               "Guten Tag {nom},\n\nIhre Rückmeldung ist unter der Nummer {numero} am {date_reception} eingegangen. "
               "Sie wird innerhalb der angekündigten Fristen bearbeitet.\n\nMit Ihrem Verfolgungscode können Sie den "
               "Stand verfolgen: {lien_suivi}\n\n{signature}",
               "{mecanisme}: Ihre Rückmeldung {numero} ist eingegangen. Verfolgung mit Ihrem Code: {lien_suivi}"),
        "ar": ("لقد استلمنا ملاحظتك {numero}",
               "مرحبًا {nom}،\n\nلقد استلمنا ملاحظتك المسجلة تحت الرقم {numero} بتاريخ {date_reception}. "
               "ستُعالَج ضمن الآجال المعلنة.\n\nيمكنك متابعة تقدمها برمز المتابعة: {lien_suivi}\n\n{signature}",
               "{mecanisme}: استلمنا ملاحظتك {numero}. تابعها برمزك: {lien_suivi}"),
    },
    "PRISE_EN_CHARGE": {
        "fr": ("Votre retour {numero} est en cours de traitement",
               "Bonjour {nom},\n\nVotre retour {numero} est pris en charge par notre équipe. Nous reviendrons vers vous "
               "dès qu'une réponse sera prête.\n\n{signature}",
               "{mecanisme} : votre retour {numero} est en cours de traitement."),
        "en": ("Your feedback {numero} is being handled",
               "Hello {nom},\n\nYour feedback {numero} is being handled by our team. We will get back to you as soon as "
               "a reply is ready.\n\n{signature}",
               "{mecanisme}: your feedback {numero} is being handled."),
        "es": ("Su comentario {numero} está en tratamiento",
               "Hola {nom},\n\nNuestro equipo se está ocupando de su comentario {numero}. Le responderemos en cuanto "
               "tengamos una respuesta.\n\n{signature}",
               "{mecanisme}: su comentario {numero} está en tratamiento."),
        "de": ("Ihre Rückmeldung {numero} wird bearbeitet",
               "Guten Tag {nom},\n\nIhre Rückmeldung {numero} wird von unserem Team bearbeitet. Wir melden uns, sobald "
               "eine Antwort vorliegt.\n\n{signature}",
               "{mecanisme}: Ihre Rückmeldung {numero} wird bearbeitet."),
        "ar": ("ملاحظتك {numero} قيد المعالجة",
               "مرحبًا {nom}،\n\nيتكفّل فريقنا بملاحظتك {numero}. سنعود إليك بمجرد أن يصبح الرد جاهزًا.\n\n{signature}",
               "{mecanisme}: ملاحظتك {numero} قيد المعالجة."),
    },
    "DEMANDE_COMPLEMENT": {
        "fr": ("Votre retour {numero} : un complément d'information est nécessaire",
               "Bonjour {nom},\n\nPour traiter votre retour {numero}, nous avons besoin de quelques informations "
               "complémentaires. Un membre de notre équipe va vous contacter ; vous pouvez aussi répondre à ce "
               "message.\n\n{signature}",
               "{mecanisme} : pour traiter votre retour {numero}, nous avons besoin d'un complément. Nous allons vous contacter."),
        "en": ("Your feedback {numero}: more information is needed",
               "Hello {nom},\n\nTo handle your feedback {numero}, we need some additional information. A member of our "
               "team will contact you; you can also reply to this message.\n\n{signature}",
               "{mecanisme}: to handle your feedback {numero}, we need more information. We will contact you."),
        "es": ("Su comentario {numero}: se necesita información adicional",
               "Hola {nom},\n\nPara tratar su comentario {numero}, necesitamos información adicional. Un miembro de "
               "nuestro equipo le contactará; también puede responder a este mensaje.\n\n{signature}",
               "{mecanisme}: para tratar su comentario {numero}, necesitamos más información. Le contactaremos."),
        "de": ("Ihre Rückmeldung {numero}: weitere Angaben nötig",
               "Guten Tag {nom},\n\nUm Ihre Rückmeldung {numero} zu bearbeiten, benötigen wir einige zusätzliche "
               "Angaben. Ein Teammitglied wird Sie kontaktieren; Sie können auch auf diese Nachricht antworten."
               "\n\n{signature}",
               "{mecanisme}: Für Ihre Rückmeldung {numero} benötigen wir weitere Angaben. Wir melden uns."),
        "ar": ("ملاحظتك {numero}: نحتاج إلى معلومات إضافية",
               "مرحبًا {nom}،\n\nلمعالجة ملاحظتك {numero}، نحتاج إلى بعض المعلومات الإضافية. سيتصل بك أحد أعضاء "
               "فريقنا؛ ويمكنك أيضًا الرد على هذه الرسالة.\n\n{signature}",
               "{mecanisme}: لمعالجة ملاحظتك {numero} نحتاج إلى معلومات إضافية. سنتصل بك."),
    },
    "DECISION": {
        "fr": ("Réponse à votre retour {numero}",
               "Bonjour {nom},\n\nVoici la réponse apportée à votre retour {numero} :\n\n{decision}\n\nSi cette réponse "
               "ne vous convient pas, vous pouvez la contester en nous recontactant.\n\n{signature}",
               "{mecanisme} : réponse à votre retour {numero}. {decision}"),
        "en": ("Reply to your feedback {numero}",
               "Hello {nom},\n\nHere is the reply to your feedback {numero}:\n\n{decision}\n\nIf this reply does not "
               "suit you, you can dispute it by contacting us again.\n\n{signature}",
               "{mecanisme}: reply to your feedback {numero}. {decision}"),
        "es": ("Respuesta a su comentario {numero}",
               "Hola {nom},\n\nEsta es la respuesta a su comentario {numero}:\n\n{decision}\n\nSi esta respuesta no le "
               "conviene, puede impugnarla contactándonos de nuevo.\n\n{signature}",
               "{mecanisme}: respuesta a su comentario {numero}. {decision}"),
        "de": ("Antwort auf Ihre Rückmeldung {numero}",
               "Guten Tag {nom},\n\nHier ist die Antwort auf Ihre Rückmeldung {numero}:\n\n{decision}\n\nWenn Sie mit "
               "dieser Antwort nicht einverstanden sind, können Sie uns erneut kontaktieren.\n\n{signature}",
               "{mecanisme}: Antwort auf Ihre Rückmeldung {numero}. {decision}"),
        "ar": ("الرد على ملاحظتك {numero}",
               "مرحبًا {nom}،\n\nإليك الرد على ملاحظتك {numero}:\n\n{decision}\n\nإن لم يناسبك هذا الرد، يمكنك "
               "الاعتراض عليه بالتواصل معنا مجددًا.\n\n{signature}",
               "{mecanisme}: الرد على ملاحظتك {numero}. {decision}"),
    },
    "CLOTURE": {
        "fr": ("Votre retour {numero} est clôturé",
               "Bonjour {nom},\n\nVotre retour {numero} est maintenant clôturé. Merci de nous avoir fait part de votre "
               "retour : il nous aide à améliorer nos actions.\n\n{signature}",
               "{mecanisme} : votre retour {numero} est clôturé. Merci de votre confiance."),
        "en": ("Your feedback {numero} is closed",
               "Hello {nom},\n\nYour feedback {numero} is now closed. Thank you for sharing it with us: it helps us "
               "improve our work.\n\n{signature}",
               "{mecanisme}: your feedback {numero} is closed. Thank you for your trust."),
        "es": ("Su comentario {numero} está cerrado",
               "Hola {nom},\n\nSu comentario {numero} está cerrado. Gracias por compartirlo con nosotros: nos ayuda a "
               "mejorar nuestras acciones.\n\n{signature}",
               "{mecanisme}: su comentario {numero} está cerrado. Gracias por su confianza."),
        "de": ("Ihre Rückmeldung {numero} ist abgeschlossen",
               "Guten Tag {nom},\n\nIhre Rückmeldung {numero} ist jetzt abgeschlossen. Vielen Dank: Sie hilft uns, "
               "unsere Arbeit zu verbessern.\n\n{signature}",
               "{mecanisme}: Ihre Rückmeldung {numero} ist abgeschlossen. Danke für Ihr Vertrauen."),
        "ar": ("أُغلقت ملاحظتك {numero}",
               "مرحبًا {nom}،\n\nأُغلقت ملاحظتك {numero}. شكرًا لمشاركتها معنا: فهي تساعدنا على تحسين عملنا.\n\n{signature}",
               "{mecanisme}: أُغلقت ملاحظتك {numero}. شكرًا لثقتك."),
    },
    "SATISFACTION": {
        "fr": ("Votre avis sur le traitement de votre retour {numero}",
               "Bonjour {nom},\n\nÊtes-vous satisfait de la façon dont votre retour {numero} a été traité ? Répondez "
               "simplement à ce message par OUI ou NON ; vous pouvez ajouter un commentaire.\n\n{signature}",
               "{mecanisme} : êtes-vous satisfait du traitement de votre retour {numero} ? Répondez OUI ou NON."),
        "en": ("Your opinion on how your feedback {numero} was handled",
               "Hello {nom},\n\nAre you satisfied with how your feedback {numero} was handled? Simply reply YES or NO "
               "to this message; you can add a comment.\n\n{signature}",
               "{mecanisme}: are you satisfied with how your feedback {numero} was handled? Reply YES or NO."),
        "es": ("Su opinión sobre el tratamiento de su comentario {numero}",
               "Hola {nom},\n\n¿Está satisfecho con el tratamiento de su comentario {numero}? Responda a este mensaje "
               "con SÍ o NO; puede añadir un comentario.\n\n{signature}",
               "{mecanisme}: ¿está satisfecho con el tratamiento de su comentario {numero}? Responda SÍ o NO."),
        "de": ("Ihre Meinung zur Bearbeitung Ihrer Rückmeldung {numero}",
               "Guten Tag {nom},\n\nSind Sie mit der Bearbeitung Ihrer Rückmeldung {numero} zufrieden? Antworten Sie "
               "einfach mit JA oder NEIN; Sie können einen Kommentar hinzufügen.\n\n{signature}",
               "{mecanisme}: Sind Sie mit der Bearbeitung Ihrer Rückmeldung {numero} zufrieden? Antworten Sie JA oder NEIN."),
        "ar": ("رأيك في معالجة ملاحظتك {numero}",
               "مرحبًا {nom}،\n\nهل أنت راضٍ عن طريقة معالجة ملاحظتك {numero}؟ أجب على هذه الرسالة بنعم أو لا؛ "
               "ويمكنك إضافة تعليق.\n\n{signature}",
               "{mecanisme}: هل أنت راضٍ عن معالجة ملاحظتك {numero}؟ أجب بنعم أو لا."),
    },
}

# Pour un dossier confidentiel, à la place de la décision.
DECISION_CONFIDENTIELLE = {
    "fr": "Un membre de notre équipe vous communiquera la réponse de façon confidentielle.",
    "en": "A member of our team will share the reply with you confidentially.",
    "es": "Un miembro de nuestro equipo le comunicará la respuesta de forma confidencial.",
    "de": "Ein Teammitglied wird Ihnen die Antwort vertraulich mitteilen.",
    "ar": "سيُبلغك أحد أعضاء فريقنا بالرد بسرية.",
}


def installer_modeles():
    """Ajoute les modèles par défaut qui manquent (sans écraser ceux de l'organisation)."""
    ajoutes = 0
    for objet, langues in MODELES.items():
        for langue, (sujet, courriel, sms) in langues.items():
            _, cree = ModeleMessage.objects.get_or_create(
                objet=objet, langue=langue, defaults={"sujet": sujet, "texte_courriel": courriel, "texte_sms": sms})
            ajoutes += cree
    return ajoutes


def modele_pour(objet, langue):
    """Modèle actif de l'objet dans la langue du plaignant, sinon en français, sinon le premier disponible."""
    qs = ModeleMessage.objects.filter(objet=objet, actif=True)
    return qs.filter(langue=langue).first() or qs.filter(langue="fr").first() or qs.first()


def lien_suivi():
    from apps.organisations.contexte import lien_public

    return lien_public("/plainte/suivi")


def rediger(dossier, objet, canal):
    """(sujet, texte, langue) du message, variables remplacées ; aucun détail pour un dossier confidentiel."""
    langue = dossier.langue if dossier.langue in DECISION_CONFIDENTIELLE else "fr"
    modele = modele_pour(objet, langue)
    if modele is None:
        raise ValidationError({"objet": v("Aucun modèle de message pour cet objet : installez les modèles dans le paramétrage.")})
    mecanisme = Mecanisme.courant()
    decision = DECISION_CONFIDENTIELLE.get(modele.langue, DECISION_CONFIDENTIELLE["fr"]) if dossier.sensible else (dossier.decision or "")
    valeurs = {
        "numero": dossier.numero,
        "nom": "" if dossier.anonyme else dossier.nom,
        "mecanisme": mecanisme.nom,
        "date_reception": dossier.date_reception.strftime("%d/%m/%Y"),
        "lien_suivi": lien_suivi(),
        "decision": decision,
        "signature": mecanisme.signature_messages or mecanisme.nom,
    }

    def remplir(texte):
        texte = re.sub(r"\{(\w+)\}", lambda m: str(valeurs.get(m.group(1), m.group(0))), texte or "")
        return re.sub(r"[ \t]+([,،])", r"\1", texte).strip()  # « Bonjour , » quand le nom est absent

    texte = modele.texte_sms if canal == SMS else modele.texte_courriel
    return remplir(modele.sujet), remplir(texte), modele.langue


# --- Envoi -------------------------------------------------------------------------------------------

def envoyer_sms(numero, texte):
    """(statut, erreur) : passerelle HTTP configurée, sinon simulation (journalisée comme telle)."""
    url = getattr(settings, "PLAINTES_SMS_URL", "")
    if not url:
        logger.info("SMS simulé (aucune passerelle configurée) vers un numéro de plaignant.")
        return "SIMULE", ""
    charge = json.dumps({"to": numero, "message": texte, "from": getattr(settings, "PLAINTES_SMS_EXPEDITEUR", "")}).encode()
    requete = urllib.request.Request(url, data=charge, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {getattr(settings, 'PLAINTES_SMS_JETON', '')}"})
    try:
        with urllib.request.urlopen(requete, timeout=15) as reponse:
            return ("ENVOYE", "") if 200 <= reponse.status < 300 else ("ECHEC", f"HTTP {reponse.status}")
    except Exception as erreur:  # passerelle injoignable, refus…  — jamais le contenu dans le journal technique
        logger.warning("Échec d'envoi d'un SMS au plaignant : %s", type(erreur).__name__)
        return "ECHEC", type(erreur).__name__


def envoyer_courriel(adresse, sujet, texte):
    backend = getattr(settings, "EMAIL_BACKEND", "")
    try:
        envoyes = send_mail(sujet, texte, getattr(settings, "DEFAULT_FROM_EMAIL", None), [adresse], fail_silently=False)
    except Exception as erreur:
        logger.warning("Échec d'envoi d'un courriel au plaignant : %s", type(erreur).__name__)
        return "ECHEC", type(erreur).__name__
    # Console, ou destinataire hors liste blanche d'un poste de test : rien n'est réellement parti.
    if "console" in backend or "dummy" in backend or not envoyes:
        return "SIMULE", ""
    return "ENVOYE", ""


def envoyer(dossier, auteur, donnees):
    """
    Envoie un message au plaignant (objet, canal SMS ou COURRIEL ; sujet et texte modifiables, sinon le
    modèle) et l'inscrit au journal avec son statut d'envoi. La décision communiquée passe le dossier à
    « Réponse donnée » (comme un échange tracé à la main).
    """
    from . import traitement

    objet = donnees.get("objet")
    canal = donnees.get("canal")
    if objet not in dict(ModeleMessage.OBJETS):
        raise ValidationError({"objet": v("Choisissez l'objet du message.")})
    if canal not in (SMS, COURRIEL):
        raise ValidationError({"canal": v("Choisissez l'envoi par SMS ou par courriel.")})
    if dossier.anonyme:
        raise ValidationError({"detail": v("Plaignant anonyme : aucun moyen de le contacter. Il suit son dossier avec son code.")})
    if canal == SMS and not dossier.telephone:
        raise ValidationError({"canal": v("Aucun numéro de téléphone n'est enregistré pour ce plaignant.")})
    if canal == COURRIEL and not dossier.courriel:
        raise ValidationError({"canal": v("Aucune adresse courriel n'est enregistrée pour ce plaignant.")})
    if objet == "DECISION" and not dossier.decision:
        raise ValidationError({"objet": v("Enregistrez d'abord la décision.")})
    sujet, texte, langue = rediger(dossier, objet, canal)
    sujet = (donnees.get("sujet") or "").strip() or sujet
    texte = (donnees.get("texte") or "").strip() or texte
    statut, erreur = envoyer_sms(dossier.telephone, texte) if canal == SMS else envoyer_courriel(dossier.courriel, sujet, texte)
    details = {"statut_envoi": statut, "erreur": erreur, "langue": langue, "sujet": sujet if canal == COURRIEL else ""}
    if statut == "ECHEC":
        # Rien n'est parti : on trace la tentative sans changer l'état du dossier.
        ActionDossier.objects.create(dossier=dossier, type=ActionDossier.Type.COMMUNICATION, auteur=auteur, texte=texte,
                                     sens="SORTANT", canal=canal, objet=objet, details=details)
        return dossier
    traitement.communiquer(dossier, auteur, {"sens": "SORTANT", "canal": canal, "objet": objet, "texte": texte},
                           details_envoi=details)
    return dossier


# Coupé pendant la génération des données de démonstration (seed_demo_plaintes).
ENVOIS_AUTOMATIQUES = True


def accuse_reception_automatique(dossier):
    """À la réception : accusé de réception par le moyen demandé (courriel, ou SMS pour SMS et téléphone)."""
    mecanisme = Mecanisme.courant()
    if not ENVOIS_AUTOMATIQUES or not mecanisme.accuse_reception_auto or dossier.anonyme:
        return None
    if dossier.mode_reponse == ModeReponse.COURRIEL and dossier.courriel:
        canal = COURRIEL
    elif dossier.mode_reponse in (ModeReponse.SMS, ModeReponse.TELEPHONE) and dossier.telephone:
        canal = SMS
    else:
        return None
    if not modele_pour("ACCUSE_RECEPTION", dossier.langue or "fr"):
        return None
    try:
        envoyer(dossier, None, {"objet": "ACCUSE_RECEPTION", "canal": canal})
    except ValidationError:
        return None
    return canal
