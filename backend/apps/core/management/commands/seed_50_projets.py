"""
Remplace toutes les données métier (projets, cadres stratégiques, indicateurs, équipes, intervenants,
bénéficiaires, bailleurs, partenaires, parties prenantes, structures, notifications) par 4 cadres
stratégiques et 50 projets entièrement renseignés : planification à 3 niveaux avec sous-activités,
planification par période, suivi réalisé, indicateurs et valeurs, financements multi-bailleurs et
rallonges, partenaires, équipe, risques et réévaluations, documents (GED), jalons et livrables,
cadre logique, bénéficiaires. Les comptes utilisateurs et le référentiel géographique sont conservés.
Graine fixe : mêmes données d'une base à l'autre (aux zones près).

ATTENTION : vide d'abord toutes les données métier de la base. Usage :
    docker compose exec backend python manage.py seed_50_projets
Puis, pour la chaîne des documents (programme, piliers) : seed_chaine_documents.
"""
import random

from django.core.management.base import BaseCommand
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.beneficiaries.models import (
    Beneficiaire, ParticipationProjet, SignalementDoublon, StatutParticulier, TypeActiviteBeneficiaire,
)
from apps.documents.models import Document, DocumentVersion, Dossier
from apps.geo.models import Zone
from apps.indicators.models import Indicateur, IndicateurElement, ValeurIndicateur
from apps.intervenants.models import Intervenant
from apps.notifications.models import Notification
from apps.partners.models import (
    Bailleur, CategoriePartiePrenante, Financement, Partenaire, PartiePrenante, RallongeFinancement,
    StructureOrganisation,
)
from apps.projects.models import (
    Activite, Equipe, EvaluationRisque, JalonLivrable, PartenaireProjet, Projet, Risque, SousActivite,
)
from apps.projects.services import nommer_niveaux, supprimer_projet_cascade
from apps.projects.verrou import verrou_desactive
from apps.strategy.models import AppreciationStrategique, CadreStrategique, ElementStrategique, TypeNiveau
from apps.strategy.services import supprimer_cadre_strategique_cascade
from apps.suivi.models import PeriodePlanification, PointSuivi, TranchePlanifiee
from apps.suivi.services import synchroniser_activite_depuis_suivi, synchroniser_sous_activite_depuis_suivi

random.seed(20261029)
User = get_user_model()
AUJOURDHUI = timezone.localdate()
NB_PROJETS = 50

