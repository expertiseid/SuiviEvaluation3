"""
Double authentification par courriel : à chaque connexion, un code à 6 chiffres est envoyé à l'adresse
du compte ; les jetons de connexion ne sont remis qu'une fois ce code saisi.

- Concerne tous les comptes (DOUBLE_AUTH_OBLIGATOIRE, vrai par défaut ; à ne désactiver que sur un
  poste de développement). Un compte sans adresse courriel réelle ne peut pas se connecter : il faut
  d'abord lui en donner une (page Utilisateurs).
- Le mot de passe vérifié, le serveur envoie le code et remet un jeton d'étape signé ; le code est
  valable 10 minutes, pour 5 essais, une seule fois ; seule son empreinte est gardée. Un nouveau code
  peut être demandé (au plus 3 fois, une minute d'intervalle) ; il annule le précédent.
- Les jetons remis après le code portent la marque « df » (conservée au renouvellement) ; un jeton sans
  cette marque est refusé (JWTAvecDoubleFacteur), y compris pour les sessions ouvertes avant.
- Codes refusés et envois impossibles : au journal d'audit (jamais le code).
"""
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import inactivite
from apps.core.audit import A, auditer
from apps.organisations.contexte import actif as multi_organisations
from apps.organisations.contexte import identifiant as organisation_courante
from apps.organisations.contexte import sel
from apps.core.vocabulaire import v

from .models import CodeConnexion

MARQUE = "df"
SEL = "code-connexion"
DUREE_CODE = timedelta(minutes=10)
ESSAIS_MAX = 5
RENVOIS_MAX = 3
INTERVALLE_RENVOI = timedelta(minutes=1)


def obligatoire() -> bool:
    return getattr(settings, "DOUBLE_AUTH_OBLIGATOIRE", True)


class JWTAvecDoubleFacteur(JWTAuthentication):
    """Refuse un jeton obtenu sans le code envoyé par courriel."""

    def authenticate(self, request):
        resultat = super().authenticate(request)
        # Plateforme multi-organisations : un jeton ne vaut que dans l'espace qui l'a délivré (les comptes
        # de deux organisations peuvent porter le même numéro).
        if resultat is not None and multi_organisations() and resultat[1].get("org", "") != organisation_courante():
            raise AuthenticationFailed({"detail": v("Session d'un autre espace : reconnectez-vous."),
                                        "code": "double_authentification_requise"})
        if resultat is not None and obligatoire() and not resultat[1].get(MARQUE):
            # « code » dans la réponse : l'interface renvoie alors à l'écran de connexion.
            raise AuthenticationFailed({"detail": v("Double authentification requise : reconnectez-vous."),
                                        "code": "double_authentification_requise"})
        if resultat is not None:
            # Session restée inactive trop longtemps (apps.core.inactivite) : refusée même si le jeton est valide.
            if inactivite.inactif(resultat[0]):
                raise AuthenticationFailed({"detail": v("Session fermée après une période d'inactivité : reconnectez-vous."),
                                            "code": "session_inactive"})
            inactivite.noter(resultat[0])
        return resultat


def jetons(utilisateur, **marques) -> dict:
    refresh = RefreshToken.for_user(utilisateur)
    refresh[MARQUE] = True  # recopié dans les jetons d'accès, et conservé à chaque renouvellement
    refresh["org"] = organisation_courante()  # espace qui a délivré le jeton
    refresh[inactivite.MARQUE] = inactivite.minutes(utilisateur)  # minuteur d'avertissement de l'interface
    inactivite.noter(utilisateur, forcer=True)
    for cle, valeur in marques.items():  # ex : demo=True (apps.accounts.demo)
        refresh[cle] = valeur
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _empreinte(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), (code or "").strip().encode(), hashlib.sha256).hexdigest()


def adresse_masquee(adresse: str) -> str:
    nom, _, domaine = adresse.partition("@")
    return f"{nom[:2]}{'•' * max(len(nom) - 2, 3)}@{domaine}"


def _envoyer(utilisateur):
    """Nouveau code (les précédents non utilisés sont annulés), envoyé à l'adresse du compte."""
    from apps.core.courriel import adresse_fictive
    from apps.core.langues import en_langue

    adresse = (utilisateur.email or "").strip()
    if not adresse or adresse_fictive(adresse):
        auditer(utilisateur, A.DOUBLE_AUTHENTIFICATION, utilisateur.username, module="comptes", operation="sans_adresse")
        raise ValidationError({"detail": v("Aucune adresse courriel valide n'est enregistrée pour ce compte : "
                                           "demandez à l'administrateur de la renseigner.")})
    CodeConnexion.objects.filter(utilisateur=utilisateur, utilise=False).update(utilise=True)
    code = f"{secrets.randbelow(1_000_000):06d}"
    enregistre = CodeConnexion.objects.create(utilisateur=utilisateur, empreinte=_empreinte(code),
                                              expire_le=timezone.now() + DUREE_CODE)
    with en_langue(utilisateur.langue or "fr"):
        sujet = v(f"Votre code de connexion : {code}")
        texte = v(f"Bonjour,\n\nVotre code de connexion à la plateforme Expertise-ID Monitora est : {code}\n\n"
                  "Il est valable 10 minutes et ne sert qu'une fois. Si vous n'êtes pas à l'origine de cette "
                  "connexion, ne communiquez ce code à personne et changez votre mot de passe.")
    try:
        envoyes = send_mail(sujet, texte, getattr(settings, "DEFAULT_FROM_EMAIL", None), [adresse], fail_silently=False)
    except Exception as erreur:  # serveur de courriel injoignable : on n'écrit ni l'adresse ni le code
        envoyes = 0
        auditer(utilisateur, A.DOUBLE_AUTHENTIFICATION, utilisateur.username, module="comptes",
                operation="envoi_impossible", erreur=type(erreur).__name__)
    if not envoyes:
        enregistre.delete()
        raise ValidationError({"detail": v("Le code de connexion n'a pas pu être envoyé. Réessayez dans un instant.")})


