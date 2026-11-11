from django.db.models import ProtectedError
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.core.audit import A, auditer
from apps.core.permissions import IsAdmin, IsAdminOrReadOnly
from apps.core.vocabulaire import v

from . import double_auth
from .models import Role, User
from .serializers import DemandeInscriptionSerializer, RoleSerializer, UserSerializer, UserWriteSerializer


class UserViewSet(viewsets.ModelViewSet):
    """CRUD des utilisateurs — réservé à l'Administrateur, sauf /me/."""

    queryset = User.objects.all().order_by("username")
    filterset_fields = ("role", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ("me", "list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdmin()]

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Son propre compte ; PATCH : seulement ses préférences (langue de l'interface)."""
        if request.method == "PATCH":
            from apps.core.models import CODES_LANGUES

            langue = request.data.get("langue", "")
            if langue not in ("", *CODES_LANGUES):
                raise ValidationError({"langue": "Langue inconnue."})
            request.user.langue = langue
            request.user.save(update_fields=["langue"])
        return Response(UserSerializer(request.user).data)

    # Droits d'un compte : inscrits au journal d'audit (champs changés seulement, jamais le mot de passe).
    CHAMPS_DROITS = ("role", "niveau_acces", "acces_modules", "is_active")

    def perform_create(self, serializer):
        compte = serializer.save()
        auditer(self.request.user, A.PERMISSION, compte.username, module="comptes", operation="creation",
                **{c: getattr(compte, c) for c in self.CHAMPS_DROITS})

    def perform_update(self, serializer):
        avant = {c: getattr(serializer.instance, c) for c in self.CHAMPS_DROITS}
        compte = serializer.save()
        changes = {c: [avant[c], getattr(compte, c)] for c in self.CHAMPS_DROITS if avant[c] != getattr(compte, c)}
        if changes:
            auditer(self.request.user, A.PERMISSION, compte.username, module="comptes", operation="modification", **changes)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError({"detail": "Impossible de supprimer ton propre compte."})
        try:
            nom = instance.username
            instance.delete()
            auditer(self.request.user, A.PERMISSION, nom, module="comptes", operation="suppression")
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": v('Impossible de supprimer cet utilisateur : il a déjà des données rattachées (valeurs saisies, documents, points de suivi...). Désactive-le plutôt (Actif = Non).')
                }
            )


class RoleViewSet(viewsets.ModelViewSet):
    """Référentiel des rôles — lecture pour tous, gestion réservée à l'Administrateur."""

    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = (IsAdminOrReadOnly,)
    pagination_class = None

    def perform_destroy(self, instance):
        if instance.systeme:
            raise ValidationError({"detail": "Rôle système : il peut être renommé, mais pas supprimé."})
        if User.objects.filter(role=instance.code).exists():
            raise ValidationError(
                {"detail": v("Impossible de supprimer ce rôle : des utilisateurs l'ont encore. Change d'abord leur rôle.")}
            )
        instance.delete()


# --- Connexion en deux temps (sans jeton de connexion : le jeton d'étape suffit) -------------------

class LimiteSecondFacteur(AnonRateThrottle):
    rate = "30/hour"


def _etape(vue):
    return api_view(["POST"])(authentication_classes([])(permission_classes([AllowAny])(throttle_classes([LimiteSecondFacteur])(vue))))


@_etape
def connexion_code(request):
    """{jeton, code} : code reçu par courriel ; renvoie les jetons de connexion."""
    with double_auth.espace_du_jeton(request.data.get("jeton", "")) as jeton:
        return Response(double_auth.verifier(jeton, request.data.get("code", "")))


@_etape
def connexion_renvoyer(request):
    """{jeton} : envoie un nouveau code ; renvoie le nouveau jeton d'étape."""
    with double_auth.espace_du_jeton(request.data.get("jeton", "")) as jeton:
        return Response(double_auth.renvoyer(jeton))


# --- Mot de passe oublié (apps.accounts.mot_de_passe) ---------------------------------------------

class LimiteMotDePasse(AnonRateThrottle):
    rate = "10/hour"


def _mot_de_passe(vue):
    return api_view(["POST"])(authentication_classes([])(permission_classes([AllowAny])(throttle_classes([LimiteMotDePasse])(vue))))


@_mot_de_passe
def mot_de_passe_oublie(request):
    """{courriel, langue?} : envoie le lien si un compte porte cette adresse ; même réponse dans tous les cas."""
    from . import mot_de_passe

    mot_de_passe.demander(request.data.get("courriel", ""), str(request.data.get("langue", ""))[:5])
    return Response({"detail": v("Si un compte existe pour cette adresse, un lien pour choisir un nouveau mot de passe "
                                 "vient d'y être envoyé. Il est valable 1 heure.")})


@_mot_de_passe
def mot_de_passe_verifier(request):
    """{jeton} : le lien est-il encore valable ? (adresse masquée du compte)"""
    from . import mot_de_passe

    return Response(mot_de_passe.verifier(request.data.get("jeton", "")))


@_mot_de_passe
def mot_de_passe_changer(request):
    """{jeton, mot_de_passe} : enregistre le nouveau mot de passe ; le lien ne sert plus."""
    from . import mot_de_passe

    mot_de_passe.changer(request.data.get("jeton", ""), request.data.get("mot_de_passe", ""))
    return Response({"detail": v("Votre mot de passe a été changé. Vous pouvez vous connecter.")})


# --- Inscription d'une organisation (page d'accueil) -----------------------------------------------

class LimiteInscription(AnonRateThrottle):
    rate = "10/hour"


def _public(vue):
    return api_view(["POST"])(authentication_classes([])(permission_classes([AllowAny])(throttle_classes([LimiteInscription])(vue))))


@_public
def inscription(request):
    """Création du profil d'une organisation ; renvoie la référence pour la page d'abonnement."""
    from . import inscriptions

    if request.data.get("site_web"):  # champ piège, invisible pour une personne
        raise ValidationError({"detail": "Envoi refusé."})
    return Response(inscriptions.resume(inscriptions.creer(request.data)), status=201)


@_public
def inscription_offre(request):
    """{reference, offre, message, moyen?, mois?, tranches?} : offre transmise à Expertise-ID (Partenariat, ou carte bancaire)."""
    from . import inscriptions

    demande = inscriptions.demande_du_jeton(request.data.get("reference"))
    return Response(inscriptions.resume(inscriptions.choisir_offre(
        demande, request.data.get("offre"), request.data.get("message") or "", request.data.get("moyen") or "",
        request.data.get("mois") or 1, request.data.get("tranches") or 0)))


# --- Paiement en ligne de l'abonnement (apps.organisations.paiement) -------------------------------

class LimiteEtatPaiement(AnonRateThrottle):
    scope = "etat_paiement"  # compté à part : ne doit pas épuiser la limite des inscriptions
    rate = "300/hour"  # la page de retour redemande le statut toutes les quelques secondes


@_public
def inscription_paiement(request):
    """{reference, offre, mois, tranches, message, langue} : renvoie le lien vers la page de paiement de CinetPay."""
    from apps.organisations import paiement

    from . import inscriptions

    demande = inscriptions.demande_du_jeton(request.data.get("reference"))
    suite = paiement.creer(demande, request.data.get("offre"), request.data.get("mois") or 1, request.data.get("tranches") or 0,
                           request.data.get("message") or "", request.data.get("langue") or "fr")
    return Response({"lien": suite.lien, "paiement": suite.reference, "montant": suite.montant, "devise": suite.devise})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def inscription_tarifs(request):
    """Prix des offres payées en ligne, affichés par le site (page d'accueil et inscription)."""
    from apps.organisations import paiement

    return Response(paiement.tarifs())


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LimiteEtatPaiement])
def inscription_paiement_etat(request, reference):
    """Retour sur le site après le paiement : payé, en attente ou échoué."""
    from apps.organisations import paiement

    return Response(paiement.etat(reference))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def inscription_paiement_notification(request):
    """Notification de CinetPay (notify_token vérifié, statut redemandé à CinetPay). Répond toujours 200."""
    from apps.organisations import paiement

    paiement.notifier(request.data)
    return Response({"recu": True})


class DemandeInscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """Profils d'organisations créés depuis la page d'accueil (Administrateur) ; …/statut/ pour les suivre."""

    permission_classes = (IsAdmin,)
    pagination_class = None

    def get_queryset(self):
        from apps.organisations import contexte

        from .models import DemandeInscription

        # Plateforme multi-organisations : les demandes de toutes les organisations sont dans la base
        # centrale ; elles ne se consultent que dans la console Expertise-ID, jamais depuis un espace.
        if contexte.actif():
            raise PermissionDenied("Les demandes d'inscription se consultent dans la console Expertise-ID.")
        return DemandeInscription.objects.all()

    serializer_class = DemandeInscriptionSerializer

    @action(detail=True, methods=["post"])
    def statut(self, request, pk=None):
        from .models import DemandeInscription

        demande = self.get_object()
        if request.data.get("statut") not in DemandeInscription.Statut.values:
            raise ValidationError({"statut": "Statut inconnu."})
        demande.statut = request.data["statut"]
        demande.save(update_fields=["statut"])
        return Response(self.get_serializer(demande).data)
