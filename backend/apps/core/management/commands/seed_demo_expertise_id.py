"""
Nettoie les données métier (projets, cadres stratégiques, indicateurs,
équipes, intervenants, bénéficiaires, partenaires/bailleurs, notifications)
et les remplace par un jeu de données de démonstration complet et cohérent :
un plan stratégique, deux projets entièrement renseignés, leurs équipes,
indicateurs et bénéficiaires.

Les comptes utilisateurs (accounts_user) et le référentiel géographique
(geo_zone) ne sont jamais touchés.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.beneficiaries.models import Beneficiaire, ParticipationProjet, SignalementDoublon, StatutParticulier
from apps.geo.models import Zone
from apps.indicators.models import Indicateur, ValeurIndicateur
from apps.intervenants.models import Intervenant
from apps.notifications.models import Notification
from apps.partners.models import Bailleur, Financement, Partenaire
from apps.projects.models import Activite, Equipe, Projet, SousActivite
from apps.projects.services import nommer_niveaux
from apps.projects.services import supprimer_projet_cascade
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau
from apps.strategy.services import supprimer_cadre_strategique_cascade

User = get_user_model()


class Command(BaseCommand):
    help = "Vide les données métier et les remplace par un jeu de démonstration complet (Expertise ID)."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.vider()
            self.peupler()
        self.stdout.write(self.style.SUCCESS("Jeu de données de démonstration créé avec succès."))

    # ------------------------------------------------------------------
    # Nettoyage
    # ------------------------------------------------------------------
    def vider(self):
        self.stdout.write("Nettoyage des données métier existantes…")
        for projet in list(Projet.objects.all()):
            supprimer_projet_cascade(projet)
        for cadre in list(CadreStrategique.objects.all()):
            supprimer_cadre_strategique_cascade(cadre)

        Equipe.objects.all().delete()
        Intervenant.objects.all().delete()
        SignalementDoublon.objects.all().delete()
        Beneficiaire.objects.all().delete()
        Bailleur.objects.all().delete()
        Partenaire.objects.all().delete()
        Notification.objects.all().delete()
        self.stdout.write("  … terminé.")

    # ------------------------------------------------------------------
    # Peuplement
    # ------------------------------------------------------------------
    def peupler(self):
        users = self.recuperer_utilisateurs()
        partenaires = self.creer_partenaires_bailleurs()
        statuts = self.creer_statuts_particuliers()
        intervenants = self.creer_intervenants()
        equipes = self.creer_equipes(intervenants)
        cadre, elements = self.creer_cadre_strategique()

        self.stdout.write("Création du projet 1 (Résilience Agroécologique)…")
        self.creer_projet_1(users, partenaires, cadre, elements, intervenants, equipes, statuts)

        self.stdout.write("Création du projet 2 (Sécurité Alimentaire & Gouvernance Locale)…")
        self.creer_projet_2(users, partenaires, cadre, elements, intervenants, equipes, statuts)

    def recuperer_utilisateurs(self):
        def u(username):
            return User.objects.filter(username=username).first()

        return {
            "admin": u("demo_admin"),
            "coordo": u("demo_coordo_general"),
            "charge_se": u("demo_charge_se"),
            "chef_projet": u("demo_chef_projet"),
            "animateur": u("demo_animateur_terrain"),
            "chef_service": u("demo_chef_service"),
        }

    def creer_partenaires_bailleurs(self):
        expertise_id = Partenaire.objects.create(
            nom="Expertise ID",
            type=Partenaire.TypePartenaire.MISE_EN_OEUVRE,
            contact="Direction des programmes",
            email="contact@expertise-id.org",
            telephone="+226 25 30 00 00",
        )
        ue_partenaire = Partenaire.objects.create(
            nom="Délégation de l'Union Européenne au Burkina Faso",
            type=Partenaire.TypePartenaire.BAILLEUR,
            contact="Section Coopération",
            email="delegation-burkina-faso@eeas.europa.eu",
            telephone="+226 25 49 71 00",
        )
        afd_partenaire = Partenaire.objects.create(
            nom="Agence Française de Développement",
            type=Partenaire.TypePartenaire.BAILLEUR,
            contact="Agence AFD Ouagadougou",
            email="ouagadougou@afd.fr",
            telephone="+226 25 49 46 00",
        )

        bailleur_ue = Bailleur.objects.create(
            nom="Union Européenne", type=Bailleur.TypeBailleur.INSTITUTIONNEL, contact="Délégation UE Ouagadougou"
        )
        bailleur_afd = Bailleur.objects.create(
            nom="Agence Française de Développement",
            type=Bailleur.TypeBailleur.COOPERATION_BILATERALE,
            contact="Agence AFD Ouagadougou",
        )
        bailleur_ff = Bailleur.objects.create(
            nom="Fondation de France", type=Bailleur.TypeBailleur.FONDATION, contact="Pôle International"
        )

        return {
            "expertise_id": expertise_id,
            "ue_partenaire": ue_partenaire,
            "afd_partenaire": afd_partenaire,
            "bailleur_ue": bailleur_ue,
            "bailleur_afd": bailleur_afd,
            "bailleur_ff": bailleur_ff,
        }

    def creer_statuts_particuliers(self):
        def get_or_create(code, libelle):
            statut, _ = StatutParticulier.objects.get_or_create(code=code, defaults={"libelle": libelle})
            return statut

        return {
            "pdi": get_or_create("PDI", "Personne déplacée interne"),
            "jeune": get_or_create("JEUNE", "Jeune (moins de 35 ans)"),
            "femme_chef_menage": get_or_create("FEMME_CHEF_MENAGE", "Femme cheffe de ménage"),
            "handicap": get_or_create("HANDICAP", "Personne en situation de handicap"),
        }

    def creer_intervenants(self):
        def i(nom, prenom, fonction, contact):
            return Intervenant.objects.create(nom=nom, prenom=prenom, fonction=fonction, contact=contact)

        return {
            "ouedraogo": i("OUEDRAOGO", "Awa", "Chargée de Suivi-Évaluation", "+226 70 12 34 56"),
            "sawadogo": i("SAWADOGO", "Boukary", "Coordonnateur de projet", "+226 70 22 33 44"),
            "kabore": i("KABORE", "Fatimata", "Animatrice terrain", "+226 76 11 22 33"),
            "traore": i("TRAORE", "Ali", "Technicien agroécologie", "+226 71 44 55 66"),
            "zongo": i("ZONGO", "Salif", "Chef d'équipe terrain", "+226 78 55 66 77"),
            "nikiema": i("NIKIEMA", "Aminata", "Chargée de nutrition", "+226 72 66 77 88"),
            "compaore": i("COMPAORE", "Issouf", "Animateur communautaire", "+226 75 77 88 99"),
            "sanou": i("SANOU", "Mariam", "Assistante administrative et financière", "+226 70 88 99 00"),
            "bationo": i("BATIONO", "Rasmané", "Technicien génie rural", "+226 73 99 00 11"),
            "diallo": i("DIALLO", "Aissata", "Chargée de genre et gouvernance", "+226 74 00 11 22"),
        }

    def creer_equipes(self, iv):
        equipe_coord = Equipe.objects.create(
            nom="Équipe coordination Expertise ID",
            date_debut_contrat=date(2024, 1, 1),
            date_fin_contrat=date(2027, 12, 31),
        )
        equipe_coord.membres.set([iv["sawadogo"], iv["ouedraogo"], iv["kabore"]])

        equipe_nakambe = Equipe.objects.create(
            nom="Équipe terrain Nakambe",
            date_debut_contrat=date(2024, 2, 1),
            date_fin_contrat=date(2027, 12, 31),
        )
        equipe_nakambe.membres.set([iv["zongo"], iv["compaore"], iv["sanou"], iv["traore"]])

        equipe_sahel = Equipe.objects.create(
            nom="Équipe terrain Sahel",
            date_debut_contrat=date(2025, 3, 1),
            date_fin_contrat=date(2028, 2, 29),
        )
        equipe_sahel.membres.set([iv["bationo"], iv["diallo"], iv["nikiema"]])

        return {"coord": equipe_coord, "nakambe": equipe_nakambe, "sahel": equipe_sahel}

    def creer_cadre_strategique(self):
        cadre = CadreStrategique.objects.create(
            nom="Plan stratégique Expertise ID 2024–2028",
            description=(
                "Cadre stratégique quinquennal d'Expertise ID, structurant l'ensemble de ses projets "
                "autour de trois axes prioritaires : résilience agroécologique, sécurité alimentaire "
                "et nutritionnelle, gouvernance locale et cohésion sociale."
            ),
        )

        niveau_axe = TypeNiveau.objects.create(
            cadre_strategique=cadre, nom_niveau="Axe stratégique", ordre=1, aide_code="Ex : AXE1"
        )
        niveau_orientation = TypeNiveau.objects.create(
            cadre_strategique=cadre,
            nom_niveau="Orientation stratégique",
            ordre=2,
            niveau_parent=niveau_axe,
            aide_code="Ex : OR1.1",
        )
        niveau_resultat = TypeNiveau.objects.create(
            cadre_strategique=cadre,
            nom_niveau="Résultat attendu",
            ordre=3,
            niveau_parent=niveau_orientation,
            aide_code="Ex : RA1.1.1",
        )

        def axe(code, nom):
            return ElementStrategique.objects.create(type_niveau=niveau_axe, code=code, nom=nom)

        def orientation(parent, code, nom):
            return ElementStrategique.objects.create(
                type_niveau=niveau_orientation, element_parent=parent, code=code, nom=nom
            )

        def resultat(parent, code, nom):
            return ElementStrategique.objects.create(
                type_niveau=niveau_resultat, element_parent=parent, code=code, nom=nom
            )

        axe1 = axe("AXE1", "Renforcement de la résilience agroécologique des communautés rurales")
        or11 = orientation(
            axe1, "OR1.1", "Promotion des pratiques agroécologiques et de gestion durable des ressources naturelles"
        )
        ra111 = resultat(or11, "RA1.1.1", "Les producteurs et productrices adoptent des pratiques agroécologiques durables")
        ra112 = resultat(or11, "RA1.1.2", "La fertilité des sols est restaurée dans les zones d'intervention")
        or12 = orientation(axe1, "OR1.2", "Renforcement des capacités techniques et organisationnelles des producteurs")
        ra121 = resultat(or12, "RA1.2.1", "Les organisations paysannes sont structurées et autonomes")
        ra122 = resultat(or12, "RA1.2.2", "L'accès aux intrants et équipements agroécologiques est amélioré")

        axe2 = axe("AXE2", "Amélioration de la sécurité alimentaire et nutritionnelle des ménages vulnérables")
        or21 = orientation(axe2, "OR2.1", "Diversification des sources de revenus et des productions")
        ra211 = resultat(or21, "RA2.1.1", "Les ménages disposent de revenus diversifiés et stables")
        ra212 = resultat(or21, "RA2.1.2", "La production maraîchère et vivrière est intensifiée")
        or22 = orientation(axe2, "OR2.2", "Prévention et prise en charge de la malnutrition")
        ra221 = resultat(or22, "RA2.2.1", "Les pratiques nutritionnelles des ménages sont améliorées")

        axe3 = axe("AXE3", "Renforcement de la gouvernance locale et de la résilience communautaire")
        or31 = orientation(axe3, "OR3.1", "Appui à la gouvernance locale et à la cohésion sociale")
        ra311 = resultat(or31, "RA3.1.1", "Les instances locales de gouvernance sont fonctionnelles")
        or32 = orientation(axe3, "OR3.2", "Prévention et gestion des conflits liés aux ressources naturelles")
        ra321 = resultat(or32, "RA3.2.1", "Les mécanismes de médiation communautaire sont opérationnels")

        elements = {
            "axe1": axe1, "or11": or11, "ra111": ra111, "ra112": ra112, "or12": or12, "ra121": ra121, "ra122": ra122,
            "axe2": axe2, "or21": or21, "ra211": ra211, "ra212": ra212, "or22": or22, "ra221": ra221,
            "axe3": axe3, "or31": or31, "ra311": ra311, "or32": or32, "ra321": ra321,
        }
        return cadre, elements

    def zones_par_nom(self, *noms):
        return list(Zone.objects.filter(nom__in=noms))

    # ------------------------------------------------------------------
    # Projet 1
    # ------------------------------------------------------------------
    def creer_projet_1(self, users, partenaires, cadre, el, iv, eq, statuts):
        projet = Projet.objects.create(
            nom="Programme d'Appui à la Résilience Agroécologique et Alimentaire",
            code="EXPERTISE-ID-RA-2024",
            pays=["BF"],
            partenaire_bailleur=partenaires["ue_partenaire"],
            cadre_strategique=cadre,
            budget_total=Decimal("850000000"),
            fonds_propres=Decimal("85000000"),
            date_debut=date(2024, 1, 1),
            date_fin=date(2027, 12, 31),
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.DIRECT,
            chef_de_projet_nom="SAWADOGO Boukary",
            cible_totale=5000,
            cible_hommes=2000,
            cible_femmes=3000,
            cible_jeunes=1800,
            cible_pdi=600,
            elements_capitalisation=(
                "Les champs-écoles paysans se révèlent être le format de formation le plus efficace pour "
                "l'adoption durable des pratiques agroécologiques — capitalisé pour réplication sur le projet 2."
            ),
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        projet.zones.set(self.zones_par_nom("Nakambe", "Boulgou", "Koulpelogo", "Kourittenga"))
        projet.utilisateurs_affectes.set(
            [u for u in (users["chef_projet"], users["charge_se"], users["animateur"]) if u]
        )

        Financement.objects.create(projet=projet, bailleur=partenaires["bailleur_ue"], montant_finance=Decimal("500000000"))
        Financement.objects.create(projet=projet, bailleur=partenaires["bailleur_afd"], montant_finance=Decimal("265000000"))

        og = Activite.objects.create(
            projet=projet,
            libelle=(
                "Contribuer à l'amélioration durable de la résilience agroécologique et alimentaire des "
                "ménages ruraux vulnérables de la région du Nakambe"
            ),
            description=(
                "Le programme vise à renforcer l'adoption de pratiques agroécologiques durables et la "
                "structuration des organisations paysannes sur un horizon de quatre ans (2024-2027)."
            ),
        )

        os11 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Renforcer l'adoption de pratiques agroécologiques durables par les producteurs et productrices",
            description="Formation, accompagnement technique et aménagements de conservation des eaux et des sols.",
        )
        os12 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Améliorer la structuration et l'autonomisation des organisations paysannes",
            description="Appui institutionnel aux organisations paysannes et facilitation de l'accès aux intrants.",
        )

        a111 = Activite.objects.create(
            projet=os11.projet, activite_parent=os11,
            code_activite="A1.1.1",
            libelle="Formation des producteurs et productrices aux techniques agroécologiques (compost, CES/DRS, agroforesterie)",
            statut=Activite.Statut.EN_COURS,
            axe_strategique=el["ra111"],
            budget_alloue=Decimal("45000000"),
            budget_realise=Decimal("18000000"),
            quantite_prevue=Decimal("1200"),
            quantite_realisee=Decimal("540"),
            unite_quantite="producteurs formés",
            date_debut=date(2024, 3, 1),
            date_fin=date(2025, 12, 31),
            date_debut_reelle=date(2024, 3, 15),
            equipe_responsable=eq["nakambe"],
        )
        a111.responsables.set([iv["zongo"], iv["traore"]])
        SousActivite.objects.create(
            activite=a111,
            libelle="Organisation de sessions de formation pratique en champs-écoles paysans",
            axe_strategique=el["ra111"],
            quantite_prevue=Decimal("40"),
            quantite_realisee=Decimal("18"),
            unite_quantite="sessions",
            date_debut=date(2024, 3, 15),
            date_fin=date(2025, 6, 30),
            statut=SousActivite.Statut.EN_COURS,
        )

        a112 = Activite.objects.create(
            projet=os11.projet, activite_parent=os11,
            code_activite="A1.1.2",
            libelle="Aménagement de dispositifs de conservation des eaux et des sols (cordons pierreux, zaï, demi-lunes)",
            statut=Activite.Statut.EN_COURS,
            axe_strategique=el["ra112"],
            budget_alloue=Decimal("60000000"),
            budget_realise=Decimal("21000000"),
            quantite_prevue=Decimal("300"),
            quantite_realisee=Decimal("95"),
            unite_quantite="hectares",
            date_debut=date(2024, 4, 1),
            date_fin=date(2026, 6, 30),
            date_debut_reelle=date(2024, 4, 10),
            equipe_responsable=eq["nakambe"],
        )
        a112.responsables.set([iv["compaore"]])
        SousActivite.objects.create(
            activite=a112,
            libelle="Réalisation de chantiers communautaires d'aménagement CES/DRS",
            axe_strategique=el["ra112"],
            quantite_prevue=Decimal("300"),
            quantite_realisee=Decimal("95"),
            unite_quantite="hectares",
            date_debut=date(2024, 4, 15),
            date_fin=date(2026, 6, 30),
            statut=SousActivite.Statut.EN_COURS,
        )

        a121 = Activite.objects.create(
            projet=os12.projet, activite_parent=os12,
            code_activite="A1.2.1",
            libelle="Appui à la structuration et à la formalisation des organisations paysannes",
            statut=Activite.Statut.EN_COURS,
            axe_strategique=el["ra121"],
            budget_alloue=Decimal("25000000"),
            budget_realise=Decimal("9000000"),
            quantite_prevue=Decimal("40"),
            quantite_realisee=Decimal("11"),
            unite_quantite="organisations paysannes",
            date_debut=date(2024, 5, 1),
            date_fin=date(2026, 12, 31),
            date_debut_reelle=date(2024, 5, 20),
            equipe_responsable=eq["coord"],
        )
        a121.responsables.set([iv["ouedraogo"], iv["kabore"]])
        SousActivite.objects.create(
            activite=a121,
            libelle="Accompagnement à l'élaboration des textes statutaires et à l'enregistrement légal",
            axe_strategique=el["ra121"],
            quantite_prevue=Decimal("40"),
            quantite_realisee=Decimal("11"),
            unite_quantite="dossiers",
            date_debut=date(2024, 6, 1),
            date_fin=date(2026, 12, 31),
            statut=SousActivite.Statut.EN_COURS,
        )

        a122 = Activite.objects.create(
            projet=os12.projet, activite_parent=os12,
            code_activite="A1.2.2",
            libelle="Facilitation de l'accès aux intrants et équipements agroécologiques",
            statut=Activite.Statut.NON_REALISEE,
            axe_strategique=el["ra122"],
            budget_alloue=Decimal("30000000"),
            budget_realise=Decimal("4000000"),
            quantite_prevue=Decimal("12"),
            quantite_realisee=Decimal("3"),
            unite_quantite="boutiques d'intrants",
            date_debut=date(2025, 1, 1),
            date_fin=date(2027, 6, 30),
            equipe_responsable=eq["nakambe"],
        )
        a122.responsables.set([iv["sanou"]])
        SousActivite.objects.create(
            activite=a122,
            libelle="Mise en place d'un système de warrantage / boutique d'intrants communautaire",
            axe_strategique=el["ra122"],
            quantite_prevue=Decimal("12"),
            quantite_realisee=Decimal("3"),
            unite_quantite="boutiques",
            date_debut=date(2025, 1, 15),
            date_fin=date(2027, 6, 30),
            statut=SousActivite.Statut.PLANIFIEE,
        )

        # Indicateurs
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre total de bénéficiaires directs touchés par le programme",
            unite="personnes",
            valeur_reference=0,
            valeur_cible=5000,
            frequence="ANNUELLE",
            rattachement={"projet": projet},
            elements=[el["axe1"]],
            valeurs=[(date(2024, 1, 1), date(2024, 12, 31), 1800), (date(2025, 1, 1), date(2025, 12, 31), 1400)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Taux d'adoption de pratiques agroécologiques durables par les producteurs formés",
            unite="%",
            valeur_reference=0,
            valeur_cible=75,
            frequence="ANNUELLE",
            rattachement={"activite": og},
            elements=[],
            valeurs=[(date(2024, 1, 1), date(2024, 12, 31), 30), (date(2025, 1, 1), date(2025, 12, 31), 25)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre de producteurs et productrices formés aux techniques agroécologiques",
            unite="producteurs",
            valeur_reference=0,
            valeur_cible=1200,
            frequence="SEMESTRIELLE",
            rattachement={"activite": os11},
            elements=[el["ra111"]],
            valeurs=[(date(2024, 1, 1), date(2024, 12, 31), 300), (date(2025, 1, 1), date(2025, 12, 31), 450)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre d'organisations paysannes formalisées et fonctionnelles",
            unite="organisations",
            valeur_reference=0,
            valeur_cible=30,
            frequence="ANNUELLE",
            rattachement={"activite": os12},
            elements=[el["ra121"]],
            valeurs=[(date(2024, 1, 1), date(2024, 12, 31), 10), (date(2025, 1, 1), date(2025, 12, 31), 17)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Superficie aménagée en dispositifs de conservation des eaux et des sols",
            unite="hectares",
            valeur_reference=0,
            valeur_cible=300,
            frequence="SEMESTRIELLE",
            rattachement={"activite": a112},
            elements=[el["ra112"]],
            valeurs=[(date(2024, 1, 1), date(2024, 12, 31), 40), (date(2025, 1, 1), date(2025, 12, 31), 55)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre de boutiques d'intrants communautaires opérationnelles",
            unite="boutiques",
            valeur_reference=0,
            valeur_cible=12,
            frequence="ANNUELLE",
            rattachement={"activite": a122},
            elements=[el["ra122"]],
            valeurs=[(date(2025, 1, 1), date(2025, 12, 31), 3)],
            saisi_par=users["charge_se"],
        )

        # Bénéficiaires
        zone_boulgou = Zone.objects.filter(nom="Boulgou").first()
        zone_koulpelogo = Zone.objects.filter(nom="Koulpelogo").first()
        beneficiaires_data = [
            ("SOME", "Adama", "M", zone_boulgou, ["jeune"]),
            ("OUATTARA", "Rasmata", "F", zone_boulgou, ["femme_chef_menage"]),
            ("KABORE", "Boureima", "M", zone_koulpelogo, []),
            ("YAMEOGO", "Salamata", "F", zone_koulpelogo, ["jeune", "femme_chef_menage"]),
            ("NANA", "Issa", "M", zone_boulgou, ["handicap"]),
        ]
        for nom, prenom, sexe, zone, codes_statuts in beneficiaires_data:
            beneficiaire = Beneficiaire.objects.create(
                nom=nom,
                prenom=prenom,
                sexe=sexe,
                telephone="+226 7" + str(hash((nom, prenom)) % 10000000).zfill(7),
                numero_piece_identite="B" + str(abs(hash((nom, prenom))) % 100000000),
                type_piece="CNIB",
                zone=zone,
            )
            if codes_statuts:
                beneficiaire.statuts_particuliers.set([statuts[c] for c in codes_statuts])
            ParticipationProjet.objects.create(
                beneficiaire=beneficiaire,
                projet=projet,
                date_inscription=date(2024, 3, 1),
                role_dans_projet="Bénéficiaire direct — formation agroécologique",
            )

    # ------------------------------------------------------------------
    # Projet 2
    # ------------------------------------------------------------------
    def creer_projet_2(self, users, partenaires, cadre, el, iv, eq, statuts):
        projet = Projet.objects.create(
            nom="Projet de Renforcement de la Sécurité Alimentaire et de la Gouvernance Locale",
            code="EXPERTISE-ID-SAGL-2025",
            pays=["BF"],
            partenaire_bailleur=partenaires["afd_partenaire"],
            cadre_strategique=cadre,
            budget_total=Decimal("620000000"),
            fonds_propres=Decimal("62000000"),
            date_debut=date(2025, 3, 1),
            date_fin=date(2028, 2, 29),
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.CONSORTIUM,
            chef_de_projet_nom="OUEDRAOGO Awa",
            cible_totale=3500,
            cible_hommes=1300,
            cible_femmes=2200,
            cible_jeunes=1100,
            cible_pdi=900,
            elements_capitalisation="",
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        projet.zones.set(self.zones_par_nom("Liptako", "Oudalan", "Seno", "Yagha"))
        projet.utilisateurs_affectes.set(
            [u for u in (users["coordo"], users["charge_se"], users["chef_service"]) if u]
        )

        Financement.objects.create(projet=projet, bailleur=partenaires["bailleur_afd"], montant_finance=Decimal("400000000"))
        Financement.objects.create(projet=projet, bailleur=partenaires["bailleur_ff"], montant_finance=Decimal("158000000"))

        og = Activite.objects.create(
            projet=projet,
            libelle=(
                "Contribuer à la réduction de l'insécurité alimentaire et au renforcement de la gouvernance "
                "locale dans les zones à forte pression sur les ressources naturelles de la région du Liptako"
            ),
            description=(
                "Le projet combine diversification des revenus, intensification maraîchère et appui à la "
                "gouvernance locale pour renforcer la résilience des ménages les plus vulnérables, dont de "
                "nombreuses personnes déplacées internes, sur un horizon de trois ans (2025-2028)."
            ),
        )

        os21 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Diversifier les sources de revenus et intensifier la production maraîchère et vivrière",
            description="Appui aux activités génératrices de revenus et développement de périmètres maraîchers irrigués.",
        )
        os22 = Activite.objects.create(
            projet=og.projet, activite_parent=og,
            libelle="Renforcer la gouvernance locale et la cohésion sociale autour des ressources naturelles",
            description="Appui aux instances locales de gouvernance et mise en place de mécanismes de médiation.",
        )

        a211 = Activite.objects.create(
            projet=os21.projet, activite_parent=os21,
            code_activite="A2.1.1",
            libelle="Appui à la diversification des activités génératrices de revenus (AGR) pour les femmes et les jeunes",
            statut=Activite.Statut.EN_COURS,
            axe_strategique=el["ra211"],
            budget_alloue=Decimal("55000000"),
            budget_realise=Decimal("12000000"),
            quantite_prevue=Decimal("60"),
            quantite_realisee=Decimal("18"),
            unite_quantite="groupements d'AGR",
            date_debut=date(2025, 4, 1),
            date_fin=date(2027, 3, 31),
            date_debut_reelle=date(2025, 4, 20),
            equipe_responsable=eq["sahel"],
        )
        a211.responsables.set([iv["diallo"], iv["nikiema"]])
        SousActivite.objects.create(
            activite=a211,
            libelle="Octroi de kits de démarrage et accompagnement des groupements d'AGR",
            axe_strategique=el["ra211"],
            quantite_prevue=Decimal("60"),
            quantite_realisee=Decimal("18"),
            unite_quantite="groupements",
            date_debut=date(2025, 5, 1),
            date_fin=date(2027, 3, 31),
            statut=SousActivite.Statut.EN_COURS,
        )

        a212 = Activite.objects.create(
            projet=os21.projet, activite_parent=os21,
            code_activite="A2.1.2",
            libelle="Développement de périmètres maraîchers communautaires irrigués",
            statut=Activite.Statut.EN_COURS,
            axe_strategique=el["ra212"],
            budget_alloue=Decimal("90000000"),
            budget_realise=Decimal("22000000"),
            quantite_prevue=Decimal("50"),
            quantite_realisee=Decimal("14"),
            unite_quantite="hectares",
            date_debut=date(2025, 5, 1),
            date_fin=date(2027, 12, 31),
            date_debut_reelle=date(2025, 5, 15),
            equipe_responsable=eq["sahel"],
        )
        a212.responsables.set([iv["bationo"]])
        SousActivite.objects.create(
            activite=a212,
            libelle="Aménagement et équipement de périmètres maraîchers",
            axe_strategique=el["ra212"],
            quantite_prevue=Decimal("50"),
            quantite_realisee=Decimal("14"),
            unite_quantite="hectares",
            date_debut=date(2025, 6, 1),
            date_fin=date(2027, 12, 31),
            statut=SousActivite.Statut.EN_COURS,
        )

        a221 = Activite.objects.create(
            projet=os22.projet, activite_parent=os22,
            code_activite="A2.2.1",
            libelle="Appui au fonctionnement des instances locales de gouvernance (CVD, cadres de concertation)",
            statut=Activite.Statut.EN_COURS,
            axe_strategique=el["ra311"],
            budget_alloue=Decimal("28000000"),
            budget_realise=Decimal("9000000"),
            quantite_prevue=Decimal("20"),
            quantite_realisee=Decimal("17"),
            unite_quantite="sessions de dialogue",
            date_debut=date(2025, 4, 1),
            date_fin=date(2028, 2, 29),
            date_debut_reelle=date(2025, 4, 10),
            equipe_responsable=eq["coord"],
        )
        a221.responsables.set([iv["sawadogo"], iv["kabore"]])
        SousActivite.objects.create(
            activite=a221,
            libelle="Organisation de sessions de dialogue communautaire et de reddition de comptes",
            axe_strategique=el["ra311"],
            quantite_prevue=Decimal("20"),
            quantite_realisee=Decimal("17"),
            unite_quantite="sessions",
            date_debut=date(2025, 4, 15),
            date_fin=date(2028, 2, 29),
            statut=SousActivite.Statut.EN_COURS,
        )

        a222 = Activite.objects.create(
            projet=os22.projet, activite_parent=os22,
            code_activite="A2.2.2",
            libelle="Mise en place de mécanismes communautaires de prévention et de médiation des conflits fonciers",
            statut=Activite.Statut.NON_REALISEE,
            axe_strategique=el["ra321"],
            budget_alloue=Decimal("20000000"),
            budget_realise=Decimal("0"),
            quantite_prevue=Decimal("15"),
            quantite_realisee=Decimal("0"),
            unite_quantite="comités de médiation",
            date_debut=date(2026, 1, 1),
            date_fin=date(2028, 2, 29),
            equipe_responsable=eq["sahel"],
        )
        a222.responsables.set([iv["diallo"]])
        SousActivite.objects.create(
            activite=a222,
            libelle="Formation de comités locaux de médiation",
            axe_strategique=el["ra321"],
            quantite_prevue=Decimal("15"),
            quantite_realisee=Decimal("0"),
            unite_quantite="comités",
            date_debut=date(2026, 1, 15),
            date_fin=date(2028, 2, 29),
            statut=SousActivite.Statut.PLANIFIEE,
        )

        # Indicateurs
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre de ménages bénéficiaires de l'appui à la sécurité alimentaire",
            unite="ménages",
            valeur_reference=0,
            valeur_cible=3500,
            frequence="ANNUELLE",
            rattachement={"projet": projet},
            elements=[el["axe2"], el["axe3"]],
            valeurs=[(date(2025, 3, 1), date(2025, 12, 31), 900)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Taux de ménages ayant un score de diversité alimentaire acceptable",
            unite="%",
            valeur_reference=22,
            valeur_cible=70,
            frequence="ANNUELLE",
            rattachement={"activite": og},
            elements=[el["ra221"]],
            valeurs=[(date(2025, 3, 1), date(2025, 12, 31), 38)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre de groupements d'AGR appuyés et fonctionnels",
            unite="groupements",
            valeur_reference=0,
            valeur_cible=60,
            frequence="SEMESTRIELLE",
            rattachement={"activite": os21},
            elements=[el["ra211"]],
            valeurs=[(date(2025, 3, 1), date(2025, 12, 31), 18)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre d'instances locales de gouvernance appuyées et fonctionnelles",
            unite="instances",
            valeur_reference=0,
            valeur_cible=25,
            frequence="ANNUELLE",
            rattachement={"activite": os22},
            elements=[el["ra311"], el["ra321"]],
            valeurs=[(date(2025, 3, 1), date(2025, 12, 31), 22)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Superficie de périmètres maraîchers aménagés et irrigués",
            unite="hectares",
            valeur_reference=0,
            valeur_cible=50,
            frequence="SEMESTRIELLE",
            rattachement={"activite": a212},
            elements=[el["ra212"]],
            valeurs=[(date(2025, 3, 1), date(2025, 12, 31), 14)],
            saisi_par=users["charge_se"],
        )
        self.creer_indicateur_avec_valeurs(
            libelle="Nombre de sessions de dialogue communautaire organisées",
            unite="sessions",
            valeur_reference=0,
            valeur_cible=20,
            frequence="TRIMESTRIELLE",
            rattachement={"activite": a221},
            elements=[el["ra311"]],
            valeurs=[(date(2025, 3, 1), date(2025, 12, 31), 17)],
            saisi_par=users["charge_se"],
        )

        # Bénéficiaires
        zone_oudalan = Zone.objects.filter(nom="Oudalan").first()
        zone_seno = Zone.objects.filter(nom="Seno").first()
        beneficiaires_data = [
            ("MAIGA", "Fatoumata", "F", zone_oudalan, ["pdi", "femme_chef_menage"]),
            ("CISSE", "Boureima", "M", zone_oudalan, ["pdi"]),
            ("DICKO", "Aissa", "F", zone_seno, ["jeune"]),
            ("TOURE", "Hamidou", "M", zone_seno, []),
            ("BARRY", "Zenabou", "F", zone_oudalan, ["pdi", "jeune"]),
        ]
        for nom, prenom, sexe, zone, codes_statuts in beneficiaires_data:
            beneficiaire = Beneficiaire.objects.create(
                nom=nom,
                prenom=prenom,
                sexe=sexe,
                telephone="+226 7" + str(hash((nom, prenom, "p2")) % 10000000).zfill(7),
                numero_piece_identite="B" + str(abs(hash((nom, prenom, "p2"))) % 100000000),
                type_piece="CNIB",
                zone=zone,
            )
            if codes_statuts:
                beneficiaire.statuts_particuliers.set([statuts[c] for c in codes_statuts])
            ParticipationProjet.objects.create(
                beneficiaire=beneficiaire,
                projet=projet,
                date_inscription=date(2025, 4, 1),
                role_dans_projet="Bénéficiaire direct — appui AGR / maraîchage",
            )

    # ------------------------------------------------------------------
    # Helper indicateurs
    # ------------------------------------------------------------------
    def creer_indicateur_avec_valeurs(
        self, *, libelle, unite, valeur_reference, valeur_cible, frequence, rattachement, elements, valeurs, saisi_par
    ):
        indicateur = Indicateur.objects.create(
            libelle=libelle,
            unite=unite,
            valeur_reference=Decimal(str(valeur_reference)),
            valeur_cible=Decimal(str(valeur_cible)),
            frequence_collecte=frequence,
            **rattachement,
        )
        if elements:
            indicateur.elements_strategiques.set(elements)
        for periode_debut, periode_fin, valeur in valeurs:
            ValeurIndicateur.objects.create(
                indicateur=indicateur,
                periode_debut=periode_debut,
                periode_fin=periode_fin,
                valeur_realisee=Decimal(str(valeur)),
                saisi_par=saisi_par,
            )
        return indicateur
