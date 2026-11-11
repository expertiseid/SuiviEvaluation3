import re

from django.db import transaction
from django.http import HttpResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.constants import ROLE_ADMIN

from .audit import A, auditer
from .langues import dans_la_langue_demandee
from .models import CODES_LANGUES, LANGUES, EvenementAudit, TraductionCorrigee
from .permissions import IsAdmin, IsAdminOrReadOnly

REPERE = re.compile(r"\{\d+\}")


def reperes_incoherents(source, traduction):
    """
    Les emplacements {0}, {1}… du texte français, que l'interface remplace par une valeur (un nom,
    un nombre) : la traduction doit garder exactement les mêmes. Renvoie le message d'erreur, ou None.
    """
    attendus, presents = set(REPERE.findall(source)), set(REPERE.findall(traduction))
    if attendus == presents:
        return None
    manquants, en_trop = sorted(attendus - presents), sorted(presents - attendus)
    morceaux = []
    if manquants:
        morceaux.append(f"il manque {', '.join(manquants)}")
    if en_trop:
        morceaux.append(f"{', '.join(en_trop)} n'existe pas dans le texte français")
    return "Emplacements à conserver tels quels : " + " ; ".join(morceaux) + "."


@api_view(["POST"])
def activite(request):
    """
    Activité de l'utilisateur sans échange avec le serveur (saisie longue) : signalée par l'interface
    pour que la session ne soit pas fermée pour inactivité. L'authentification la note (apps.core.inactivite).
    """
    return Response(status=204)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def traductions(request):
    """
    Au démarrage de l'interface (même avant connexion) : langues proposées, langue par défaut
    de l'organisation et, pour ?langue=xx, les traductions corrigées par l'Administrateur.
    """
    from apps.dashboard.models import ConfigurationMenu

    langue = request.query_params.get("langue", "")
    corrections = {}
    if langue in CODES_LANGUES:
        corrections = dict(TraductionCorrigee.objects.filter(langue=langue).values_list("source", "traduction"))
    return Response({
        "langue_defaut": ConfigurationMenu.courante().langue_defaut or "fr",
        "langues": [{"code": code, "nom": nom} for code, nom in LANGUES],
        "corrections": corrections,
    })


class TraductionCorrigeeSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = TraductionCorrigee
        fields = ("id", "langue", "source", "traduction", "updated_at", "modifie_par_nom")
        validators = []  # une nouvelle saisie remplace la précédente (voir create)

    def get_modifie_par_nom(self, obj):
        return str(obj.modifie_par) if obj.modifie_par else None

    def validate_langue(self, valeur):
        if valeur == "fr":
            raise serializers.ValidationError("Le français est la langue source : modifiez plutôt le vocabulaire.")
        return valeur

    def validate(self, attrs):
        erreur = reperes_incoherents(attrs["source"], attrs["traduction"])
        if erreur:
            raise serializers.ValidationError({"traduction": erreur})
        return attrs

    def create(self, validated_data):
        # Une correction par texte et par langue : une nouvelle saisie remplace l'ancienne.
        correction, _ = TraductionCorrigee.objects.update_or_create(
            langue=validated_data["langue"], source=validated_data["source"],
            defaults={"traduction": validated_data["traduction"], "modifie_par": self.context["request"].user},
        )
        return correction