# ----------------------------------------------------------------------------------------------
# Contenu par secteur : 3 thèmes (objectifs) × 2 résultats × 3 activités, chacun avec son indicateur.
# ----------------------------------------------------------------------------------------------
SECTEURS = {
    "AGRI": {
        "cadre": "B", "axe": ("P1", "Production agricole durable"),
        "projets": [("Projet d'appui à la productivité agricole", "PAPA"), ("Programme de résilience des exploitations familiales", "PREF"),
                    ("Projet de développement de l'irrigation de proximité", "PDIP"), ("Projet de valorisation des produits agricoles", "PVPA"),
                    ("Programme d'intensification agricole durable", "PIAD")],
        "types_benef": ["Agriculture pluviale", "Maraîchage", "Transformation agroalimentaire"],
        "themes": [
            ("Accroître durablement la production agricole des exploitations familiales", ("Rendement moyen des céréales dans les exploitations appuyées", "kg/ha", 1400), [
                ("Les producteurs adoptent des techniques culturales améliorées", ("Nombre de producteurs appliquant au moins trois techniques améliorées", "producteurs", 2500), [
                    ("Formation des producteurs aux itinéraires techniques améliorés", "producteurs", 2400),
                    ("Installation de champs-écoles paysans", "champs-écoles", 80),
                    ("Diffusion de semences améliorées certifiées", "tonnes", 150)]),
                ("Les terres dégradées sont récupérées et restaurées", ("Superficie de terres dégradées récupérées", "hectares", 1200), [
                    ("Réalisation de cordons pierreux", "hectares", 800),
                    ("Aménagement de demi-lunes et de zaï", "hectares", 500),
                    ("Production de fumure organique en fosses fumières", "fosses", 1500)])]),
            ("Améliorer la maîtrise de l'eau agricole", ("Superficie irriguée exploitée en contre-saison", "hectares", 450), [
                ("Les aménagements hydro-agricoles sont réalisés", ("Nombre de bas-fonds aménagés et exploités", "bas-fonds", 25), [
                    ("Aménagement de bas-fonds rizicoles", "hectares", 300),
                    ("Réalisation de forages maraîchers équipés", "forages", 30),
                    ("Installation de kits d'irrigation goutte-à-goutte", "kits", 500)]),
                ("Les comités d'usagers gèrent durablement les ouvrages", ("Proportion de comités de gestion fonctionnels", "%", 85), [
                    ("Mise en place des comités de gestion des aménagements", "comités", 40),
                    ("Formation des comités à l'entretien des ouvrages", "sessions", 60),
                    ("Appui à l'élaboration des règles locales de gestion", "conventions locales", 40)])]),
            ("Renforcer la mise en marché des produits agricoles", ("Volume de produits commercialisés par les organisations appuyées", "tonnes", 3000), [
                ("Les infrastructures de stockage et de transformation sont opérationnelles", ("Nombre de magasins de stockage fonctionnels", "magasins", 15), [
                    ("Construction de magasins de stockage", "magasins", 15),
                    ("Équipement d'unités de transformation", "unités", 30),
                    ("Mise en place du warrantage", "sacs warrantés", 6000)]),
                ("Les organisations paysannes accèdent à des marchés rémunérateurs", ("Nombre de contrats commerciaux signés par les OP", "contrats", 60), [
                    ("Organisation de bourses aux céréales", "bourses", 10),
                    ("Mise en relation avec les acheteurs institutionnels", "rencontres", 24),
                    ("Formation des OP en gestion commerciale", "OP formées", 80)])]),
        ],
    },
    "NUT": {
        "cadre": "B", "axe": ("P2", "Nutrition et protection sociale"),
        "projets": [("Projet de lutte contre la malnutrition infantile", "PLMI"), ("Programme d'amélioration de la nutrition des ménages", "PANM"),
                    ("Projet de filets sociaux adaptatifs", "PFSA"), ("Programme nutrition et résilience communautaire", "PNRC")],
        "types_benef": ["Maraîchage", "Petit commerce", "Élevage"],
        "themes": [
            ("Réduire la malnutrition des enfants de moins de cinq ans", ("Proportion d'enfants de 6 à 23 mois recevant une alimentation minimum acceptable", "%", 60), [
                ("Les cas de malnutrition sont dépistés et pris en charge", ("Nombre d'enfants malnutris pris en charge", "enfants", 6000), [
                    ("Dépistage actif de la malnutrition dans les villages", "enfants dépistés", 20000),
                    ("Prise en charge des enfants malnutris aigus modérés", "enfants", 4000),
                    ("Formation des agents de santé communautaire au dépistage", "agents", 300)]),
                ("Les mères adoptent les pratiques optimales d'alimentation du nourrisson", ("Nombre de mères pratiquant l'allaitement exclusif", "mères", 3500), [
                    ("Animation de groupes d'apprentissage des mères", "séances", 900),
                    ("Démonstrations culinaires à base de produits locaux", "démonstrations", 600),
                    ("Visites à domicile des relais communautaires", "visites", 8000)])]),
            ("Diversifier l'alimentation des ménages", ("Nombre de ménages ayant une diversité alimentaire acceptable", "ménages", 4000), [
                ("Les ménages produisent des aliments riches en nutriments", ("Nombre de jardins nutritifs fonctionnels", "jardins", 1500), [
                    ("Création de jardins nutritifs de case", "jardins", 1500),
                    ("Distribution de kits de petit élevage", "kits", 900),
                    ("Diffusion de variétés biofortifiées", "ménages", 2000)]),
                ("Les connaissances nutritionnelles des ménages sont renforcées", ("Nombre de personnes sensibilisées à la nutrition", "personnes", 12000), [
                    ("Campagnes radiophoniques sur la nutrition", "émissions", 120),
                    ("Causeries éducatives dans les villages", "causeries", 700),
                    ("Formation des leaders communautaires", "leaders", 400)])]),
            ("Renforcer les filets sociaux de sécurité", ("Nombre de ménages vulnérables bénéficiant d'un filet social", "ménages", 3000), [
                ("Les ménages très pauvres reçoivent des transferts monétaires", ("Nombre de ménages ayant reçu des transferts monétaires", "ménages", 3000), [
                    ("Ciblage communautaire des ménages vulnérables", "ménages ciblés", 3500),
                    ("Transferts monétaires saisonniers", "ménages", 3000),
                    ("Suivi post-distribution", "enquêtes", 12)]),
                ("L'épargne communautaire est développée", ("Nombre de groupes d'épargne fonctionnels", "groupes", 150), [
                    ("Constitution de groupes d'épargne et de crédit", "groupes", 150),
                    ("Formation des membres en gestion financière", "membres", 3000),
                    ("Mise en place de banques de céréales", "banques", 20)])]),
        ],
    },
    "ELEV": {
        "cadre": "B", "axe": ("P3", "Élevage et pastoralisme"),
        "projets": [("Projet d'appui au pastoralisme et à la santé animale", "PAPSA"), ("Programme de développement des filières animales", "PDFA"),
                    ("Projet de sécurisation de la mobilité pastorale", "PSMP"), ("Projet d'appui à la filière lait local", "PAFL")],
        "types_benef": ["Élevage", "Transformation agroalimentaire"],
        "themes": [
            ("Améliorer la santé et la productivité du cheptel", ("Taux de couverture vaccinale du cheptel", "%", 80), [
                ("Le cheptel est protégé contre les maladies prioritaires", ("Nombre de têtes de bétail vaccinées", "têtes", 60000), [
                    ("Campagnes de vaccination du bétail", "têtes", 60000),
                    ("Formation d'auxiliaires vétérinaires", "auxiliaires", 120),
                    ("Équipement des parcs de vaccination", "parcs", 25)]),
                ("L'alimentation du bétail est sécurisée", ("Quantité de fourrage produite et stockée", "tonnes", 2500), [
                    ("Production de cultures fourragères", "hectares", 400),
                    ("Fauche et conservation du fourrage naturel", "tonnes", 1500),
                    ("Mise en place de banques d'aliments bétail", "banques", 20)])]),
            ("Sécuriser la mobilité pastorale", ("Longueur de pistes à bétail balisées", "km", 350), [
                ("Les pistes et aires de pâture sont balisées", ("Nombre d'aires de pâture sécurisées", "aires", 20), [
                    ("Balisage des pistes à bétail", "km", 350),
                    ("Sécurisation foncière des aires de pâture", "aires", 20),
                    ("Réalisation de points d'eau pastoraux", "points d'eau", 30)]),
                ("Les mécanismes de prévention des conflits sont fonctionnels", ("Nombre de commissions de conciliation fonctionnelles", "commissions", 40), [
                    ("Mise en place de commissions foncières villageoises", "commissions", 40),
                    ("Organisation de fora intercommunautaires", "fora", 24),
                    ("Formation des leaders à la médiation", "leaders", 300)])]),
            ("Développer les filières animales", ("Nombre d'unités de transformation laitière opérationnelles", "unités", 15), [
                ("La filière lait local est structurée", ("Volume de lait collecté", "litres", 400000), [
                    ("Installation de centres de collecte de lait", "centres", 12),
                    ("Formation des collecteurs à l'hygiène du lait", "collecteurs", 250),
                    ("Équipement des mini-laiteries", "mini-laiteries", 15)]),
                ("Les éleveurs pratiquent l'embouche améliorée", ("Nombre d'éleveurs pratiquant l'embouche", "éleveurs", 1800), [
                    ("Formation des éleveurs à l'embouche ovine et bovine", "éleveurs", 1800),
                    ("Octroi de kits d'embouche aux femmes et aux jeunes", "kits", 900),
                    ("Organisation de foires au bétail", "foires", 10)])]),
        ],
    },
    "EAU": {
        "cadre": "C", "axe": ("PIL1", "Eau potable et gestion des ressources en eau"),
        "projets": [("Projet d'accès à l'eau potable en milieu rural", "PAEPR"), ("Programme d'approvisionnement en eau des petites villes", "PAEPV"),
                    ("Projet de gestion intégrée des ressources en eau", "PGIRE"), ("Projet eau potable et résilience", "PEPR"),
                    ("Programme de réhabilitation des points d'eau", "PRPE")],
        "types_benef": ["Maraîchage", "Petit commerce"],
        "themes": [
            ("Accroître l'accès durable à l'eau potable", ("Nombre de personnes ayant un accès nouveau à l'eau potable", "personnes", 40000), [
                ("Les ouvrages d'eau potable sont réalisés", ("Nombre de forages positifs équipés de pompes", "forages", 80), [
                    ("Réalisation de forages équipés de pompes à motricité humaine", "forages", 80),
                    ("Construction d'adductions d'eau potable simplifiées", "AEPS", 8),
                    ("Réhabilitation de forages en panne", "forages", 120)]),
                ("Les ouvrages sont gérés durablement par les communes", ("Taux de fonctionnalité des points d'eau", "%", 90), [
                    ("Mise en place d'associations d'usagers de l'eau", "AUE", 150),
                    ("Formation des artisans réparateurs", "artisans", 80),
                    ("Appui aux communes pour la délégation du service", "conventions", 20)])]),
            ("Améliorer la qualité de l'eau consommée", ("Proportion de points d'eau conformes aux normes de potabilité", "%", 95), [
                ("La qualité de l'eau est contrôlée", ("Nombre d'analyses de qualité de l'eau réalisées", "analyses", 600), [
                    ("Analyses physico-chimiques et bactériologiques", "analyses", 600),
                    ("Désinfection des points d'eau", "points d'eau", 300),
                    ("Formation au traitement de l'eau à domicile", "ménages", 5000)]),
                ("Les ménages conservent l'eau de façon hygiénique", ("Nombre de ménages équipés de récipients de stockage hygiéniques", "ménages", 6000), [
                    ("Distribution de kits de stockage et de traitement de l'eau", "kits", 6000),
                    ("Sensibilisation sur la chaîne de l'eau", "séances", 500),
                    ("Suivi de la qualité de l'eau au point de consommation", "prélèvements", 800)])]),
            ("Gérer durablement les ressources en eau", ("Nombre de plans locaux de gestion de l'eau adoptés", "plans", 12), [
                ("Les ressources en eau sont mieux connues", ("Nombre de piézomètres suivis", "piézomètres", 40), [
                    ("Installation de piézomètres de suivi", "piézomètres", 40),
                    ("Collecte mensuelle des données hydrologiques", "relevés", 960),
                    ("Élaboration d'un atlas local des ressources en eau", "atlas", 3)]),
                ("Les berges et bassins versants sont protégés", ("Superficie de berges protégées", "hectares", 350), [
                    ("Reboisement des berges des retenues d'eau", "hectares", 350),
                    ("Lutte contre l'ensablement des retenues", "sites", 15),
                    ("Mise en place de comités locaux de l'eau", "comités", 12)])]),
        ],
    },
    "ASSAIN": {
        "cadre": "C", "axe": ("PIL2", "Hygiène et assainissement"),
        "projets": [("Projet d'assainissement total piloté par la communauté", "PATPC"), ("Programme WASH en milieu scolaire", "PWASH"),
                    ("Projet d'assainissement du cadre de vie urbain", "PACVU"), ("Projet hygiène et santé communautaire", "PHSC")],
        "types_benef": ["Artisanat", "Petit commerce"],
        "themes": [
            ("Mettre fin à la défécation à l'air libre", ("Nombre de villages certifiés fin de la défécation à l'air libre", "villages", 120), [
                ("Les communautés sont mobilisées pour l'assainissement total", ("Nombre de villages déclenchés", "villages", 180), [
                    ("Déclenchement de l'assainissement total piloté par la communauté", "villages", 180),
                    ("Formation des maçons à la construction de latrines", "maçons", 200),
                    ("Suivi post-déclenchement des villages", "visites", 900)]),
                ("Les ménages disposent de latrines améliorées", ("Nombre de latrines familiales construites", "latrines", 8000), [
                    ("Construction de latrines familiales améliorées", "latrines", 8000),
                    ("Subvention ciblée des ménages très pauvres", "ménages", 1500),
                    ("Promotion du marketing de l'assainissement", "points de vente", 30)])]),
            ("Améliorer l'hygiène en milieu scolaire et sanitaire", ("Nombre d'écoles disposant d'un paquet WASH complet", "écoles", 90), [
                ("Les écoles et centres de santé sont équipés", ("Nombre de blocs de latrines institutionnelles construits", "blocs", 120), [
                    ("Construction de blocs de latrines dans les écoles", "blocs", 90),
                    ("Installation de dispositifs de lavage des mains", "dispositifs", 400),
                    ("Équipement des centres de santé en ouvrages d'hygiène", "centres de santé", 30)]),
                ("Les élèves adoptent les bonnes pratiques d'hygiène", ("Nombre d'élèves sensibilisés", "élèves", 25000), [
                    ("Mise en place de clubs d'hygiène scolaires", "clubs", 90),
                    ("Sessions de sensibilisation au lavage des mains", "sessions", 700),
                    ("Gestion de l'hygiène menstruelle dans les écoles", "filles sensibilisées", 6000)])]),
            ("Assainir le cadre de vie urbain", ("Quantité de déchets collectés et traités", "tonnes", 8000), [
                ("La gestion des déchets solides est organisée", ("Nombre de ménages abonnés à la pré-collecte", "ménages", 9000), [
                    ("Appui aux associations de pré-collecte des déchets", "associations", 20),
                    ("Aménagement de centres de transit des déchets", "centres", 6),
                    ("Campagnes de salubrité", "campagnes", 48)]),
                ("Les eaux usées sont mieux gérées", ("Nombre de puisards et fosses construits", "ouvrages", 1500), [
                    ("Construction de puisards domestiques", "puisards", 1200),
                    ("Vidange mécanique des fosses", "vidanges", 900),
                    ("Formation des vidangeurs à la sécurité", "vidangeurs", 60)])]),
        ],
    },
    "EDU": {
        "cadre": "A", "axe": ("AXE1", "Développer le capital humain"),
        "projets": [("Projet d'amélioration de l'accès et de la qualité de l'éducation", "PAAQE"), ("Programme d'éducation de base inclusive", "PEBI"),
                    ("Projet d'appui aux cantines scolaires", "PACS"), ("Projet école de qualité pour tous", "PEQT"), ("Programme de scolarisation des filles", "PSF")],
        "types_benef": ["Petit commerce", "Artisanat"],
        "themes": [
            ("Améliorer l'accès à une éducation de base de qualité", ("Taux brut de scolarisation au primaire dans les communes ciblées", "%", 95), [
                ("Les capacités d'accueil des écoles sont renforcées", ("Nombre de salles de classe construites", "salles", 120), [
                    ("Construction de salles de classe", "salles", 120),
                    ("Équipement des écoles en tables-bancs", "tables-bancs", 3600),
                    ("Construction de logements d'enseignants", "logements", 40)]),
                ("Les enfants hors école sont réinsérés", ("Nombre d'enfants réinsérés dans le système éducatif", "enfants", 4000), [
                    ("Recensement des enfants hors école", "enfants recensés", 8000),
                    ("Ouverture de centres d'éducation de base non formelle", "centres", 40),
                    ("Distribution de kits scolaires", "kits", 10000)])]),
            ("Améliorer la qualité des apprentissages", ("Proportion d'élèves de CM2 atteignant le seuil de compétence en lecture", "%", 70), [
                ("Les enseignants sont mieux formés", ("Nombre d'enseignants formés", "enseignants", 1200), [
                    ("Formation continue des enseignants en lecture et calcul", "enseignants", 1200),
                    ("Encadrement pédagogique de proximité", "visites", 2400),
                    ("Formation des directeurs d'école à la gestion", "directeurs", 300)]),
                ("Les écoles disposent de manuels et de matériel didactique", ("Nombre de manuels distribués", "manuels", 60000), [
                    ("Distribution de manuels scolaires", "manuels", 60000),
                    ("Dotation en matériel didactique", "écoles", 300),
                    ("Création de bibliothèques scolaires", "bibliothèques", 80)])]),
            ("Renforcer la gestion participative des écoles", ("Proportion d'écoles avec un COGES fonctionnel", "%", 90), [
                ("Les comités de gestion des écoles sont fonctionnels", ("Nombre de COGES formés", "COGES", 300), [
                    ("Formation des comités de gestion des écoles", "COGES", 300),
                    ("Élaboration des projets d'école", "projets d'école", 300),
                    ("Octroi de subventions aux écoles", "écoles", 250)]),
                ("Les cantines scolaires sont fonctionnelles", ("Nombre d'élèves bénéficiant d'un repas scolaire", "élèves", 40000), [
                    ("Approvisionnement des cantines en vivres", "tonnes", 1200),
                    ("Construction de cuisines et magasins scolaires", "cuisines", 60),
                    ("Formation des cantinières", "cantinières", 400)])]),
        ],
    },
    "SANTE": {
        "cadre": "A", "axe": ("AXE1", "Développer le capital humain"),
        "projets": [("Projet d'appui aux soins de santé primaires", "PASSP"), ("Programme santé de la mère et de l'enfant", "PSME"),
                    ("Projet de lutte contre le paludisme", "PLP"), ("Projet de renforcement du système de santé de district", "PRSSD")],
        "types_benef": ["Petit commerce", "Maraîchage"],
        "themes": [
            ("Améliorer l'accès aux soins de santé primaires", ("Taux de fréquentation des centres de santé", "%", 75), [
                ("Les formations sanitaires sont construites et équipées", ("Nombre de centres de santé construits ou réhabilités", "centres", 25), [
                    ("Construction de centres de santé et de promotion sociale", "CSPS", 12),
                    ("Réhabilitation de maternités", "maternités", 15),
                    ("Équipement des formations sanitaires en matériel médical", "formations sanitaires", 40)]),
                ("Les soins communautaires sont disponibles", ("Nombre d'agents de santé à base communautaire actifs", "agents", 600), [
                    ("Recrutement et formation d'agents de santé à base communautaire", "agents", 600),
                    ("Dotation des agents en médicaments essentiels", "kits", 600),
                    ("Supervision mensuelle des agents communautaires", "supervisions", 3000)])]),
            ("Améliorer la santé de la mère et de l'enfant", ("Taux d'accouchements assistés par du personnel qualifié", "%", 85), [
                ("Les femmes enceintes bénéficient de consultations prénatales", ("Nombre de femmes ayant effectué au moins quatre CPN", "femmes", 9000), [
                    ("Organisation de consultations prénatales foraines", "sorties", 400),
                    ("Sensibilisation des maris et belles-mères", "séances", 800),
                    ("Mise en place de mutuelles de santé", "mutuelles", 20)]),
                ("Les enfants sont complètement vaccinés", ("Nombre d'enfants complètement vaccinés", "enfants", 15000), [
                    ("Appui aux stratégies avancées de vaccination", "sorties", 600),
                    ("Recherche active des enfants perdus de vue", "enfants", 3000),
                    ("Renforcement de la chaîne du froid", "réfrigérateurs", 40)])]),
            ("Renforcer la prévention des maladies", ("Nombre de cas de paludisme confirmés pris en charge", "cas", 30000), [
                ("Les ménages sont protégés contre le paludisme", ("Nombre de moustiquaires imprégnées distribuées", "moustiquaires", 50000), [
                    ("Distribution de moustiquaires imprégnées", "moustiquaires", 50000),
                    ("Chimioprévention du paludisme saisonnier", "enfants", 25000),
                    ("Assainissement péri-domiciliaire", "villages", 120)]),
                ("La surveillance épidémiologique est renforcée", ("Nombre de rapports de surveillance transmis à temps", "rapports", 1200), [
                    ("Formation des agents à la surveillance à base communautaire", "agents", 400),
                    ("Mise en place d'un système d'alerte précoce", "districts", 8),
                    ("Organisation de simulations de riposte aux épidémies", "simulations", 12)])]),
        ],
    },
    "EMPLOI": {
        "cadre": "A", "axe": ("AXE2", "Dynamiser l'économie et l'emploi"),
        "projets": [("Projet d'insertion professionnelle des jeunes", "PIPJ"), ("Programme d'entrepreneuriat des jeunes et des femmes", "PEJF"),
                    ("Projet de développement des chaînes de valeur", "PDCV"), ("Projet emplois verts pour les jeunes", "PEVJ"), ("Programme compétences et emploi", "PCE")],
        "types_benef": ["Artisanat", "Petit commerce", "Transformation agroalimentaire"],
        "themes": [
            ("Favoriser l'insertion professionnelle des jeunes", ("Nombre de jeunes insérés dans un emploi ou une activité", "jeunes", 3000), [
                ("Les jeunes acquièrent des compétences professionnelles", ("Nombre de jeunes formés en métiers", "jeunes", 3500), [
                    ("Formation des jeunes en apprentissage de type dual", "jeunes", 2000),
                    ("Formation qualifiante aux métiers du numérique", "jeunes", 800),
                    ("Stages de perfectionnement en entreprise", "stagiaires", 700)]),
                ("Les jeunes formés sont accompagnés vers l'emploi", ("Nombre de jeunes placés en emploi salarié", "jeunes", 1200), [
                    ("Organisation de salons de l'emploi", "salons", 8),
                    ("Accompagnement personnalisé à la recherche d'emploi", "jeunes", 2500),
                    ("Conventions de placement avec les entreprises", "conventions", 60)])]),
            ("Promouvoir l'entrepreneuriat des jeunes et des femmes", ("Nombre de micro-entreprises créées", "entreprises", 1500), [
                ("Les porteurs de projets bénéficient d'incubation", ("Nombre de plans d'affaires validés", "plans d'affaires", 1800), [
                    ("Formation en entrepreneuriat et gestion d'entreprise", "promoteurs", 2500),
                    ("Coaching des promoteurs pour l'élaboration des plans d'affaires", "plans d'affaires", 1800),
                    ("Incubation de jeunes entreprises innovantes", "entreprises", 60)]),
                ("Les micro-entreprises accèdent au financement", ("Nombre de micro-entreprises ayant obtenu un crédit", "entreprises", 1000), [
                    ("Octroi de subventions de démarrage", "entreprises", 1200),
                    ("Mise en relation avec les institutions de microfinance", "dossiers", 1500),
                    ("Fonds de garantie pour les jeunes entrepreneurs", "garanties", 400)])]),
            ("Développer les chaînes de valeur porteuses d'emplois", ("Nombre d'emplois créés dans les chaînes de valeur", "emplois", 2500), [
                ("Les unités de production sont modernisées", ("Nombre d'unités de production équipées", "unités", 200), [
                    ("Équipement des unités artisanales", "unités", 200),
                    ("Mise aux normes de la qualité des produits", "produits certifiés", 60),
                    ("Formation des artisans au design et au marketing", "artisans", 500)]),
                ("Les produits locaux accèdent aux marchés", ("Nombre de contrats de vente conclus", "contrats", 150), [
                    ("Participation à des foires commerciales", "foires", 20),
                    ("Création d'une plateforme de vente en ligne", "plateformes", 1),
                    ("Contrats d'approvisionnement avec les grandes surfaces", "contrats", 40)])]),
        ],
    },
    "GOUV": {
        "cadre": "A", "axe": ("AXE3", "Consolider la gouvernance et la décentralisation"),
        "projets": [("Projet d'appui à la gouvernance locale", "PAGL"), ("Programme de participation citoyenne et de redevabilité", "PPCR"),
                    ("Projet de modernisation de l'état civil", "PMEC"), ("Projet de renforcement des finances locales", "PRFL")],
        "types_benef": ["Petit commerce", "Artisanat"],
        "themes": [
            ("Renforcer la gouvernance locale", ("Nombre de communes disposant d'un plan communal de développement à jour", "communes", 30), [
                ("Les collectivités planifient leur développement de manière participative", ("Nombre de plans communaux élaborés", "plans", 30), [
                    ("Appui à l'élaboration des plans communaux de développement", "communes", 30),
                    ("Formation des élus locaux à la planification", "élus", 600),
                    ("Organisation de cadres de concertation communaux", "sessions", 120)]),
                ("Les finances locales sont améliorées", ("Taux de recouvrement des recettes propres des communes", "%", 70), [
                    ("Recensement fiscal des contribuables", "contribuables", 25000),
                    ("Formation des agents de recouvrement", "agents", 150),
                    ("Informatisation de la chaîne des recettes", "communes", 20)])]),
            ("Promouvoir la participation citoyenne et la redevabilité", ("Nombre d'audiences publiques de reddition de comptes tenues", "audiences", 60), [
                ("Les citoyens participent à la gestion des affaires locales", ("Nombre de citoyens ayant participé aux espaces de dialogue", "citoyens", 15000), [
                    ("Organisation d'audiences publiques de reddition de comptes", "audiences", 60),
                    ("Mise en place de cellules de veille citoyenne", "cellules", 40),
                    ("Émissions radiophoniques interactives sur la gouvernance", "émissions", 150)]),
                ("L'accès à l'information publique est amélioré", ("Nombre de communes publiant leur budget", "communes", 30), [
                    ("Affichage public des budgets communaux", "communes", 30),
                    ("Création de sites d'information communaux", "sites", 15),
                    ("Formation des journalistes locaux", "journalistes", 100)])]),
            ("Moderniser l'administration publique", ("Nombre de services administratifs dématérialisés", "services", 25), [
                ("L'état civil est modernisé", ("Nombre d'actes d'état civil numérisés", "actes", 200000), [
                    ("Numérisation des registres d'état civil", "actes", 200000),
                    ("Équipement des centres d'état civil", "centres", 60),
                    ("Audiences foraines de délivrance des jugements supplétifs", "audiences", 80)]),
                ("Les agents publics maîtrisent les outils numériques", ("Nombre d'agents formés aux outils numériques", "agents", 1200), [
                    ("Formation des agents aux outils bureautiques", "agents", 1200),
                    ("Déploiement d'une messagerie professionnelle", "services", 25),
                    ("Mise en place de guichets uniques", "guichets", 10)])]),
        ],
    },
    "CLIMAT": {
        "cadre": "D", "axe": ("D1", "Climat et environnement"),
        "projets": [("Projet d'adaptation des communautés au changement climatique", "PACC"), ("Programme de restauration des écosystèmes", "PRE"),
                    ("Projet énergies propres pour les ménages", "PEPM"), ("Projet de gestion durable des terres et des forêts", "PGDTF"), ("Programme résilience climatique", "PRC")],
        "types_benef": ["Agriculture pluviale", "Élevage", "Artisanat"],
        "themes": [
            ("Renforcer l'adaptation des communautés au changement climatique", ("Nombre de ménages appliquant au moins une mesure d'adaptation", "ménages", 6000), [
                ("Les plans locaux d'adaptation sont élaborés", ("Nombre de plans locaux d'adaptation adoptés", "plans", 20), [
                    ("Analyse participative de la vulnérabilité climatique", "villages", 80),
                    ("Élaboration des plans locaux d'adaptation", "plans", 20),
                    ("Intégration de l'adaptation dans les budgets communaux", "communes", 20)]),
                ("L'information climatique est accessible aux producteurs", ("Nombre de producteurs recevant l'information agro-météorologique", "producteurs", 10000), [
                    ("Installation de pluviomètres paysans", "pluviomètres", 300),
                    ("Diffusion de bulletins agro-météorologiques par SMS", "messages", 50000),
                    ("Formation des producteurs à l'usage de l'information climatique", "producteurs", 4000)])]),
            ("Restaurer les écosystèmes dégradés", ("Superficie d'écosystèmes restaurés", "hectares", 3000), [
                ("Les forêts communautaires sont aménagées", ("Nombre de forêts dotées d'un plan d'aménagement", "forêts", 15), [
                    ("Délimitation et bornage des forêts communautaires", "forêts", 15),
                    ("Reboisement et régénération naturelle assistée", "hectares", 2000),
                    ("Mise en place de brigades villageoises de surveillance", "brigades", 40)]),
                ("Les pratiques de gestion durable des terres sont diffusées", ("Superficie sous gestion durable des terres", "hectares", 1500), [
                    ("Installation de bandes enherbées et de haies vives", "km", 250),
                    ("Promotion de l'agroforesterie", "plants", 80000),
                    ("Ouverture de pare-feux contre les feux de brousse", "km", 400)])]),
            ("Promouvoir les énergies propres", ("Nombre de ménages utilisant une énergie propre", "ménages", 5000), [
                ("Les ménages adoptent des foyers améliorés", ("Nombre de foyers améliorés diffusés", "foyers", 8000), [
                    ("Formation des artisanes à la fabrication de foyers améliorés", "artisanes", 200),
                    ("Diffusion de foyers améliorés", "foyers", 8000),
                    ("Promotion du biodigesteur domestique", "biodigesteurs", 300)]),
                ("Les infrastructures communautaires sont solarisées", ("Nombre d'infrastructures équipées en énergie solaire", "infrastructures", 120), [
                    ("Installation de kits solaires dans les centres de santé", "centres", 40),
                    ("Électrification solaire des écoles", "écoles", 60),
                    ("Installation de lampadaires solaires", "lampadaires", 500)])]),
        ],
    },
    "GENRE": {
        "cadre": "D", "axe": ("D2", "Genre et inclusion sociale"),
        "projets": [("Projet d'autonomisation économique des femmes", "PAEF"), ("Programme de lutte contre les violences basées sur le genre", "PLVBG"),
                    ("Projet d'inclusion des personnes vulnérables", "PIPV"), ("Projet cohésion sociale et réinsertion des personnes déplacées", "PCSR"),
                    ("Programme femmes leaders et développement local", "PFLDL")],
        "types_benef": ["Petit commerce", "Transformation agroalimentaire", "Maraîchage"],
        "themes": [
            ("Renforcer l'autonomisation économique des femmes", ("Nombre de femmes ayant augmenté leurs revenus", "femmes", 4000), [
                ("Les femmes accèdent aux facteurs de production", ("Nombre de femmes ayant obtenu une attestation foncière", "femmes", 1500), [
                    ("Appui à la sécurisation foncière des femmes", "attestations", 1500),
                    ("Dotation des groupements féminins en équipements", "groupements", 120),
                    ("Facilitation de l'accès des femmes aux intrants agricoles", "femmes", 3000)]),
                ("Les activités génératrices de revenus des femmes sont développées", ("Nombre d'AGR fonctionnelles", "AGR", 2000), [
                    ("Formation des femmes à la gestion d'AGR", "femmes", 3000),
                    ("Octroi de fonds de démarrage", "AGR", 2000),
                    ("Alphabétisation fonctionnelle des femmes", "apprenantes", 2500)])]),
            ("Lutter contre les violences basées sur le genre", ("Nombre de survivantes de VBG prises en charge", "survivantes", 800), [
                ("Les survivantes accèdent à une prise en charge holistique", ("Nombre de centres d'écoute fonctionnels", "centres", 12), [
                    ("Mise en place de centres d'écoute", "centres", 12),
                    ("Prise en charge psychosociale et médicale", "survivantes", 800),
                    ("Assistance juridique et judiciaire", "dossiers", 250)]),
                ("Les communautés rejettent les pratiques néfastes", ("Nombre de villages ayant déclaré l'abandon des pratiques néfastes", "villages", 80), [
                    ("Dialogues communautaires sur les normes sociales", "dialogues", 400),
                    ("Engagement des leaders religieux et coutumiers", "leaders", 500),
                    ("Clubs de jeunes filles et garçons pour l'égalité", "clubs", 100)])]),
            ("Promouvoir l'inclusion des personnes vulnérables", ("Nombre de personnes en situation de handicap appuyées", "personnes", 1200), [
                ("Les personnes handicapées accèdent aux services sociaux", ("Nombre de cartes d'invalidité délivrées", "cartes", 1000), [
                    ("Recensement des personnes en situation de handicap", "personnes", 2500),
                    ("Appui à l'obtention des cartes d'invalidité", "cartes", 1000),
                    ("Dotation en aides techniques", "aides techniques", 600)]),
                ("Les personnes déplacées internes sont intégrées", ("Nombre de ménages déplacés bénéficiant d'un appui à la réinsertion", "ménages", 2000), [
                    ("Distribution de kits de réinstallation", "kits", 2000),
                    ("Appui psychosocial aux personnes déplacées", "personnes", 3000),
                    ("Activités de cohésion sociale entre déplacés et communautés hôtes", "activités", 150)])]),
        ],
    },
}

