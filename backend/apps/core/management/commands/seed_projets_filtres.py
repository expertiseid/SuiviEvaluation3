"""
Ajoute une vingtaine de projets de test (codes « TEST-… ») très variés pour
essayer les filtres et blocs du tableau de bord consolidé : dates étalées de
2022 à 2029, tous les statuts, plusieurs pays, zones d'intervention,
bailleurs (avec ou sans financement détaillé), consortiums, partenaires de
mise en œuvre, cibles, activités et points de suivi. Les projets sont
rattachés à un cadre stratégique de test à 5 niveaux (Pilier > Orientation >
Axe > Programme > Action), créé ici et supprimé avec eux, pour essayer le
regroupement par niveau de l'onglet « Axes & budgets ».

    python manage.py seed_projets_filtres             # ajoute (ou recrée) les projets de test
    python manage.py seed_projets_filtres --supprimer # supprime uniquement les projets TEST-

Ne touche à aucune autre donnée ; les partenaires/bailleurs créés au passage
sont conservés (réutilisés au prochain lancement).
"""
import datetime
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.geo.models import Zone
from apps.partners.models import Bailleur, Financement, Partenaire
from apps.projects.models import Activite, ObjectifGeneral, ObjectifSpecifique, Projet
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau
from apps.suivi.models import PointSuivi
from apps.suivi.services import synchroniser_activite_depuis_suivi

PREFIXE = "TEST-"
NOM_CADRE_TEST = "Cadre de test — 5 niveaux"
NIVEAUX_TEST = ["Pilier", "Orientation stratégique", "Axe d'intervention", "Programme", "Action prioritaire"]
NOMS_ELEMENTS = {
    "Pilier": ["Développement humain", "Économie et résilience"],
    "Orientation stratégique": ["Services sociaux de base", "Inclusion et protection", "Économie rurale", "Environnement et climat"],
    "Axe d'intervention": ["Santé", "Éducation", "Protection sociale", "Cohésion sociale", "Agriculture", "Emploi",
                           "Gestion des terres", "Eau et assainissement"],
    "Programme": ["Accès", "Qualité", "Gouvernance", "Renforcement des capacités"],
    "Action prioritaire": ["Infrastructures", "Équipements", "Formation", "Sensibilisation"],
}

THEMES = [
    ("Sécurité alimentaire et nutrition", "ménages", ["Distribuer des kits agricoles", "Former aux bonnes pratiques nutritionnelles", "Installer des jardins maraîchers"]),
    ("Accès à l'eau potable", "forages", ["Réaliser des forages", "Réhabiliter des pompes", "Former des comités de gestion de l'eau"]),
    ("Éducation des filles", "élèves", ["Construire des salles de classe", "Octroyer des bourses scolaires", "Former des enseignants"]),
    ("Santé maternelle et infantile", "femmes", ["Équiper des centres de santé", "Former des accoucheuses", "Mener des campagnes de vaccination"]),
    ("Emploi des jeunes", "jeunes", ["Former aux métiers", "Financer des microprojets", "Accompagner l'insertion professionnelle"]),
    ("Résilience climatique", "hectares", ["Récupérer des terres dégradées", "Reboiser des sites", "Diffuser des semences adaptées"]),
    ("Cohésion sociale et paix", "communes", ["Animer des cadres de dialogue", "Former des médiateurs communautaires", "Appuyer des initiatives culturelles"]),
    ("Appui aux personnes déplacées", "ménages", ["Distribuer des abris", "Distribuer des vivres", "Appuyer l'accès aux documents d'état civil"]),
]
BAILLEURS = ["Union européenne", "Agence française de développement (AFD)", "UNICEF", "Banque mondiale", "USAID", "GIZ",
             "Coopération suisse", "FIDA"]
PARTENAIRES_MEO = ["Expertise ID", "ONG Sahel Solidarité", "Eau Vive Burkina", "Association Tind Yalgré",
                   "Réseau des caisses populaires du Houet", "Plan International Burkina", "Croix-Rouge burkinabè",
                   "ATAD"]
PAYS = [["BF"]] * 6 + [["ML"], ["NE"], ["BF", "NE"], ["BF", "ML"]]
NB_PROJETS = 24


