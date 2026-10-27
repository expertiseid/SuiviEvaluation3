"""
Vide les données métier (projets, cadres stratégiques, indicateurs, équipes,
intervenants, bénéficiaires, partenaires/bailleurs, notifications) et les
remplace par 5 cadres stratégiques et 5 projets entièrement renseignés — un
projet par cadre, chacun avec sa planification complète (objectifs,
activités, sous-activités), ses indicateurs et leur historique de valeurs,
ses zones d'intervention, son équipe, ses bénéficiaires et son financement.

Les comptes utilisateurs (accounts_user) ne sont jamais touchés. Le
référentiel géographique (geo_zone) n'est pas régénéré, mais les zones de
test orphelines créées lors de vérifications précédentes (Djibo, Koubri,
Ouagadougou-village, VillageTest79125) sont supprimées.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.beneficiaries.models import Beneficiaire, ParticipationProjet, SignalementDoublon, StatutParticulier
from apps.geo.models import NiveauAdministratif, Zone
from apps.indicators.models import Indicateur, PalierAlerte, ValeurIndicateur
from apps.intervenants.models import Intervenant
from apps.notifications.models import Notification
from apps.partners.models import Bailleur, Financement, Partenaire
from apps.projects.models import Activite, Equipe, Projet, SousActivite
from apps.projects.services import nommer_niveaux
from apps.projects.services import supprimer_projet_cascade
from apps.strategy.models import CadreStrategique, ElementStrategique, TypeNiveau
from apps.strategy.services import supprimer_cadre_strategique_cascade

User = get_user_model()


# ======================================================================
# Contenu des 5 projets — chaque profil porte tout le texte et les valeurs
# spécifiques à son secteur ; une seule fonction générique (peupler_projet)
# construit les objets à partir de ce contenu, pour éviter cinq blocs de
# code dupliqués.
# ======================================================================
PROFILS = [
    {
        "cle": "ARA",
        "cadre_nom": "Cadre stratégique — Résilience Agroécologique 2026-2029",
        "axe": ("AXE1", "Renforcement de la résilience agroécologique des communautés rurales"),
        "orientation": ("OR1.1", "Promotion des pratiques agroécologiques et de gestion durable des sols"),
        "resultats": [
            ("RA1.1.1", "Les producteurs et productrices adoptent des pratiques agroécologiques durables"),
            ("RA1.1.2", "La fertilité des sols est restaurée dans les zones d'intervention"),
        ],
        "projet_nom": "Programme d'Appui à la Résilience Agroécologique",
        "code": "EXPERTISE-ID-ARA-2026",
        "date_debut": date(2026, 1, 1),
        "date_fin": date(2029, 12, 31),
        "date_rappel": date(2026, 12, 15),
        "budget_total": Decimal("780000000"),
        "fonds_propres": Decimal("78000000"),
        "type_mise_en_oeuvre": Projet.TypeMiseEnOeuvre.DIRECT,
        "chef_de_projet": "SAWADOGO Boukary",
        "cibles": dict(cible_totale=4800, cible_hommes=1900, cible_femmes=2900, cible_jeunes=1700, cible_pdi=400),
        "bailleur_principal": "Union Européenne",
        "financements": [("Union Européenne", Decimal("470000000")), ("Agence Française de Développement", Decimal("232000000"))],
        "zones": ["Nakambe", "Boulgou", "Kourittenga"],
        "capitalisation": (
            "Les champs-écoles paysans se révèlent être le format de formation le plus efficace pour "
            "l'adoption durable des pratiques agroécologiques."
        ),
        "og": "Contribuer à l'amélioration durable de la résilience agroécologique des ménages ruraux vulnérables de la région du Nakambe",
        "og_description": "Le programme vise à renforcer l'adoption de pratiques agroécologiques durables sur un horizon de quatre ans.",
        "os": [
            {
                "libelle": "Renforcer l'adoption de pratiques agroécologiques durables par les producteurs et productrices",
                "description": "Formation, accompagnement technique et aménagements de conservation des eaux et des sols.",
                "resultat_idx": 0,
                "indicateur": ("Taux d'adoption de pratiques agroécologiques durables par les producteurs formés", "%", 0, 75, "ANNUELLE", [30, 25]),
                "activites": [
                    {
                        "code": "A1.1.1",
                        "libelle": "Formation des producteurs et productrices aux techniques agroécologiques (compost, CES/DRS, agroforesterie)",
                        "unite": "producteurs formés",
                        "prevue": 1200, "realisee": 540,
                        "sous_activite": "Organisation de sessions de formation pratique en champs-écoles paysans",
                        "sous_activite_unite": "sessions", "sous_prevue": 40, "sous_realisee": 18,
                        "budget_alloue": Decimal("45000000"), "budget_realise": Decimal("18000000"),
                        "indicateur": ("Nombre de producteurs et productrices formés aux techniques agroécologiques", "producteurs", 0, 1200, "SEMESTRIELLE", [300, 450]),
                    },
                    {
                        "code": "A1.1.2",
                        "libelle": "Aménagement de dispositifs de conservation des eaux et des sols (cordons pierreux, zaï, demi-lunes)",
                        "unite": "hectares",
                        "prevue": 300, "realisee": 95,
                        "sous_activite": "Réalisation de chantiers communautaires d'aménagement CES/DRS",
                        "sous_activite_unite": "hectares", "sous_prevue": 300, "sous_realisee": 95,
                        "budget_alloue": Decimal("60000000"), "budget_realise": Decimal("21000000"),
                        "indicateur": ("Superficie aménagée en dispositifs de conservation des eaux et des sols", "hectares", 0, 300, "SEMESTRIELLE", [40, 55]),
                    },
                ],
            },
            {
                "libelle": "Améliorer la structuration et l'autonomisation des organisations paysannes",
                "description": "Appui institutionnel aux organisations paysannes et facilitation de l'accès aux intrants.",
                "resultat_idx": 1,
                "indicateur": ("Nombre d'organisations paysannes formalisées et fonctionnelles", "organisations", 0, 30, "ANNUELLE", [10, 17]),
                "activites": [
                    {
                        "code": "A1.2.1",
                        "libelle": "Appui à la structuration et à la formalisation des organisations paysannes",
                        "unite": "organisations paysannes",
                        "prevue": 40, "realisee": 11,
                        "sous_activite": "Accompagnement à l'élaboration des textes statutaires et à l'enregistrement légal",
                        "sous_activite_unite": "dossiers", "sous_prevue": 40, "sous_realisee": 11,
                        "budget_alloue": Decimal("25000000"), "budget_realise": Decimal("9000000"),
                        "indicateur": None,
                    },
                    {
                        "code": "A1.2.2",
                        "libelle": "Facilitation de l'accès aux intrants et équipements agroécologiques",
                        "unite": "boutiques d'intrants",
                        "prevue": 12, "realisee": 3,
                        "sous_activite": "Mise en place d'un système de warrantage / boutique d'intrants communautaire",
                        "sous_activite_unite": "boutiques", "sous_prevue": 12, "sous_realisee": 3,
                        "budget_alloue": Decimal("30000000"), "budget_realise": Decimal("4000000"),
                        "indicateur": ("Nombre de boutiques d'intrants communautaires opérationnelles", "boutiques", 0, 12, "ANNUELLE", [3]),
                    },
                ],
            },
        ],
        "indicateur_projet": ("Nombre total de bénéficiaires directs touchés par le programme", "personnes", 0, 4800, "ANNUELLE", [1800, 1400]),
        "intervenants": [("ZONGO", "Salif", "Chef d'équipe terrain"), ("TRAORE", "Ali", "Technicien agroécologie"), ("SANOU", "Mariam", "Assistante administrative et financière")],
        "beneficiaires": [
            ("SOME", "Adama", "M", ["jeune"]), ("OUATTARA", "Rasmata", "F", ["femme_chef_menage"]),
            ("KABORE", "Boureima", "M", []), ("YAMEOGO", "Salamata", "F", ["jeune", "femme_chef_menage"]),
            ("NANA", "Issa", "M", ["handicap"]),
        ],
        "grille_alerte": None,
    },
    {
        "cle": "PAERP",
        "cadre_nom": "Cadre stratégique — Élevage et Résilience Pastorale 2026-2028",
        "axe": ("AXE1", "Sécurisation et amélioration de la production pastorale"),
        "orientation": ("OR1.1", "Santé animale et gestion des ressources pastorales"),
        "resultats": [
            ("RA1.1.1", "Le cheptel est mieux protégé contre les maladies prioritaires"),
            ("RA1.1.2", "Les points d'eau pastoraux sont fonctionnels toute l'année"),
        ],
        "projet_nom": "Programme d'Appui à l'Élevage et à la Résilience Pastorale",
        "code": "PAERP-2026",
        "date_debut": date(2026, 2, 1),
        "date_fin": date(2028, 1, 31),
        "date_rappel": date(2026, 11, 30),
        "budget_total": Decimal("480000000"),
        "fonds_propres": Decimal("48000000"),
        "type_mise_en_oeuvre": Projet.TypeMiseEnOeuvre.CONSORTIUM,
        "chef_de_projet": "COMPAORE Issouf",
        "cibles": dict(cible_totale=3200, cible_hommes=2100, cible_femmes=1100, cible_jeunes=900, cible_pdi=350),
        "bailleur_principal": "Fondation de France",
        "financements": [("Fondation de France", Decimal("300000000")), ("UNICEF", Decimal("132000000"))],
        "zones": ["Liptako", "Oudalan", "Seno"],
        "capitalisation": "",
        "og": "Contribuer à la sécurisation et à la résilience des systèmes pastoraux dans la région du Liptako",
        "og_description": "Le programme combine santé animale, hydraulique pastorale et professionnalisation des éleveurs sur deux ans.",
        "os": [
            {
                "libelle": "Améliorer la couverture sanitaire du cheptel",
                "description": "Campagnes de vaccination et formation d'auxiliaires vétérinaires communautaires.",
                "resultat_idx": 0,
                "indicateur": ("Taux de couverture vaccinale du cheptel suivi", "%", 15, 80, "SEMESTRIELLE", [35, 52]),
                "activites": [
                    {
                        "code": "AE1.1",
                        "libelle": "Organiser des campagnes de vaccination et de déparasitage du bétail",
                        "unite": "têtes de bétail",
                        "prevue": 25000, "realisee": 11200,
                        "sous_activite": "Organisation de campagnes mobiles de vaccination en saison sèche",
                        "sous_activite_unite": "campagnes", "sous_prevue": 6, "sous_realisee": 3,
                        "budget_alloue": Decimal("60000000"), "budget_realise": Decimal("24000000"),
                        "indicateur": ("Nombre de têtes de bétail effectivement vaccinées et suivies", "têtes", 0, 25000, "SEMESTRIELLE", [4800, 6400]),
                    },
                    {
                        "code": "AE1.2",
                        "libelle": "Former des auxiliaires vétérinaires communautaires",
                        "unite": "auxiliaires formés",
                        "prevue": 80, "realisee": 34,
                        "sous_activite": "Sessions de formation initiale et de recyclage des auxiliaires",
                        "sous_activite_unite": "sessions", "sous_prevue": 10, "sous_realisee": 5,
                        "budget_alloue": Decimal("35000000"), "budget_realise": Decimal("14000000"),
                        "indicateur": ("Nombre d'auxiliaires vétérinaires communautaires opérationnels", "auxiliaires", 0, 80, "ANNUELLE", [34]),
                    },
                ],
            },
            {
                "libelle": "Sécuriser l'accès à l'eau et aux ressources pastorales",
                "description": "Réhabilitation de points d'eau pastoraux et balisage de couloirs de transhumance.",
                "resultat_idx": 1,
                "indicateur": ("Taux de fonctionnalité des points d'eau pastoraux réhabilités", "%", 20, 90, "SEMESTRIELLE", [45, 58]),
                "activites": [
                    {
                        "code": "AE2.1",
                        "libelle": "Réhabiliter des points d'eau pastoraux",
                        "unite": "points d'eau",
                        "prevue": 25, "realisee": 9,
                        "sous_activite": "Travaux de réhabilitation et équipement en pompes solaires",
                        "sous_activite_unite": "points d'eau", "sous_prevue": 25, "sous_realisee": 9,
                        "budget_alloue": Decimal("70000000"), "budget_realise": Decimal("22000000"),
                        "indicateur": None,
                    },
                    {
                        "code": "AE2.2",
                        "libelle": "Baliser et sécuriser les couloirs de transhumance",
                        "unite": "kilomètres",
                        "prevue": 120, "realisee": 40,
                        "sous_activite": "Pose de balises et concertation intercommunautaire sur les tracés",
                        "sous_activite_unite": "kilomètres", "sous_prevue": 120, "sous_realisee": 40,
                        "budget_alloue": Decimal("28000000"), "budget_realise": Decimal("7000000"),
                        "indicateur": None,
                    },
                ],
            },
        ],
        "indicateur_projet": ("Nombre total d'éleveurs et éleveuses bénéficiaires directs", "personnes", 0, 3200, "ANNUELLE", [1450]),
        "intervenants": [("BATIONO", "Rasmané", "Technicien génie rural"), ("DIALLO", "Aissata", "Chargée de genre et gouvernance"), ("NIKIEMA", "Aminata", "Chargée de nutrition")],
        "beneficiaires": [
            ("MAIGA", "Fatoumata", "F", ["pdi", "femme_chef_menage"]), ("CISSE", "Boureima", "M", ["pdi"]),
            ("DICKO", "Aissa", "F", ["jeune"]), ("TOURE", "Hamidou", "M", []), ("BARRY", "Zenabou", "F", ["pdi", "jeune"]),
        ],
        "grille_alerte": [(0, "Critique", "#c92a2a"), (40, "En retard", "#e8590c"), (65, "Sur la bonne voie", "#2f9e44"), (90, "Atteint", "#087f5b")],
    },
    {
        "cle": "PRENF",
        "cadre_nom": "Cadre stratégique — Éducation Non Formelle 2026-2027",
        "axe": ("AXE1", "Accès à une éducation non formelle de qualité"),
        "orientation": ("OR1.1", "Alphabétisation et formation professionnelle des jeunes déscolarisés"),
        "resultats": [
            ("RA1.1.1", "Les jeunes et adultes déscolarisés maîtrisent la lecture, l'écriture et le calcul de base"),
            ("RA1.1.2", "Les jeunes formés accèdent à une insertion socio-économique durable"),
        ],
        "projet_nom": "Programme de Renforcement de l'Éducation Non Formelle",
        "code": "PRENF-2026",
        "date_debut": date(2026, 3, 1),
        "date_fin": date(2027, 8, 31),
        "date_rappel": date(2026, 9, 1),
        "budget_total": Decimal("310000000"),
        "fonds_propres": Decimal("31000000"),
        "type_mise_en_oeuvre": Projet.TypeMiseEnOeuvre.DIRECT,
        "chef_de_projet": "OUEDRAOGO Awa",
        "cibles": dict(cible_totale=2600, cible_hommes=900, cible_femmes=1700, cible_jeunes=2200, cible_pdi=250),
        "bailleur_principal": "UNICEF",
        "financements": [("UNICEF", Decimal("210000000")), ("Union Européenne", Decimal("69000000"))],
        "zones": ["Nando", "Boulkiemde", "Sissili"],
        "capitalisation": "",
        "og": "Contribuer à l'amélioration de l'accès des jeunes et adultes déscolarisés à une éducation non formelle de qualité dans la région du Nando",
        "og_description": "Le programme combine alphabétisation fonctionnelle et formation professionnelle qualifiante sur dix-huit mois.",
        "os": [
            {
                "libelle": "Renforcer les compétences de base en lecture, écriture et calcul",
                "description": "Centres d'alphabétisation fonctionnelle et kits pédagogiques.",
                "resultat_idx": 0,
                "indicateur": ("Taux de réussite au test de fin de cycle d'alphabétisation", "%", 0, 70, "ANNUELLE", [42]),
                "activites": [
                    {
                        "code": "AENF1.1",
                        "libelle": "Ouvrir et animer des centres d'alphabétisation fonctionnelle",
                        "unite": "apprenants inscrits",
                        "prevue": 1800, "realisee": 690,
                        "sous_activite": "Recrutement et formation des animateurs de centres",
                        "sous_activite_unite": "animateurs formés", "sous_prevue": 45, "sous_realisee": 32,
                        "budget_alloue": Decimal("70000000"), "budget_realise": Decimal("26000000"),
                        "indicateur": ("Nombre d'apprenants inscrits dans les centres d'alphabétisation", "apprenants", 0, 1800, "SEMESTRIELLE", [690]),
                    },
                    {
                        "code": "AENF1.2",
                        "libelle": "Distribuer des kits pédagogiques et du matériel didactique",
                        "unite": "kits distribués",
                        "prevue": 1800, "realisee": 720,
                        "sous_activite": "Confection et distribution des kits d'apprenant",
                        "sous_activite_unite": "kits", "sous_prevue": 1800, "sous_realisee": 720,
                        "budget_alloue": Decimal("22000000"), "budget_realise": Decimal("9000000"),
                        "indicateur": None,
                    },
                ],
            },
            {
                "libelle": "Faciliter l'insertion socio-économique des jeunes formés",
                "description": "Formation professionnelle qualifiante et appui à l'auto-emploi.",
                "resultat_idx": 1,
                "indicateur": ("Taux d'insertion socio-économique des jeunes formés à 6 mois", "%", 0, 55, "ANNUELLE", [18]),
                "activites": [
                    {
                        "code": "AENF2.1",
                        "libelle": "Former les jeunes à un métier porteur (couture, mécanique, électricité solaire)",
                        "unite": "jeunes formés",
                        "prevue": 600, "realisee": 180,
                        "sous_activite": "Sessions de formation professionnelle en apprentissage dual",
                        "sous_activite_unite": "cohortes", "sous_prevue": 12, "sous_realisee": 4,
                        "budget_alloue": Decimal("85000000"), "budget_realise": Decimal("28000000"),
                        "indicateur": ("Nombre de jeunes formés à un métier porteur", "jeunes", 0, 600, "SEMESTRIELLE", [180]),
                    },
                    {
                        "code": "AENF2.2",
                        "libelle": "Appuyer l'auto-emploi des jeunes formés (kits de démarrage, mentorat)",
                        "unite": "jeunes appuyés",
                        "prevue": 300, "realisee": 45,
                        "sous_activite": "Octroi de kits de démarrage et mentorat post-formation",
                        "sous_activite_unite": "kits", "sous_prevue": 300, "sous_realisee": 45,
                        "budget_alloue": Decimal("40000000"), "budget_realise": Decimal("6000000"),
                        "indicateur": None,
                    },
                ],
            },
        ],
        "indicateur_projet": ("Nombre total de jeunes et adultes déscolarisés touchés par le programme", "personnes", 0, 2600, "ANNUELLE", [720]),
        "intervenants": [("KABORE", "Fatimata", "Animatrice terrain"), ("OUEDRAOGO", "Awa", "Chargée de Suivi-Évaluation"), ("SAWADOGO", "Boukary", "Coordonnateur de projet")],
        "beneficiaires": [
            ("SAWADOGO", "Aicha", "F", ["jeune"]), ("KONATE", "Moussa", "M", ["jeune", "pdi"]),
            ("ZERBO", "Awa", "F", ["jeune", "femme_chef_menage"]), ("OUEDRAOGO", "Boukary", "M", ["jeune"]),
            ("SANA", "Ramata", "F", ["jeune", "handicap"]),
        ],
        "grille_alerte": None,
    },
    {
        "cle": "PRSNC",
        "cadre_nom": "Cadre stratégique — Santé et Nutrition Communautaire 2026-2028",
        "axe": ("AXE1", "Prévention et prise en charge de la malnutrition"),
        "orientation": ("OR1.1", "Renforcement du dépistage et de la prise en charge communautaire"),
        "resultats": [
            ("RA1.1.1", "Les enfants de moins de 5 ans sont dépistés et pris en charge précocement"),
            ("RA1.1.2", "Les pratiques familiales essentielles de nutrition sont adoptées par les ménages"),
        ],
        "projet_nom": "Programme de Renforcement de la Santé et de la Nutrition Communautaire",
        "code": "PRSNC-2026",
        "date_debut": date(2026, 1, 15),
        "date_fin": date(2028, 1, 14),
        "date_rappel": date(2026, 10, 5),
        "budget_total": Decimal("540000000"),
        "fonds_propres": Decimal("54000000"),
        "type_mise_en_oeuvre": Projet.TypeMiseEnOeuvre.CONSORTIUM,
        "chef_de_projet": "NIKIEMA Aminata",
        "cibles": dict(cible_totale=6000, cible_hommes=1200, cible_femmes=4800, cible_jeunes=2500, cible_pdi=1100),
        "bailleur_principal": "UNICEF",
        "financements": [("UNICEF", Decimal("350000000")), ("ECHO — Protection civile UE", Decimal("136000000"))],
        "zones": ["Djoro", "Ioba", "Poni"],
        "capitalisation": "",
        "og": "Contribuer à la réduction de la malnutrition aiguë chez les enfants de moins de 5 ans dans la région du Djoro",
        "og_description": "Le programme articule dépistage communautaire, prise en charge et promotion des pratiques familiales essentielles sur deux ans.",
        "os": [
            {
                "libelle": "Renforcer le dépistage et la référence précoce des enfants malnutris",
                "description": "Dépistage par les relais communautaires et référencement vers les centres de santé.",
                "resultat_idx": 0,
                "indicateur": ("Taux de couverture du dépistage communautaire chez les moins de 5 ans", "%", 10, 85, "TRIMESTRIELLE", [38, 51]),
                "activites": [
                    {
                        "code": "ASN1.1",
                        "libelle": "Former et équiper des relais communautaires en dépistage (bracelet MUAC)",
                        "unite": "relais formés",
                        "prevue": 150, "realisee": 96,
                        "sous_activite": "Sessions de formation et dotation en bracelets MUAC",
                        "sous_activite_unite": "sessions", "sous_prevue": 10, "sous_realisee": 7,
                        "budget_alloue": Decimal("48000000"), "budget_realise": Decimal("30000000"),
                        "indicateur": ("Nombre de relais communautaires formés et actifs en dépistage", "relais", 0, 150, "TRIMESTRIELLE", [96]),
                    },
                    {
                        "code": "ASN1.2",
                        "libelle": "Organiser des campagnes de dépistage de masse en saison de soudure",
                        "unite": "enfants dépistés",
                        "prevue": 9000, "realisee": 4200,
                        "sous_activite": "Campagnes mensuelles de dépistage de masse porte-à-porte",
                        "sous_activite_unite": "campagnes", "sous_prevue": 8, "sous_realisee": 4,
                        "budget_alloue": Decimal("55000000"), "budget_realise": Decimal("26000000"),
                        "indicateur": None,
                    },
                ],
            },
            {
                "libelle": "Promouvoir les pratiques familiales essentielles de nutrition",
                "description": "Groupes de soutien mère-à-mère et démonstrations culinaires.",
                "resultat_idx": 1,
                "indicateur": ("Taux de ménages appliquant au moins 3 pratiques familiales essentielles", "%", 12, 65, "ANNUELLE", [29]),
                "activites": [
                    {
                        "code": "ASN2.1",
                        "libelle": "Animer des groupes de soutien mère-à-mère sur l'allaitement et la diversification alimentaire",
                        "unite": "mères touchées",
                        "prevue": 3000, "realisee": 1150,
                        "sous_activite": "Séances hebdomadaires de groupes de soutien communautaires",
                        "sous_activite_unite": "groupes actifs", "sous_prevue": 60, "sous_realisee": 38,
                        "budget_alloue": Decimal("40000000"), "budget_realise": Decimal("15000000"),
                        "indicateur": ("Nombre de mères et pères touchés par les groupes de soutien", "personnes", 0, 3000, "SEMESTRIELLE", [1150]),
                    },
                    {
                        "code": "ASN2.2",
                        "libelle": "Organiser des démonstrations culinaires à base de produits locaux",
                        "unite": "démonstrations",
                        "prevue": 120, "realisee": 44,
                        "sous_activite": "Démonstrations culinaires mensuelles dans les villages d'intervention",
                        "sous_activite_unite": "sessions", "sous_prevue": 120, "sous_realisee": 44,
                        "budget_alloue": Decimal("18000000"), "budget_realise": Decimal("6000000"),
                        "indicateur": None,
                    },
                ],
            },
        ],
        "indicateur_projet": ("Nombre total d'enfants de moins de 5 ans et de mères touchés par le programme", "personnes", 0, 6000, "ANNUELLE", [2100]),
        "intervenants": [("NIKIEMA", "Aminata", "Chargée de nutrition"), ("SANOU", "Mariam", "Assistante administrative et financière"), ("DIALLO", "Aissata", "Chargée de genre et gouvernance")],
        "beneficiaires": [
            ("HIEN", "Fatimata", "F", ["femme_chef_menage"]), ("SOME", "Palenfo", "M", []),
            ("KAMBOU", "Alizeta", "F", ["pdi", "femme_chef_menage"]), ("DA", "Bakary", "M", ["handicap"]),
            ("PALM", "Rihanata", "F", ["jeune", "pdi"]),
        ],
        "grille_alerte": [(0, "Alerte rouge", "#c92a2a"), (50, "Vigilance", "#f08c00"), (75, "Conforme", "#2f9e44")],
    },
    {
        "cle": "PGLCS",
        "cadre_nom": "Cadre stratégique — Gouvernance Locale et Cohésion Sociale 2026-2028",
        "axe": ("AXE1", "Renforcement de la gouvernance locale et de la cohésion sociale"),
        "orientation": ("OR1.1", "Appui aux instances locales et à la médiation communautaire"),
        "resultats": [
            ("RA1.1.1", "Les instances locales de gouvernance sont fonctionnelles et redevables"),
            ("RA1.1.2", "Les mécanismes communautaires de prévention des conflits sont opérationnels"),
        ],
        "projet_nom": "Programme de Gouvernance Locale et de Cohésion Sociale",
        "code": "PGLCS-2026",
        "date_debut": date(2026, 4, 1),
        "date_fin": date(2028, 3, 31),
        "date_rappel": date(2026, 12, 1),
        "budget_total": Decimal("395000000"),
        "fonds_propres": Decimal("39500000"),
        "type_mise_en_oeuvre": Projet.TypeMiseEnOeuvre.CONSORTIUM,
        "chef_de_projet": "SAWADOGO Boukary",
        "cibles": dict(cible_totale=3800, cible_hommes=1900, cible_femmes=1900, cible_jeunes=1400, cible_pdi=1600),
        "bailleur_principal": "ECHO — Protection civile UE",
        "financements": [("ECHO — Protection civile UE", Decimal("250000000")), ("Agence Française de Développement", Decimal("106000000"))],
        "zones": ["Sirba", "Gnagna", "Komandjari"],
        "capitalisation": "",
        "og": "Contribuer au renforcement de la gouvernance locale et de la cohésion sociale dans les zones à forte présence de personnes déplacées de la région du Sirba",
        "og_description": "Le programme appuie les instances locales de gouvernance et les mécanismes de médiation communautaire sur deux ans.",
        "os": [
            {
                "libelle": "Renforcer le fonctionnement et la redevabilité des instances locales de gouvernance",
                "description": "Appui aux cadres de concertation villageois et aux sessions de reddition de comptes.",
                "resultat_idx": 0,
                "indicateur": ("Taux d'instances locales de gouvernance jugées fonctionnelles", "%", 25, 80, "ANNUELLE", [40]),
                "activites": [
                    {
                        "code": "AGL1.1",
                        "libelle": "Appuyer le fonctionnement des cadres de concertation villageois (CVD)",
                        "unite": "CVD appuyés",
                        "prevue": 35, "realisee": 19,
                        "sous_activite": "Dotation en équipement et accompagnement méthodologique des CVD",
                        "sous_activite_unite": "CVD", "sous_prevue": 35, "sous_realisee": 19,
                        "budget_alloue": Decimal("32000000"), "budget_realise": Decimal("14000000"),
                        "indicateur": ("Nombre de cadres de concertation villageois appuyés et actifs", "CVD", 0, 35, "SEMESTRIELLE", [19]),
                    },
                    {
                        "code": "AGL1.2",
                        "libelle": "Organiser des sessions de dialogue communautaire et de reddition de comptes",
                        "unite": "sessions",
                        "prevue": 24, "realisee": 15,
                        "sous_activite": "Sessions trimestrielles de reddition de comptes avec la population",
                        "sous_activite_unite": "sessions", "sous_prevue": 24, "sous_realisee": 15,
                        "budget_alloue": Decimal("20000000"), "budget_realise": Decimal("12000000"),
                        "indicateur": None,
                    },
                ],
            },
            {
                "libelle": "Prévenir et gérer les conflits liés à la cohabitation et aux ressources naturelles",
                "description": "Formation de comités de médiation et facilitation du dialogue intercommunautaire.",
                "resultat_idx": 1,
                "indicateur": ("Nombre de conflits communautaires résolus par médiation locale", "conflits", 0, 40, "TRIMESTRIELLE", [6, 11]),
                "activites": [
                    {
                        "code": "AGL2.1",
                        "libelle": "Former des comités locaux de médiation et de prévention des conflits",
                        "unite": "comités formés",
                        "prevue": 18, "realisee": 8,
                        "sous_activite": "Formation initiale des membres des comités de médiation",
                        "sous_activite_unite": "sessions", "sous_prevue": 6, "sous_realisee": 3,
                        "budget_alloue": Decimal("22000000"), "budget_realise": Decimal("9000000"),
                        "indicateur": ("Nombre de comités locaux de médiation opérationnels", "comités", 0, 18, "SEMESTRIELLE", [8]),
                    },
                    {
                        "code": "AGL2.2",
                        "libelle": "Faciliter le dialogue intercommunautaire entre populations hôtes et déplacées",
                        "unite": "rencontres",
                        "prevue": 30, "realisee": 12,
                        "sous_activite": "Rencontres intercommunautaires de dialogue et de cohésion sociale",
                        "sous_activite_unite": "rencontres", "sous_prevue": 30, "sous_realisee": 12,
                        "budget_alloue": Decimal("26000000"), "budget_realise": Decimal("8000000"),
                        "indicateur": None,
                    },
                ],
            },
        ],
        "indicateur_projet": ("Nombre total de personnes touchées par les activités de cohésion sociale", "personnes", 0, 3800, "ANNUELLE", [1050]),
        "intervenants": [("DIALLO", "Aissata", "Chargée de genre et gouvernance"), ("COMPAORE", "Issouf", "Animateur communautaire"), ("KABORE", "Fatimata", "Animatrice terrain")],
        "beneficiaires": [
            ("OUEDRAOGO", "Salif", "M", ["pdi"]), ("TAPSOBA", "Assita", "F", ["pdi", "femme_chef_menage"]),
            ("ILBOUDO", "Rasmane", "M", []), ("KABRE", "Nathalie", "F", ["jeune"]), ("BONKOUNGOU", "Abdoulaye", "M", ["pdi", "jeune"]),
        ],
        "grille_alerte": None,
    },
]

# Communes (chef-lieux) des 10 provinces couvertes par les 5 projets, avec un
# village d'intervention sous la première commune de chaque province — le
# script officiel de référentiel (seed_zones_bfa) s'arrête à la province par
# design ("communes et villages restent à ajouter librement au fil de la
# saisie") ; on les complète ici pour que la couverture géographique des 5
# projets de démonstration remonte aussi ces deux niveaux.
COMMUNES_PAR_PROVINCE = {
    "Boulgou": ["Tenkodogo", "Bittou"],
    "Kourittenga": ["Koupéla", "Andemtenga"],
    "Oudalan": ["Gorom-Gorom", "Markoye"],
    "Seno": ["Dori", "Gorgadji"],
    "Boulkiemde": ["Koudougou", "Ramongo"],
    "Sissili": ["Léo", "Bieha"],
    "Ioba": ["Dano", "Zambo"],
    "Poni": ["Gaoua", "Loropeni"],
    "Gnagna": ["Bogandé", "Piéla"],
    "Komandjari": ["Gayéri", "Foutouri"],
}


class Command(BaseCommand):
    help = "Vide les données métier et les remplace par 5 cadres stratégiques et 5 projets complets."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.vider()
            self.peupler()
        self.stdout.write(self.style.SUCCESS("5 cadres stratégiques et 5 projets complets créés avec succès."))

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

        # Zones orphelines créées lors de vérifications manuelles précédentes
        # (jamais rattachées à un projet réel) — pas du vrai référentiel.
        Zone.objects.filter(nom__in=["Djibo", "Koubri", "Ouagadougou", "VillageTest79125"]).delete()

        self.stdout.write("  … terminé.")

    # ------------------------------------------------------------------
    # Peuplement
    # ------------------------------------------------------------------
    def peupler(self):
        users = self.recuperer_utilisateurs()
        statuts = self.creer_statuts_particuliers()
        expertise_id = Partenaire.objects.create(
            nom="Expertise ID",
            type=Partenaire.TypePartenaire.MISE_EN_OEUVRE,
            contact="Direction des programmes",
            email="contact@expertise-id.org",
            telephone="+226 25 30 00 00",
        )
        reseau_ong = Partenaire.objects.create(
            nom="Réseau des ONG locales du Sahel",
            type=Partenaire.TypePartenaire.MISE_EN_OEUVRE,
            contact="Coordination du réseau",
            email="coordination@reseau-ong-sahel.org",
            telephone="+226 25 40 12 34",
        )
        partenaires_bailleur, bailleurs = self.creer_bailleurs()
        self.creer_communes_et_villages()

        for profil in PROFILS:
            self.stdout.write(f"Création du cadre et du projet {profil['cle']} ({profil['projet_nom']})…")
            self.creer_cadre_et_projet(profil, users, statuts, expertise_id, reseau_ong, partenaires_bailleur, bailleurs)

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

    def creer_bailleurs(self):
        noms_types = [
            ("Union Européenne", Bailleur.TypeBailleur.INSTITUTIONNEL, "Délégation UE Ouagadougou"),
            ("Agence Française de Développement", Bailleur.TypeBailleur.COOPERATION_BILATERALE, "Agence AFD Ouagadougou"),
            ("Fondation de France", Bailleur.TypeBailleur.FONDATION, "Pôle International"),
            ("UNICEF", Bailleur.TypeBailleur.INSTITUTIONNEL, "Bureau UNICEF Burkina Faso"),
            ("ECHO — Protection civile UE", Bailleur.TypeBailleur.INSTITUTIONNEL, "Bureau régional ECHO Ouagadougou"),
        ]
        partenaires_bailleur = {}
        bailleurs = {}
        for nom, type_bailleur, contact in noms_types:
            partenaires_bailleur[nom] = Partenaire.objects.create(
                nom=nom, type=Partenaire.TypePartenaire.BAILLEUR, contact=contact,
                email=f"{nom.split()[0].lower().strip('—')}@partenaires.org", telephone="+226 25 49 00 00",
            )
            bailleurs[nom] = Bailleur.objects.create(nom=nom, type=type_bailleur, contact=contact)
        return partenaires_bailleur, bailleurs

    def creer_communes_et_villages(self):
        niveau_commune = NiveauAdministratif.objects.get(pays="BF", nom_niveau="Commune")
        niveau_village, _ = NiveauAdministratif.objects.get_or_create(
            pays="BF", nom_niveau="Village", defaults={"ordre": 4, "niveau_parent": niveau_commune}
        )
        for nom_province, communes in COMMUNES_PAR_PROVINCE.items():
            province = Zone.objects.filter(nom=nom_province, niveau_administratif__nom_niveau="Province").first()
            if not province:
                continue
            premiere_commune = None
            for i, nom_commune in enumerate(communes):
                commune, _ = Zone.objects.get_or_create(
                    nom=nom_commune, niveau_administratif=niveau_commune, defaults={"parent": province}
                )
                if i == 0:
                    premiere_commune = commune
            if premiere_commune:
                Zone.objects.get_or_create(
                    nom=f"Village pilote de {premiere_commune.nom}",
                    niveau_administratif=niveau_village,
                    defaults={"parent": premiere_commune},
                )

    def creer_cadre_et_projet(self, profil, users, statuts, expertise_id, reseau_ong, partenaires_bailleur, bailleurs):
        cadre = CadreStrategique.objects.create(
            nom=profil["cadre_nom"],
            description=f"Cadre stratégique structurant le {profil['projet_nom']} et ses futurs projets connexes.",
        )
        niveau_axe = TypeNiveau.objects.create(cadre_strategique=cadre, nom_niveau="Axe stratégique", ordre=1, aide_code="Ex : AXE1")
        niveau_orientation = TypeNiveau.objects.create(
            cadre_strategique=cadre, nom_niveau="Orientation stratégique", ordre=2, niveau_parent=niveau_axe, aide_code="Ex : OR1.1"
        )
        niveau_resultat = TypeNiveau.objects.create(
            cadre_strategique=cadre, nom_niveau="Résultat attendu", ordre=3, niveau_parent=niveau_orientation, aide_code="Ex : RA1.1.1"
        )

        axe = ElementStrategique.objects.create(type_niveau=niveau_axe, code=profil["axe"][0], nom=profil["axe"][1])
        orientation = ElementStrategique.objects.create(
            type_niveau=niveau_orientation, element_parent=axe, code=profil["orientation"][0], nom=profil["orientation"][1]
        )
        resultats = [
            ElementStrategique.objects.create(type_niveau=niveau_resultat, element_parent=orientation, code=code, nom=nom)
            for code, nom in profil["resultats"]
        ]

        equipe = Equipe.objects.create(
            nom=f"Équipe terrain {profil['cle']}",
            date_debut_contrat=profil["date_debut"],
            date_fin_contrat=profil["date_fin"],
        )
        intervenants = [
            Intervenant.objects.create(nom=nom, prenom=prenom, fonction=fonction, contact="+226 7" + str(abs(hash((nom, prenom, profil["cle"]))) % 10000000).zfill(7))
            for nom, prenom, fonction in profil["intervenants"]
        ]
        equipe.membres.set(intervenants)

        projet = Projet.objects.create(
            nom=profil["projet_nom"],
            code=profil["code"],
            pays=["BF"],
            partenaire_bailleur=partenaires_bailleur[profil["bailleur_principal"]],
            partenaire_mise_en_oeuvre=expertise_id,
            cadre_strategique=cadre,
            budget_total=profil["budget_total"],
            fonds_propres=profil["fonds_propres"],
            date_debut=profil["date_debut"],
            date_fin=profil["date_fin"],
            date_rappel=profil["date_rappel"],
            statut=Projet.Statut.EN_COURS,
            type_mise_en_oeuvre=profil["type_mise_en_oeuvre"],
            chef_de_projet_nom=profil["chef_de_projet"],
            elements_capitalisation=profil["capitalisation"],
            **profil["cibles"],
        )
        nommer_niveaux(projet, ["Objectif général", "Objectif spécifique", "Activité"])
        if profil["type_mise_en_oeuvre"] == Projet.TypeMiseEnOeuvre.CONSORTIUM:
            projet.partenaires_consortium.set([expertise_id, reseau_ong])
        noms_provinces = [z for z in profil["zones"] if z in COMMUNES_PAR_PROVINCE]
        noms_communes = [nom for province in noms_provinces for nom in COMMUNES_PAR_PROVINCE[province]]
        zones_a_assigner = Zone.objects.filter(nom__in=profil["zones"] + noms_communes) | Zone.objects.filter(
            niveau_administratif__nom_niveau="Village", parent__nom__in=noms_communes
        )
        projet.zones.set(zones_a_assigner.distinct())
        projet.utilisateurs_affectes.set(
            [u for u in (users["chef_projet"], users["charge_se"], users["animateur"], users["coordo"]) if u]
        )

        for nom_bailleur, montant in profil["financements"]:
            Financement.objects.create(projet=projet, bailleur=bailleurs[nom_bailleur], montant_finance=montant)

        if profil["grille_alerte"]:
            for borne_min, libelle, couleur in profil["grille_alerte"]:
                PalierAlerte.objects.create(projet=projet, borne_min=borne_min, libelle=libelle, couleur=couleur)

        og = Activite.objects.create(projet=projet, libelle=profil["og"], description=profil["og_description"])

        self.creer_indicateur_avec_valeurs(
            *profil["indicateur_projet"], rattachement={"projet": projet}, elements=[axe], saisi_par=users["charge_se"],
        )

        for os_data in profil["os"]:
            os_obj = Activite.objects.create(
                projet=og.projet, activite_parent=og, libelle=os_data["libelle"], description=os_data["description"]
            )
            resultat = resultats[os_data["resultat_idx"]]
            if os_data["indicateur"]:
                self.creer_indicateur_avec_valeurs(
                    *os_data["indicateur"], rattachement={"activite": os_obj}, elements=[resultat], saisi_par=users["charge_se"],
                )

            for i, act_data in enumerate(os_data["activites"]):
                statut_activite = (
                    Activite.Statut.NON_REALISEE if act_data["realisee"] == 0
                    else Activite.Statut.REALISEE if act_data["realisee"] >= act_data["prevue"]
                    else Activite.Statut.EN_COURS
                )
                activite = Activite.objects.create(
                    projet=os_obj.projet, activite_parent=os_obj,
                    code_activite=act_data["code"],
                    libelle=act_data["libelle"],
                    statut=statut_activite,
                    axe_strategique=resultat,
                    budget_alloue=act_data["budget_alloue"],
                    budget_realise=act_data["budget_realise"],
                    valeur_reference=Decimal("0"),
                    quantite_prevue=Decimal(str(act_data["prevue"])),
                    quantite_realisee=Decimal(str(act_data["realisee"])),
                    unite_quantite=act_data["unite"],
                    date_debut=profil["date_debut"],
                    date_fin=profil["date_fin"],
                    date_debut_reelle=profil["date_debut"],
                    nb_jours_planifies=(profil["date_fin"] - profil["date_debut"]).days,
                    equipe_responsable=equipe,
                )
                activite.responsables.set([intervenants[i % len(intervenants)]])
                SousActivite.objects.create(
                    activite=activite,
                    libelle=act_data["sous_activite"],
                    axe_strategique=resultat,
                    quantite_prevue=Decimal(str(act_data["sous_prevue"])),
                    quantite_realisee=Decimal(str(act_data["sous_realisee"])),
                    unite_quantite=act_data["sous_activite_unite"],
                    date_debut=profil["date_debut"],
                    date_fin=profil["date_fin"],
                    statut=SousActivite.Statut.TERMINEE if act_data["sous_realisee"] >= act_data["sous_prevue"] else SousActivite.Statut.EN_COURS,
                )
                if act_data["indicateur"]:
                    self.creer_indicateur_avec_valeurs(
                        *act_data["indicateur"], rattachement={"activite": activite}, elements=[resultat], saisi_par=users["charge_se"],
                    )

        # Bénéficiaires
        zones_projet = list(projet.zones.all())
        for i, (nom, prenom, sexe, codes_statuts) in enumerate(profil["beneficiaires"]):
            beneficiaire = Beneficiaire.objects.create(
                nom=nom,
                prenom=prenom,
                sexe=sexe,
                telephone="+226 7" + str(abs(hash((nom, prenom, profil["cle"]))) % 10000000).zfill(7),
                numero_piece_identite="B" + str(abs(hash((nom, prenom, profil["cle"]))) % 100000000),
                type_piece="CNIB",
                pays="BF",
                zone=zones_projet[i % len(zones_projet)] if zones_projet else None,
            )
            if codes_statuts:
                beneficiaire.statuts_particuliers.set([statuts[c] for c in codes_statuts])
            ParticipationProjet.objects.create(
                beneficiaire=beneficiaire,
                projet=projet,
                date_inscription=profil["date_debut"],
                role_dans_projet="Bénéficiaire direct",
            )

    # ------------------------------------------------------------------
    # Helper indicateurs
    # ------------------------------------------------------------------
    def creer_indicateur_avec_valeurs(
        self, libelle, unite, valeur_reference, valeur_cible, frequence, valeurs_annuelles, *, rattachement, elements, saisi_par
    ):
        indicateur = Indicateur.objects.create(
            libelle=libelle,
            unite=unite,
            valeur_reference=Decimal(str(valeur_reference)),
            valeur_reference_date=date(2025, 12, 1),
            valeur_cible=Decimal(str(valeur_cible)),
            frequence_collecte=frequence,
            **rattachement,
        )
        if elements:
            indicateur.elements_strategiques.set(elements)
        annee_depart = 2026
        for i, valeur in enumerate(valeurs_annuelles):
            annee = annee_depart + i
            ValeurIndicateur.objects.create(
                indicateur=indicateur,
                periode_debut=date(annee, 1, 1),
                periode_fin=date(annee, 6, 30) if i == len(valeurs_annuelles) - 1 else date(annee, 12, 31),
                valeur_realisee=Decimal(str(valeur)),
                saisi_par=saisi_par,
                commentaire=f"Valeur relevée lors du suivi {annee}.",
            )
        return indicateur
