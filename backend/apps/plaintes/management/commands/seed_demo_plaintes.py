"""
Données de démonstration du mécanisme de plaintes et retours : mécanisme « standard » activé,
point focal du circuit confidentiel, et une quarantaine de dossiers reçus par tous les canaux sur
les six derniers mois, à des états d'avancement variés. Les dossiers passent par l'interface
d'entrée commune (reception.recevoir) : mêmes règles que le formulaire public et la saisie agent.

Chaque dossier est ensuite traité par les vraies opérations (traitement.py) — affectation, étapes,
notes, décision, communication, clôture, un recours — avec des dates cohérentes : son journal
raconte son histoire.

Usage : docker compose exec backend python manage.py seed_demo_plaintes [--reinitialiser]
        … seed_demo_plaintes --historique : complète seulement le journal des dossiers qui n'en ont pas
        (sans rien supprimer).
Les dossiers confidentiels sont visibles de l'Administrateur et des points focaux du circuit
confidentiel (admin et pf_psea / demo1234!).
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants import ROLE_CHARGE_SE
from apps.accounts.models import User

MOT_DE_PASSE = "demo1234!"

# (catégorie ou sous-catégorie, type, description, concerne le personnel)
RETOURS = [
    ("Critères de sélection", "Plainte", "Notre ménage remplit les critères mais n'a pas été retenu pour les transferts monétaires. Nous voulons savoir pourquoi.", False),
    ("Critères de sélection", "Question", "Comment sont choisis les ménages bénéficiaires des kits agricoles cette saison ?", False),
    ("Exclusion d'un ménage", "Plainte", "Ma mère, veuve avec cinq enfants, a été retirée de la liste lors du dernier recensement.", False),
    ("Exclusion d'un ménage", "Plainte", "Trois ménages déplacés du quartier ne figurent pas sur la liste des bénéficiaires.", False),
    ("Quantité ou qualité", "Plainte", "Les sacs de maïs reçus pesaient moins que les 50 kg annoncés.", False),
    ("Quantité ou qualité", "Plainte", "Une partie des semences distribuées n'a pas germé.", False),
    ("Retard", "Plainte", "La distribution prévue le 15 n'a toujours pas eu lieu et personne ne nous a informés.", False),
    ("Retard", "Question", "Quand reprendront les travaux du forage arrêtés depuis un mois ?", False),
    ("Lieu ou horaires", "Suggestion", "Le site de distribution est trop loin pour les personnes âgées : il faudrait un point au marché.", False),
    ("Lieu ou horaires", "Plainte", "Nous avons attendu toute la journée au soleil sans abri ni eau.", False),
    ("Information et communication", "Question", "Où peut-on consulter la liste définitive des bénéficiaires ?", False),
    ("Information et communication", "Suggestion", "Annoncer les distributions à la radio communautaire en langue locale.", False),
    ("Accès aux services", "Plainte", "Le centre de santé réhabilité est fermé le week-end, les femmes doivent aller en ville.", False),
    ("Accès aux services", "Plainte", "La pompe de l'école est en panne depuis deux semaines, les élèves n'ont plus d'eau.", False),
    ("Accès aux services", "Question", "Les enfants non inscrits peuvent-ils bénéficier de la cantine scolaire ?", False),
    ("Suggestion d'amélioration", "Suggestion", "Former des femmes du village à l'entretien des latrines pour qu'elles durent plus longtemps.", False),
    ("Suggestion d'amélioration", "Suggestion", "Prévoir des bancs supplémentaires dans les nouvelles salles de classe.", False),
    ("Comportement du personnel", "Plainte", "Un agent de distribution parle mal aux personnes âgées et les fait attendre.", False),
    (None, "Remerciement", "Merci pour la nouvelle maternité : ma fille y a accouché en sécurité.", False),
    (None, "Remerciement", "Les cours d'alphabétisation ont changé la vie des femmes du groupement.", False),
    (None, "Remerciement", "Le forage fonctionne très bien, nous n'allons plus chercher l'eau au marigot.", False),
    (None, "Question", "Le projet recrute-t-il des maçons locaux pour les prochains chantiers ?", False),
    ("Autre", "Suggestion", "Planter des arbres autour de la nouvelle école pour l'ombre.", False),
    # Sensibles : transmis au circuit confidentiel.
    ("Exploitation et abus sexuels", "Signalement", "Signalement recueilli par téléphone : demande de faveurs en échange de l'inscription sur une liste.", False),
    ("Fraude et corruption", "Signalement", "Des bons de distribution seraient revendus par une personne du comité de gestion.", False),
    ("Violence ou atteinte à la protection (dont enfants)", "Signalement", "Un enfant travaillerait sur le chantier de l'école pendant les heures de classe.", False),
    ("Menaces et représailles", "Signalement", "Une personne dit avoir été menacée après avoir déposé une plainte le mois dernier.", False),
    (None, "Plainte", "Un superviseur du partenaire exige une contribution en argent pour accéder au service.", True),
]

CANAUX_AGENT = ["TELEPHONE", "EN_PERSONNE", "REUNION", "BOITE", "COURRIER", "COURRIEL"]
NOMS = ["Awa Ouédraogo", "Issa Sawadogo", "Mariam Kaboré", "Boukary Zongo", "Salimata Traoré", "Adama Compaoré",
        "Fatimata Diallo", "Moussa Ilboudo", "Rasmata Ouattara", "Hamidou Sankara"]
LIEUX = ["Koudougou, secteur 3", "Kaya, village de Basma", "Fada N'Gourma", "Djibo, site de déplacés", "Ouahigouya",
         "Tenkodogo, marché central", "Dori", "Ziniaré, école de Nagréongo", "Gaoua", "Bogandé"]


DECISIONS = {
    "Plainte": [
        "Vérification faite sur place : la plainte est fondée. Correction demandée au partenaire de mise en œuvre.",
        "Le ménage est réintégré sur la liste après vérification des critères.",
        "Le complément manquant sera distribué lors du prochain passage.",
        "Plainte non fondée : les critères ont été appliqués correctement ; explication donnée au plaignant.",
    ],
    "Suggestion": ["Suggestion retenue : elle sera mise en œuvre au prochain cycle.", "Suggestion transmise à l'équipe du projet pour étude."],
    "Question": ["Information communiquée au plaignant."],
    "Remerciement": ["Remerciement transmis à l'équipe du projet."],
    "Signalement": ["Mesures de protection prises selon le protocole de l'organisation ; suivi assuré par le point focal."],
}
NOTES = [
    ("Visite de terrain prévue avec le chef de site.", False),
    ("Le partenaire a confirmé le problème ; correction en cours.", True),
    ("Liste de distribution vérifiée avec le comité villageois.", False),
    ("Remplacement des articles défectueux organisé.", True),
]


def dater_echeances(dossier):
    """Échéances calculées depuis l'entrée réelle dans l'étape en cours (d'après le journal)."""
    from apps.plaintes import delais
    from apps.plaintes.models import ActionDossier, Dossier

    derniere = ActionDossier.objects.filter(dossier=dossier, type__in=["ETAPE", "REOUVERTURE", "RECOURS"]).order_by("-date").first()
    dossier = Dossier.objects.select_related("categorie__parent", "priorite", "etape").get(pk=dossier.pk)
    entree = timezone.localtime(derniere.date).date() if derniere else dossier.date_reception
    delais.recalculer(dossier, entree_etape=entree)


def historiser(dossier, statut, rang, depart, alea, gestionnaires, points_focaux, chef):
    try:
        _historiser(dossier, statut, rang, depart, alea, gestionnaires, points_focaux, chef)
    finally:
        dater_echeances(dossier)


def _historiser(dossier, statut, rang, depart, alea, gestionnaires, points_focaux, chef):
    """
    Fait passer le dossier par les opérations de traitement jusqu'à l'état visé, puis date chaque
    action (et les dates du dossier) en avançant de quelques jours à partir de sa réception.
    """
    from datetime import datetime, time

    from apps.plaintes import traitement as t
    from apps.plaintes.models import ActionDossier, Dossier

    aujourdhui = timezone.localdate()
    curseur = [depart]

    def faire(fonction, auteur, *args, jours=(1, 3)):
        connues = set(ActionDossier.objects.filter(dossier=dossier).values_list("id", flat=True))
        fonction(dossier, auteur, *args)
        curseur[0] = min(curseur[0] + timedelta(days=alea.randint(*jours)), aujourdhui)
        moment = timezone.make_aware(datetime.combine(curseur[0], time(alea.randint(8, 16), alea.randint(0, 59))))
        ActionDossier.objects.filter(dossier=dossier).exclude(id__in=connues).update(date=moment)
        return curseur[0]

    ActionDossier.objects.filter(dossier=dossier, type="RECEPTION").update(
        date=timezone.make_aware(datetime.combine(depart, time(9, 0))))
    if statut == "RECU":
        return
    gestionnaire = alea.choice(points_focaux if dossier.sensible else gestionnaires)
    faire(t.affecter, chef, gestionnaire.pk)
    etapes = list(dossier.circuit.etapes.order_by("ordre", "id"))
    cible = etapes[min(rang, len(etapes) - 2)]
    if cible != dossier.etape:
        faire(t.changer_etape, gestionnaire, {"etape": cible.pk}, jours=(3, 10))
    if alea.random() < 0.6:
        texte, corrective = alea.choice(NOTES)
        faire(t.noter, gestionnaire, {"texte": texte, "corrective": corrective})
    if statut == "EN_COURS":
        return
    decision = alea.choice(DECISIONS.get(dossier.type_retour.nom, DECISIONS["Question"]))
    jour = faire(t.decider, gestionnaire, {"decision": decision}, jours=(2, 6))
    dossier.date_decision = jour  # l'objet en mémoire est réenregistré par l'opération suivante
    Dossier.objects.filter(pk=dossier.pk).update(date_decision=jour)
    if not dossier.anonyme:
        canal = dossier.mode_reponse if dossier.mode_reponse in ("TELEPHONE", "SMS") and dossier.telephone else "EN_PERSONNE"
        jour = faire(t.communiquer, gestionnaire, {"sens": "SORTANT", "canal": canal, "objet": "DECISION",
                                                   "texte": "Décision expliquée au plaignant."})
        dossier.date_reponse = jour  # l'objet en mémoire est réenregistré par l'opération suivante
    Dossier.objects.filter(pk=dossier.pk).update(date_reponse=jour)
    if statut == "REPONDU":
        return
    non_fonde = decision.startswith("Plainte non fondée")
    jour = faire(t.cloturer, gestionnaire, {
        "issue": "NON_FONDE" if non_fonde else "RESOLU",
        "motif": "Explication donnée, aucune autre suite." if non_fonde else "Problème traité, le plaignant a été informé.",
        "retour_donne": not dossier.anonyme,
        "raison_sans_retour": "Plaignant anonyme : réponse consultable avec son code de suivi.",
    }, jours=(1, 5))
    dossier.date_cloture = jour  # l'objet en mémoire est réenregistré par l'opération suivante
    Dossier.objects.filter(pk=dossier.pk).update(date_cloture=jour)


class Command(BaseCommand):
    help = "Remplit le mécanisme de plaintes et retours avec des données de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--reinitialiser", action="store_true", help="Efface d'abord tout le module plaintes.")
        parser.add_argument("--historique", action="store_true",
                            help="Complète seulement le journal des dossiers qui n'en ont pas, sans rien supprimer.")
        parser.add_argument("--confidentiel", action="store_true",
                            help="Ajoute seulement la démonstration du circuit confidentiel (lot 5), sans rien supprimer.")

    def handle(self, *args, **options):
        from apps.plaintes import delais

        # Données de démonstration : personne n'est notifié de dossiers fictifs.
        delais.NOTIFICATIONS_ACTIVES = False
        try:
            self.remplir(**options)
        finally:
            delais.NOTIFICATIONS_ACTIVES = True

    @transaction.atomic
    def remplir(self, **options):
        from apps.plaintes import models as m
        from apps.plaintes.controles import controler_activation
        from apps.plaintes.modeles_mecanisme import appliquer_modele
        from apps.plaintes.reception import recevoir
        from apps.projects.models import Projet

        if options["historique"]:
            return self.completer_historique()
        if options["confidentiel"]:
            return self.confidentiel_de_demonstration()
        if m.Dossier.objects.exists() or m.Categorie.objects.exists():
            if not options["reinitialiser"]:
                raise CommandError("Le module contient déjà des données : relancer avec --reinitialiser pour les effacer.")
            m.Dossier.objects.all().delete()
            m.CompteurDossiers.objects.all().delete()
            m.Categorie.objects.filter(parent__isnull=False).delete()
            for modele in (m.Categorie, m.EtapeCircuit, m.Circuit, m.Priorite, m.TypeRetour, m.Mecanisme):
                modele.objects.all().delete()

        alea = random.Random(2026)
        appliquer_modele("standard")
        point_focal, cree = User.objects.get_or_create(
            username="pf_psea",
            defaults={"first_name": "Aminata", "last_name": "Ouédraogo", "role": ROLE_CHARGE_SE,
                      "email": "pf_psea@example.org"},
        )
        if cree:
            point_focal.set_password(MOT_DE_PASSE)
            point_focal.save()
        m.EtapeCircuit.objects.filter(circuit__sensible=True).update(responsable=point_focal)
        # L'Administrateur est aussi point focal : réception, évaluation des risques, décision, clôture.
        admin = User.objects.filter(role="ADMIN", is_active=True, username="admin").first()
        if admin:
            m.EtapeCircuit.objects.filter(
                circuit__sensible=True, nom__in=["Réception confidentielle", "Évaluation des risques", "Décision", "Clôture"],
            ).update(responsable=admin)
        mecanisme = m.Mecanisme.courant()
        mecanisme.conservation_ordinaire_mois = 60
        mecanisme.conservation_sensible_mois = 120
        mecanisme.langues = ["fr", "en", "ar"]
        mecanisme.save()
        erreurs = controler_activation(mecanisme)
        if erreurs:
            raise CommandError("Activation impossible : " + " ; ".join(erreurs))
        mecanisme.actif = True
        mecanisme.save(update_fields=["actif"])

        projets = list(Projet.objects.order_by("id")[:20])
        agents = list(User.objects.filter(is_active=True).exclude(pk=point_focal.pk)) or [None]
        types = {t.nom: t for t in m.TypeRetour.objects.all()}
        categories = {c.nom: c for c in m.Categorie.objects.all()}
        priorites = {p.nom: p for p in m.Priorite.objects.all()}
        aujourdhui = timezone.localdate()

        # Retours tirés au hasard (reproductible), triés par date pour des numéros dans l'ordre.
        a_creer = []
        for i in range(42):
            categorie, type_nom, description, personnel = RETOURS[i % len(RETOURS)]
            a_creer.append((aujourdhui - timedelta(days=alea.randint(0, 180)), categorie, type_nom, description, personnel))
        a_creer.sort(key=lambda r: r[0])

        compte = {"sensibles": 0}
        for date_reception, categorie, type_nom, description, personnel in a_creer:
            public = alea.random() < 0.4
            anonyme = alea.random() < 0.3
            nom = alea.choice(NOMS)
            mode = alea.choice(["AUCUN", "TELEPHONE", "SMS", "EN_PERSONNE"])
            donnees = {
                "type_retour": types[type_nom].id,
                "categorie": categories[categorie].id if categorie else None,
                "projet": alea.choice(projets).id if projets and alea.random() < 0.8 else None,
                "lieu": alea.choice(LIEUX),
                "description": description,
                "concerne_personnel": True if personnel else alea.choice([False, None]),
                "anonyme": anonyme,
                "nom": nom,
                "telephone": f"+226 7{alea.randint(0, 9)} {alea.randint(10, 99)} {alea.randint(10, 99)} {alea.randint(10, 99)}",
                "mode_reponse": mode,
                "consentement": True,
                "langue": "fr",
            }
            if public:
                dossier, _ = recevoir(donnees, "FORMULAIRE", public=True)
            else:
                donnees.update({
                    "date_reception": date_reception.isoformat(),
                    "recueilli_directement": alea.random() < 0.8,
                    "priorite": alea.choice([None, priorites["Normale"].id, priorites["Élevée"].id, priorites["Urgente"].id]),
                })
                dossier, _ = recevoir(donnees, alea.choice(CANAUX_AGENT), saisi_par=alea.choice(agents))
            # Dépôts du formulaire datés comme s'ils avaient été reçus ce jour-là ; avancement selon l'ancienneté.
            age = (aujourdhui - date_reception).days
            statut = "CLOTURE" if age > 70 else "REPONDU" if age > 40 else "EN_COURS" if age > 6 else "RECU"
            m.Dossier.objects.filter(pk=dossier.pk).update(
                date_reception=date_reception,
                priorite=dossier.priorite or (priorites["Normale"] if statut != "RECU" else None),
            )
            dossier.refresh_from_db()
            historiser(dossier, statut, 4 if statut == "EN_COURS" else 99, date_reception, alea, *self.personnes(point_focal))
            compte["sensibles"] += dossier.sensible
        self.recours_de_demonstration(alea, point_focal)
        self.confidentiel_de_demonstration()

        self.stdout.write(self.style.SUCCESS(
            f"Mécanisme activé ; {m.Dossier.objects.count()} dossiers dont {compte['sensibles']} confidentiels "
            f"(visibles par l'Administrateur et par pf_psea / {MOT_DE_PASSE})."
        ))

    def personnes(self, point_focal):
        """Gestionnaires des dossiers ordinaires, points focaux du circuit confidentiel, et qui affecte."""
        noms = ["demo_chef_projet", "demo_charge_se", "demo_chef_service", "demo_animateur_terrain"]
        gestionnaires = list(User.objects.filter(username__in=noms, is_active=True))
        admin = User.objects.filter(username="admin", is_active=True).first() or User.objects.filter(role="ADMIN").first()
        chef = User.objects.filter(username="demo_coordo_general", is_active=True).first() or admin
        return gestionnaires or [admin], [p for p in (point_focal, admin) if p], chef

    def recours_de_demonstration(self, alea, point_focal):
        """Un plaignant conteste une réponse : réexamen par une autre personne."""
        from apps.plaintes import traitement as t
        from apps.plaintes.models import Dossier

        dossier = Dossier.objects.filter(statut="CLOTURE", sensible=False, anonyme=False).exclude(responsable=None).order_by("-date_cloture").first()
        if dossier is None:
            return
        gestionnaires, _, chef = self.personnes(point_focal)
        t.recours(dossier, chef, {"motif": "Le plaignant estime que la réponse ne règle pas son problème."})
        autre = next((g for g in gestionnaires if g.pk != dossier.gestionnaire_initial_id), None)
        if autre:
            t.affecter(dossier, chef, autre.pk)

    def completer_historique(self):
        """Journal des dossiers qui n'en ont pas : rejoue leur traitement jusqu'à leur état actuel."""
        from apps.plaintes.models import ActionDossier, Dossier

        point_focal = User.objects.filter(username="pf_psea").first()
        alea = random.Random(7)
        completes = 0
        for dossier in Dossier.objects.filter(actions__isnull=True).select_related("circuit", "type_retour").order_by("numero"):
            statut = dossier.statut
            etapes = list(dossier.circuit.etapes.order_by("ordre", "id")) if dossier.circuit_id else []
            rang = etapes.index(dossier.etape) if dossier.etape in etapes else 0
            ActionDossier.objects.create(dossier=dossier, type="RECEPTION", auteur=dossier.saisi_par,
                                         details={"canal": dossier.canal, "circuit": dossier.circuit.nom if dossier.circuit else "",
                                                  "sensible": dossier.sensible})
            # On repart de la réception, puis on rejoue le traitement.
            Dossier.objects.filter(pk=dossier.pk).update(statut="RECU", etape=etapes[0] if etapes else None, responsable=None,
                                                         gestionnaire_initial=None)
            dossier.refresh_from_db()
            historiser(dossier, statut, rang, dossier.date_reception, alea, *self.personnes(point_focal))
            completes += 1
        if not Dossier.objects.filter(en_recours=True).exists():
            self.recours_de_demonstration(alea, point_focal)
        self.confidentiel_de_demonstration()
        self.stdout.write(self.style.SUCCESS(f"Journal complété pour {completes} dossier(s)."))

    def confidentiel_de_demonstration(self):
        """
        Lot 5 : circuit alternatif confié à la coordination, annuaire de prestataires, orientations
        vers une assistance, un dossier mettant en cause un point focal, une suspension légale.
        """
        from apps.plaintes import confidentiel
        from apps.plaintes.modeles_mecanisme import appliquer_modele
        from apps.plaintes.models import Dossier, EtapeCircuit, Mecanisme, Prestataire, TypeRetour
        from apps.plaintes.reception import recevoir

        appliquer_modele(Mecanisme.courant().modele or "standard")  # installe le circuit alternatif s'il manque
        mecanisme = Mecanisme.courant()
        referent = User.objects.filter(username="demo_coordo_general").first() or User.objects.filter(role="ADMIN").first()
        EtapeCircuit.objects.filter(circuit=mecanisme.circuit_alternatif, responsable=None).update(responsable=referent)
        prestataires = [Prestataire.objects.get_or_create(nom=nom, defaults={"type": type_, "contact": contact, "zone": zone})[0]
                        for nom, type_, contact, zone in (
                            ("Centre d'écoute et de prise en charge psychosociale", "PSYCHOSOCIAL", "+226 25 30 00 00", "Ouagadougou"),
                            ("CMA du secteur 30", "MEDICAL", "+226 25 36 00 00", "Ouagadougou"),
                            ("Clinique juridique de l'Association des femmes juristes", "JURIDIQUE", "+226 25 31 00 00", "National"),
                            ("Maison d'accueil temporaire", "SECURITE", "+226 70 00 00 00", "Centre"),
                        )]
        admin = User.objects.filter(username="admin").first() or referent
        for dossier, prestataire in zip(Dossier.objects.filter(sensible=True, referencements__isnull=True).order_by("numero")[:3], prestataires):
            confidentiel.orienter_assistance(dossier, admin, {"prestataire": prestataire.pk, "consentement": True,
                                                              "date": dossier.date_reception.isoformat()})
        point_focal = User.objects.filter(username="pf_psea").first()
        if point_focal and not Dossier.objects.filter(mis_en_cause_utilisateurs=point_focal).exists():
            recevoir({
                "type_retour": TypeRetour.objects.get(nom="Signalement").pk,
                "description": "Signalement visant un membre de l'équipe de protection : transmis au circuit alternatif.",
                "concerne_personnel": True, "anonyme": True, "consentement": True,
                "mis_en_cause_utilisateurs": [point_focal.pk],
                "date_reception": (timezone.localdate() - timedelta(days=3)).isoformat(),
            }, "TELEPHONE", saisi_par=admin)
        cloture = Dossier.objects.filter(statut="CLOTURE", sensible=True, suspension_legale=False).order_by("date_cloture").first()
        if cloture and not Dossier.objects.filter(suspension_legale=True).exists():
            confidentiel.suspendre(cloture, admin, {"motif": "Procédure judiciaire en cours : conservation obligatoire."})
        self.stdout.write(self.style.SUCCESS("Démonstration du circuit confidentiel ajoutée."))