class Command(BaseCommand):
    help = "Ajoute (ou supprime avec --supprimer) des projets de test TEST-… pour essayer les filtres du tableau de bord."

    def add_arguments(self, parser):
        parser.add_argument("--supprimer", action="store_true", help="Supprime uniquement les projets TEST-.")

    def handle(self, *args, supprimer=False, **options):
        with transaction.atomic():
            nb = self.supprimer()
            if supprimer:
                self.stdout.write(self.style.SUCCESS(f"{nb} projet(s) de test supprimé(s)."))
                return
            self.creer()
        self.stdout.write(self.style.SUCCESS(f"{NB_PROJETS} projets de test créés (codes {PREFIXE}01 à {PREFIXE}{NB_PROJETS:02d})."))

    def supprimer(self):
        projets = list(Projet.objects.filter(code__startswith=PREFIXE))
        nb = self.supprimer_projets(projets)
        for cadre in CadreStrategique.objects.filter(nom=NOM_CADRE_TEST):
            elements = ElementStrategique.objects.filter(type_niveau__cadre_strategique=cadre)
            for ordre in range(len(NIVEAUX_TEST), 0, -1):  # des feuilles vers la racine (PROTECT)
                elements.filter(type_niveau__ordre=ordre).delete()
            for niveau in TypeNiveau.objects.filter(cadre_strategique=cadre).order_by("-ordre"):
                niveau.delete()
            cadre.delete()
        return nb

    def creer_cadre_test(self):
        """Cadre à 5 niveaux, 2 enfants par élément (2 piliers … 32 actions)."""
        cadre = CadreStrategique.objects.create(
            nom=NOM_CADRE_TEST, description="Créé par seed_projets_filtres — supprimé avec --supprimer."
        )
        parent = None
        niveaux = []
        for ordre, nom in enumerate(NIVEAUX_TEST, start=1):
            parent = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau=nom, ordre=ordre, niveau_parent=parent)
            niveaux.append(parent)
        elements_par_niveau = [[]]
        for n, niveau in enumerate(niveaux):
            noms = NOMS_ELEMENTS[niveau.nom_niveau]
            parents = elements_par_niveau[-1] if n else [None]
            crees = []
            for p_index, element_parent in enumerate(parents):
                for k in range(2):
                    nom = noms[(p_index * 2 + k) % len(noms)]
                    code = f"{element_parent.code}.{k + 1}" if element_parent else str(k + 1)
                    crees.append(ElementStrategique.objects.create(
                        type_niveau=niveau, element_parent=element_parent, code=code,
                        nom=f"{nom}" if n < 2 else f"{nom} ({code})",
                    ))
            elements_par_niveau.append(crees)
        return cadre, elements_par_niveau[1:]

    def supprimer_projets(self, projets):
        for projet in projets:
            activites = Activite.objects.filter(objectif_specifique__objectif_general__projet=projet)
            PointSuivi.objects.filter(activite__in=activites).delete()
            activites.delete()
            ObjectifSpecifique.objects.filter(objectif_general__projet=projet).delete()
            ObjectifGeneral.objects.filter(projet=projet).delete()
            projet.delete()  # financements supprimés en cascade
        return len(projets)

    def creer(self):
        hasard = random.Random(2026)  # mêmes projets à chaque lancement
        aujourdhui = datetime.date.today()
        admin = get_user_model().objects.filter(role="ADMIN").first()
        cadre, elements_par_niveau = self.creer_cadre_test()
        # Surtout les actions (dernier niveau), parfois un programme ou un axe :
        # une activité peut être rattachée à n'importe quel niveau.
        axes = elements_par_niveau[4] * 6 + elements_par_niveau[3] * 2 + elements_par_niveau[2]
        regions = list(Zone.objects.filter(niveau_administratif__pays="BF", niveau_administratif__ordre=1))
        bailleurs = {nom: Partenaire.objects.get_or_create(nom=nom, defaults={"type": "BAILLEUR"})[0] for nom in BAILLEURS}
        bailleurs_fin = {nom: Bailleur.objects.get_or_create(nom=nom)[0] for nom in BAILLEURS}
        meo = {nom: Partenaire.objects.get_or_create(nom=nom, defaults={"type": "MISE_EN_OEUVRE"})[0] for nom in PARTENAIRES_MEO}

        for i in range(1, NB_PROJETS + 1):
            theme, unite, activites = THEMES[i % len(THEMES)]
            pays = PAYS[i % len(PAYS)]
            debut = datetime.date(2022, 1, 1) + datetime.timedelta(days=hasard.randrange(0, 365 * 6))
            debut = debut.replace(day=1)
            duree_mois = hasard.choice([6, 9, 9, 12, 18, 24, 36, 48])
            fin = (debut + datetime.timedelta(days=duree_mois * 30)).replace(day=1) - datetime.timedelta(days=1)
            if fin < aujourdhui:
                statut = "CLOTURE" if hasard.random() < 0.8 else "EN_COURS"  # quelques retards de clôture
            elif debut > aujourdhui:
                statut = "EN_PREPARATION"
            else:
                statut = "EN_COURS" if hasard.random() < 0.85 else "EN_PREPARATION"

            budget = Decimal(hasard.randrange(80, 900)) * Decimal("1000000")
            fonds_propres = (budget * Decimal(hasard.choice([0, 5, 10, 15])) / 100).quantize(Decimal("1"))
            consortium = hasard.random() < 0.35
            noms_meo = hasard.sample(PARTENAIRES_MEO, 3)
            bailleur = hasard.choice(BAILLEURS)
            cible = hasard.randrange(500, 25000, 100)
            femmes = int(cible * hasard.uniform(0.45, 0.7))
            lieu = hasard.choice(regions).nom if regions and "BF" in pays else {"ML": "Mali", "NE": "Niger"}[pays[0]]

            projet = Projet.objects.create(
                code=f"{PREFIXE}{i:02d}",
                nom=f"{theme} — {lieu} ({debut.year})",
                pays=pays,
                statut=statut,
                date_debut=debut,
                date_fin=fin,
                budget_total=budget,
                fonds_propres=fonds_propres,
                partenaire_bailleur=bailleurs[bailleur],
                partenaire_mise_en_oeuvre=meo[noms_meo[0]],
                type_mise_en_oeuvre="CONSORTIUM" if consortium else "DIRECT",
                cadre_strategique=cadre,
                chef_de_projet_nom=hasard.choice(["OUEDRAOGO Awa", "SAWADOGO Issa", "TRAORE Mariam", "KABORE Paul", "DIALLO Fatou"]),
                cible_totale=cible,
                cible_femmes=femmes,
                cible_hommes=cible - femmes,
                cible_jeunes=int(cible * hasard.uniform(0.2, 0.5)),
                cible_pdi=int(cible * hasard.uniform(0, 0.25)),
            )
            if consortium:
                projet.partenaires_consortium.set([meo[noms_meo[1]], meo[noms_meo[2]]])
            if "BF" in pays and regions:
                region = next((r for r in regions if r.nom == lieu), hasard.choice(regions))
                zones = [region] + hasard.sample(list(region.enfants.all()), min(2, region.enfants.count()))
                projet.zones.set(zones)
            # Un projet sur deux a un financement détaillé (parfois deux bailleurs).
            if i % 2 == 0:
                a_financer = budget - fonds_propres
                if i % 4 == 0:
                    second = hasard.choice([b for b in BAILLEURS if b != bailleur])
                    part = (a_financer * Decimal("0.6")).quantize(Decimal("1"))
                    Financement.objects.create(projet=projet, bailleur=bailleurs_fin[bailleur], montant_finance=part)
                    Financement.objects.create(projet=projet, bailleur=bailleurs_fin[second], montant_finance=a_financer - part)
                else:
                    Financement.objects.create(projet=projet, bailleur=bailleurs_fin[bailleur], montant_finance=a_financer)

            self.creer_cadre_logique(projet, theme, unite, activites, axes, hasard, aujourdhui, admin)

    def creer_cadre_logique(self, projet, theme, unite, activites, axes, hasard, aujourdhui, admin):
        og = ObjectifGeneral.objects.create(projet=projet, libelle=f"Contribuer à : {theme.lower()}")
        os_ = ObjectifSpecifique.objects.create(objectif_general=og, libelle=f"Améliorer durablement : {theme.lower()}")
        budget_activites = projet.budget_total * Decimal("0.85")
        duree = (projet.date_fin - projet.date_debut).days
        # Avancement attendu du projet à aujourd'hui (0 avant le début, 1 après la fin).
        avancement = min(1.0, max(0.0, (aujourdhui - projet.date_debut).days / duree)) if duree > 0 else 0.0
        for n, libelle in enumerate(activites, start=1):
            axe = hasard.choice(axes) if axes else None
            quantite = Decimal(hasard.randrange(10, 500))
            budget = (budget_activites / len(activites)).quantize(Decimal("1"))
            activite = Activite.objects.create(
                objectif_specifique=os_,
                code_activite=f"{n}.1",
                libelle=libelle,
                axe_strategique=axe,
                date_debut=projet.date_debut,
                date_fin=projet.date_fin,
                quantite_prevue=quantite,
                unite_quantite=unite,
                budget_alloue=budget,
            )
            if avancement <= 0 or admin is None:
                continue
            realise = (quantite * Decimal(str(round(avancement * hasard.uniform(0.5, 1.1), 2)))).quantize(Decimal("1"))
            fin_saisie = min(aujourdhui, projet.date_fin)
            PointSuivi.objects.create(
                activite=activite,
                periode_debut=projet.date_debut,
                periode_fin=fin_saisie,
                quantite_realisee=min(realise, quantite),
                budget_realise=(budget * Decimal(str(round(avancement * hasard.uniform(0.4, 1.0), 2)))).quantize(Decimal("1")),
                statut="REALISEE" if realise >= quantite else "EN_COURS",
                saisi_par=admin,
            )
            synchroniser_activite_depuis_suivi(activite)
