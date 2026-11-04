"""
Contenu du cours en ligne d'Expertise-ID Monitora : modules, leçons, quiz.

Chaque leçon est une suite de blocs affichés dans l'ordre :
- {"type": "texte", "texte": …}          paragraphe ;
- {"type": "etapes", "items": [...]}     étapes numérotées ;
- {"type": "image", "src": …, "legende"} capture d'écran (frontend/public/formation/) ;
- {"type": "video", "chapitre": …}       extrait de la vidéo de présentation (voir CHAPITRES) ;
- {"type": "astuce" | "attention", "texte": …} encadrés ;
- {"type": "exercice", "items": [...]}   à faire dans son propre espace.
Les **mots en gras** s'écrivent entre doubles astérisques.

Quiz : 5 questions par module ; « bonne » est l'indice de la bonne réponse (jamais envoyé au
navigateur avant la réponse). Réussite : SEUIL_REUSSITE bonnes réponses sur 5.
"""

SEUIL_REUSSITE = 4

# Extraits de la vidéo de présentation (secondes de début et de fin).
# Début : 2 secondes après le changement de page (la page et sa légende sont affichées).
CHAPITRES = {
    "tableau_de_bord": (6, 15), "strategie": (17, 21), "projets": (23, 27), "planification": (29, 33),
    "cadre_logique": (35, 39), "indicateurs": (41, 46), "carte": (48, 62), "plaintes": (64, 70),
}