CADRES = {
    "A": {
        "nom": "Plan national de développement économique et social 2026-2030 (PNDES-II)",
        "description": "Référentiel national de développement : capital humain, transformation de l'économie et gouvernance. "
                       "Les projets y sont rattachés par axe ; leurs activités alimentent les effets attendus.",
        "niveaux": [("Axe stratégique", "Ex : AXE1"), ("Objectif stratégique", "Ex : OS1.1"), ("Effet attendu", "Ex : EA1.1.1")],
        "codes": ("{axe}", "OS{a}.{o}", "EA{a}.{o}.{r}"),
    },
    "B": {
        "nom": "Stratégie nationale de sécurité alimentaire et nutritionnelle 2025-2030",
        "description": "Stratégie sectorielle de la production agricole, de l'élevage, de la nutrition et de la protection sociale.",
        "niveaux": [("Programme", "Ex : P1"), ("Sous-programme", "Ex : SP1.1"), ("Action", "Ex : A1.1.1")],
        "codes": ("{axe}", "SP{a}.{o}", "A{a}.{o}.{r}"),
    },
    "C": {
        "nom": "Programme national eau potable, hygiène et assainissement 2026-2030",
        "description": "Programme national d'accès universel à l'eau potable et à l'assainissement et de gestion des ressources en eau.",
        "niveaux": [("Composante", "Ex : COMP1"), ("Objectif", "Ex : OBJ1.1"), ("Résultat attendu", "Ex : RA1.1.1")],
        "codes": ("{axe}", "OBJ{a}.{o}", "RA{a}.{o}.{r}"),
    },
    "D": {
        "nom": "Plan stratégique Expertise ID 2026-2030",
        "description": "Plan stratégique de l'organisation : domaines d'intervention, objectifs, résultats et interventions types.",
        "niveaux": [("Domaine d'intervention", "Ex : D1"), ("Objectif stratégique", "Ex : OS1.1"), ("Résultat", "Ex : R1.1.1"), ("Intervention", "Ex : I1.1.1.1")],
        "codes": ("{axe}", "OS{a}.{o}", "R{a}.{o}.{r}", "I{a}.{o}.{r}.{i}"),
    },
}