class TraductionCorrigeeViewSet(viewsets.ModelViewSet):
    """Traductions corrigées (?langue=) : lecture pour tous, correction par l'Administrateur."""

    queryset = TraductionCorrigee.objects.all().order_by("source")
    serializer_class = TraductionCorrigeeSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_fields = ("langue",)
    pagination_class = None

    @action(detail=False, methods=["post"])
    def importer(self, request):
        """
        Import d'un fichier de traductions : {langue, lignes: [{source, traduction}]}, où une
        traduction nulle retire la correction. Tout ou rien : la moindre ligne invalide annule l'import.
        """
        langue = request.data.get("langue")
        lignes = request.data.get("lignes")
        if langue not in CODES_LANGUES or langue == "fr":
            raise serializers.ValidationError({"langue": "Langue inconnue ou langue source."})
        if not isinstance(lignes, list):
            raise serializers.ValidationError({"lignes": "Liste attendue."})
        erreurs = []
        for i, ligne in enumerate(lignes):
            source, traduction = (ligne or {}).get("source"), (ligne or {}).get("traduction")
            if not isinstance(source, str) or not source.strip() or not (traduction is None or isinstance(traduction, str)):
                erreurs.append({"source": source, "erreur": "Ligne illisible."})
            elif traduction is not None and not traduction.strip():
                erreurs.append({"source": source, "erreur": "Traduction vide."})
            elif traduction is not None and (erreur := reperes_incoherents(source, traduction)):
                erreurs.append({"source": source, "erreur": erreur})
        if erreurs:
            raise serializers.ValidationError({"lignes": erreurs})
        corrigees = retirees = 0
        with transaction.atomic():
            for ligne in lignes:
                if ligne["traduction"] is None:
                    # Supprimer objet par objet pour que l'historique garde la trace du retrait.
                    for correction in TraductionCorrigee.objects.filter(langue=langue, source=ligne["source"]):
                        correction.delete()
                        retirees += 1
                else:
                    TraductionCorrigee.objects.update_or_create(
                        langue=langue, source=ligne["source"],
                        defaults={"traduction": ligne["traduction"], "modifie_par": request.user},
                    )
                    corrigees += 1
        return Response({"corrigees": corrigees, "retirees": retirees})

    @action(detail=False)
    def journal(self, request):
        """Les 200 dernières modifications des traductions d'une langue (?langue=) : qui, quand, quoi."""
        if request.user.role != ROLE_ADMIN:
            raise PermissionDenied()
        historique = TraductionCorrigee.history.select_related("history_user").order_by("-history_date")
        if request.query_params.get("langue"):
            historique = historique.filter(langue=request.query_params["langue"])
        return Response([
            {
                "date": h.history_date,
                "utilisateur": str(h.history_user) if h.history_user else None,
                "type": {"+": "correction", "~": "correction", "-": "retrait"}[h.history_type],
                "source": h.source,
                "traduction": h.traduction,
            }
            for h in historique[:200]
        ])


# --- Journal d'audit ---------------------------------------------------------------------------------

ESSAI_TERMINE = ("Votre essai gratuit est terminé : la plateforme n'est plus accessible. Pour continuer, "
                 "abonnez-vous depuis le site.")


class ConnexionAuditee(TokenObtainPairView):
    """
    Connexion, inscrite au journal d'audit, réussie ou refusée (identifiant tenté seulement). Le mot de
    passe vérifié, un code est envoyé par courriel et seul un jeton d'étape est remis (apps.accounts.double_auth).

    Plateforme multi-organisations (adresse unique) : {courriel, password}. L'index des comptes dit dans
    quelle organisation chercher le compte ; {console: true} : opérateur Expertise-ID (base centrale,
    page de connexion à part).
    """

    def post(self, request, *args, **kwargs):
        from apps.organisations import contexte

        if contexte.actif():
            return self._connexion_par_courriel(request)
        return self._connexion_installation_unique(request)

    def _connexion_installation_unique(self, request):
        from apps.accounts import double_auth

        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            auditer(None, A.CONNEXION_ECHOUEE, module="comptes", identifiant=str(request.data.get("username", ""))[:150])
            # Profil d'organisation créé mais pas encore abonné : page « Vous devez vous abonner ».
            reponse = self._renvoi_profil(request.data.get("username"), request.data.get("password"))
            if reponse is not None:
                return reponse
            raise
        return self._etape_code(serializer.user)

    @staticmethod
    def _etape_code(utilisateur):
        from apps.accounts import double_auth

        etape = double_auth.demarrer(utilisateur)
        if etape:
            return Response(etape)
        auditer(utilisateur, A.CONNEXION, module="comptes")
        # Code non exigé (poste de développement) : jetons marqués comme ayant franchi l'étape.
        return Response(double_auth.jetons(utilisateur))

    def _connexion_par_courriel(self, request):
        from django.db.models import Q

        from apps.accounts.models import User
        from apps.organisations import comptes, contexte
        from apps.organisations.models import Organisation

        courriel = str(request.data.get("courriel") or request.data.get("username") or "").strip()
        mot_de_passe = request.data.get("password") or ""
        refus = Response({"detail": "Adresse courriel ou mot de passe incorrect.", "code": "identifiants_invalides"}, status=401)
        if request.data.get("console"):
            # Opérateurs Expertise-ID : comptes « superutilisateur » de la base centrale.
            operateur = User.objects.filter(Q(email__iexact=courriel) | Q(username__iexact=courriel),
                                            is_superuser=True, is_active=True).first() if courriel else None
            if operateur is None or not operateur.check_password(mot_de_passe):
                auditer(None, A.CONNEXION_ECHOUEE, module="comptes", identifiant=courriel[:150], espace="console")
                return refus
            return self._etape_code(operateur)
        org = comptes.organisation_du_courriel(courriel) if courriel else None
        if org is None or org.statut == Organisation.Statut.EN_ATTENTE:
            auditer(None, A.CONNEXION_ECHOUEE, module="comptes", identifiant=courriel[:150])
            return self._renvoi_profil(courriel, mot_de_passe) or refus
        if org.statut == Organisation.Statut.SUSPENDUE:
            return Response({"detail": "L'abonnement de votre organisation est suspendu. Contactez Expertise-ID.",
                             "code": "organisation_suspendue"}, status=403)
        with contexte.dans_organisation(org):
            utilisateur = User.objects.filter(email__iexact=courriel, is_active=True).first()
            if utilisateur is None or not utilisateur.check_password(mot_de_passe):
                auditer(None, A.CONNEXION_ECHOUEE, module="comptes", identifiant=courriel[:150])
                return refus
            # Essai gratuit terminé : la plateforme ne s'ouvre plus ; seule la connexion pour s'abonner (bouton
            # « J'ai déjà un espace : choisir une offre » du site, {abonnement: true}) mène à la page Abonnement.
            from apps.organisations import abonnement

            if org.offre == abonnement.ESSAI and abonnement.bloque(org) and request.data.get("abonnement") is not True:
                return Response({"detail": ESSAI_TERMINE, "code": "essai_termine"}, status=403)
            return self._etape_code(utilisateur)

    @staticmethod
    def _renvoi_profil(identifiant, mot_de_passe):
        """Identifiants d'un profil créé depuis l'accueil mais pas encore activé : page d'abonnement."""
        from apps.accounts import inscriptions
        from apps.accounts.models import DemandeInscription

        demande = inscriptions.demande_pour(identifiant, mot_de_passe)
        if demande is None or demande.statut == DemandeInscription.Statut.ACTIVEE:
            return None
        return Response({"code": "abonnement_requis", **inscriptions.resume(demande)}, status=403)


