"""
Ajoute 4 projets de démonstration entièrement renseignés (cadre stratégique
propre, objectifs, activités, sous-activités, indicateurs avec historique de
valeurs, points de suivi périodiques, bénéficiaires et rapport de suivi) —
SANS RIEN SUPPRIMER : contrairement à seed_demo_arfa/seed_points_suivi, cette
commande n'efface aucune donnée existante (elle réutilise les partenaires,
bailleurs, intervenants, équipes, statuts particuliers et bénéficiaires déjà
en base quand c'est pertinent) — sûre à exécuter même quand un projet réel a
déjà été saisi/importé par un utilisateur.

Rejouable seulement si les codes projet ne sont pas déjà utilisés (Projet.code
est unique) : relancer sans purge échouerait sur un IntegrityError, ce qui est
le comportement voulu (pas de doublon silencieux).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.beneficiaries.models import Beneficiaire, ParticipationProjet, StatutParticulier
from apps.geo.models import Zone
from apps.indicators.models import Indicateur, ValeurIndicateur
from apps.intervenants.models import Intervenant
from apps.partners.models import Bailleur, Financement, Partenaire
from apps.projects.models import Activite, Projet, SousActivite
from apps.projects.services import nommer_niveaux
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau
from apps.suivi.models import PointSuivi
from apps.suivi.services import synchroniser_activite_depuis_suivi, synchroniser_sous_activite_depuis_suivi

User = get_user_model()


class Command(BaseCommand):
    help = "Ajoute 4 projets de démonstration complets, sans supprimer les données existantes."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.users = self.recuperer_utilisateurs()
            self.statuts = self.recuperer_ou_creer_statuts()
            self.intervenants = {i.nom: i for i in Intervenant.objects.all()}

            self.creer_projet_education()
            self.creer_projet_sante()
            self.creer_projet_eau()
            self.creer_projet_autonomisation()

        self.stdout.write(self.style.SUCCESS("4 projets de démonstration ajoutés avec succès."))

    # ------------------------------------------------------------------
    # Aides communes
    # ------------------------------------------------------------------
    def recuperer_utilisateurs(self):
        def u(username):
            return User.objects.filter(username=username).first()

        return {
            "admin": u("demo_admin"),
            "coordo": u("demo_coordo_general"),
            "charge_se": u("demo_charge_se") or u("demo_admin"),
            "chef_projet": u("demo_chef_projet"),
            "animateur": u("demo_animateur_terrain"),
            "chef_service": u("demo_chef_service"),
        }

    def recuperer_ou_creer_statuts(self):
        def get_or_create(code, libelle):
            statut, _ = StatutParticulier.objects.get_or_create(code=code, defaults={"libelle": libelle})
            return statut

        return {
            "pdi": get_or_create("PDI", "Personne déplacée interne"),
            "jeune": get_or_create("JEUNE", "Jeune (moins de 35 ans)"),
            "femme_chef_menage": get_or_create("FEMME_CHEF_MENAGE", "Femme cheffe de ménage"),
            "handicap": get_or_create("HANDICAP", "Personne en situation de handicap"),
        }

    def partenaire(self, nom, type_):
        obj, _ = Partenaire.objects.get_or_create(nom=nom, defaults={"type": type_})
        return obj

    def bailleur(self, nom, type_=Bailleur.TypeBailleur.AUTRE):
        obj, _ = Bailleur.objects.get_or_create(nom=nom, defaults={"type": type_})
        return obj

    def zones_par_nom(self, *noms):
        return list(Zone.objects.filter(nom__in=noms))

    def creer_cadre(self, nom, description, axes):
        """
        axes: liste de (code, nom, [(code, nom, [(code, nom), ...]), ...])
        — Axe stratégique -> Orientation stratégique -> Résultat attendu,
        même structure à 3 niveaux que le plan stratégique Expertise ID.
        Retourne (cadre, dict code -> ElementStrategique).
        """
        cadre = CadreStrategique.objects.create(nom=nom, description=description)
        niveau_axe = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Axe stratégique", ordre=1)
        niveau_orientation = TypeNiveau.objects.create(
            cadre_strategique=cadre, nom_niveau="Orientation stratégique", ordre=2, niveau_parent=niveau_axe
        )
        niveau_resultat = TypeNiveau.objects.create(
            cadre_strategique=cadre, nom_niveau="Résultat attendu", ordre=3, niveau_parent=niveau_orientation
        )
        elements = {}
        for code_axe, nom_axe, orientations in axes:
            axe = ElementStrategique.objects.create(type_niveau=niveau_axe, code=code_axe, nom=nom_axe)
            elements[code_axe] = axe
            for code_or, nom_or, resultats in orientations:
                orientation = ElementStrategique.objects.create(
                    type_niveau=niveau_orientation, element_parent=axe, code=code_or, nom=nom_or
                )
                elements[code_or] = orientation
                for code_ra, nom_ra in resultats:
                    resultat = ElementStrategique.objects.create(
                        type_niveau=niveau_resultat, element_parent=orientation, code=code_ra, nom=nom_ra
                    )
                    elements[code_ra] = resultat
        return cadre, elements

    def creer_indicateur(self, *, libelle, unite, valeur_reference, valeur_cible, frequence, rattachement, element, valeurs):
        indicateur = Indicateur.objects.create(
            libelle=libelle,
            unite=unite,
            valeur_reference=Decimal(str(valeur_reference)),
            valeur_cible=Decimal(str(valeur_cible)),
            frequence_collecte=frequence,
            **rattachement,
        )
        if element:
            indicateur.elements_strategiques.set([element])
        for periode_debut, periode_fin, valeur in valeurs:
            ValeurIndicateur.objects.create(
                indicateur=indicateur,
                periode_debut=periode_debut,
                periode_fin=periode_fin,
                valeur_realisee=Decimal(str(valeur)),
                saisi_par=self.users["charge_se"],
            )
        return indicateur

    def creer_activite(self, *, os, code, libelle, element, budget_alloue, quantite_prevue, unite, date_debut, date_fin, points):
        """points : [(periode_debut, periode_fin, quantite, budget, statut), ...] — un point par période
        (delta, pas cumul) ; Activite.quantite_realisee/budget_realise/statut sont ensuite dérivés
        automatiquement de ces points par synchroniser_activite_depuis_suivi (source de vérité unique)."""
        activite = Activite.objects.create(
            projet=os.projet, activite_parent=os,
            code_activite=code,
            libelle=libelle,
            axe_strategique=element,
            budget_alloue=Decimal(str(budget_alloue)),
            quantite_prevue=Decimal(str(quantite_prevue)),
            unite_quantite=unite,
            date_debut=date_debut,
            date_fin=date_fin,
        )
        for periode_debut, periode_fin, quantite, budget, statut in points:
            PointSuivi.objects.create(
                activite=activite,
                periode_debut=periode_debut,
                periode_fin=periode_fin,
                quantite_realisee=Decimal(str(quantite)),
                budget_realise=Decimal(str(budget)),
                statut=statut,
                saisi_par=self.users["charge_se"],
            )
        synchroniser_activite_depuis_suivi(activite)
        return activite

    def creer_sous_activite(self, *, activite, libelle, element, quantite_prevue, unite, date_debut, date_fin, points):
        """points : [(periode_debut, periode_fin, quantite, statut), ...]"""
        sous_activite = SousActivite.objects.create(
            activite=activite,
            libelle=libelle,
            axe_strategique=element,
            quantite_prevue=Decimal(str(quantite_prevue)),
            unite_quantite=unite,
            date_debut=date_debut,
            date_fin=date_fin,
        )
        for periode_debut, periode_fin, quantite, statut in points:
            PointSuivi.objects.create(
                sous_activite=sous_activite,
                periode_debut=periode_debut,
                periode_fin=periode_fin,
                quantite_realisee=Decimal(str(quantite)),
                statut=statut,
                saisi_par=self.users["charge_se"],
            )
        synchroniser_sous_activite_depuis_suivi(sous_activite)
        return sous_activite

    def creer_beneficiaires(self, projet, date_inscription, role, zones, donnees, suffixe_hash):
        """donnees : [(nom, prenom, sexe, index_zone, [codes_statuts]), ...] — crée les bénéficiaires et
        les inscrit sur le projet."""
        for nom, prenom, sexe, index_zone, codes_statuts in donnees:
            zone = zones[index_zone] if zones else None
            beneficiaire = Beneficiaire.objects.create(
                nom=nom,
                prenom=prenom,
                sexe=sexe,
                telephone="+226 7" + str(abs(hash((nom, prenom, suffixe_hash))) % 10000000).zfill(7),
                numero_piece_identite="B" + str(abs(hash((nom, prenom, suffixe_hash, "id"))) % 100000000),
                type_piece="CNIB",
                pays="BF",
                zone=zone,
            )
            if codes_statuts:
                beneficiaire.statuts_particuliers.set([self.statuts[c] for c in codes_statuts])
            ParticipationProjet.objects.create(
                beneficiaire=beneficiaire, projet=projet, date_inscription=date_inscription, role_dans_projet=role
            )

    def rattacher_beneficiaires_existants(self, projet, noms, date_inscription, role):
        for nom, prenom in noms:
            beneficiaire = Beneficiaire.objects.filter(nom=nom, prenom=prenom).first()
            if beneficiaire and not ParticipationProjet.objects.filter(beneficiaire=beneficiaire, projet=projet).exists():
                ParticipationProjet.objects.create(
                    beneficiaire=beneficiaire, projet=projet, date_inscription=date_inscription, role_dans_projet=role
                )

    # ------------------------------------------------------------------
    # Projet 1 — Éducation de base
    # ------------------------------------------------------------------
    def creer_projet_education(self):
        self.stdout.write("Création du projet Éducation…")
        bailleur_p = self.partenaire("Délégation de l'Union Européenne au Burkina Faso", Partenaire.TypePartenaire.BAILLEUR)
        mise_en_oeuvre_p = self.partenaire("Expertise ID", Partenaire.TypePartenaire.MISE_EN_OEUVRE)

        cadre, el = self.creer_cadre(
            nom="Plan stratégique Éducation 2026-2028",
            description="Cadre stratégique dédié à l'accès et à la qualité de l'éducation de base en zone rurale.",
            axes=[
                (
                    "AXE1",
                    "Amélioration de l'accès à une éducation de base de qualité",
                    [
                        (
                            "OR1.1",
                            "Renforcement de l'offre scolaire et de l'alphabétisation",
                            [
                                ("RA1.1.1", "Les enfants non scolarisés accèdent à une offre éducative adaptée"),
                                ("RA1.1.2", "Les adultes analphabètes acquièrent des compétences de base en lecture/écriture/calcul"),
                            ],
                        ),
                        (
                            "OR1.2",
                            "Amélioration des conditions d'apprentissage et de la qualité pédagogique",
                            [("RA1.2.1", "Les enseignants sont formés et les infrastructures scolaires réhabilitées")],
                        ),
                    ],
                )
            ],
        )

        projet = Projet.objects.create(
            nom="Programme d'Éducation de Base et d'Alphabétisation en Milieu Rural",
            code="EXPERTISE-ID-EDUC-2026",
            pays=["BF"],
            partenaire_bailleur=bailleur_p,
            partenaire_mise_en_oeuvre=mise_en_oeuvre_p,
            cadre_strategique=cadre,
            budget_total=Decimal("410000000"),
            fonds_propres=Decimal("41000000"),
            date_debut=date(2026, 1, 15),
            date_fin=date(2027, 12, 31),
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.DIRECT,
            chef_de_projet_nom="OUEDRAOGO Awa",
            cible_totale=4200,
            cible_hommes=1900,
            cible_femmes=2300,
            cible_jeunes=3100,
            cible_pdi=250,
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        zones = self.zones_par_nom("Kadiogo", "Boulkiemde", "Sanguie")
        projet.zones.set(zones)
        projet.utilisateurs_affectes.set([u for u in (self.users["chef_projet"], self.users["charge_se"]) if u])
        Financement.objects.create(
            projet=projet, bailleur=self.bailleur("Union Européenne"), montant_finance=Decimal("369000000")
        )

        og = Activite.objects.create(
            projet=projet,
            libelle="Contribuer à l'amélioration de l'accès à une éducation de base de qualité dans les zones rurales d'intervention",
            description="Le programme combine ouverture de classes alternatives, alphabétisation des adultes et renforcement des capacités enseignantes sur deux ans (2026-2027).",
        )
        os1 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Améliorer l'accès à l'éducation de base pour les enfants non scolarisés et les adultes analphabètes",
            description="Ouverture de centres d'éducation alternative et de centres d'alphabétisation fonctionnelle.",
        )
        os2 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Renforcer la qualité de l'enseignement et les infrastructures scolaires",
            description="Formation continue des enseignants et réhabilitation d'infrastructures scolaires.",
        )

        a1 = self.creer_activite(
            os=os1, code="AE1.1", libelle="Ouverture et animation de centres d'éducation alternative pour enfants non scolarisés",
            element=el["RA1.1.1"], budget_alloue=70000000, quantite_prevue=1500, unite="enfants inscrits",
            date_debut=date(2026, 2, 1), date_fin=date(2027, 10, 31),
            points=[
                (date(2026, 2, 1), date(2026, 6, 30), 420, 16000000, "EN_COURS"),
                (date(2026, 7, 1), date(2026, 8, 20), 260, 9000000, "EN_COURS"),
            ],
        )
        self.creer_sous_activite(
            activite=a1, libelle="Recrutement et formation des facilitateurs communautaires", element=el["RA1.1.1"],
            quantite_prevue=45, unite="facilitateurs", date_debut=date(2026, 2, 1), date_fin=date(2026, 5, 31),
            points=[(date(2026, 2, 1), date(2026, 5, 31), 38, "TERMINEE")],
        )

        a2 = self.creer_activite(
            os=os1, code="AE1.2", libelle="Alphabétisation fonctionnelle des adultes (femmes en priorité)",
            element=el["RA1.1.2"], budget_alloue=55000000, quantite_prevue=1800, unite="adultes alphabétisés",
            date_debut=date(2026, 3, 1), date_fin=date(2027, 12, 31),
            points=[(date(2026, 3, 1), date(2026, 8, 20), 410, 11000000, "EN_COURS")],
        )
        self.creer_sous_activite(
            activite=a2, libelle="Organisation de sessions d'alphabétisation en langues nationales", element=el["RA1.1.2"],
            quantite_prevue=80, unite="sessions", date_debut=date(2026, 3, 15), date_fin=date(2027, 12, 31),
            points=[(date(2026, 3, 15), date(2026, 8, 20), 22, "EN_COURS")],
        )

        a3 = self.creer_activite(
            os=os2, code="AE2.1", libelle="Formation continue des enseignants du primaire aux méthodes pédagogiques actives",
            element=el["RA1.2.1"], budget_alloue=35000000, quantite_prevue=220, unite="enseignants formés",
            date_debut=date(2026, 4, 1), date_fin=date(2027, 6, 30),
            points=[(date(2026, 4, 1), date(2026, 8, 20), 95, 14000000, "EN_COURS")],
        )
        a4 = self.creer_activite(
            os=os2, code="AE2.2", libelle="Réhabilitation et équipement de salles de classe",
            element=el["RA1.2.1"], budget_alloue=90000000, quantite_prevue=30, unite="salles de classe",
            date_debut=date(2026, 5, 1), date_fin=date(2027, 11, 30),
            points=[(date(2026, 5, 1), date(2026, 8, 20), 6, 18000000, "EN_COURS")],
        )
        self.creer_sous_activite(
            activite=a4, libelle="Construction de latrines et points d'eau dans les écoles réhabilitées", element=el["RA1.2.1"],
            quantite_prevue=15, unite="blocs", date_debut=date(2026, 6, 1), date_fin=date(2027, 11, 30),
            points=[(date(2026, 6, 1), date(2026, 8, 20), 2, "EN_COURS")],
        )

        self.creer_indicateur(
            libelle="Nombre total de bénéficiaires directs touchés par le programme éducatif", unite="personnes",
            valeur_reference=0, valeur_cible=4200, frequence="SEMESTRIELLE", rattachement={"projet": projet},
            element=el["AXE1"], valeurs=[(date(2026, 1, 15), date(2026, 6, 30), 1050), (date(2026, 7, 1), date(2026, 8, 20), 640)],
        )
        self.creer_indicateur(
            libelle="Taux net de scolarisation dans les zones d'intervention", unite="%",
            valeur_reference=48, valeur_cible=72, frequence="ANNUELLE", rattachement={"activite": og},
            element=None, valeurs=[(date(2026, 1, 15), date(2026, 8, 20), 55)],
        )
        self.creer_indicateur(
            libelle="Nombre d'enfants non scolarisés accédant à une offre éducative", unite="enfants",
            valeur_reference=0, valeur_cible=1500, frequence="SEMESTRIELLE", rattachement={"activite": os1},
            element=el["RA1.1.1"], valeurs=[(date(2026, 2, 1), date(2026, 8, 20), 680)],
        )
        self.creer_indicateur(
            libelle="Taux d'alphabétisation fonctionnelle des adultes formés", unite="%",
            valeur_reference=15, valeur_cible=65, frequence="ANNUELLE", rattachement={"activite": a2},
            element=el["RA1.1.2"], valeurs=[(date(2026, 3, 1), date(2026, 8, 20), 34)],
        )
        self.creer_indicateur(
            libelle="Nombre d'enseignants appliquant les méthodes pédagogiques actives", unite="enseignants",
            valeur_reference=0, valeur_cible=220, frequence="SEMESTRIELLE", rattachement={"activite": a3},
            element=el["RA1.2.1"], valeurs=[(date(2026, 4, 1), date(2026, 8, 20), 95)],
        )

        zones_b = self.zones_par_nom("Boulkiemde", "Sanguie")
        self.creer_beneficiaires(
            projet, date(2026, 2, 10), "Bénéficiaire direct — éducation/alphabétisation", zones_b,
            [
                ("KABORE", "Rasmane", "M", 0, ["jeune"]),
                ("SAWADOGO", "Fatimata", "F", 0, ["femme_chef_menage"]),
                ("OUEDRAOGO", "Issa", "M", 1, []),
                ("ZOUNGRANA", "Aminata", "F", 1, ["jeune"]),
            ],
            "educ",
        )
        self.rattacher_beneficiaires_existants(
            projet, [("SOME", "Adama"), ("OUATTARA", "Rasmata")], date(2026, 2, 10), "Bénéficiaire — session d'alphabétisation"
        )

    # ------------------------------------------------------------------
    # Projet 2 — Santé maternelle et infantile
    # ------------------------------------------------------------------
    def creer_projet_sante(self):
        self.stdout.write("Création du projet Santé…")
        bailleur_p = self.partenaire("Fondation Grameen", Partenaire.TypePartenaire.BAILLEUR)
        mise_en_oeuvre_p = self.partenaire("ONG Sahel Solidarité", Partenaire.TypePartenaire.MISE_EN_OEUVRE)

        cadre, el = self.creer_cadre(
            nom="Plan stratégique Santé 2026-2028",
            description="Cadre stratégique dédié à la santé maternelle, infantile et nutritionnelle.",
            axes=[
                (
                    "AXE1",
                    "Réduction de la morbidité et de la mortalité maternelle et infantile",
                    [
                        (
                            "OR1.1",
                            "Amélioration de l'accès aux soins de santé primaire",
                            [
                                ("RA1.1.1", "Les femmes enceintes bénéficient d'un suivi prénatal régulier"),
                                ("RA1.1.2", "Les enfants de moins de 5 ans sont dépistés et pris en charge contre la malnutrition"),
                            ],
                        ),
                        (
                            "OR1.2",
                            "Renforcement du plateau technique et des ressources humaines de santé",
                            [("RA1.2.1", "Les agents de santé communautaire sont formés et équipés")],
                        ),
                    ],
                )
            ],
        )

        projet = Projet.objects.create(
            nom="Projet d'Amélioration de la Santé Maternelle et Infantile",
            code="EXPERTISE-ID-SANTE-2026",
            pays=["BF"],
            partenaire_bailleur=bailleur_p,
            partenaire_mise_en_oeuvre=mise_en_oeuvre_p,
            cadre_strategique=cadre,
            budget_total=Decimal("530000000"),
            fonds_propres=Decimal("53000000"),
            date_debut=date(2026, 2, 1),
            date_fin=date(2028, 1, 31),
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.DIRECT,
            chef_de_projet_nom="NIKIEMA Aminata",
            cible_totale=6000,
            cible_hommes=800,
            cible_femmes=5200,
            cible_jeunes=1500,
            cible_pdi=700,
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        zones = self.zones_par_nom("Guiriko", "Houet", "Kenedougou")
        projet.zones.set(zones)
        projet.utilisateurs_affectes.set([u for u in (self.users["coordo"], self.users["charge_se"]) if u])
        Financement.objects.create(
            projet=projet, bailleur=self.bailleur("Fondation Grameen", Bailleur.TypeBailleur.FONDATION),
            montant_finance=Decimal("477000000"),
        )

        og = Activite.objects.create(
            projet=projet,
            libelle="Contribuer à la réduction de la mortalité maternelle et infantile dans la région du Guiriko",
            description="Le projet renforce l'offre de soins prénatals, la prise en charge nutritionnelle et les capacités des agents de santé communautaire sur deux ans (2026-2027).",
        )
        os1 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Améliorer la couverture en soins prénatals et la prise en charge de la malnutrition infantile",
            description="Consultations prénatales, dépistage et prise en charge de la malnutrition aiguë.",
        )
        os2 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Renforcer les capacités et les équipements des agents de santé communautaire",
            description="Formation et dotation en kits des agents de santé à base communautaire (ASBC).",
        )

        a1 = self.creer_activite(
            os=os1, code="AS1.1", libelle="Organisation de consultations prénatales décentralisées",
            element=el["RA1.1.1"], budget_alloue=85000000, quantite_prevue=5000, unite="consultations",
            date_debut=date(2026, 2, 15), date_fin=date(2027, 12, 31),
            points=[
                (date(2026, 2, 15), date(2026, 6, 30), 1450, 22000000, "EN_COURS"),
                (date(2026, 7, 1), date(2026, 8, 20), 780, 12000000, "EN_COURS"),
            ],
        )
        self.creer_sous_activite(
            activite=a1, libelle="Tenue de cliniques mobiles dans les zones difficiles d'accès", element=el["RA1.1.1"],
            quantite_prevue=48, unite="sorties mobiles", date_debut=date(2026, 3, 1), date_fin=date(2027, 12, 31),
            points=[(date(2026, 3, 1), date(2026, 8, 20), 14, "EN_COURS")],
        )

        a2 = self.creer_activite(
            os=os1, code="AS1.2", libelle="Dépistage et prise en charge de la malnutrition aiguë chez les enfants de moins de 5 ans",
            element=el["RA1.1.2"], budget_alloue=110000000, quantite_prevue=3500, unite="enfants pris en charge",
            date_debut=date(2026, 2, 15), date_fin=date(2028, 1, 31),
            points=[(date(2026, 2, 15), date(2026, 8, 20), 980, 28000000, "EN_COURS")],
        )

        a3 = self.creer_activite(
            os=os2, code="AS2.1", libelle="Formation des agents de santé communautaire aux protocoles de prise en charge",
            element=el["RA1.2.1"], budget_alloue=40000000, quantite_prevue=180, unite="ASBC formés",
            date_debut=date(2026, 3, 1), date_fin=date(2026, 12, 31),
            points=[(date(2026, 3, 1), date(2026, 8, 20), 150, 32000000, "EN_COURS")],
        )
        a4 = self.creer_activite(
            os=os2, code="AS2.2", libelle="Dotation des agents de santé communautaire en kits et équipements de terrain",
            element=el["RA1.2.1"], budget_alloue=60000000, quantite_prevue=180, unite="kits distribués",
            date_debut=date(2026, 4, 1), date_fin=date(2027, 3, 31),
            points=[(date(2026, 4, 1), date(2026, 8, 20), 60, 19000000, "EN_COURS")],
        )
        self.creer_sous_activite(
            activite=a4, libelle="Mise en place d'un système de réapprovisionnement en intrants nutritionnels", element=el["RA1.2.1"],
            quantite_prevue=10, unite="dépôts communautaires", date_debut=date(2026, 5, 1), date_fin=date(2027, 3, 31),
            points=[(date(2026, 5, 1), date(2026, 8, 20), 3, "EN_COURS")],
        )

        self.creer_indicateur(
            libelle="Nombre total de femmes et d'enfants bénéficiaires directs", unite="personnes",
            valeur_reference=0, valeur_cible=6000, frequence="SEMESTRIELLE", rattachement={"projet": projet},
            element=el["AXE1"], valeurs=[(date(2026, 2, 1), date(2026, 6, 30), 1900), (date(2026, 7, 1), date(2026, 8, 20), 1050)],
        )
        self.creer_indicateur(
            libelle="Taux de couverture en consultations prénatales dans les zones d'intervention", unite="%",
            valeur_reference=41, valeur_cible=80, frequence="ANNUELLE", rattachement={"activite": og},
            element=None, valeurs=[(date(2026, 2, 1), date(2026, 8, 20), 58)],
        )
        self.creer_indicateur(
            libelle="Nombre d'enfants dépistés et pris en charge pour malnutrition aiguë", unite="enfants",
            valeur_reference=0, valeur_cible=3500, frequence="SEMESTRIELLE", rattachement={"activite": os1},
            element=el["RA1.1.2"], valeurs=[(date(2026, 2, 15), date(2026, 8, 20), 980)],
        )
        self.creer_indicateur(
            libelle="Proportion d'agents de santé communautaire opérationnels selon les protocoles", unite="%",
            valeur_reference=20, valeur_cible=90, frequence="ANNUELLE", rattachement={"activite": a3},
            element=el["RA1.2.1"], valeurs=[(date(2026, 3, 1), date(2026, 8, 20), 75)],
        )
        self.creer_indicateur(
            libelle="Nombre de sorties de cliniques mobiles réalisées", unite="sorties",
            valeur_reference=0, valeur_cible=48, frequence="TRIMESTRIELLE", rattachement={"activite": a1},
            element=el["RA1.1.1"], valeurs=[(date(2026, 3, 1), date(2026, 8, 20), 14)],
        )

        zones_b = self.zones_par_nom("Houet", "Kenedougou")
        self.creer_beneficiaires(
            projet, date(2026, 2, 20), "Bénéficiaire direct — santé maternelle et infantile", zones_b,
            [
                ("TRAORE", "Salimata", "F", 0, ["femme_chef_menage"]),
                ("DA", "Adjara", "F", 0, ["pdi"]),
                ("SANOGO", "Kadidia", "F", 1, ["jeune"]),
                ("KONE", "Bakary", "M", 1, []),
            ],
            "sante",
        )
        self.rattacher_beneficiaires_existants(
            projet, [("YAMEOGO", "Salamata")], date(2026, 2, 20), "Bénéficiaire — suivi nutritionnel"
        )

    # ------------------------------------------------------------------
    # Projet 3 — Eau, hygiène et assainissement
    # ------------------------------------------------------------------
    def creer_projet_eau(self):
        self.stdout.write("Création du projet Eau/Assainissement…")
        bailleur_p = self.partenaire("Agence Française de Développement", Partenaire.TypePartenaire.BAILLEUR)
        mise_en_oeuvre_p = self.partenaire("Expertise ID", Partenaire.TypePartenaire.MISE_EN_OEUVRE)
        consortium_p = self.partenaire("ONG Sahel Solidarité", Partenaire.TypePartenaire.MISE_EN_OEUVRE)

        cadre, el = self.creer_cadre(
            nom="Plan stratégique Eau & Assainissement 2026-2027",
            description="Cadre stratégique dédié à l'accès à l'eau potable, l'hygiène et l'assainissement (WASH).",
            axes=[
                (
                    "AXE1",
                    "Amélioration de l'accès durable à l'eau potable, l'hygiène et l'assainissement",
                    [
                        (
                            "OR1.1",
                            "Extension de l'accès à l'eau potable",
                            [("RA1.1.1", "Les ménages ont accès à une source d'eau potable améliorée à proximité")],
                        ),
                        (
                            "OR1.2",
                            "Promotion de l'hygiène et de l'assainissement familial et communautaire",
                            [("RA1.2.1", "Les ménages adoptent des pratiques d'hygiène et d'assainissement améliorées")],
                        ),
                    ],
                )
            ],
        )

        projet = Projet.objects.create(
            nom="Programme d'Accès à l'Eau Potable, à l'Hygiène et à l'Assainissement",
            code="EXPERTISE-ID-EAU-2026",
            pays=["BF"],
            partenaire_bailleur=bailleur_p,
            partenaire_mise_en_oeuvre=mise_en_oeuvre_p,
            cadre_strategique=cadre,
            budget_total=Decimal("670000000"),
            fonds_propres=Decimal("67000000"),
            date_debut=date(2026, 3, 1),
            date_fin=date(2027, 8, 31),
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.CONSORTIUM,
            chef_de_projet_nom="ZONGO Salif",
            cible_totale=8500,
            cible_hommes=4000,
            cible_femmes=4500,
            cible_jeunes=2600,
            cible_pdi=1200,
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        projet.partenaires_consortium.set([consortium_p])
        zones = self.zones_par_nom("Soum", "Yatenga", "Loroum")
        projet.zones.set(zones)
        projet.utilisateurs_affectes.set([u for u in (self.users["chef_projet"], self.users["animateur"]) if u])
        Financement.objects.create(
            projet=projet, bailleur=self.bailleur("Agence Française de Développement"), montant_finance=Decimal("603000000")
        )

        og = Activite.objects.create(
            projet=projet,
            libelle="Contribuer à l'amélioration durable de l'accès à l'eau potable, l'hygiène et l'assainissement dans le Soum",
            description="Le programme combine réalisation de points d'eau, promotion de l'hygiène et assainissement familial sur un an et demi (2026-2027), en zone à fort taux de déplacement interne.",
        )
        os1 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Étendre l'accès des ménages à une source d'eau potable améliorée",
            description="Réalisation et réhabilitation de forages et de bornes-fontaines.",
        )
        os2 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Promouvoir l'adoption de pratiques d'hygiène et d'assainissement au niveau des ménages et des communautés",
            description="Sensibilisation à l'hygiène, assainissement total piloté par la communauté (ATPC), construction de latrines familiales.",
        )

        a1 = self.creer_activite(
            os=os1, code="AW1.1", libelle="Réalisation et réhabilitation de forages équipés de pompes à motricité humaine",
            element=el["RA1.1.1"], budget_alloue=220000000, quantite_prevue=70, unite="forages",
            date_debut=date(2026, 3, 15), date_fin=date(2027, 6, 30),
            points=[
                (date(2026, 3, 15), date(2026, 6, 30), 12, 34000000, "EN_COURS"),
                (date(2026, 7, 1), date(2026, 8, 20), 9, 27000000, "EN_COURS"),
            ],
        )
        self.creer_sous_activite(
            activite=a1, libelle="Mise en place de comités de gestion de point d'eau (CGPE)", element=el["RA1.1.1"],
            quantite_prevue=70, unite="comités", date_debut=date(2026, 4, 1), date_fin=date(2027, 6, 30),
            points=[(date(2026, 4, 1), date(2026, 8, 20), 19, "EN_COURS")],
        )

        a2 = self.creer_activite(
            os=os1, code="AW1.2", libelle="Extension de réseaux d'adduction d'eau potable simplifiés (AEPS)",
            element=el["RA1.1.1"], budget_alloue=150000000, quantite_prevue=6, unite="réseaux AEPS",
            date_debut=date(2026, 5, 1), date_fin=date(2027, 8, 31),
            points=[(date(2026, 5, 1), date(2026, 8, 20), 1, 21000000, "EN_COURS")],
        )

        a3 = self.creer_activite(
            os=os2, code="AW2.1", libelle="Mise en œuvre de l'assainissement total piloté par la communauté (ATPC)",
            element=el["RA1.2.1"], budget_alloue=95000000, quantite_prevue=120, unite="villages déclenchés",
            date_debut=date(2026, 3, 15), date_fin=date(2027, 8, 31),
            points=[(date(2026, 3, 15), date(2026, 8, 20), 58, 41000000, "EN_COURS")],
        )
        a4 = self.creer_activite(
            os=os2, code="AW2.2", libelle="Sensibilisation aux bonnes pratiques d'hygiène (lavage des mains, traitement de l'eau)",
            element=el["RA1.2.1"], budget_alloue=45000000, quantite_prevue=8500, unite="personnes sensibilisées",
            date_debut=date(2026, 3, 15), date_fin=date(2027, 8, 31),
            points=[(date(2026, 3, 15), date(2026, 8, 20), 3100, 18000000, "EN_COURS")],
        )
        self.creer_sous_activite(
            activite=a4, libelle="Distribution de kits de lavage des mains et de traitement de l'eau", element=el["RA1.2.1"],
            quantite_prevue=1500, unite="kits", date_debut=date(2026, 4, 1), date_fin=date(2027, 8, 31),
            points=[(date(2026, 4, 1), date(2026, 8, 20), 620, "EN_COURS")],
        )

        self.creer_indicateur(
            libelle="Nombre total de personnes ayant accès à une source d'eau potable améliorée", unite="personnes",
            valeur_reference=0, valeur_cible=8500, frequence="SEMESTRIELLE", rattachement={"projet": projet},
            element=el["AXE1"], valeurs=[(date(2026, 3, 1), date(2026, 6, 30), 1450), (date(2026, 7, 1), date(2026, 8, 20), 980)],
        )
        self.creer_indicateur(
            libelle="Taux de couverture en eau potable dans les zones d'intervention", unite="%",
            valeur_reference=32, valeur_cible=75, frequence="ANNUELLE", rattachement={"activite": og},
            element=None, valeurs=[(date(2026, 3, 1), date(2026, 8, 20), 46)],
        )
        self.creer_indicateur(
            libelle="Nombre de villages certifiés « Fin de défécation à l'air libre » (FDAL)", unite="villages",
            valeur_reference=0, valeur_cible=120, frequence="TRIMESTRIELLE", rattachement={"activite": os2},
            element=el["RA1.2.1"], valeurs=[(date(2026, 3, 15), date(2026, 8, 20), 22)],
        )
        self.creer_indicateur(
            libelle="Fonctionnalité des forages réalisés après 6 mois d'exploitation", unite="%",
            valeur_reference=0, valeur_cible=95, frequence="SEMESTRIELLE", rattachement={"activite": a1},
            element=el["RA1.1.1"], valeurs=[(date(2026, 3, 15), date(2026, 8, 20), 90)],
        )
        self.creer_indicateur(
            libelle="Nombre de personnes sensibilisées aux bonnes pratiques d'hygiène", unite="personnes",
            valeur_reference=0, valeur_cible=8500, frequence="TRIMESTRIELLE", rattachement={"activite": a4},
            element=el["RA1.2.1"], valeurs=[(date(2026, 3, 15), date(2026, 8, 20), 3100)],
        )

        zones_b = self.zones_par_nom("Yatenga", "Loroum")
        self.creer_beneficiaires(
            projet, date(2026, 3, 20), "Bénéficiaire direct — accès à l'eau et assainissement", zones_b,
            [
                ("OUEDRAOGO", "Boureima", "M", 0, ["pdi"]),
                ("SAWADOGO", "Mariam", "F", 0, ["pdi", "femme_chef_menage"]),
                ("ILBOUDO", "Younoussa", "M", 1, ["jeune"]),
                ("KABORE", "Awa", "F", 1, ["handicap"]),
            ],
            "eau",
        )
        self.rattacher_beneficiaires_existants(
            projet, [("NANA", "Issa"), ("TOURE", "Hamidou")], date(2026, 3, 20), "Bénéficiaire — comité de gestion de point d'eau"
        )

    # ------------------------------------------------------------------
    # Projet 4 — Autonomisation économique des femmes et des jeunes
    # ------------------------------------------------------------------
    def creer_projet_autonomisation(self):
        self.stdout.write("Création du projet Autonomisation économique…")
        bailleur_p = self.partenaire("Délégation de l'Union Européenne au Burkina Faso", Partenaire.TypePartenaire.BAILLEUR)
        mise_en_oeuvre_p = self.partenaire("ONG Sahel Solidarité", Partenaire.TypePartenaire.MISE_EN_OEUVRE)

        cadre, el = self.creer_cadre(
            nom="Plan stratégique Autonomisation économique 2026",
            description="Cadre stratégique dédié à l'autonomisation économique des femmes et des jeunes ruraux.",
            axes=[
                (
                    "AXE1",
                    "Autonomisation économique des femmes et des jeunes ruraux",
                    [
                        (
                            "OR1.1",
                            "Accès au financement et développement de l'entrepreneuriat",
                            [("RA1.1.1", "Les femmes et les jeunes développent des activités génératrices de revenus viables")],
                        ),
                        (
                            "OR1.2",
                            "Renforcement des compétences techniques et entrepreneuriales",
                            [("RA1.2.1", "Les bénéficiaires maîtrisent les compétences de gestion et les métiers porteurs")],
                        ),
                    ],
                )
            ],
        )

        projet = Projet.objects.create(
            nom="Projet d'Autonomisation Économique des Femmes et des Jeunes Ruraux",
            code="EXPERTISE-ID-AUTONOMISATION-2026",
            pays=["BF"],
            partenaire_bailleur=bailleur_p,
            partenaire_mise_en_oeuvre=mise_en_oeuvre_p,
            cadre_strategique=cadre,
            budget_total=Decimal("380000000"),
            fonds_propres=Decimal("38000000"),
            date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31),
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.DIRECT,
            chef_de_projet_nom="DIALLO Aissata",
            cible_totale=2500,
            cible_hommes=600,
            cible_femmes=1900,
            cible_jeunes=1700,
            cible_pdi=300,
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        zones = self.zones_par_nom("Nazinon", "Zoundweogo", "Nahouri", "Bazega")
        projet.zones.set(zones)
        projet.utilisateurs_affectes.set([u for u in (self.users["coordo"], self.users["chef_service"]) if u])
        Financement.objects.create(
            projet=projet, bailleur=self.bailleur("Union Européenne"), montant_finance=Decimal("250000000")
        )
        Financement.objects.create(
            projet=projet, bailleur=self.bailleur("Fondation Grameen", Bailleur.TypeBailleur.FONDATION), montant_finance=Decimal("92000000")
        )

        og = Activite.objects.create(
            projet=projet,
            libelle="Contribuer à l'autonomisation économique des femmes et des jeunes ruraux de la région du Nazinon",
            description="Projet pilote d'un an (2026) combinant accès au financement, entrepreneuriat et formation professionnelle courte.",
        )
        os1 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Faciliter l'accès des femmes et des jeunes au financement et à l'entrepreneuriat",
            description="Mise en place de fonds de garantie, appui aux groupements d'épargne et crédit.",
        )
        os2 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Renforcer les compétences techniques et entrepreneuriales des bénéficiaires",
            description="Formation professionnelle courte sur les métiers porteurs et gestion d'entreprise.",
        )

        a1 = self.creer_activite(
            os=os1, code="AA1.1", libelle="Mise en place et capitalisation de groupements d'épargne et de crédit (AVEC)",
            element=el["RA1.1.1"], budget_alloue=80000000, quantite_prevue=100, unite="groupements AVEC",
            date_debut=date(2026, 1, 15), date_fin=date(2026, 10, 31),
            points=[
                (date(2026, 1, 15), date(2026, 6, 30), 58, 38000000, "EN_COURS"),
                (date(2026, 7, 1), date(2026, 8, 20), 27, 21000000, "EN_COURS"),
            ],
        )
        a2 = self.creer_activite(
            os=os1, code="AA1.2", libelle="Octroi de subventions de démarrage pour micro-entreprises portées par des femmes et des jeunes",
            element=el["RA1.1.1"], budget_alloue=110000000, quantite_prevue=350, unite="micro-entreprises appuyées",
            date_debut=date(2026, 3, 1), date_fin=date(2026, 12, 31),
            points=[(date(2026, 3, 1), date(2026, 8, 20), 140, 45000000, "EN_COURS")],
        )
        self.creer_sous_activite(
            activite=a2, libelle="Accompagnement post-financement des micro-entrepreneurs", element=el["RA1.1.1"],
            quantite_prevue=350, unite="entreprises suivies", date_debut=date(2026, 4, 1), date_fin=date(2026, 12, 31),
            points=[(date(2026, 4, 1), date(2026, 8, 20), 112, "EN_COURS")],
        )

        a3 = self.creer_activite(
            os=os2, code="AA2.1", libelle="Formation professionnelle courte sur les métiers porteurs (transformation agroalimentaire, couture, TIC)",
            element=el["RA1.2.1"], budget_alloue=70000000, quantite_prevue=900, unite="personnes formées",
            date_debut=date(2026, 2, 1), date_fin=date(2026, 11, 30),
            points=[(date(2026, 2, 1), date(2026, 8, 20), 610, 48000000, "REALISEE")],
        )
        a4 = self.creer_activite(
            os=os2, code="AA2.2", libelle="Formation en gestion d'entreprise et éducation financière",
            element=el["RA1.2.1"], budget_alloue=40000000, quantite_prevue=900, unite="personnes formées",
            date_debut=date(2026, 2, 15), date_fin=date(2026, 11, 30),
            points=[(date(2026, 2, 15), date(2026, 8, 20), 520, 24000000, "EN_COURS")],
        )
        self.creer_sous_activite(
            activite=a4, libelle="Production et diffusion d'un guide simplifié de gestion financière", element=el["RA1.2.1"],
            quantite_prevue=1, unite="guide", date_debut=date(2026, 2, 15), date_fin=date(2026, 5, 31),
            points=[(date(2026, 2, 15), date(2026, 5, 31), 1, "TERMINEE")],
        )

        self.creer_indicateur(
            libelle="Nombre total de femmes et de jeunes bénéficiaires directs de l'appui économique", unite="personnes",
            valeur_reference=0, valeur_cible=2500, frequence="SEMESTRIELLE", rattachement={"projet": projet},
            element=el["AXE1"], valeurs=[(date(2026, 1, 1), date(2026, 6, 30), 780), (date(2026, 7, 1), date(2026, 8, 20), 510)],
        )
        self.creer_indicateur(
            libelle="Taux de femmes et de jeunes ayant un revenu mensuel en hausse suite à l'appui reçu", unite="%",
            valeur_reference=18, valeur_cible=60, frequence="ANNUELLE", rattachement={"activite": og},
            element=None, valeurs=[(date(2026, 1, 1), date(2026, 8, 20), 37)],
        )
        self.creer_indicateur(
            libelle="Nombre de micro-entreprises actives 6 mois après le financement", unite="micro-entreprises",
            valeur_reference=0, valeur_cible=350, frequence="TRIMESTRIELLE", rattachement={"activite": os1},
            element=el["RA1.1.1"], valeurs=[(date(2026, 3, 1), date(2026, 8, 20), 140)],
        )
        self.creer_indicateur(
            libelle="Nombre de personnes formées appliquant les compétences acquises dans leur activité", unite="personnes",
            valeur_reference=0, valeur_cible=900, frequence="TRIMESTRIELLE", rattachement={"activite": a3},
            element=el["RA1.2.1"], valeurs=[(date(2026, 2, 1), date(2026, 8, 20), 480)],
        )
        self.creer_indicateur(
            libelle="Montant moyen épargné par groupement d'épargne et de crédit", unite="FCFA",
            valeur_reference=0, valeur_cible=500000, frequence="TRIMESTRIELLE", rattachement={"activite": a1},
            element=el["RA1.1.1"], valeurs=[(date(2026, 1, 15), date(2026, 8, 20), 210000)],
        )

        zones_b = self.zones_par_nom("Zoundweogo", "Nahouri")
        self.creer_beneficiaires(
            projet, date(2026, 1, 25), "Bénéficiaire direct — autonomisation économique", zones_b,
            [
                ("KOUDOUGOU", "Bintou", "F", 0, ["jeune", "femme_chef_menage"]),
                ("SANOU", "Adama", "M", 0, ["jeune"]),
                ("BELEM", "Alizeta", "F", 1, ["pdi"]),
                ("OUEDRAOGO", "Moussa", "M", 1, []),
            ],
            "auton",
        )
        self.rattacher_beneficiaires_existants(
            projet, [("Kaboré", "Issa"), ("Traoré", "Awa")], date(2026, 1, 25), "Bénéficiaire — groupement d'épargne"
        )