NIVEAUX_PROJET = [
    ["Objectif spécifique", "Résultat", "Activité"],
    ["Composante", "Produit", "Activité"],
    ["Effet", "Extrant", "Activité"],
    ["Axe d'intervention", "Résultat attendu", "Action"],
]
ETAPES = [
    "Identification et ciblage des bénéficiaires pour : ",
    "Passation des marchés et acquisitions pour : ",
    "Mise en œuvre sur le terrain : ",
    "Supervision et contrôle qualité : ",
    "Capitalisation et rapportage : ",
]
HYPOTHESES = [
    "La situation sécuritaire permet l'accès régulier aux sites d'intervention.",
    "Les services techniques déconcentrés s'impliquent dans l'accompagnement.",
    "Les conditions pluviométriques restent dans la normale saisonnière.",
    "Les fonds sont décaissés à temps par les bailleurs.",
    "Les communautés restent mobilisées tout au long du projet.",
    "Les prix des intrants et matériaux restent stables.",
    "Les autorités locales soutiennent la démarche.",
]
SOURCES = [
    "Enquête de référence et enquête finale ; rapports annuels du projet",
    "Rapports semestriels ; base de données de suivi ; procès-verbaux de réception",
    "Listes de présence ; fiches de suivi terrain ; rapports d'activité ; photos géolocalisées",
]
CAPITALISATION = [
    "L'implication des services techniques dès la conception a facilité l'appropriation des ouvrages par les communes.",
    "Les approches communautaires (comités, relais) ont réduit les coûts de suivi et amélioré la durabilité des acquis.",
    "La planification par période a permis d'anticiper les retards de saison des pluies et de réaffecter les budgets à temps.",
    "Le ciblage participatif a renforcé l'acceptation sociale du projet et limité les plaintes.",
    "Les partenariats avec les radios communautaires se sont révélés le canal de sensibilisation le plus efficace.",
    "La contractualisation avec des prestataires locaux a raccourci les délais mais demande un contrôle qualité renforcé.",
]

BAILLEURS = [
    ("Union européenne", "INSTITUTIONNEL", "Délégation de l'Union européenne"),
    ("Agence française de développement", "COOPERATION_BILATERALE", "Agence de Ouagadougou"),
    ("Banque mondiale", "INSTITUTIONNEL", "Bureau pays"),
    ("Banque africaine de développement", "INSTITUTIONNEL", "Bureau régional"),
    ("Coopération suisse", "COOPERATION_BILATERALE", "Bureau de la coopération"),
    ("Ambassade des Pays-Bas", "COOPERATION_BILATERALE", "Section coopération"),
    ("Coopération allemande (GIZ)", "COOPERATION_BILATERALE", "Bureau GIZ"),
    ("Coopération luxembourgeoise", "COOPERATION_BILATERALE", "Bureau LuxDev"),
    ("Enabel, Agence belge de développement", "COOPERATION_BILATERALE", "Représentation"),
    ("UNICEF", "INSTITUTIONNEL", "Bureau pays"),
    ("Programme alimentaire mondial", "INSTITUTIONNEL", "Bureau pays"),
    ("Fonds vert pour le climat", "INSTITUTIONNEL", "Secrétariat"),
    ("Fondation de France", "FONDATION", "Pôle international"),
    ("Fondation Bill & Melinda Gates", "FONDATION", "Programme Afrique de l'Ouest"),
]
PARTENAIRES_MEO = [
    ("Expertise ID", "Direction des programmes", "contact@expertise-id.org"),
    ("Réseau des ONG locales du Sahel", "Coordination du réseau", "coordination@reseau-ong-sahel.org"),
    ("Association Zood Nooma pour le développement", "Secrétariat exécutif", "contact@zoodnooma.org"),
    ("ONG Wend Panga", "Direction exécutive", "info@wendpanga.org"),
    ("Association des femmes rurales du Centre-Est", "Présidence", "afrce@asso.bf"),
    ("Union des groupements villageois du Nord", "Bureau exécutif", "ugvn@asso.bf"),
    ("Centre d'études et de formation pour le développement", "Direction", "cefod@centre.bf"),
    ("Bureau d'études Sahel Ingénierie", "Direction technique", "contact@sahel-ingenierie.bf"),
]
PARTIES_PRENANTES = [
    ("Ministère de l'Agriculture, des Ressources animales et halieutiques", "Ministère"),
    ("Ministère de l'Éducation nationale", "Ministère"),
    ("Ministère de la Santé", "Ministère"),
    ("Ministère de l'Environnement, de l'Eau et de l'Assainissement", "Ministère"),
    ("Ministère de l'Action humanitaire et de la Solidarité nationale", "Ministère"),
    ("Conseils régionaux", "Collectivité territoriale"),
    ("Association des municipalités", "Collectivité territoriale"),
    ("Directions régionales de l'agriculture", "Service technique"),
    ("Directions régionales de l'eau et de l'assainissement", "Service technique"),
    ("Districts sanitaires", "Service technique"),
    ("Fédération des unions de producteurs", "Organisation communautaire"),
    ("Coordination des associations féminines", "Organisation communautaire"),
    ("Chambres régionales d'agriculture", "Secteur privé"),
    ("Réseau des institutions de microfinance", "Secteur privé"),
]
RISQUES = [
    ("Dégradation de la situation sécuritaire dans les zones d'intervention", "Sécuritaire", "EXTERNE",
     "Attaques ou menaces limitant l'accès des équipes et des prestataires aux villages.",
     "Analyse sécuritaire hebdomadaire ; recours aux relais communautaires ; plan de repli.",
     "Suspension temporaire des missions et réaffectation des activités vers les communes accessibles."),
    ("Retard dans le décaissement des fonds des bailleurs", "Financier", "EXTERNE",
     "Retard de virement des tranches entraînant l'arrêt de certaines activités.",
     "Transmission à temps des rapports financiers ; dialogue régulier avec les bailleurs.",
     "Préfinancement sur fonds propres des activités prioritaires."),
    ("Pluviométrie déficitaire ou mal répartie", "Climatique et environnemental", "EXTERNE",
     "Une mauvaise saison réduit les rendements et décourage les producteurs.",
     "Diffusion de variétés précoces ; information climatique ; techniques de conservation de l'eau.",
     "Activation des appuis d'urgence (semences de contre-saison, transferts)."),
    ("Faible mobilisation des communautés bénéficiaires", "Social et communautaire", "EXTERNE",
     "Les bénéficiaires participent peu aux activités ou abandonnent en cours de route.",
     "Implication des leaders locaux ; calendrier adapté aux travaux champêtres.",
     "Révision du ciblage et des modalités d'intervention avec les communautés."),
    ("Rotation élevée du personnel du projet", "Opérationnel", "INTERNE",
     "Départs de personnel clé entraînant une perte de compétences et des retards.",
     "Politique de rétention ; documentation des procédures ; binômes sur les postes clés.",
     "Recrutement accéléré et appui temporaire du siège."),
    ("Hausse des prix des intrants et des matériaux", "Financier", "EXTERNE",
     "L'inflation renchérit les coûts unitaires au-delà des budgets prévus.",
     "Contrats-cadres à prix fermes ; achats groupés ; provision pour imprévus.",
     "Révision des quantités avec l'accord du bailleur."),
    ("Retards dans la passation des marchés", "Fiduciaire", "INTERNE",
     "Les procédures d'acquisition retardent le démarrage des travaux.",
     "Plan de passation validé en début d'année ; dossiers types ; suivi mensuel.",
     "Recours aux procédures simplifiées autorisées par le manuel."),
    ("Changements institutionnels au niveau des collectivités", "Politique et institutionnel", "EXTERNE",
     "Le remplacement des exécutifs locaux remet en cause les engagements pris.",
     "Conventions écrites ; information régulière des nouvelles autorités.",
     "Nouvelle séance de présentation du projet et renégociation des engagements."),
    ("Épidémie limitant les rassemblements", "Sanitaire", "EXTERNE",
     "Les mesures sanitaires empêchent les formations et réunions de groupe.",
     "Plan de continuité ; formats en petits groupes ; outils à distance.",
     "Report des sessions et passage à des visites individuelles."),
    ("Mauvaise qualité des ouvrages réalisés par les prestataires", "Opérationnel", "INTERNE",
     "Malfaçons sur les ouvrages entraînant des reprises coûteuses.",
     "Contrôle technique indépendant ; retenue de garantie ; réception contradictoire.",
     "Mise en jeu de la garantie et reprise aux frais du prestataire."),
    ("Conflits fonciers autour des sites aménagés", "Juridique", "EXTERNE",
     "Contestations sur la propriété des terres aménagées.",
     "Actes de cession volontaire signés avant les travaux ; commissions foncières.",
     "Médiation coutumière et administrative."),
    ("Insuffisance de données de suivi fiables", "Opérationnel", "INTERNE",
     "Les données remontées sont incomplètes ou tardives.",
     "Formation des agents ; outils de collecte numériques ; contrôles de cohérence.",
     "Missions de vérification ciblées et enquêtes rapides."),
]
NOMS = ["OUÉDRAOGO", "SAWADOGO", "KABORÉ", "ZONGO", "TRAORÉ", "COMPAORÉ", "ILBOUDO", "KONATÉ", "SANOU", "OUATTARA",
        "SOMÉ", "DABIRÉ", "YAMÉOGO", "NIKIÉMA", "TIENDRÉBÉOGO", "BARRY", "DIALLO", "KAFANDO", "ZERBO", "BAMOGO",
        "NANA", "BONKOUNGOU", "ROAMBA", "SOULAMA", "HIEN", "PODA", "KIENDRÉBÉOGO", "GUIRA", "BÉLEM", "COULIBALY",
        "DIARRA", "KAMBOU", "PALENFO", "SIMPORÉ", "TAPSOBA", "ZOUNGRANA", "BAZIÉ", "KINDA", "OUÉDA", "TOÉ"]