class EvenementAuditSerializer(serializers.ModelSerializer):
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = EvenementAudit
        fields = ("id", "date", "utilisateur_id", "utilisateur", "action", "action_libelle", "module", "objet", "details")
        read_only_fields = fields


def filtrer_audit(params):
    qs = EvenementAudit.objects.all()
    if params.get("action"):
        qs = qs.filter(action=params["action"])
    if params.get("utilisateur"):
        qs = qs.filter(utilisateur__icontains=params["utilisateur"])
    if params.get("objet"):
        qs = qs.filter(objet__icontains=params["objet"])
    if params.get("du"):
        qs = qs.filter(date__date__gte=params["du"])
    if params.get("au"):
        qs = qs.filter(date__date__lte=params["au"])
    return qs


class JournalAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Journal d'audit (Administrateur) : consultation filtrée (?action=&utilisateur=&objet=&du=&au=) et export
    Excel. Lecture seule : aucune route ne modifie ni ne supprime un événement.
    """

    serializer_class = EvenementAuditSerializer
    permission_classes = (IsAdmin,)

    def get_queryset(self):
        return filtrer_audit(self.request.query_params)

    @action(detail=False, methods=["get"])
    @dans_la_langue_demandee
    def exporter(self, request):
        from .audit import journal_excel

        evenements = list(self.get_queryset()[:50000])
        contenu = journal_excel(evenements)
        auditer(request.user, A.EXPORT, "Journal d'audit", module="comptes", nombre=len(evenements))
        reponse = HttpResponse(contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        reponse["Content-Disposition"] = "attachment; filename=journal_audit.xlsx"
        return reponse


# --- Identité de l'organisation et informations publiques de la plateforme -------------------------

FORMATS_LOGO = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
TAILLE_MAX_LOGO = 2 * 1024 * 1024


def _plateforme(request):
    from django.conf import settings

    from .models import IdentiteOrganisation

    identite = IdentiteOrganisation.courante()
    logo = None
    if identite.logo:
        from apps.organisations.contexte import parametre_org

        org = parametre_org()
        logo = request.build_absolute_uri(f"/api/v1/identite/logo/?v={int(identite.modifie_le.timestamp())}" + (f"&{org}" if org else ""))
    return {
        "nom": identite.nom,
        "logo": logo,
        # Démonstration (apps.accounts.demo) : visiteur connecté à la démo (mode_demo), ou démo proposée.
        "mode_demo": demo_actif(),
        "demo_disponible": _demo_disponible(),
        "url_demo": getattr(settings, "URL_DEMO", ""),
        "inscriptions": getattr(settings, "INSCRIPTIONS_OUVERTES", True),
        "contact": getattr(settings, "COURRIEL_ABONNEMENTS", ""),
        # Site vitrine : conditions d'utilisation, confidentialité, cookies (liens du pied de page).
        "url_site": getattr(settings, "URL_SITE", "").rstrip("/"),
        # Plateforme multi-organisations : organisation du compte connecté (sinon None).
        "multi_organisations": getattr(settings, "MULTI_ORGANISATIONS", False),
        "espace": _espace_courant(),
    }


def demo_actif():
    from apps.accounts.demo import actif

    return actif()


def _demo_disponible():
    """Une démonstration est proposée : installation de démo, espace de démo, ou adresse URL_DEMO."""
    from django.conf import settings

    from apps.accounts.demo import espace_demo
    from apps.organisations import contexte

    if not getattr(settings, "DEMO_OUVERTE", False):
        return False
    if demo_actif() or getattr(settings, "URL_DEMO", ""):
        return True
    return bool(contexte.actif() and espace_demo())


def _espace_courant():
    from apps.organisations import contexte

    org = contexte.courante()
    return {"sous_domaine": org.sous_domaine, "nom": org.nom} if org else None


@api_view(["GET", "PATCH"])
@authentication_classes([])
@permission_classes([AllowAny])
def identite(request):
    """
    GET (sans compte : écran d'accueil et de connexion) : nom, logo, démo, inscriptions.
    PATCH (Administrateur, multipart) : nom, logo (PNG, JPEG ou WebP, 2 Mo au plus), supprimer_logo.
    """
    from .models import IdentiteOrganisation

    if request.method == "PATCH":
        from apps.accounts.double_auth import JWTAvecDoubleFacteur

        authentification = JWTAvecDoubleFacteur().authenticate(request)
        if not authentification or authentification[0].role != ROLE_ADMIN:
            raise PermissionDenied("Réservé à l'Administrateur.")
        utilisateur = authentification[0]
        objet = IdentiteOrganisation.courante()
        changements = []
        if "nom" in request.data:
            objet.nom = (request.data.get("nom") or "").strip()[:200]
            changements.append("nom")
        if request.data.get("supprimer_logo") in ("true", True, "1"):
            if objet.logo:
                objet.logo.delete(save=False)
            objet.logo = ""
            changements.append("logo")
        fichier = request.FILES.get("logo")
        if fichier:
            from PIL import Image
            from rest_framework.exceptions import ValidationError

            if fichier.size > TAILLE_MAX_LOGO:
                raise ValidationError({"logo": "Le logo dépasse 2 Mo."})
            try:
                with Image.open(fichier) as image:
                    format_ = image.format
                    image.verify()
            except Exception:
                raise ValidationError({"logo": "Image illisible : choisissez un fichier PNG, JPEG ou WebP."})
            if format_ not in FORMATS_LOGO:
                raise ValidationError({"logo": "Format non accepté : choisissez un fichier PNG, JPEG ou WebP."})
            fichier.seek(0)
            if objet.logo:
                objet.logo.delete(save=False)
            objet.logo.save(f"logo.{format_.lower()}", fichier, save=False)
            changements.append("logo")
        objet.save()
        if changements:
            auditer(utilisateur, A.CONFIGURATION, "Identité de l'organisation", module="comptes",
                    operation="modification", champs=changements)
    return Response(_plateforme(request))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def logo_organisation(request):
    from django.http import FileResponse, Http404

    from .models import IdentiteOrganisation

    identite = IdentiteOrganisation.courante()
    if not identite.logo or not identite.logo.storage.exists(identite.logo.name):
        raise Http404
    extension = identite.logo.name.rsplit(".", 1)[-1].upper()
    reponse = FileResponse(identite.logo.open("rb"), content_type=FORMATS_LOGO.get("JPEG" if extension == "JPG" else extension, "image/png"))
    reponse["Cache-Control"] = "public, max-age=86400"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse
