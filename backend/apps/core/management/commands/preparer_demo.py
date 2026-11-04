"""
Prépare l'installation de démonstration : 5 projets complets, tous les onglets remplis.

À lancer SEULEMENT sur l'installation de démonstration (MODE_DEMO=True) : la commande remplace toutes
les données métier par des données fictives. Elle refuse de tourner ailleurs.

Étapes :
1. jeu complet de démonstration (seed_50_projets, seed_chaine_documents, seed_demo_complements) ;
2. on garde les 5 projets les mieux renseignés (planification, période, partenaires, équipe,
   indicateurs et valeurs, financement, documents, cadre logique, risques, suivi) et on supprime
   les autres ;
3. mécanisme de plaintes et dossiers à tous les états, sur ces 5 projets (seed_demo_plaintes, avec
   historique, pilotage et circuit confidentiel) : onglet « Retours des communautés » ;
4. compte « visiteur_demo » (connexion directe depuis la page d'accueil, rien ne s'enregistre).

Usage (installation de démonstration) :
    docker compose exec backend python manage.py preparer_demo
Plateforme multi-organisations : dans l'espace de démonstration (créé avec creer_organisation --demo) :
    docker compose exec backend python manage.py preparer_demo --organisation demo
"""
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q

NOMBRE_PROJETS = 5


def score(projet):
    """Nombre d'onglets remplis (et un peu de volume pour départager)."""
    from apps.documents.models import Document
    from apps.indicators.models import ValeurIndicateur
    from apps.suivi.models import PointSuivi

    onglets = {
        "planification": projet.activites.count(),
        "periode": projet.periodes_planification.count(),
        "partenaires": projet.roles_partenaires.count() + projet.partenaires_consortium.count(),
        "equipe": projet.intervenants.count(),
        "indicateurs": ValeurIndicateur.objects.filter(indicateur__projet=projet).count(),
        "financement": projet.financements.count(),
        "documents": Document.objects.filter(Q(projet=projet) | Q(activite__projet=projet)).count(),
        "cadre_logique": projet.activites.exclude(sources_verification="").count(),
        "risques": projet.risques.count(),
        "suivi": PointSuivi.objects.filter(Q(activite__projet=projet) | Q(sous_activite__activite__projet=projet)).count(),
        "retours": projet.dossiers_plaintes.count(),
    }
    remplis = sum(1 for n in onglets.values() if n)
    return remplis, sum(min(n, 20) for n in onglets.values()), onglets


class Command(BaseCommand):
    help = "Installation de démonstration : 5 projets complets (remplace les données métier ; MODE_DEMO obligatoire)."

    def add_arguments(self, parser):
        parser.add_argument("--organisation", help="Sous-domaine de l'espace de démonstration (plateforme multi-organisations).")

    def handle(self, *args, **options):
        if options.get("organisation"):
            from apps.organisations import contexte
            from apps.organisations.models import Organisation

            org = Organisation.objects.filter(sous_domaine=options["organisation"]).first()
            if org is None or not org.mode_demo:
                raise CommandError("Refusé : cet espace n'existe pas ou n'est pas un espace de démonstration "
                                   "(creer_organisation … --demo).")
            with contexte.dans_organisation(org):
                return self.preparer()
        return self.preparer()

    def preparer(self):
        from apps.accounts.demo import actif

        if not actif():
            raise CommandError("Refusé : cette commande remplace toutes les données. Elle ne tourne que sur "
                               "l'installation de démonstration (MODE_DEMO=True dans le .env).")
        from apps.accounts.demo import visiteur
        from apps.plaintes.models import Dossier
        from apps.projects.models import Projet
        from apps.projects.services import supprimer_projet_cascade

        self.stdout.write("1/4 Jeu de démonstration complet…")
        call_command("seed_50_projets", stdout=self.stdout)
        call_command("seed_chaine_documents", stdout=self.stdout)
        call_command("seed_demo_complements", stdout=self.stdout)

        self.stdout.write("2/4 Choix des 5 projets les plus complets…")
        classement = sorted(Projet.objects.all(), key=lambda p: score(p)[:2], reverse=True)
        gardes, autres = classement[:NOMBRE_PROJETS], classement[NOMBRE_PROJETS:]
        with transaction.atomic():
            for projet in autres:
                supprimer_projet_cascade(projet)

        # Après la réduction : les dossiers se répartissent sur les 5 projets gardés. Les options de
        # seed_demo_plaintes sont des modes séparés, d'où les quatre appels.
        self.stdout.write("3/4 Plaintes et retours des communautés…")
        call_command("seed_demo_plaintes", "--reinitialiser", stdout=self.stdout)
        for mode in ("--historique", "--pilotage", "--confidentiel"):
            call_command("seed_demo_plaintes", mode, stdout=self.stdout)
        for i, dossier in enumerate(Dossier.objects.filter(projet__isnull=True).order_by("id")):
            dossier.projet = gardes[i % len(gardes)]
            dossier.save(update_fields=["projet"])
        for projet in gardes:
            remplis, _, onglets = score(projet)
            vides = [nom for nom, n in onglets.items() if not n]
            self.stdout.write(f"   {projet.code} : {remplis}/{len(onglets)} onglets remplis"
                              + (f" (vides : {', '.join(vides)})" if vides else ""))

        self.stdout.write("4/4 Compte visiteur de démonstration…")
        visiteur()
        self.stdout.write(self.style.SUCCESS(f"Démonstration prête : {len(gardes)} projets, "
                                             f"{Dossier.objects.count()} dossiers de plaintes."))