PRENOMS_H = ["Adama", "Boukary", "Issouf", "Salif", "Ali", "Moussa", "Hamidou", "Boureima", "Issa", "Souleymane",
             "Idrissa", "Abdoulaye", "Paul", "Jean-Baptiste", "Rasmané", "Seydou", "Karim", "Ousmane", "Yacouba", "Dramane",
             "Mahamadi", "Lassané", "Inoussa", "Arouna", "Fidèle"]
PRENOMS_F = ["Mariam", "Rasmata", "Salamata", "Aminata", "Fatimata", "Awa", "Alimata", "Assétou", "Habibou", "Zénabo",
             "Haoua", "Pauline", "Odile", "Bibata", "Kadidia", "Rokia", "Safiatou", "Adjaratou", "Germaine", "Clarisse",
             "Ramata", "Mariétou", "Fanta", "Ines", "Juliette"]
FONCTIONS = ["Chef de projet", "Chargé(e) de suivi-évaluation", "Responsable administratif et financier",
             "Animateur(trice) terrain", "Animateur(trice) terrain", "Technicien(ne) spécialisé(e)"]


def repartir(total, n):
    """Découpe un total entier en n parts entières proches."""
    if n <= 0:
        return []
    base = [total // n] * n
    base[-1] += total - sum(base)
    return base


def arrondi(montant, pas=1_000_000):
    return int(round(montant / pas)) * pas


def chevauchement(d1, f1, d2, f2):
    debut, fin = max(d1, d2), min(f1, f2)
    return (fin - debut).days + 1 if fin >= debut else 0


def fin_mois(annee, mois):
    return (date(annee + mois // 12, mois % 12 + 1, 1) - timedelta(days=1))


def periodes_suivi(debut, fin):
    """Semestres écoulés (puis le trimestre écoulé de l'année en cours) entre debut et fin."""
    periodes = []
    for annee in range(debut.year, fin.year + 1):
        if annee < AUJOURDHUI.year:
            bornes = [(date(annee, 1, 1), date(annee, 6, 30)), (date(annee, 7, 1), date(annee, 12, 31))]
        else:
            bornes = [(date(annee, 1, 1), date(annee, 6, 30)), (date(annee, 7, 1), date(annee, 9, 30))]
        for d, f in bornes:
            d, f = max(d, debut), min(f, fin)
            if d <= f and f < AUJOURDHUI:
                periodes.append((d, f))
    return periodes


def pdf(titre, lignes):
    """PDF d'une page (texte simple), pour les documents de la GED."""
    def txt(s):
        s = s.replace("œ", "oe").replace("—", "-").replace("’", "'").replace("–", "-").replace("…", "...")
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace")
    flux = b"BT /F1 16 Tf 60 780 Td (" + txt(titre) + b") Tj ET\n"
    y = 740
    for ligne in lignes:
        flux += b"BT /F1 11 Tf 60 " + str(y).encode() + b" Td (" + txt(ligne) + b") Tj ET\n"
        y -= 18
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(flux)).encode() + b" >>\nstream\n" + flux + b"endstream",
    ]
    sortie = b"%PDF-1.4\n"
    positions = []
    for i, obj in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for p in positions:
        sortie += f"{p:010d} 00000 n \n".encode()
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return sortie


# ----------------------------------------------------------------------------------------------
# 1. Suppression
# ----------------------------------------------------------------------------------------------
def vider():
    for v in DocumentVersion.objects.filter(document__projet__isnull=False):
        v.fichier.delete(save=False)
    for projet in list(Projet.objects.all()):
        supprimer_projet_cascade(projet)
    ValeurIndicateur.tous.all().delete()
    Indicateur.objects.all().delete()
    # Chaîne des documents : liens entre documents (protégés) défaits avant de les supprimer.
    # Les maillons (TypeDocument) sont un réglage de l'organisation : conservés.
    ElementStrategique.objects.update(contribue_a=None)
    CadreStrategique.objects.update(document_parent=None, element_parent=None)
    for cadre in list(CadreStrategique.objects.all()):
        supprimer_cadre_strategique_cascade(cadre)
    Equipe.objects.all().delete()
    Intervenant.objects.all().delete()
    SignalementDoublon.objects.all().delete()
    ParticipationProjet.objects.all().delete()
    Beneficiaire.objects.all().delete()
    Bailleur.objects.all().delete()
    Partenaire.objects.all().delete()
    PartiePrenante.objects.all().delete()
    CategoriePartiePrenante.objects.all().delete()
    while StructureOrganisation.objects.exists():
        StructureOrganisation.objects.filter(enfants__isnull=True).delete()
    Notification.objects.all().delete()


# ----------------------------------------------------------------------------------------------
# 2. Référentiels communs
# ----------------------------------------------------------------------------------------------
def creer_referentiels():
    ref = {}
    dg = StructureOrganisation.objects.create(nom="Direction générale", sigle="DG", type="Organisation", responsable="Directeur général")
    dp = StructureOrganisation.objects.create(nom="Direction des programmes", sigle="DP", parent=dg, type="Direction", responsable="Directrice des programmes")
    daf = StructureOrganisation.objects.create(nom="Direction administrative et financière", sigle="DAF", parent=dg, type="Direction", responsable="Directeur administratif et financier")
    dsec = StructureOrganisation.objects.create(nom="Direction du suivi-évaluation et de la capitalisation", sigle="DSEC", parent=dg, type="Direction", responsable="Responsable suivi-évaluation")
    services = {
        "SASA": StructureOrganisation.objects.create(nom="Service agriculture, élevage et nutrition", sigle="SAEN", parent=dp, type="Service", responsable="Chef du service agriculture"),
        "SEHA": StructureOrganisation.objects.create(nom="Service eau, hygiène et assainissement", sigle="SEHA", parent=dp, type="Service", responsable="Cheffe du service EHA"),
        "SES": StructureOrganisation.objects.create(nom="Service éducation, santé et emploi", sigle="SESE", parent=dp, type="Service", responsable="Chef du service éducation-santé"),
        "SGI": StructureOrganisation.objects.create(nom="Service gouvernance, climat et inclusion", sigle="SGCI", parent=dp, type="Service", responsable="Cheffe du service gouvernance"),
    }
    ref["structure_secteur"] = {
        "AGRI": services["SASA"], "NUT": services["SASA"], "ELEV": services["SASA"], "EAU": services["SEHA"],
        "ASSAIN": services["SEHA"], "EDU": services["SES"], "SANTE": services["SES"], "EMPLOI": services["SES"],
        "GOUV": services["SGI"], "CLIMAT": services["SGI"], "GENRE": services["SGI"],
    }
    ref["dsec"], ref["dp"], ref["daf"] = dsec, dp, daf

    categories = {}
    ref["parties_prenantes"] = []
    for nom, cat in PARTIES_PRENANTES:
        if cat not in categories:
            categories[cat] = CategoriePartiePrenante.objects.create(nom=cat)
        ref["parties_prenantes"].append(PartiePrenante.objects.create(
            nom=nom, categorie=categories[cat], contact="Point focal", email=f"pointfocal{len(ref['parties_prenantes']) + 1}@partenaires.bf",
            telephone=f"+226 25 3{random.randint(0, 9)} {random.randint(10, 99)} {random.randint(10, 99)}",
        ))

    ref["bailleurs"], ref["partenaires_bailleur"] = [], {}
    for nom, type_bailleur, contact in BAILLEURS:
        ref["bailleurs"].append(Bailleur.objects.create(nom=nom, type=type_bailleur, contact=contact))
        ref["partenaires_bailleur"][nom] = Partenaire.objects.create(
            nom=nom, type=Partenaire.TypePartenaire.BAILLEUR, contact=contact,
            email=f"contact{len(ref['partenaires_bailleur']) + 1}@bailleurs.org", telephone="+226 25 49 00 00",
        )
    ref["partenaires_meo"] = [
        Partenaire.objects.create(nom=nom, type=Partenaire.TypePartenaire.MISE_EN_OEUVRE, contact=contact, email=email,
                                  telephone=f"+226 25 4{i} 12 3{i}")
        for i, (nom, contact, email) in enumerate(PARTENAIRES_MEO)
    ]
    ref["statuts"] = {s.code: s for s in StatutParticulier.objects.all()}
    ref["types_activite"] = {t.libelle: t for t in TypeActiviteBeneficiaire.objects.all()}
    ref["admin"] = User.objects.filter(role="ADMIN").order_by("id").first() or User.objects.order_by("id").first()
    ref["utilisateurs"] = list(User.objects.exclude(pk=ref["admin"].pk).order_by("id"))
    provinces = list(Zone.objects.filter(niveau_administratif__nom_niveau="Province").select_related("parent").order_by("nom"))
    ref["regions"] = {}
    for p in provinces:
        if p.parent:
            ref["regions"].setdefault(p.parent, []).append(p)
    return ref


# ----------------------------------------------------------------------------------------------
# 3. Cadres stratégiques (éléments tirés du contenu des secteurs)
# ----------------------------------------------------------------------------------------------
def creer_cadres(ref):
    elements = {}  # (secteur, "axe") / (secteur, t) / (secteur, t, r) / (secteur, t, r, a) -> ElementStrategique
    cadres = {}
    for cle, conf in CADRES.items():
        cadre = CadreStrategique.objects.create(nom=conf["nom"], description=conf["description"])
        cadre.structures.set([ref["dp"], ref["dsec"]])
        cadre.parties_prenantes.set(random.sample(ref["parties_prenantes"], 4))
        niveaux, parent = [], None
        for ordre, (nom, aide) in enumerate(conf["niveaux"], start=1):
            parent = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau=nom, ordre=ordre, niveau_parent=parent, aide_code=aide)
            niveaux.append(parent)
        cadres[cle] = cadre
        axes, num_os = {}, {}
        for secteur, s in SECTEURS.items():
            if s["cadre"] != cle:
                continue
            code_axe, nom_axe = s["axe"]
            if code_axe not in axes:
                axes[code_axe] = ElementStrategique.objects.create(
                    type_niveau=niveaux[0], code=code_axe, nom=nom_axe,
                    description=f"{nom_axe} : orientations et priorités retenues pour la période.",
                )
                axes[code_axe].structures.set([ref["structure_secteur"][secteur]])
                num_os[code_axe] = 0
            axe = axes[code_axe]
            elements[(secteur, "axe")] = axe
            a = int("".join(c for c in code_axe if c.isdigit()))
            for t, (theme, _, resultats) in enumerate(s["themes"]):
                num_os[code_axe] += 1
                o = num_os[code_axe]
                el_os = ElementStrategique.objects.create(type_niveau=niveaux[1], element_parent=axe, code=conf["codes"][1].format(a=a, o=o), nom=theme)
                elements[(secteur, t)] = el_os
                for r, (resultat, _, activites) in enumerate(resultats):
                    el_r = ElementStrategique.objects.create(
                        type_niveau=niveaux[2], element_parent=el_os, code=conf["codes"][2].format(a=a, o=o, r=r + 1), nom=resultat,
                    )
                    elements[(secteur, t, r)] = el_r
                    if len(niveaux) > 3:
                        for i, (libelle, _, _) in enumerate(activites):
                            elements[(secteur, t, r, i)] = ElementStrategique.objects.create(
                                type_niveau=niveaux[3], element_parent=el_r, code=conf["codes"][3].format(a=a, o=o, r=r + 1, i=i + 1), nom=libelle,
                            )
        # Appréciations de l'année écoulée sur les deux premiers niveaux.
        etats = ["BON", "BON", "MOYEN", "INSUFFISANT"]
        for el in ElementStrategique.objects.filter(type_niveau__in=niveaux[:2]):
            etat = random.choice(etats)
            AppreciationStrategique.objects.create(
                element=el, libelle_periode="Année 2025", periode_debut=date(2025, 1, 1), periode_fin=date(2025, 12, 31), etat=etat,
                commentaire={"BON": "Les projets rattachés progressent conformément à la programmation annuelle.",
                             "MOYEN": "Progression contrastée : plusieurs activités ont pris du retard au second semestre.",
                             "INSUFFISANT": "Les réalisations restent nettement en deçà des cibles de l'année."}[etat],
                difficultes="Accès difficile à certaines zones ; retards de décaissement sur deux financements.",
                recommandations="Renforcer la coordination avec les services techniques et anticiper les acquisitions.",
                saisi_par=ref["admin"],
            )
    return cadres, elements


