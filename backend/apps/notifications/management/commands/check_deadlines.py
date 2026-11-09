from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.core.vocabulaire import v
from apps.notifications.models import Notification
from apps.notifications.services import lister_echeances, notifier
from apps.projects.models import Projet

User = get_user_model()

LIBELLE_TYPE = {
    "ACTIVITE": "Activité",
    "SOUS_ACTIVITE": "Sous-activité",
    "PROJET": "Projet",
}


class Command(BaseCommand):
    help = (
        "Vérifie les activités, sous-activités et projets dont l'échéance est proche ou dépassée et "
        "notifie tous les utilisateurs actifs. À planifier périodiquement (cron/service scheduler)."
    )

    def handle(self, *args, **options):
        # Une échéance qui approche ou qui est dépassée concerne tout le monde par défaut, affecté
        # au projet ou non — pas de restriction aux seuls utilisateurs_affectes (souvent vide en
        # pratique), pour ne jamais laisser une échéance réelle passer inaperçue.
        destinataires = list(User.objects.filter(is_active=True))
        tous_projets_ids = list(Projet.objects.values_list("id", flat=True))

        total = 0
        for echeance in lister_echeances(tous_projets_ids):
            type_libelle = LIBELLE_TYPE[echeance["type"]]
            if echeance["est_rappel"]:
                titre = f"Rappel programmé : {echeance['libelle']}"
            elif echeance["type"] == "PROJET":
                titre = (
                    f"Projet arrivé à échéance : {echeance['libelle']}"
                    if echeance["en_retard"]
                    else f"Échéance de projet proche : {echeance['libelle']}"
                )
            else:
                titre = (
                    f"{type_libelle} en retard : {echeance['libelle']}"
                    if echeance["en_retard"]
                    else f"Échéance proche : {echeance['libelle']}"
                )
            total += self.notifier_echeance(
                destinataires=destinataires,
                titre=titre,
                projet_nom=echeance["projet_nom"],
                echeance=echeance["date_fin"],
                lien=echeance["lien"],
            )

        self.stdout.write(self.style.SUCCESS(f"{total} notification(s) d'échéance créée(s)."))
        # Mécanisme de plaintes : rappels et escalades sur les échéances des dossiers.
        from django.core.management import call_command

        call_command("verifier_echeances_plaintes", stdout=self.stdout)
        # Corbeille des documents : vidée de ce qui y est depuis plus de 30 jours.
        from apps.documents.corbeille import purger

        purges = purger()
        if purges:
            self.stdout.write(f"{purges} élément(s) de la corbeille supprimé(s) définitivement (plus de 30 jours).")
        # Espace de stockage presque plein ou plein : administrateurs prévenus (une fois par seuil).
        from apps.organisations import quota

        quota.alerter()

    def notifier_echeance(self, *, destinataires, titre, projet_nom, echeance, lien):
        deja_notifie = Notification.objects.filter(
            destinataire__in=destinataires, type=Notification.Type.ECHEANCE_ACTIVITE, titre=titre
        ).values_list("destinataire_id", flat=True)
        a_notifier = [d for d in destinataires if d.id not in set(deja_notifie)]
        if not a_notifier:
            return 0
        notifier(
            a_notifier,
            Notification.Type.ECHEANCE_ACTIVITE,
            titre,
            message=f"{v('Projet ')}{projet_nom} — échéance prévue le {echeance}.",
            lien=lien,
        )
        return len(a_notifier)