def _etape(utilisateur, renvois):
    jeton = signing.dumps({"u": utilisateur.pk, "r": renvois}, salt=sel(SEL))
    if multi_organisations():
        # Adresse unique : le jeton d'étape dit dans quel espace chercher le compte (espace_du_jeton).
        jeton = f"{organisation_courante()}~{jeton}"
    return {
        "double_authentification": "code",
        "jeton": jeton,
        "destination": adresse_masquee(utilisateur.email),
        "validite_minutes": int(DUREE_CODE.total_seconds() // 60),
    }


def demarrer(utilisateur):
    """Après le mot de passe : None (code non exigé) ou l'étape « code » (adresse masquée, jeton d'étape)."""
    if not obligatoire():
        return None
    _envoyer(utilisateur)
    return _etape(utilisateur, 0)


@contextmanager
def espace_du_jeton(jeton):
    """
    Étape « code » sur l'adresse unique de la plateforme : se place dans l'espace de l'organisation que
    désigne le jeton d'étape (« sous-domaine~jeton signé ») et rend le jeton signé. Un préfixe modifié ne
    sert à rien : la signature dépend de l'organisation (sel()).
    """
    from apps.organisations import contexte
    from apps.organisations.models import Organisation

    sous_domaine, separateur, signe = (jeton or "").partition("~")
    if not (multi_organisations() and separateur):
        yield jeton
        return
    if not sous_domaine:  # opérateur Expertise-ID : base centrale
        yield signe
        return
    org = Organisation.objects.using("central").filter(sous_domaine=sous_domaine, statut=Organisation.Statut.ACTIVE).first()
    if org is None:
        raise AuthenticationFailed(v("Étape de connexion expirée : reconnectez-vous."))
    with contexte.dans_organisation(org):
        yield signe


def lire_jeton(jeton):
    from .models import User

    try:
        contenu = signing.loads(jeton or "", salt=sel(SEL), max_age=int(DUREE_CODE.total_seconds()))
    except signing.BadSignature:  # comprend le jeton expiré
        raise AuthenticationFailed(v("Étape de connexion expirée : reconnectez-vous."))
    utilisateur = User.objects.filter(pk=contenu.get("u"), is_active=True).first()
    if utilisateur is None:
        raise AuthenticationFailed(v("Étape de connexion expirée : reconnectez-vous."))
    return utilisateur, contenu.get("r", 0)


def verifier(jeton, code):
    """Code saisi : renvoie les jetons de connexion ; sinon refus (essais comptés, journal d'audit)."""
    utilisateur, _ = lire_jeton(jeton)
    enregistre = CodeConnexion.objects.filter(utilisateur=utilisateur, utilise=False).first()
    if enregistre is None or enregistre.expire_le < timezone.now() or enregistre.essais >= ESSAIS_MAX:
        raise AuthenticationFailed(v("Code expiré : reconnectez-vous ou demandez un nouveau code."))
    if not hmac.compare_digest(_empreinte(code), enregistre.empreinte):
        enregistre.essais += 1
        enregistre.save(update_fields=["essais"])
        auditer(None, A.CONNEXION_ECHOUEE, module="comptes", identifiant=utilisateur.username, etape="second_facteur")
        restants = ESSAIS_MAX - enregistre.essais
        if restants <= 0:
            raise AuthenticationFailed(v("Trop d'essais : reconnectez-vous pour recevoir un nouveau code."))
        raise ValidationError({"code": v(f"Code incorrect. Essais restants : {restants}.")})
    enregistre.utilise = True
    enregistre.save(update_fields=["utilise"])
    auditer(utilisateur, A.CONNEXION, module="comptes", second_facteur=True)
    return jetons(utilisateur)


def renvoyer(jeton):
    """Nouveau code par courriel (au plus 3 fois par connexion, une minute d'intervalle) ; nouveau jeton d'étape."""
    utilisateur, renvois = lire_jeton(jeton)
    if renvois >= RENVOIS_MAX:
        raise ValidationError({"detail": v("Trop de codes demandés : reconnectez-vous.")})
    dernier = CodeConnexion.objects.filter(utilisateur=utilisateur).first()
    if dernier and timezone.now() - dernier.cree_le < INTERVALLE_RENVOI:
        raise ValidationError({"detail": v("Patientez une minute avant de demander un nouveau code.")})
    _envoyer(utilisateur)
    return _etape(utilisateur, renvois + 1)