# ----------------------------------------------------------------------------------------------
# 4. Projets
# ----------------------------------------------------------------------------------------------
def calendrier(i):
    """Dates et statut : quelques projets clôturés, quelques-uns en préparation, la plupart en cours."""
    if i % 9 == 0:   # clôturé
        debut = date(random.choice([2021, 2022]), random.choice([1, 4, 7]), 1)
        fin = fin_mois(debut.year + random.choice([3, 3, 4]), debut.month - 1)
        if fin >= AUJOURDHUI:
            fin = date(2025, 12, 31)
        return debut, fin, Projet.Statut.CLOTURE
    if i % 9 == 4:   # en préparation
        debut = date(2027, random.choice([1, 1, 4]), 1)
        return debut, fin_mois(debut.year + random.choice([3, 4]), debut.month - 1), Projet.Statut.EN_PREPARATION
    debut = date(random.choice([2023, 2024, 2024, 2025, 2025, 2026]), random.choice([1, 1, 4, 7, 10]), 1)
    if debut > AUJOURDHUI:
        debut = date(2026, 1, 1)
    fin = fin_mois(debut.year + random.choice([3, 4, 5]), debut.month - 1)
    return debut, fin, Projet.Statut.EN_COURS


def creer_projet(i, secteur, ref, cadres, elements, region, provinces, codes_pris):
    s = SECTEURS[secteur]
    nom_base, sigle = s["projets"][(i // len(SECTEURS)) % len(s["projets"])]
    debut, fin, statut = calendrier(i)
    echelle = random.uniform(0.35, 1.0)
    perf = random.uniform(0.92, 1.0) if statut == Projet.Statut.CLOTURE else random.uniform(0.6, 1.0)
    code = f"{sigle}-{region.nom[:3].upper()}-{debut.year}"
    while code in codes_pris:
        code += "B"
    codes_pris.add(code)

    # Équipe et intervenants
    membres = []
    for f in FONCTIONS:
        sexe = random.choice("MF")
        membres.append(Intervenant.objects.create(
            nom=random.choice(NOMS), prenom=random.choice(PRENOMS_H if sexe == "M" else PRENOMS_F), fonction=f,
            contact=f"+226 7{random.randint(0, 9)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
        ))
    equipe = Equipe.objects.create(nom=f"Équipe projet {code}", date_debut_contrat=debut, date_fin_contrat=fin)
    equipe.membres.set(membres)
    chef = membres[0]

    cible = int(random.uniform(2000, 15000) * echelle / 100) * 100 + 1000
    femmes = int(cible * random.uniform(0.5, 0.62))
    mise_en_oeuvre = ref["partenaires_meo"][0] if random.random() < 0.6 else random.choice(ref["partenaires_meo"][1:])
    consortium = random.random() < 0.35
    projet = Projet.objects.create(
        nom=f"{nom_base} – région {region.nom}", code=code, pays=["BF"],
        partenaire_mise_en_oeuvre=mise_en_oeuvre, cadre_strategique=cadres[s["cadre"]],
        element_strategique=elements[(secteur, "axe")],
        date_debut=debut, date_fin=fin, statut=Projet.Statut.EN_COURS,
        type_mise_en_oeuvre=Projet.TypeMiseEnOeuvre.CONSORTIUM if consortium else Projet.TypeMiseEnOeuvre.DIRECT,
        chef_de_projet_nom=f"{chef.nom} {chef.prenom}",
        cible_totale=cible, cible_femmes=femmes, cible_hommes=cible - femmes,
        cible_jeunes=int(cible * random.uniform(0.25, 0.4)), cible_pdi=int(cible * random.uniform(0.03, 0.15)),
        date_rappel=(AUJOURDHUI + timedelta(days=random.randint(20, 120))) if statut == Projet.Statut.EN_COURS else None,
        elements_capitalisation=" ".join(random.sample(CAPITALISATION, 2 if statut == Projet.Statut.CLOTURE else 1))
        if statut != Projet.Statut.EN_PREPARATION else "",
        ordre_attributs=["Lieu de mise en œuvre", "Priorité"],
    )
    for m in membres:
        m.projets_associes.add(projet)
    projet.structures.set([ref["structure_secteur"][secteur], ref["dsec"]])
    projet.parties_prenantes.set(random.sample(ref["parties_prenantes"], random.randint(2, 4)))
    autres_axes = [e for k, e in elements.items() if k[1] == "axe" and e != elements[(secteur, "axe")]]
    if autres_axes and random.random() < 0.5:
        projet.elements_strategiques_secondaires.set([random.choice(autres_axes)])
    zones = [region, *provinces, *Zone.objects.filter(parent__in=provinces)]
    projet.zones.set(zones)
    if ref["utilisateurs"]:
        projet.utilisateurs_affectes.set(ref["utilisateurs"])
    noms_niveaux = random.choice(NIVEAUX_PROJET)
    nommer_niveaux(projet, noms_niveaux)

    annees = list(range(debut.year, fin.year + 1))
    periodes = {
        a: PeriodePlanification.objects.create(projet=projet, libelle=f"Année {a}", date_debut=max(date(a, 1, 1), debut), date_fin=min(date(a, 12, 31), fin))
        for a in annees
    }
    duree = (fin - debut).days

    # Planification : thèmes → résultats → activités → sous-activités
    themes = random.sample(range(3), random.choice([2, 3, 3]))
    themes.sort()
    feuilles, tops = [], []
    for nt, t in enumerate(themes, start=1):
        theme, ind_theme, resultats = s["themes"][t]
        top = Activite.objects.create(
            projet=projet, code_activite=f"OS{nt}", libelle=theme, description=f"{theme} dans les provinces {', '.join(p.nom for p in provinces)}.",
            axe_strategique=elements[(secteur, t)], sources_verification=SOURCES[0], hypotheses=" ".join(random.sample(HYPOTHESES, 2)),
            equipe_responsable=equipe,
        )
        top.responsables.set([chef])
        tops.append((top, t, ind_theme))
        for nr, (resultat, ind_r, activites) in enumerate(resultats, start=1):
            mid = Activite.objects.create(
                projet=projet, activite_parent=top, code_activite=f"R{nt}.{nr}", libelle=resultat,
                axe_strategique=elements[(secteur, t, nr - 1)], sources_verification=SOURCES[1], hypotheses=random.choice(HYPOTHESES),
                equipe_responsable=equipe,
            )
            mid.responsables.set([membres[1]])
            mid._indicateur = ind_r
            mid._enfants = []
            choix = sorted(random.sample(range(3), random.choice([2, 3, 3])))
            for na, ia in enumerate(choix, start=1):
                libelle, unite, qte = activites[ia]
                q = max(6, int(qte * echelle * random.uniform(0.7, 1.1)))
                # Fenêtre de l'activité : un ou plusieurs blocs d'années dans la durée du projet.
                a_debut = debut + timedelta(days=int(duree * random.uniform(0, 0.35)))
                a_fin = min(fin, a_debut + timedelta(days=int(duree * random.uniform(0.4, 0.9))))
                a_debut = a_debut.replace(day=1)
                budget = arrondi(random.uniform(15, 140) * 1_000_000 * echelle)
                axe = elements.get((secteur, t, nr - 1, ia)) or elements[(secteur, t, nr - 1)]
                feuille = Activite.objects.create(
                    projet=projet, activite_parent=mid, code_activite=f"A{nt}.{nr}.{na}", libelle=libelle,
                    description=f"{libelle} au profit des communautés de la région {region.nom}.",
                    commentaire=random.choice(["", "", "Validée en comité de pilotage.", "Priorité du plan de travail annuel."]),
                    axe_strategique=axe, sources_verification=SOURCES[2], hypotheses=random.choice(HYPOTHESES),
                    attributs={"Lieu de mise en œuvre": random.choice(provinces).nom, "Priorité": random.choice(["Haute", "Moyenne", "Moyenne", "Basse"])},
                    budget_alloue=budget, valeur_reference=Decimal("0"), quantite_prevue=q, unite_quantite=unite,
                    date_debut=a_debut, date_fin=a_fin, equipe_responsable=equipe,
                    date_rappel=(a_fin - timedelta(days=30)) if a_fin > AUJOURDHUI else None,
                )
                feuille.responsables.set([random.choice(membres[2:])])
                feuille.structures.set([ref["structure_secteur"][secteur]])
                feuille._sous = []
                mid._enfants.append(feuille)
                feuilles.append(feuille)
                # Tranches annuelles de l'activité
                a_annees = [a for a in annees if chevauchement(a_debut, a_fin, date(a, 1, 1), date(a, 12, 31))]
                poids = [chevauchement(a_debut, a_fin, date(a, 1, 1), date(a, 12, 31)) for a in a_annees]
                total_poids = sum(poids)
                parts_q = [int(q * p / total_poids) for p in poids]
                parts_q[-1] += q - sum(parts_q)
                parts_b = [arrondi(budget * p / total_poids, 100_000) for p in poids]
                parts_b[-1] += budget - sum(parts_b)
                for a, pq, pb in zip(a_annees, parts_q, parts_b):
                    TranchePlanifiee.objects.create(
                        periode=periodes[a], activite=feuille, libelle=f"Année {a}", periode_debut=periodes[a].date_debut, periode_fin=periodes[a].date_fin,
                        cible=pq, budget=pb, date_debut_prevue=max(a_debut, date(a, 1, 1)), date_fin_prevue=min(a_fin, date(a, 12, 31)),
                    )
                # Sous-activités : étapes successives dans la fenêtre de l'activité
                etapes = random.sample(ETAPES, random.choice([2, 3, 3]))
                etapes.sort(key=ETAPES.index)
                jours = (a_fin - a_debut).days
                for ns, (etape, part) in enumerate(zip(etapes, repartir(q, len(etapes)))):
                    s_debut = a_debut + timedelta(days=int(jours * ns / len(etapes) * 0.6))
                    s_fin = a_fin if ns == len(etapes) - 1 else min(a_fin, s_debut + timedelta(days=int(jours * random.uniform(0.4, 0.8))))
                    sa = SousActivite.objects.create(
                        activite=feuille, libelle=etape + libelle[0].lower() + libelle[1:], axe_strategique=axe,
                        quantite_prevue=part, unite_quantite=unite, date_debut=s_debut, date_fin=s_fin,
                        attributs={"Lieu de mise en œuvre": random.choice(provinces).nom},
                    )
                    feuille._sous.append(sa)
                    for a in annees:
                        jours_a = chevauchement(s_debut, s_fin, date(a, 1, 1), date(a, 12, 31))
                        if jours_a:
                            TranchePlanifiee.objects.create(
                                periode=periodes[a], sous_activite=sa, libelle=f"Année {a}", periode_debut=periodes[a].date_debut,
                                periode_fin=periodes[a].date_fin, cible=round(part * jours_a / ((s_fin - s_debut).days + 1)),
                                date_debut_prevue=max(s_debut, date(a, 1, 1)), date_fin_prevue=min(s_fin, date(a, 12, 31)),
                            )
            top._mids = getattr(top, "_mids", []) + [mid]

    # Suivi réalisé : points semestriels sur les sous-activités puis sur les activités
    if statut != Projet.Statut.EN_PREPARATION:
        for feuille in feuilles:
            perf_a = min(1.0, perf * random.uniform(0.85, 1.15))
            perf_fin = random.uniform(0.75, 0.98)
            realise_par_periode = {}
            toutes_terminees = True
            for sa in feuille._sous:
                pts = periodes_suivi(sa.date_debut, sa.date_fin)
                if not pts:
                    toutes_terminees = False
                    continue
                total_jours = (sa.date_fin - sa.date_debut).days + 1
                fini = sa.date_fin < AUJOURDHUI and (statut == Projet.Statut.CLOTURE or perf_a > 0.9)
                cumul, cumul_q = 0, 0
                for k, (d, f) in enumerate(pts):
                    cumul += (f - d).days + 1
                    cible_cumul = int(sa.quantite_prevue) if fini and k == len(pts) - 1 else int(float(sa.quantite_prevue) * cumul / total_jours * perf_a)
                    q = max(0, cible_cumul - cumul_q)
                    cumul_q += q
                    termine = fini and k == len(pts) - 1
                    PointSuivi.objects.create(
                        sous_activite=sa, periode_debut=d, periode_fin=f, quantite_realisee=q,
                        statut="TERMINEE" if termine else "EN_COURS", saisi_par=ref["admin"],
                        commentaire="" if q else "Pas de réalisation sur la période.",
                    )
                    cle = (date(d.year, 1 if d.month <= 6 else 7, 1))
                    realise_par_periode[cle] = realise_par_periode.get(cle, 0) + q
                if not fini:
                    toutes_terminees = False
                synchroniser_sous_activite_depuis_suivi(sa)
            pts = periodes_suivi(feuille.date_debut, feuille.date_fin)
            if pts:
                total_jours = (feuille.date_fin - feuille.date_debut).days + 1
                fini = toutes_terminees and feuille.date_fin < AUJOURDHUI
                deja = 0
                for k, (d, f) in enumerate(pts):
                    cle = date(d.year, 1 if d.month <= 6 else 7, 1)
                    q = realise_par_periode.pop(cle, 0)
                    if k == len(pts) - 1:
                        q += sum(realise_par_periode.values())
                    part = ((f - d).days + 1) / total_jours
                    depense = arrondi(float(feuille.budget_alloue) * part * perf_fin, 50_000)
                    if fini and k == len(pts) - 1:
                        depense = max(0, int(float(feuille.budget_alloue) * random.uniform(0.92, 1.0)) - deja)
                    deja += depense
                    PointSuivi.objects.create(
                        activite=feuille, periode_debut=d, periode_fin=f, quantite_realisee=q, budget_realise=depense,
                        statut="REALISEE" if fini and k == len(pts) - 1 else "EN_COURS", saisi_par=ref["admin"],
                        commentaire=random.choice(["", "", "Activité conduite avec les services techniques.", "Retard dû à la saison des pluies."]),
                    )
                synchroniser_activite_depuis_suivi(feuille)

    # Agrégats des niveaux supérieurs (budgets, dates, statut)
    total_alloue = 0
    for top, t, ind_theme in tops:
        b_top, r_top, enfants_top = 0, 0, []
        for mid in top._mids:
            enfants = [Activite.objects.get(pk=f.pk) for f in mid._enfants]
            mid.budget_alloue = sum(e.budget_alloue or 0 for e in enfants)
            mid.budget_realise = sum(e.budget_realise or 0 for e in enfants)
            mid.date_debut = min(e.date_debut for e in enfants)
            mid.date_fin = max(e.date_fin for e in enfants)
            statuts = {e.statut for e in enfants}
            mid.statut = "REALISEE" if statuts == {"REALISEE"} else "EN_COURS" if statuts - {"NON_REALISEE"} else "NON_REALISEE"
            mid.save()
            b_top += mid.budget_alloue
            r_top += mid.budget_realise
            enfants_top.append(mid)
        top.budget_alloue, top.budget_realise = b_top, r_top
        top.date_debut = min(m.date_debut for m in enfants_top)
        top.date_fin = max(m.date_fin for m in enfants_top)
        statuts = {m.statut for m in enfants_top}
        top.statut = "REALISEE" if statuts == {"REALISEE"} else "EN_COURS" if statuts - {"NON_REALISEE"} else "NON_REALISEE"
        top.save()
        total_alloue += b_top

    # Objectifs par période des niveaux supérieurs : avancement attendu en fin d'année et budget des activités
    def tranches_parent(element, feuilles_dessous):
        jours = (element.date_fin - element.date_debut).days + 1
        for a in annees:
            if not chevauchement(element.date_debut, element.date_fin, date(a, 1, 1), date(a, 12, 31)):
                continue
            ecoule = chevauchement(element.date_debut, element.date_fin, element.date_debut, date(a, 12, 31))
            budget = sum(t.budget or 0 for t in TranchePlanifiee.objects.filter(activite__in=feuilles_dessous, periode=periodes[a]))
            TranchePlanifiee.objects.create(
                periode=periodes[a], activite=element, libelle=f"Année {a}", periode_debut=periodes[a].date_debut,
                periode_fin=periodes[a].date_fin, cible=min(100, round(ecoule / jours * 100)), budget=budget,
                date_debut_prevue=max(element.date_debut, date(a, 1, 1)), date_fin_prevue=min(element.date_fin, date(a, 12, 31)),
            )

    for top, _, _ in tops:
        tranches_parent(top, [f for m in top._mids for f in m._enfants])
        for mid in top._mids:
            tranches_parent(mid, mid._enfants)

    # Financement : fonds propres + plusieurs bailleurs (+ rallonges éventuelles)
    total_projet = arrondi(float(total_alloue) * random.uniform(1.06, 1.15))
    fonds_propres = arrondi(total_projet * random.uniform(0.04, 0.12))
    bailleurs = random.sample(ref["bailleurs"], random.choice([1, 2, 2, 3, 3, 4]))
    parts = [random.uniform(1, 3) for _ in bailleurs]
    reste = total_projet - fonds_propres
    montants = [arrondi(reste * p / sum(parts)) for p in parts]
    montants[0] += reste - sum(montants)
    financements = [Financement.objects.create(projet=projet, bailleur=b, montant_finance=m) for b, m in zip(bailleurs, montants)]
    if statut != Projet.Statut.EN_PREPARATION and random.random() < 0.3:
        f = random.choice(financements)
        RallongeFinancement.objects.create(
            financement=f, montant=arrondi(float(f.montant_finance) * random.uniform(0.05, 0.15)),
            date=min(AUJOURDHUI - timedelta(days=30), debut + timedelta(days=int(duree * 0.5))),
            motif=random.choice(["Extension de la couverture à de nouvelles communes.", "Hausse des coûts des matériaux de construction.",
                                 "Intégration d'une réponse aux besoins des personnes déplacées."]),
            saisi_par=ref["admin"],
        )
    projet.fonds_propres = fonds_propres
    projet.partenaire_bailleur = ref["partenaires_bailleur"][bailleurs[0].nom]
    projet.save()
    projet.budget_total = projet.fonds_propres + projet.financement_bailleurs_total
    projet.save(update_fields=["budget_total"])

    # Partenaires du projet et rôles
    PartenaireProjet.objects.create(
        projet=projet, partenaire=mise_en_oeuvre, nature=PartenaireProjet.Nature.MISE_EN_OEUVRE, chef_de_file=True,
        role="Pilotage technique et financier, coordination des partenaires et rapportage aux bailleurs.",
    ).elements.set([t[0] for t in tops])
    if consortium:
        autres = random.sample([p for p in ref["partenaires_meo"] if p != mise_en_oeuvre], 2)
        projet.partenaires_consortium.set([mise_en_oeuvre, *autres])
        for p in autres:
            pp = PartenaireProjet.objects.create(
                projet=projet, partenaire=p, nature=PartenaireProjet.Nature.CONSORTIUM,
                role="Mise en œuvre des activités de terrain dans sa zone d'implantation et mobilisation communautaire.",
            )
            pp.elements.set(random.sample(feuilles, min(3, len(feuilles))))

    # Indicateurs : projet, objectifs, résultats — valeurs annuelles et cibles par période
    def indicateur(libelle, unite, cible_base, rattachement, element, frequence, brut=False):
        cible_i = cible_base if unite == "%" or brut else max(5, int(cible_base * echelle))
        ref_i = round(cible_i * random.uniform(0.2, 0.4)) if unite == "%" else 0
        ind = Indicateur.objects.create(
            libelle=libelle, unite=unite, valeur_reference=ref_i, valeur_reference_date=debut - timedelta(days=30),
            valeur_cible=cible_i, frequence_collecte=frequence, **rattachement,
        )
        if element:
            IndicateurElement.objects.create(indicateur=ind, element_strategique=element)
        for a, poids in zip(annees, repartir(100, len(annees))):
            TranchePlanifiee.objects.create(
                periode=periodes[a], indicateur=ind, libelle=f"Année {a}", periode_debut=periodes[a].date_debut,
                periode_fin=periodes[a].date_fin, cible=round(cible_i * poids / 100),
            )
        if statut == Projet.Statut.EN_PREPARATION:
            return
        cumul_avant = 0
        for a in annees:
            d = max(date(a, 1, 1), debut)
            f = min(date(a, 12, 31), fin)
            if f >= AUJOURDHUI:
                f = min(fin, date(a, 6, 30))
                if f >= AUJOURDHUI or f < d:
                    break
            avance = min(1.0, ((f - debut).days + 1) / (duree + 1) * perf * random.uniform(0.9, 1.1))
            total = round(cible_i * avance)
            valeur = max(0, total - cumul_avant)
            cumul_avant += valeur
            ValeurIndicateur.objects.create(
                indicateur=ind, periode_debut=d, periode_fin=f, valeur_realisee=valeur, saisi_par=ref["admin"],
                commentaire=f"Données consolidées des rapports de terrain ({d.strftime('%m/%Y')} - {f.strftime('%m/%Y')}).",
            )

    indicateur("Nombre de bénéficiaires directs touchés par le projet", "personnes", cible, {"projet": projet}, elements[(secteur, "axe")], "ANNUELLE", brut=True)
    indicateur("Proportion de femmes parmi les bénéficiaires directs", "%", 55, {"projet": projet}, None, "ANNUELLE")
    for top, t, (lib, unite, c) in tops:
        indicateur(lib, unite, c, {"activite": top}, elements[(secteur, t)], "ANNUELLE")
        for nr, mid in enumerate(top._mids):
            lib_r, unite_r, c_r = mid._indicateur
            indicateur(lib_r, unite_r, c_r, {"activite": mid}, elements[(secteur, t, nr)], "SEMESTRIELLE")

    # Jalons et livrables
    for nom_l, frac in [("Rapport de démarrage", 0.08), ("Rapport à mi-parcours", 0.5), ("Rapport final", 1.0)]:
        prevue = debut + timedelta(days=int(duree * frac))
        fait = prevue < AUJOURDHUI and statut != Projet.Statut.EN_PREPARATION
        JalonLivrable.objects.create(
            activite=tops[0][0], type=JalonLivrable.Type.LIVRABLE, libelle=nom_l, date_prevue=prevue, valide=fait,
            valide_par=ref["admin"] if fait else None, date_validation=prevue + timedelta(days=10) if fait else None,
        )
    for mid in tops[0][0]._mids:
        for nom_j, poids, frac in [("Lancement des activités", 30, 0.1), ("Réalisation de la moitié des cibles", 40, 0.5), ("Réception finale", 30, 0.95)]:
            prevue = mid.date_debut + timedelta(days=int((mid.date_fin - mid.date_debut).days * frac))
            JalonLivrable.objects.create(
                activite=mid, type=JalonLivrable.Type.JALON, libelle=nom_j, poids=poids, date_prevue=prevue,
                achevement=100 if prevue < AUJOURDHUI and statut != Projet.Statut.EN_PREPARATION else (40 if prevue < AUJOURDHUI + timedelta(days=180) else 0),
            )

    # Risques et réévaluations
    for r in random.sample(RISQUES, random.randint(4, 6)):
        libelle, categorie, nature, description, mesures, contingence = r
        p0, i0 = random.randint(2, 5), random.randint(2, 5)
        risque = Risque.objects.create(
            projet=projet, libelle=libelle, description=description, nature=nature, categorie=categorie,
            element=random.choice([t[0] for t in tops] + feuilles[:3]), probabilite=p0, impact=i0,
            mesures_attenuation=mesures, plan_contingence=contingence, responsable=random.choice(membres[:3]),
            date_identification=debut + timedelta(days=random.randint(0, 45)) if debut < AUJOURDHUI else AUJOURDHUI - timedelta(days=10),
            date_prochaine_revue=AUJOURDHUI + timedelta(days=random.randint(15, 90)) if statut != Projet.Statut.CLOTURE else None,
        )
        if statut == Projet.Statut.EN_PREPARATION:
            continue
        p, imp, d = p0, i0, risque.date_identification
        dernier_statut = Risque.Statut.ACTIF
        for k in range(random.randint(1, 3)):
            d = d + timedelta(days=random.randint(90, 200))
            if d >= AUJOURDHUI or (statut == Projet.Statut.CLOTURE and d > fin):
                break
            p, imp = max(1, min(5, p + random.choice([-1, -1, 0, 1]))), max(1, min(5, imp + random.choice([-1, 0, 0, 1])))
            dernier_statut = random.choice([Risque.Statut.ACTIF, Risque.Statut.ACTIF, Risque.Statut.MAITRISE, Risque.Statut.SURVENU])
            EvaluationRisque.objects.create(
                risque=risque, date=d, probabilite=p, impact=imp, statut=dernier_statut,
                actions_menees="Mesures d'atténuation appliquées et suivies en réunion de coordination mensuelle.",
                commentaire=random.choice(["Situation stable.", "Vigilance renforcée sur la période.", "Amélioration constatée après les mesures prises."]),
                saisi_par=ref["admin"],
            )
        if statut == Projet.Statut.CLOTURE:
            Risque.objects.filter(pk=risque.pk).update(statut=Risque.Statut.CLOS)
        else:
            Risque.objects.filter(pk=risque.pk).update(statut=dernier_statut)

    # Documents (GED)
    dossiers = {n: Dossier.objects.create(nom=n, projet=projet, cree_par=ref["admin"])
                for n in ["01 - Documents contractuels", "02 - Rapports", "03 - Suivi-évaluation", "04 - Passation des marchés"]}

    def document(nom, dossier, type_doc, lignes, activite=None, versions=1):
        doc = Document.objects.create(nom=nom, dossier=dossiers[dossier], projet=projet, activite=activite, type_document=type_doc,
                                      description=lignes[0], cree_par=ref["admin"])
        for v in range(1, versions + 1):
            contenu = pdf(nom, [f"Projet : {projet.code} - {projet.nom}"[:95], *lignes, f"Version {v}"])
            version = DocumentVersion(document=doc, version=v, uploaded_by=ref["admin"],
                                      commentaire="Version initiale" if v == 1 else "Version validée en comité de pilotage")
            version.fichier.save(f"{projet.code}_{nom[:40]}.pdf".replace(" ", "_").replace("/", "-"), ContentFile(contenu), save=False)
            version.save()

    document("Document de projet (PRODOC)", "01 - Documents contractuels", "Document de projet",
             ["Présentation du contexte, de la logique d'intervention et du budget du projet.", f"Période : {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"], versions=2)
    for f in financements:
        document(f"Convention de financement - {f.bailleur.nom}", "01 - Documents contractuels", "Convention",
                 [f"Convention signée avec {f.bailleur.nom}.", f"Montant : {int(f.montant_finance):,} FCFA".replace(",", " ")])
    document("Plan de suivi-évaluation", "03 - Suivi-évaluation", "Plan S&E",
             ["Indicateurs, sources de vérification, fréquences de collecte et responsabilités."])
    if statut != Projet.Statut.EN_PREPARATION:
        document("Rapport de l'enquête de référence", "03 - Suivi-évaluation", "Rapport d'étude",
                 ["Situation de référence des indicateurs dans la zone d'intervention."])
        document("Rapport de démarrage", "02 - Rapports", "Rapport", ["Mise en place de l'équipe, des partenaires et du dispositif de suivi."])
        for a in annees:
            if date(a, 12, 31) < AUJOURDHUI and date(a, 12, 31) <= fin:
                document(f"Rapport annuel {a}", "02 - Rapports", "Rapport annuel", [f"Bilan physique et financier de l'année {a}."])
        for feuille in random.sample(feuilles, min(2, len(feuilles))):
            document(f"PV de réception - {feuille.libelle}"[:120], "04 - Passation des marchés", "Procès-verbal",
                     ["Réception provisoire des réalisations sans réserve majeure."], activite=feuille)
    if statut == Projet.Statut.CLOTURE:
        document("Rapport final d'exécution", "02 - Rapports", "Rapport final", ["Bilan complet du projet, leçons apprises et recommandations."])

    # Bénéficiaires et participations
    zones_benef = [z for z in zones if z != region]
    types = [ref["types_activite"][t] for t in s["types_benef"] if t in ref["types_activite"]]
    if statut != Projet.Statut.EN_PREPARATION:
        for _ in range(random.randint(12, 24)):
            sexe = "F" if random.random() < 0.58 else "M"
            b = Beneficiaire.objects.create(
                nom=random.choice(NOMS), prenom=random.choice(PRENOMS_F if sexe == "F" else PRENOMS_H), sexe=sexe,
                date_naissance=date(random.randint(1962, 2006), random.randint(1, 12), random.randint(1, 28)),
                telephone=f"+226 {random.choice([5, 6, 7])}{random.randint(0, 9)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                numero_piece_identite=f"B{random.randint(10000000, 99999999)}", type_piece="CNIB", pays="BF",
                zone=random.choice(zones_benef),
            )
            statuts = []
            if random.random() < 0.15:
                statuts.append(ref["statuts"].get("PDI"))
            if random.random() < 0.35:
                statuts.append(ref["statuts"].get("JEUNE"))
            if sexe == "F" and random.random() < 0.25:
                statuts.append(ref["statuts"].get("FEMME_CHEF_MENAGE"))
            if random.random() < 0.06:
                statuts.append(ref["statuts"].get("HANDICAP"))
            b.statuts_particuliers.set([x for x in statuts if x])
            if types:
                b.types_activite.set(random.sample(types, random.randint(1, min(2, len(types)))))
            ParticipationProjet.objects.create(
                beneficiaire=b, projet=projet, activite=random.choice(feuilles),
                date_inscription=debut + timedelta(days=random.randint(0, max(1, min(duree, (AUJOURDHUI - debut).days)))),
                role_dans_projet=random.choice(["Bénéficiaire direct", "Bénéficiaire direct", "Membre de groupement", "Relais communautaire", "Producteur pilote"]),
            )

    # Statut définitif (après coup : un projet clôturé est verrouillé)
    Projet.objects.filter(pk=projet.pk).update(statut=statut)
    return projet


def executer():
    with transaction.atomic(), verrou_desactive():
        vider()
        print("Données supprimées.")
        ref = creer_referentiels()
        cadres, elements = creer_cadres(ref)
        print(f"{len(cadres)} cadres stratégiques, {len([k for k in elements])} éléments.")
        regions = list(ref["regions"].items())
        random.shuffle(regions)
        secteurs = list(SECTEURS)
        codes_pris = set()
        for i in range(NB_PROJETS):
            secteur = secteurs[i % len(secteurs)]
            region, provinces_region = regions[i % len(regions)]
            provinces = random.sample(provinces_region, min(len(provinces_region), random.randint(2, 3)))
            projet = creer_projet(i, secteur, ref, cadres, elements, region, provinces, codes_pris)
            print(f"{i + 1:2d}. {projet.code} — {projet.activites.count()} éléments, "
                  f"{SousActivite.objects.filter(activite__projet=projet).count()} sous-activités")




class Command(BaseCommand):
    help = "Vide les données métier et crée 4 cadres stratégiques et 50 projets entièrement renseignés."

    def handle(self, *args, **options):
        random.seed(20261029)
        executer()
        from django.apps import apps as _apps

        for modele in ["projects.Projet", "projects.Activite", "projects.SousActivite", "suivi.PointSuivi",
                       "indicators.Indicateur", "projects.Risque", "documents.Document", "beneficiaries.Beneficiaire"]:
            self.stdout.write(f"{modele} : {_apps.get_model(modele).objects.count()}")
