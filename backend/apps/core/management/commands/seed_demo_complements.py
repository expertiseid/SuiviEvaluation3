"""
Complète les données de démonstration là où les autres commandes ne mettent rien : variables des
bénéficiaires (avec réponses), doublons signalés, liens de partage, pièces justificatives des
valeurs d'indicateurs. Sans effet sur ce qui existe déjà (relançable).

Usage : docker compose exec backend python manage.py seed_demo_complements
"""
import random
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

VARIABLES = [
    ("Taille du ménage", "NOMBRE", [], "personnes", lambda a: a.randint(2, 14)),
    ("Superficie cultivée", "NOMBRE", [], "ha", lambda a: round(a.uniform(0.25, 6), 2)),
    ("Personne en situation de handicap dans le ménage", "OUI_NON", [], "", lambda a: a.random() < 0.12),
    ("Source principale d'eau", "CHOIX", ["Forage", "Puits", "Borne fontaine", "Marigot"], "",
     lambda a: a.choice(["Forage", "Forage", "Puits", "Borne fontaine", "Marigot"])),
    ("Activités génératrices de revenus", "CHOIX_MULTIPLE", ["Agriculture", "Élevage", "Commerce", "Artisanat"], "",
     lambda a: a.sample(["Agriculture", "Élevage", "Commerce", "Artisanat"], a.randint(1, 2))),
]


def _piece_pdf(titre, lignes):
    from weasyprint import HTML

    corps = "".join(f"<p>{ligne}</p>" for ligne in lignes)
    return HTML(string=f"<h2>{titre}</h2>{corps}<p style='margin-top:40px'>Signature du responsable : ______</p>").write_pdf()


class Command(BaseCommand):
    help = "Complète les données de démonstration (variables, doublons, partages, pièces justificatives)."

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.accounts.models import User
        from apps.beneficiaries.models import Beneficiaire, SignalementDoublon, VariableBeneficiaire
        from apps.documents.models import PieceJustificative
        from apps.indicators.models import ValeurIndicateur
        from apps.projects.models import Projet
        from apps.reports.models import LienPartage

        alea = random.Random(31)
        admin = User.objects.filter(role="ADMIN", is_active=True).order_by("id").first()

        # Variables des bénéficiaires et réponses (environ deux bénéficiaires sur trois).
        variables = []
        for ordre, (libelle, type_, choix, unite, _) in enumerate(VARIABLES, start=1):
            variable, _ = VariableBeneficiaire.objects.get_or_create(
                libelle=libelle, defaults={"type": type_, "choix": choix, "unite": unite, "ordre": ordre},
            )
            variables.append(variable)
        reponses = 0
        for beneficiaire in Beneficiaire.objects.all():
            if beneficiaire.reponses or alea.random() > 0.66:
                continue
            beneficiaire.reponses = {str(v.id): tirer(alea) for v, (*_, tirer) in zip(variables, VARIABLES)}
            Beneficiaire.objects.filter(pk=beneficiaire.pk).update(reponses=beneficiaire.reponses)
            reponses += 1

        # Doublons : quelques personnes enregistrées deux fois (orthographe proche, même téléphone).
        doublons = 0
        if not SignalementDoublon.objects.exists():
            # Parmi les inscrits d'un projet en cours (un projet clôturé est en lecture seule).
            ouverts = Beneficiaire.objects.exclude(telephone="").exclude(participations__projet__statut=Projet.Statut.CLOTURE)
            for original in ouverts.filter(participations__isnull=False).distinct().order_by("?")[:6]:
                copie = Beneficiaire.objects.create(
                    nom=original.nom, prenom=original.prenom[:-1] + "e" if len(original.prenom) > 3 else original.prenom + "e",
                    sexe=original.sexe, date_naissance=original.date_naissance, telephone=original.telephone,
                    pays=original.pays, zone=original.zone,
                )
                for participation in original.participations.all()[:1]:
                    participation.pk = None
                    participation.beneficiaire = copie
                    participation.save()
                SignalementDoublon.objects.create(
                    beneficiaire_1=original, beneficiaire_2=copie, score=round(alea.uniform(0.86, 0.97), 3),
                    methode=SignalementDoublon.Methode.SIMILARITE,
                )
                doublons += 1

        # Liens de partage (lecture seule, sans compte).
        partages = 0
        if admin and not LienPartage.objects.exists():
            LienPartage.objects.create(type=LienPartage.Type.TABLEAU_DE_BORD, libelle="Comité de pilotage", cree_par=admin,
                                       expire_le=timezone.localdate() + timedelta(days=90))
            for projet in Projet.objects.order_by("id")[:2]:
                LienPartage.objects.create(type=LienPartage.Type.SUIVI_PROJET, projet=projet, cree_par=admin,
                                           libelle=f"Bailleur — {projet.code}", contenu=LienPartage.Contenu.TOUT)
            partages = LienPartage.objects.count()

        # Pièces justificatives de quelques valeurs d'indicateurs.
        pieces = 0
        if admin and not PieceJustificative.objects.exists():
            for valeur in ValeurIndicateur.objects.select_related("indicateur").order_by("-periode_fin")[:20]:
                titre = f"Fiche de collecte — {valeur.indicateur}"[:180]
                contenu = _piece_pdf(titre, [
                    f"Période : du {valeur.periode_debut:%d/%m/%Y} au {valeur.periode_fin:%d/%m/%Y}",
                    f"Valeur constatée : {valeur.valeur_realisee}",
                    "Source : registre de terrain, vérifié par le chargé de suivi-évaluation.",
                ])
                piece = PieceJustificative(nom=titre, type_document="Fiche de collecte", uploaded_by=admin, valeur_indicateur=valeur)
                piece.fichier.save(f"fiche_collecte_{valeur.id}.pdf", ContentFile(contenu), save=True)
                pieces += 1

        self.stdout.write(self.style.SUCCESS(
            f"Variables : {len(variables)} ({reponses} bénéficiaires renseignés) ; doublons signalés : {doublons} ; "
            f"liens de partage : {partages} ; pièces justificatives : {pieces}."
        ))