MODULES = [
    {
        "code": "prise-en-main", "titre": "Prendre en main la plateforme", "icone": "Compass",
        "description": "Se connecter, se repérer dans l'écran, lire le tableau de bord et choisir sa langue.",
        "lecons": [
            {
                "code": "connexion", "titre": "Se connecter en toute sécurité", "duree": 5,
                "objectif": "Savoir se connecter avec son adresse courriel, son mot de passe et le code reçu par courriel.",
                "blocs": [
                    {"type": "texte", "texte": "Tout le monde se connecte à **la même adresse** : c'est votre compte qui ouvre l'espace de votre organisation. Vous n'avez pas d'adresse à retenir pour votre organisation."},
                    {"type": "etapes", "items": [
                        "Ouvrez la page de connexion de la plateforme.",
                        "Saisissez votre **adresse courriel** et votre **mot de passe**, puis « Se connecter ».",
                        "Un **code à 6 chiffres** vous est envoyé par courriel : saisissez-le. Il est valable 10 minutes, pour une seule connexion.",
                    ]},
                    {"type": "image", "src": "connexion.webp", "legende": "La page de connexion : adresse courriel et mot de passe."},
                    {"type": "attention", "texte": "Chaque compte doit avoir une adresse courriel valide, sinon le code ne peut pas être envoyé. Pas de courriel ? Regardez dans les indésirables, ou cliquez sur « Renvoyer le code » (une minute d'attente entre deux envois)."},
                    {"type": "astuce", "texte": "Ne communiquez jamais votre code : personne d'Expertise-ID ne vous le demandera."},
                ],
            },
            {
                "code": "ecran", "titre": "Se repérer dans l'écran", "duree": 5,
                "objectif": "Connaître le menu, l'en-tête et les gestes communs à toutes les pages.",
                "blocs": [
                    {"type": "texte", "texte": "**Le menu** liste les modules : tableau de bord, stratégies et programmes, projets, indicateurs, suivi, bénéficiaires, carte, documents, plaintes… La **Corbeille** est en bas des modules ; les pages d'administration suivent pour l'administrateur."},
                    {"type": "texte", "texte": "**En haut** : le logo de votre organisation, la langue, les notifications (la cloche) et votre compte."},
                    {"type": "etapes", "items": [
                        "« ← Retour », en haut de chaque page, ramène à la page précédente.",
                        "Le bouton **Éditer** des listes fait apparaître les actions de modification et de suppression.",
                        "La **langue** se change en haut de l'écran : français, anglais, arabe, espagnol ou allemand. Votre choix est gardé dans votre compte.",
                    ]},
                    {"type": "exercice", "items": [
                        "Changez la langue de l'interface, puis revenez au français.",
                        "Ouvrez les notifications (la cloche) et lisez la plus récente.",
                    ]},
                ],
            },
            {
                "code": "tableau-de-bord", "titre": "Lire le tableau de bord", "duree": 8,
                "objectif": "Lire les chiffres clés, les filtrer, personnaliser et partager le tableau de bord.",
                "blocs": [
                    {"type": "texte", "texte": "Le tableau de bord est la première page après la connexion. **Tous les chiffres suivent les filtres du haut** : la période (toutes, une année, une plage de dates) et le statut des projets."},
                    {"type": "image", "src": "tableau-de-bord.webp", "legende": "Les chiffres clés : projets, budget, bénéficiaires, indicateurs suivis, couverture géographique."},
                    {"type": "video", "chapitre": "tableau_de_bord"},
                    {"type": "etapes", "items": [
                        "**Personnaliser** : choisissez les blocs affichés et leur ordre.",
                        "**Partager** : créez un lien en lecture seule, par exemple pour un bailleur, sans lui créer de compte.",
                    ]},
                    {"type": "exercice", "items": [
                        "Filtrez le tableau de bord sur l'année en cours, puis réinitialisez les filtres.",
                        "Ouvrez « Personnaliser » et masquez un bloc dont vous ne vous servez pas.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Avec quoi se connecte-t-on à la plateforme ?", "choix": [
                "L'adresse de l'espace de son organisation et un identifiant", "Son adresse courriel, son mot de passe puis un code reçu par courriel",
                "Seulement un mot de passe"], "bonne": 1,
             "explication": "Adresse courriel et mot de passe, puis le code à 6 chiffres envoyé à chaque connexion."},
            {"question": "Combien de temps le code de connexion est-il valable ?", "choix": ["1 minute", "10 minutes", "24 heures"], "bonne": 1,
             "explication": "Le code est valable 10 minutes, pour une seule connexion."},
            {"question": "Que faire si le code n'arrive pas ?", "choix": [
                "Regarder dans les indésirables, puis « Renvoyer le code »", "Créer un nouveau compte", "Attendre le lendemain"], "bonne": 0,
             "explication": "Vérifiez les indésirables, puis demandez un nouveau code."},
            {"question": "Les chiffres du tableau de bord…", "choix": [
                "sont fixes", "suivent les filtres de période et de statut des projets", "ne concernent que le projet ouvert"], "bonne": 1,
             "explication": "Tous les chiffres suivent les filtres du haut."},
            {"question": "Comment montrer le tableau de bord à un bailleur qui n'a pas de compte ?", "choix": [
                "Lui donner son mot de passe", "Lui créer un compte administrateur", "Créer un lien de partage en lecture seule"], "bonne": 2,
             "explication": "« Partager » crée un lien en lecture seule, sans compte."},
        ],
    },
    {
        "code": "strategie", "titre": "Stratégies, programmes et projets", "icone": "Target",
        "description": "Organiser la chaîne Stratégie → Programme → Projet et y rattacher les projets.",
        "lecons": [
            {
                "code": "chaine", "titre": "La chaîne des documents stratégiques", "duree": 7,
                "objectif": "Comprendre comment stratégies, programmes et projets s'enchaînent.",
                "blocs": [
                    {"type": "texte", "texte": "Le plan stratégique de votre organisation et les politiques nationales auxquelles vos projets contribuent sont organisés en chaîne : **Stratégie → Programme → Projet**. Chaque maillon a sa rubrique dans le menu."},
                    {"type": "texte", "texte": "Chaque document a ses axes, objectifs et résultats, à autant de niveaux que nécessaire. Un programme se rattache à un élément d'une stratégie ; un projet à un élément d'un programme ou d'une stratégie."},
                    {"type": "image", "src": "cadre-strategique.webp", "legende": "Les stratégies et les programmes qui s'y rattachent."},
                    {"type": "video", "chapitre": "strategie"},
                    {"type": "astuce", "texte": "Sauter un maillon est permis (un projet rattaché directement à une stratégie) : un avertissement le signale simplement."},
                ],
            },
            {
                "code": "fiche-programme", "titre": "Créer une stratégie et un programme", "duree": 8,
                "objectif": "Créer un document, sa structure et sa fiche (budget, bailleurs, dates).",
                "blocs": [
                    {"type": "etapes", "items": [
                        "Ouvrez la rubrique **Stratégies**, puis « Nouveau document ».",
                        "Donnez-lui un nom et, s'il s'agit d'un programme, le document au-dessus auquel il se rattache.",
                        "Construisez sa **structure** : nommez les niveaux (axe, objectif, résultat…) puis ajoutez les éléments.",
                        "Remplissez sa **fiche**, comme celle d'un projet : code, statut, dates, budget et bailleurs, zones, cibles.",
                    ]},
                    {"type": "image", "src": "cadre-strategique-detail.webp", "legende": "Un programme : sa fiche, son financement, ses cibles et les projets rattachés."},
                    {"type": "astuce", "texte": "« Chaîne des documents » (administrateur) permet de renommer ou d'ajouter des maillons. Un modèle Excel permet aussi d'importer une structure entière."},
                    {"type": "exercice", "items": [
                        "Ouvrez une stratégie existante et parcourez sa structure.",
                        "Repérez, dans un programme, les projets qui lui sont rattachés.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Dans quel ordre s'enchaînent les documents ?", "choix": [
                "Projet → Programme → Stratégie", "Stratégie → Programme → Projet", "Programme → Stratégie → Projet"], "bonne": 1,
             "explication": "La chaîne va de la stratégie au projet."},
            {"question": "À quoi se rattache un projet ?", "choix": [
                "À un élément d'un programme ou d'une stratégie", "À un utilisateur", "À rien : il est toujours isolé"], "bonne": 0,
             "explication": "Ses résultats remontent alors jusqu'aux objectifs stratégiques."},
            {"question": "Combien de niveaux peut avoir la structure d'une stratégie ?", "choix": [
                "Exactement 3", "Autant que nécessaire", "Un seul"], "bonne": 1,
             "explication": "Les niveaux sont libres : nommez-les et empilez-les comme dans votre document."},
            {"question": "Rattacher un projet directement à une stratégie, sans programme…", "choix": [
                "est interdit", "efface le projet", "est permis, avec un simple avertissement"], "bonne": 2,
             "explication": "Sauter un maillon est permis ; un avertissement le signale."},
            {"question": "Que contient la fiche d'un programme ?", "choix": [
                "Seulement son nom", "Code, statut, dates, budget et bailleurs, zones, cibles", "La liste des utilisateurs"], "bonne": 1,
             "explication": "Elle se remplit comme la fiche d'un projet."},
        ],
    },
    {
        "code": "planification", "titre": "Planifier un projet", "icone": "ListTree",
        "description": "Créer un projet, construire sa planification à niveaux libres et son cadre logique.",
        "lecons": [
            {
                "code": "creer-projet", "titre": "Créer un projet", "duree": 6,
                "objectif": "Créer un projet complet et le retrouver dans la liste.",
                "blocs": [
                    {"type": "texte", "texte": "La liste des projets affiche en haut des **compteurs par statut** (en cours, en préparation, clôturés) qui servent aussi de filtres. Chaque ligne montre la période, la part de temps écoulée, le budget et le chef de projet."},
                    {"type": "image", "src": "projets.webp", "legende": "La liste des projets, avec recherche par nom ou code."},
                    {"type": "etapes", "items": [
                        "Cliquez sur **Nouveau projet**.",
                        "Renseignez le nom, le code, les dates, le pays et les zones, le bailleur, les partenaires, le rattachement stratégique et le budget.",
                        "Enregistrez : le projet s'ouvre sur son onglet **Planification**.",
                    ]},
                    {"type": "video", "chapitre": "projets"},
                ],
            },
            {
                "code": "niveaux", "titre": "Construire la planification", "duree": 10,
                "objectif": "Nommer les niveaux du projet et programmer les activités par période.",
                "blocs": [
                    {"type": "texte", "texte": "**Aucun niveau n'est imposé** : nommez-les comme dans votre document de projet (effets, extrants, activités, sous-activités…)."},
                    {"type": "etapes", "items": [
                        "**Configuration des niveaux** : nommez et ordonnez les niveaux du projet.",
                        "Ajoutez les éléments, du plus haut au plus bas. Chaque ligne a son lieu de mise en œuvre, sa priorité, son service responsable, ses trimestres programmés et son budget.",
                        "**Planification par période** : programmez les quantités et les budgets année par année, trimestre par trimestre.",
                    ]},
                    {"type": "image", "src": "projet-planification.webp", "legende": "La planification d'un projet : vue en arbre ou en tableau."},
                    {"type": "video", "chapitre": "planification"},
                    {"type": "astuce", "texte": "Vous avez déjà votre planification dans Excel ? Le menu **Planification complète** fournit un modèle à remplir et à importer en une fois."},
                ],
            },
            {
                "code": "cadre-logique", "titre": "Le cadre logique et les risques", "duree": 6,
                "objectif": "Lire le cadre logique construit automatiquement et suivre les risques.",
                "blocs": [
                    {"type": "texte", "texte": "L'onglet **Cadre logique** se construit tout seul à partir de la planification et des indicateurs : logique d'intervention, indicateurs (référence, cible, réalisé), sources de vérification et hypothèses. Il se met à jour à chaque valeur saisie et s'exporte."},
                    {"type": "image", "src": "projet-cadre-logique.webp", "legende": "Le cadre logique d'un projet."},
                    {"type": "video", "chapitre": "cadre_logique"},
                    {"type": "texte", "texte": "Le sous-onglet **Risques** liste les risques du projet, leur probabilité, leur impact et les mesures prévues."},
                    {"type": "exercice", "items": [
                        "Ouvrez un de vos projets, puis son onglet Cadre logique.",
                        "Ajoutez un risque avec sa probabilité, son impact et une mesure prévue.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Les niveaux de la planification d'un projet…", "choix": [
                "sont imposés par la plateforme", "sont libres : on les nomme comme dans son document de projet", "sont toujours au nombre de deux"], "bonne": 1,
             "explication": "Aucun niveau n'est imposé."},
            {"question": "Où programme-t-on les quantités et budgets par trimestre ?", "choix": [
                "Dans « Planification par période »", "Dans la Corbeille", "Dans le journal d'audit"], "bonne": 0,
             "explication": "La planification par période programme année par année, trimestre par trimestre."},
            {"question": "Comment le cadre logique est-il construit ?", "choix": [
                "À la main, case par case", "Tout seul, à partir de la planification et des indicateurs", "Par Expertise-ID"], "bonne": 1,
             "explication": "Il se construit et se met à jour automatiquement."},
            {"question": "À quoi servent les compteurs en haut de la liste des projets ?", "choix": [
                "À compter les utilisateurs", "À filtrer par statut (en cours, en préparation, clôturés)", "À rien"], "bonne": 1,
             "explication": "Ils donnent le nombre de projets par statut et servent de filtres."},
            {"question": "Où trouve-t-on les risques d'un projet ?", "choix": [
                "Dans le sous-onglet Risques du cadre logique", "Dans le tableau de bord seulement", "Dans les paramètres d'alerte"], "bonne": 0,
             "explication": "Le sous-onglet Risques liste probabilité, impact et mesures."},
        ],
    },
    {
        "code": "indicateurs-suivi", "titre": "Indicateurs et suivi", "icone": "Gauge",
        "description": "Suivre les indicateurs, saisir le réalisé, faire approuver et réagir aux alertes.",
        "lecons": [
            {
                "code": "indicateurs", "titre": "Suivre les indicateurs", "duree": 8,
                "objectif": "Lire l'état des indicateurs et renseigner leurs valeurs avec des pièces justificatives.",
                "blocs": [
                    {"type": "texte", "texte": "Le menu **Indicateurs** regroupe tous les indicateurs par projet. Les compteurs du haut donnent le nombre d'indicateurs **conformes**, **à risque** et **critiques**, et servent de filtres."},
                    {"type": "image", "src": "indicateurs.webp", "legende": "Pour chaque indicateur : unité, valeur de base, cible et barre de réalisation."},
                    {"type": "video", "chapitre": "indicateurs"},
                    {"type": "texte", "texte": "La fiche d'un indicateur donne ses **cibles par période** et l'historique des valeurs saisies, avec leurs pièces justificatives."},
                    {"type": "astuce", "texte": "Les seuils (à partir de quel taux un indicateur est « à risque » ou « critique ») se règlent dans **Paramètres d'alerte**."},
                ],
            },
            {
                "code": "suivi", "titre": "Saisir le réalisé et faire approuver", "duree": 8,
                "objectif": "Saisir les réalisations d'un projet et comprendre le circuit d'approbation.",
                "blocs": [
                    {"type": "etapes", "items": [
                        "Ouvrez le menu **Suivi** et choisissez un projet.",
                        "Saisissez le **réalisé** (quantités, dépenses) activité par activité.",
                        "Si le projet le prévoit, vos saisies attendent d'être **approuvées** (menu Approbations) avant de compter.",
                    ]},
                    {"type": "image", "src": "suivi-projet.webp", "legende": "Exécution physique et financière, activité par activité."},
                    {"type": "texte", "texte": "**Périodes de saisie** : l'administrateur ouvre ou ferme la saisie par période de rapportage. Les **retards** et les échéances proches déclenchent des notifications."},
                    {"type": "exercice", "items": [
                        "Ouvrez le suivi d'un de vos projets et repérez une activité en retard.",
                        "Ouvrez la fiche d'un indicateur et regardez l'historique de ses valeurs.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Quels sont les trois états d'un indicateur ?", "choix": [
                "Conforme, à risque, critique", "Ouvert, fermé, archivé", "Rouge, vert, bleu"], "bonne": 0,
             "explication": "Conforme, à risque, critique, selon les seuils réglés."},
            {"question": "Où règle-t-on les seuils d'alerte des indicateurs ?", "choix": [
                "Dans Paramètres d'alerte", "Dans la fiche du bailleur", "On ne peut pas les régler"], "bonne": 0,
             "explication": "Les seuils se règlent dans Paramètres d'alerte."},
            {"question": "Où saisit-on les quantités et dépenses réalisées ?", "choix": [
                "Dans le menu Suivi", "Dans la Corbeille", "Dans la page de connexion"], "bonne": 0,
             "explication": "Le menu Suivi sert à saisir le réalisé."},
            {"question": "Si le projet exige une approbation, une saisie…", "choix": [
                "compte immédiatement", "attend d'être approuvée avant de compter", "est supprimée"], "bonne": 1,
             "explication": "Elle attend dans le menu Approbations."},
            {"question": "Qui ouvre ou ferme les périodes de saisie ?", "choix": [
                "N'importe quel visiteur", "L'administrateur", "Le bailleur"], "bonne": 1,
             "explication": "L'administrateur ouvre ou ferme la saisie par période."},
        ],
    },
    {
        "code": "beneficiaires-carte", "titre": "Bénéficiaires et carte", "icone": "MapPinned",
        "description": "Tenir le registre des bénéficiaires et lire la carte.",
        "lecons": [
            {
                "code": "beneficiaires", "titre": "Le registre des bénéficiaires", "duree": 8,
                "objectif": "Enregistrer, importer et retrouver les bénéficiaires, éviter les doublons.",
                "blocs": [
                    {"type": "texte", "texte": "Le menu **Bénéficiaires** tient le registre, projet par projet. Chaque personne a un **identifiant unique** ; un clic ouvre sa fiche, avec son QR code et ses participations."},
                    {"type": "image", "src": "beneficiaires.webp", "legende": "Le registre : sexe et âge, téléphone, zone, statuts particuliers, autres projets."},
                    {"type": "etapes", "items": [
                        "**Variables à collecter** : l'administrateur choisit les informations demandées.",
                        "**Importer depuis Excel** pour reprendre une liste existante ; **Exporter** pour vos rapports.",
                        "Imprimez les **cartes de bénéficiaire**.",
                        "Le menu **Doublons d'enregistrement** signale les personnes enregistrées deux fois.",
                    ]},
                ],
            },
            {
                "code": "carte", "titre": "Lire et télécharger la carte", "duree": 8,
                "objectif": "Filtrer la carte, choisir couches et fond, et la télécharger pour un rapport.",
                "blocs": [
                    {"type": "texte", "texte": "Le menu **Carte** place bénéficiaires et projets sur les zones administratives. Les compteurs au-dessus de la carte suivent les filtres."},
                    {"type": "video", "chapitre": "carte"},
                    {"type": "etapes", "items": [
                        "**Filtrer** : période, statut des projets, un projet ou une zone précise.",
                        "**Couches** : bénéficiaires, régions, provinces, routes, villes et villages, noms… « Importer une couche » ajoute vos propres données (Shapefile en .zip, GeoPackage, GeoJSON ou KML).",
                        "**Par zone** : colorez les zones selon un ou plusieurs indicateurs (projets, bénéficiaires, budget, dépenses, taux d'exécution…).",
                        "**Fond** : neutre, OpenStreetMap, satellite ou aucun.",
                        "**Télécharger la carte** : en PDF ou en image PNG, avec titre, format de papier et orientation.",
                    ]},
                    {"type": "image", "src": "carte-zones.webp", "legende": "La carte de près : bénéficiaires, limites administratives, routes et localités."},
                    {"type": "exercice", "items": [
                        "Affichez la carte d'un seul de vos projets, sur fond satellite.",
                        "Téléchargez-la en PDF avec un titre.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Que signale le menu « Doublons d'enregistrement » ?", "choix": [
                "Les projets en double", "Les personnes enregistrées deux fois", "Les documents en double"], "bonne": 1,
             "explication": "Il repère les bénéficiaires enregistrés deux fois."},
            {"question": "Qui choisit les informations demandées pour chaque bénéficiaire ?", "choix": [
                "L'administrateur, dans « Variables à collecter »", "Le bénéficiaire lui-même", "Personne : elles sont fixes"], "bonne": 0,
             "explication": "L'administrateur règle les variables à collecter."},
            {"question": "Quels fichiers peut-on importer comme couche sur la carte ?", "choix": [
                "Word et PowerPoint", "Shapefile en .zip, GeoPackage, GeoJSON ou KML", "Seulement des images"], "bonne": 1,
             "explication": "Les formats cartographiques courants sont acceptés."},
            {"question": "Sous quels formats télécharge-t-on la carte ?", "choix": ["PDF ou image PNG", "Excel seulement", "On ne peut pas"], "bonne": 0,
             "explication": "PDF ou PNG, avec titre, format de papier et orientation."},
            {"question": "À quoi sert « Par zone » ?", "choix": [
                "À supprimer des zones", "À colorer les zones selon un ou plusieurs indicateurs", "À changer de langue"], "bonne": 1,
             "explication": "Il colore régions, provinces ou communes selon les indicateurs choisis."},
        ],
    },
    {
        "code": "documents", "titre": "Documents, partage et corbeille", "icone": "FolderOpen",
        "description": "Ranger les documents, les partager par lien et retrouver ce qui a été supprimé.",
        "lecons": [
            {
                "code": "ranger", "titre": "Ranger et versionner ses documents", "duree": 6,
                "objectif": "Classer les documents en dossiers, gérer leurs versions et les sélections multiples.",
                "blocs": [
                    {"type": "texte", "texte": "Chaque projet a ses documents (onglet **Documents**) ; le menu **Documents** donne la bibliothèque libre, sans projet. Ils se rangent en **dossiers**, comme sur un ordinateur."},
                    {"type": "image", "src": "projet-documents.webp", "legende": "Dossiers, ajout de documents, sélection multiple."},
                    {"type": "etapes", "items": [
                        "**Versions** : déposez une nouvelle version ; l'ancienne est gardée.",
                        "**Sélection multiple** : cochez des éléments pour les télécharger en zip ou les supprimer.",
                    ]},
                ],
            },
            {
                "code": "partager", "titre": "Partager un document par lien", "duree": 7,
                "objectif": "Envoyer un document à une personne sans compte, avec des droits et une date d'expiration.",
                "blocs": [
                    {"type": "etapes", "items": [
                        "Dans le menu « … » d'un document, choisissez **Partager par lien**.",
                        "Choisissez le droit : **Consulter seulement** ou **Consulter et télécharger**.",
                        "Choisissez l'**expiration** (1 jour, 7 jours, 30 jours ou une date précise), et si besoin un **mot de passe** et un **nombre d'ouvertures**.",
                        "Copiez le lien et envoyez-le. Le mot de passe s'envoie séparément.",
                    ]},
                    {"type": "texte", "texte": "La liste des liens du document montre leur état (actif, expiré, révoqué) et le nombre d'ouvertures. **Révoquer** coupe l'accès immédiatement, même si la personne a déjà le lien."},
                    {"type": "attention", "texte": "« Consulter seulement » retire le bouton de téléchargement, mais un document affiché peut toujours être recopié (capture d'écran). Ne partagez que ce qui peut être vu."},
                ],
            },
            {
                "code": "corbeille", "titre": "La corbeille", "duree": 3,
                "objectif": "Restaurer un élément supprimé par erreur.",
                "blocs": [
                    {"type": "texte", "texte": "Ce qui est supprimé reste **30 jours** dans la **Corbeille** (en bas du menu) : on peut le restaurer ou le supprimer définitivement. Après 30 jours, il est effacé automatiquement."},
                    {"type": "image", "src": "corbeille.webp", "legende": "La corbeille : restaurer, supprimer définitivement, vider."},
                    {"type": "exercice", "items": [
                        "Créez un dossier d'essai, mettez-le à la corbeille, puis restaurez-le.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Combien de temps un élément supprimé reste-t-il dans la corbeille ?", "choix": ["7 jours", "30 jours", "Pour toujours"], "bonne": 1,
             "explication": "30 jours, puis il est effacé automatiquement."},
            {"question": "Que se passe-t-il quand on dépose une nouvelle version d'un document ?", "choix": [
                "L'ancienne est effacée", "L'ancienne est gardée", "Le document est dupliqué"], "bonne": 1,
             "explication": "Un document garde toutes ses versions."},
            {"question": "Un lien de partage de document peut-il expirer ?", "choix": [
                "Non, jamais", "Oui : on choisit toujours sa date d'expiration", "Seulement le dimanche"], "bonne": 1,
             "explication": "L'expiration est obligatoire : 1, 7, 30 jours ou une date précise."},
            {"question": "Comment envoyer le mot de passe d'un lien de partage ?", "choix": [
                "Dans le même message que le lien", "Séparément (téléphone ou autre message)", "On ne peut pas mettre de mot de passe"], "bonne": 1,
             "explication": "Lien et mot de passe ne voyagent jamais ensemble."},
            {"question": "Que fait « Révoquer » sur un lien ?", "choix": [
                "Prolonge le lien", "Coupe l'accès immédiatement", "Envoie le document par courriel"], "bonne": 1,
             "explication": "La personne ne peut plus ouvrir le document, même avec le lien."},
        ],
    },
    {
        "code": "plaintes", "titre": "Plaintes et retours des communautés", "icone": "MessagesSquare",
        "description": "Recevoir, traiter et suivre les plaintes jusqu'à la réponse au plaignant.",
        "lecons": [
            {
                "code": "recevoir", "titre": "Recevoir les plaintes et retours", "duree": 7,
                "objectif": "Connaître les canaux de réception et le numéro de suivi du plaignant.",
                "blocs": [
                    {"type": "texte", "texte": "Le mécanisme recueille les plaintes, avis et suggestions des communautés et les suit jusqu'à la **réponse au plaignant**."},
                    {"type": "etapes", "items": [
                        "**Formulaire public** en ligne, sans compte, aussi par **QR code** (un par projet).",
                        "**Saisie par l'équipe** : « Enregistrer un retour » (téléphone, visite, réunion…).",
                        "Le plaignant reçoit un **numéro de suivi** pour connaître l'avancement de sa demande.",
                    ]},
                    {"type": "image", "src": "plainte-formulaire-public.webp", "legende": "Le formulaire public, sans compte."},
                    {"type": "video", "chapitre": "plaintes"},
                ],
            },
            {
                "code": "traiter", "titre": "Traiter un dossier", "duree": 10,
                "objectif": "Classer, affecter, faire avancer et clôturer un dossier dans les délais.",
                "blocs": [
                    {"type": "image", "src": "plainte-dossier.webp", "legende": "La fiche d'un dossier : récit, plaignant, étape en cours, échéance et journal."},
                    {"type": "etapes", "items": [
                        "**Classer** : catégorie et priorité.",
                        "**Affecter** à un gestionnaire, qui reçoit une notification.",
                        "Le gestionnaire fait **avancer les étapes** du circuit ; chaque étape a son délai.",
                        "**Décider** et **clôturer** : motif, décision et retour au plaignant sont obligatoires.",
                    ]},
                    {"type": "attention", "texte": "Les cas sensibles (exploitation et abus, fraude…) suivent un **circuit confidentiel**, réservé à des personnes nommées et habilitées. Leurs données sont chiffrées."},
                    {"type": "texte", "texte": "**Délais** : un rappel part quand l'échéance approche ; en retard, le dossier est signalé et l'alerte remonte aux superviseurs."},
                    {"type": "exercice", "items": [
                        "Ouvrez le tableau de bord des plaintes et repérez les dossiers en retard.",
                        "Si vous en avez le droit, affectez un dossier non attribué à un gestionnaire.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Par quels moyens une plainte peut-elle arriver ?", "choix": [
                "Formulaire public, QR code ou saisie par l'équipe", "Uniquement par courrier postal", "Seulement par les administrateurs"], "bonne": 0,
             "explication": "Formulaire public (aussi par QR code) ou saisie par l'équipe."},
            {"question": "À quoi sert le numéro de suivi remis au plaignant ?", "choix": [
                "À se connecter à la plateforme", "À connaître l'avancement de sa demande", "À payer"], "bonne": 1,
             "explication": "Il permet de suivre sa demande sans compte."},
            {"question": "Que faut-il pour clôturer un dossier ?", "choix": [
                "Rien", "Un motif, une décision et un retour au plaignant", "L'accord du bailleur"], "bonne": 1,
             "explication": "Motif, décision et retour au plaignant sont obligatoires."},
            {"question": "Qui voit les dossiers du circuit confidentiel ?", "choix": [
                "Tout le monde", "Des personnes nommées et habilitées", "Le public"], "bonne": 1,
             "explication": "Le circuit confidentiel est réservé à des personnes habilitées."},
            {"question": "Que se passe-t-il quand un dossier est en retard ?", "choix": [
                "Il est supprimé", "Il est signalé et l'alerte remonte aux superviseurs", "Rien"], "bonne": 1,
             "explication": "Rappel avant l'échéance, puis signalement et escalade."},
        ],
    },
    {
        "code": "administration", "titre": "Administrer son espace", "icone": "Settings",
        "description": "Gérer les utilisateurs et leurs droits, personnaliser la plateforme, protéger les données.",
        "lecons": [
            {
                "code": "utilisateurs", "titre": "Utilisateurs et droits", "duree": 8,
                "objectif": "Créer des comptes et régler ce que chacun voit et peut modifier.",
                "blocs": [
                    {"type": "texte", "texte": "Menu **Utilisateurs** (administrateur) : « Nouvel utilisateur » avec nom, **adresse courriel** (elle sert à se connecter et à recevoir le code ; une adresse ne peut appartenir qu'à un seul compte), rôle, niveau d'accès et mot de passe."},
                    {"type": "image", "src": "utilisateurs.webp", "legende": "Les comptes : rôle, structure, accès, état."},
                    {"type": "etapes", "items": [
                        "**Rôle** : ce que la personne voit (tous les projets, ou ceux auxquels elle est affectée).",
                        "**Niveau d'accès** : consulter seulement, ou créer et modifier.",
                        "**Droits par module** : masquer un module, ou le mettre en consultation seule, utilisateur par utilisateur.",
                    ]},
                    {"type": "astuce", "texte": "L'Administrateur a toujours accès à tout. Un collègue ne voit pas un projet ? Ajoutez-le à l'équipe du projet, ou changez son rôle."},
                ],
            },
            {
                "code": "personnaliser", "titre": "Personnaliser et sécuriser", "duree": 6,
                "objectif": "Mettre le logo et le nom de l'organisation, adapter le menu, connaître les protections.",
                "blocs": [
                    {"type": "etapes", "items": [
                        "**Logo et nom** : Organisation › Identité et logo. Le logo s'affiche en haut de toutes les pages.",
                        "**Menu** : « Personnaliser le menu » pour renommer les rubriques, changer leurs icônes et adapter le vocabulaire.",
                        "**Organisation** : structure interne, parties prenantes, partenaires.",
                    ]},
                    {"type": "image", "src": "organisation-logo.webp", "legende": "Le nom et le logo de votre organisation."},
                    {"type": "texte", "texte": "Vos données sont dans **une base propre à votre organisation**, jamais mélangée avec celles d'une autre. Les récits des plaignants sont chiffrés ; les fichiers ne s'ouvrent que par des liens temporaires ; le **journal d'audit** garde la trace des connexions, consultations sensibles, exports et changements de droits, sans modification possible."},
                    {"type": "exercice", "items": [
                        "Vérifiez que le logo de votre organisation est bien en place.",
                        "Ouvrez le journal d'audit et filtrez les connexions de la semaine.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Une même adresse courriel peut-elle servir à deux comptes ?", "choix": [
                "Oui, sans limite", "Non : une adresse n'appartient qu'à un seul compte", "Seulement dans deux organisations"], "bonne": 1,
             "explication": "L'adresse sert à se connecter : elle est unique sur toute la plateforme."},
            {"question": "Que détermine le rôle d'un utilisateur ?", "choix": [
                "Sa langue", "Ce qu'il voit : tous les projets ou ceux auxquels il est affecté", "La couleur de l'écran"], "bonne": 1,
             "explication": "Le rôle règle la visibilité ; le niveau d'accès règle la modification."},
            {"question": "Comment empêcher quelqu'un de modifier un module tout en le lui laissant voir ?", "choix": [
                "Supprimer son compte", "Mettre ce module en consultation seule dans ses droits par module", "Lui changer son mot de passe"], "bonne": 1,
             "explication": "Les droits par module se règlent utilisateur par utilisateur."},
            {"question": "Où change-t-on le logo de l'organisation ?", "choix": [
                "Organisation › Identité et logo", "Dans la Corbeille", "Dans un projet"], "bonne": 0,
             "explication": "Le logo s'affiche ensuite en haut de toutes les pages."},
            {"question": "Que garde le journal d'audit ?", "choix": [
                "Les connexions, consultations sensibles, exports et changements de droits", "Les mots de passe", "Rien"], "bonne": 0,
             "explication": "Il garde ces traces sans modification possible."},
        ],
    },
]

PAR_CODE = {m["code"]: m for m in MODULES}
LECONS = {lecon["code"]: (m, lecon) for m in MODULES for lecon in m["lecons"]}
