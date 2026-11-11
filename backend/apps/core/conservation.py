"""
Durée de conservation des données des bénéficiaires (RGPD, limitation de la conservation).

Chaque projet peut fixer une durée, en mois après sa date de fin (Projet.conservation_beneficiaires_mois ;
vide : conservées). Un bénéficiaire est anonymisé quand TOUS ses projets ont une durée et qu'elle est
écoulée : un bénéficiaire encore suivi par un autre projet garde son identité.

Anonymiser = effacer ce qui identifie la personne : nom, prénom, téléphone, pièce d'identité, position GPS,
jour et mois de naissance (l'année reste, pour les tranches d'âge), réponses en texte libre, signalements de
doublon et copies de l'historique. Restent le sexe, l'année de naissance, la zone, les statuts, les autres
réponses et les participations : les statistiques des projets restent justes.

Lancé chaque jour par la tâche planifiée (check_deadlines), dans chaque espace.
"""
import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .audit import A, auditer

NOM_ANONYME = "Anonyme"


def ajouter_mois(jour: datetime.date, mois: int) -> datetime.date:
    annee, reste = divmod(jour.month - 1 + mois, 12)
    for dernier_jour in (jour.day, 30, 29, 28):  # 31 janvier + 1 mois → fin février
        try:
            return jour.replace(year=jour.year + annee, month=reste + 1, day=dernier_jour)
        except ValueError:
            continue
    raise ValueError(jour)


def projets_echus(aujourdhui=None) -> tuple[set, set]:
    """(projets dont la conservation des bénéficiaires est écoulée, autres projets)."""
    from apps.projects.models import Projet

    aujourdhui = aujourdhui or timezone.localdate()
    echus, autres = set(), set()
    for pk, fin, mois in Projet.objects.values_list("pk", "date_fin", "conservation_beneficiaires_mois"):
        (echus if mois and fin and ajouter_mois(fin, mois) <= aujourdhui else autres).add(pk)
    return echus, autres


def a_anonymiser(aujourdhui=None):
    from apps.beneficiaries.models import Beneficiaire

    echus, autres = projets_echus(aujourdhui)
    if not echus:
        return Beneficiaire.objects.none()
    return (Beneficiaire.objects.filter(date_anonymisation=None, participations__projet__in=echus)
            .exclude(participations__projet__in=autres).distinct())


def anonymiser_beneficiaire(beneficiaire):
    from apps.beneficiaries.models import SignalementDoublon, VariableBeneficiaire

    textes = {str(pk) for pk in VariableBeneficiaire.objects.filter(type=VariableBeneficiaire.Type.TEXTE).values_list("pk", flat=True)}
    with transaction.atomic():
        beneficiaire.nom, beneficiaire.prenom = NOM_ANONYME, ""
        beneficiaire.telephone = beneficiaire.numero_piece_identite = beneficiaire.type_piece = ""
        beneficiaire.latitude = beneficiaire.longitude = None
        if beneficiaire.date_naissance:
            beneficiaire.date_naissance = beneficiaire.date_naissance.replace(month=7, day=1)
        beneficiaire.reponses = {cle: valeur for cle, valeur in (beneficiaire.reponses or {}).items() if cle not in textes}
        beneficiaire.date_anonymisation = timezone.localdate()
        beneficiaire.save()
        SignalementDoublon.objects.filter(Q(beneficiaire_1=beneficiaire) | Q(beneficiaire_2=beneficiaire)).delete()
        beneficiaire.history.all().delete()  # l'identité ne doit survivre dans aucune copie


def appliquer(aujourdhui=None) -> int:
    """Anonymise les bénéficiaires dont la durée de conservation est écoulée ; renvoie leur nombre."""
    nombre = 0
    for beneficiaire in a_anonymiser(aujourdhui):
        anonymiser_beneficiaire(beneficiaire)
        nombre += 1
    if nombre:
        auditer(None, A.SUPPRESSION, f"Bénéficiaires anonymisés à l'échéance de conservation : {nombre}",
                module="beneficiaires", operation="anonymisation automatique")
    return nombre
