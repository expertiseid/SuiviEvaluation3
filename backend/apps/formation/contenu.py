"""
Contenu du cours en ligne d'Expertise-ID Monitora : modules, leçons, quiz — un guide pas à pas.

Chaque leçon est une suite de blocs affichés dans l'ordre :
- {"type": "texte", "texte": …}                       paragraphe ;
- {"type": "etapes", "items": [...]}                  étapes numérotées ;
- {"type": "capture", "src", "legende", "reperes"}    capture annotée (frontend/public/formation/guide/) : les
                                                       cadres rouges numérotés de l'image correspondent, dans
                                                       l'ordre, aux textes de « reperes » ;
- {"type": "image", "src", "legende"}                 capture simple (frontend/public/formation/) ;
- {"type": "tableau", "titre", "colonnes", "lignes"}  tableau (colonnes d'un canevas Excel…) ;
- {"type": "video", "chapitre": …}                    extrait de la vidéo de présentation (voir CHAPITRES) ;
- {"type": "astuce" | "attention", "texte": …}        encadrés ;
- {"type": "exercice", "items": [...]}                à faire dans son propre espace.
Les **mots en gras** s'écrivent entre doubles astérisques.

Quiz : 5 questions par module ; « bonne » est l'indice de la bonne réponse (jamais envoyé au
navigateur avant la réponse). Réussite : SEUIL_REUSSITE bonnes réponses sur 5.
"""

SEUIL_REUSSITE = 4

# Début : 2 secondes après le changement de page (la page et sa légende sont affichées).
CHAPITRES = {
    "tableau_de_bord": (6, 15), "strategie": (17, 21), "projets": (23, 27), "planification": (29, 33),
    "cadre_logique": (35, 39), "indicateurs": (41, 46), "carte": (48, 62), "plaintes": (64, 70),
}


def capture(src, legende, *reperes):
    return {"type": "capture", "src": f"guide/{src}.webp", "legende": legende, "reperes": list(reperes)}


MODULES = [
    # ------------------------------------------------------------------------------------------------
    {
        "code": "prise-en-main", "titre": "Prendre en main la plateforme", "icone": "Compass",
        "description": "Se connecter, se repérer dans l'écran, lire, filtrer, personnaliser et partager le tableau de bord.",
        "lecons": [
            {
                "code": "connexion", "titre": "Se connecter, pas à pas", "duree": 5,
                "objectif": "Ouvrir sa session avec son adresse courriel, son mot de passe et le code reçu par courriel.",
                "blocs": [
                    {"type": "texte", "texte": "Tout le monde se connecte à **la même adresse** de la plateforme : c'est votre compte qui ouvre l'espace de votre organisation. Vous n'avez rien d'autre à retenir que votre adresse courriel et votre mot de passe."},
                    {"type": "image", "src": "connexion.webp", "legende": "La page de connexion."},
                    {"type": "etapes", "items": [
                        "Dans le champ **Adresse courriel**, tapez l'adresse de votre compte (celle que votre administrateur a enregistrée), par exemple awa.kabore@monong.org.",
                        "Dans le champ **Mot de passe**, tapez votre mot de passe. L'œil à droite du champ affiche ce que vous tapez, pour vérifier.",
                        "Cliquez sur le bouton vert **Se connecter**.",
                        "L'écran demande alors un **code à 6 chiffres** : ouvrez votre messagerie, cherchez le courriel « Votre code de connexion » et recopiez le code dans les six cases. La connexion se fait dès la 6e case remplie (sinon, cliquez sur **Valider**).",
                    ]},
                    {"type": "attention", "texte": "Le code est valable **10 minutes** et pour **une seule** connexion. Pas de courriel ? Regardez dans les courriers indésirables, puis cliquez sur **Renvoyer le code** (une minute d'attente entre deux envois). Vous vous êtes trompé d'adresse ? **Revenir à l'adresse courriel** vous ramène au début."},
                    {"type": "astuce", "texte": "« Adresse courriel ou mot de passe incorrect » : vérifiez les majuscules et l'adresse. Après plusieurs essais ratés, demandez à votre administrateur de vous donner un nouveau mot de passe (menu Utilisateurs)."},
                    {"type": "exercice", "items": ["Déconnectez-vous (bouton **Déconnexion** en haut à droite), puis reconnectez-vous en suivant les 4 étapes."]},
                ],
            },
            {
                "code": "ecran", "titre": "Se repérer dans l'écran", "duree": 5,
                "objectif": "Savoir où se trouvent le menu, la langue, les notifications et la déconnexion.",
                "blocs": [
                    capture("m1-ecran", "L'écran principal, après la connexion.",
                            "**Le menu**, à gauche : un clic ouvre le module (Tableau de bord, Stratégies, Projets, Indicateurs, Suivi, Bénéficiaires, Cartographie, Documents, Plaintes et retours, Formation…). Le module ouvert est surligné en vert. En bas : la Corbeille, puis les pages d'administration (pour l'administrateur).",
                            "**La langue** (FR) : un clic ouvre la liste Français, English, العربية, Español, Deutsch. Votre choix est gardé dans votre compte.",
                            "**La cloche** : vos notifications (affectations, échéances, retards…). Le chiffre rouge indique celles que vous n'avez pas lues ; un clic les ouvre.",
                            "**Déconnexion** : fermez toujours votre session sur un ordinateur partagé."),
                    {"type": "texte", "texte": "La **bande rouge** qui défile sous l'en-tête du tableau de bord annonce les activités en retard (« En retard · … ») : un clic dessus ouvre le projet concerné."},
                    capture("m1-langue", "Le choix de la langue : la liste s'ouvre sous « FR »."),
                    {"type": "texte", "texte": "Cliquez sur la langue voulue : toute l'interface change aussitôt. Pour revenir en français, cliquez sur **Français**."},
                    {"type": "astuce", "texte": "En haut de chaque page, **← Retour** ramène à la page précédente. Dans les listes, le bouton **Éditer** fait apparaître les crayons (modifier) et les corbeilles (supprimer) de chaque ligne ; **Terminer l'édition** les cache de nouveau."},
                    {"type": "exercice", "items": ["Passez l'interface en anglais, ouvrez le menu Projects, puis revenez en français.", "Ouvrez la cloche et lisez votre notification la plus récente."]},
                ],
            },
            {
                "code": "tableau-de-bord", "titre": "Filtrer, personnaliser et partager le tableau de bord", "duree": 8,
                "objectif": "Lire les chiffres clés pour une période, choisir les blocs affichés, partager le tableau de bord avec un bailleur.",
                "blocs": [
                    capture("m1-tableau-filtres", "Les filtres et les boutons du tableau de bord.",
                            "**Période** : « Toutes », « Année » (choisissez l'année) ou « Plage de dates » (choisissez le début et la fin). Tous les chiffres et graphiques se recalculent.",
                            "**Statut des projets** : en cours, en préparation, clôturés… Le bouton **Réinitialiser**, à droite, enlève tous les filtres.",
                            "**Partager** : crée un lien de consultation pour une personne sans compte (voir plus bas).",
                            "**Personnaliser** : choisit les blocs affichés (le compteur indique combien sont visibles, ex. 18/18)."),
                    {"type": "video", "chapitre": "tableau_de_bord"},
                    capture("m1-personnaliser", "La fenêtre « Personnaliser le tableau de bord ».",
                            "Cochez les blocs à afficher, décochez ceux qui ne vous servent pas (ils sont rangés par thème : vue d'ensemble, géographie, budget, bénéficiaires, projets, évolution). **Tout afficher** / **Tout masquer** cochent ou décochent tout ; **Fermer** enregistre."),
                    capture("m1-partager", "La fenêtre « Partager le tableau de bord ».",
                            "Remplissez **Destinataire ou objet** (ex. « Comité de pilotage »), choisissez éventuellement **Expire le** (sans date, le lien reste valable jusqu'à ce que vous le désactiviez), puis **Créer le lien**. Le lien apparaît dans **Liens existants** : l'icône de copie le copie, l'interrupteur **Actif** le coupe, la corbeille le supprime."),
                    {"type": "attention", "texte": "La personne qui a le lien voit le tableau de bord **avec les filtres choisis au moment du partage**, en lecture seule, sans pouvoir rien modifier."},
                    {"type": "exercice", "items": [
                        "Filtrez le tableau de bord sur l'année en cours, puis cliquez sur Réinitialiser.",
                        "Dans Personnaliser, masquez un bloc, fermez, constatez qu'il a disparu, puis réaffichez-le.",
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Que faut-il pour se connecter ?", "choix": [
                "L'adresse de l'espace de son organisation et un identifiant", "Son adresse courriel, son mot de passe, puis le code à 6 chiffres reçu par courriel",
                "Seulement un mot de passe"], "bonne": 1, "explication": "Adresse courriel + mot de passe, puis le code reçu à chaque connexion."},
            {"question": "Le code de connexion n'arrive pas. Que faites-vous en premier ?", "choix": [
                "Je recrée un compte", "Je regarde dans les indésirables, puis je clique sur « Renvoyer le code »", "J'attends le lendemain"], "bonne": 1,
             "explication": "Vérifiez les indésirables, puis demandez un nouveau code."},
            {"question": "À quoi sert le chiffre rouge sur la cloche ?", "choix": [
                "Au nombre de projets", "Au nombre de notifications non lues", "Au nombre de jours avant l'échéance"], "bonne": 1,
             "explication": "Il compte les notifications que vous n'avez pas encore lues."},
            {"question": "Vous choisissez « Année 2026 » dans Période. Que se passe-t-il ?", "choix": [
                "Seul le titre change", "Tous les chiffres et graphiques du tableau de bord se recalculent pour 2026", "Les projets de 2026 sont supprimés"], "bonne": 1,
             "explication": "Tous les blocs suivent les filtres du haut."},
            {"question": "Comment montrer le tableau de bord à un bailleur sans compte ?", "choix": [
                "Lui prêter son mot de passe", "Bouton Partager → Créer le lien → copier le lien et l'envoyer", "Lui créer un compte administrateur"], "bonne": 1,
             "explication": "Le lien de partage est en lecture seule, sans compte."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "strategie", "titre": "Stratégies et programmes", "icone": "Target",
        "description": "Créer une stratégie, construire sa structure, la remplir ou l'importer d'Excel, y rattacher programmes et projets.",
        "lecons": [
            {
                "code": "creer-strategie", "titre": "Créer une stratégie", "duree": 6,
                "objectif": "Créer le document de stratégie de votre organisation (ou une politique nationale).",
                "blocs": [
                    {"type": "texte", "texte": "La plateforme range vos documents en chaîne : **Stratégie → Programme → Projet**. Chaque maillon a sa rubrique dans le menu (**Stratégies**, **Programmes**). Une stratégie peut être votre plan stratégique, ou une politique nationale à laquelle vos projets contribuent."},
                    capture("m2-liste", "La rubrique Stratégies.",
                            "Cliquez sur **Stratégies** dans le menu.",
                            "Cliquez sur **Nouveau document — Stratégie** pour en créer une.",
                            "**Chaîne des documents** (administrateur) : renommer les maillons ou en ajouter (ex. Stratégie → Programme → Sous-programme).",
                            "**Ouvrir** : ouvre une stratégie existante."),
                    capture("m2-nouveau", "La fenêtre « Nouveau document — Stratégie ».",
                            "**Nom** (obligatoire) : le titre complet, ex. « Plan stratégique 2026-2030 ».",
                            "**Description** : en une ou deux phrases, de quoi il s'agit.",
                            "Cliquez sur **Créer**. (Services chargés et Parties prenantes sont facultatifs.)"),
                    {"type": "video", "chapitre": "strategie"},
                ],
            },
            {
                "code": "structure", "titre": "Construire la structure et la remplir", "duree": 10,
                "objectif": "Nommer les niveaux (axe, objectif, effet…) puis saisir les éléments, à la main ou par Excel.",
                "blocs": [
                    capture("m2-detail", "La page d'une stratégie.",
                            "Les onglets : **Configuration des niveaux** (les niveaux), **Arborescence & saisie** (les éléments), **Axes & budgets**, **Suivi stratégique**, **Projets & budgets**.",
                            "**Exporter le canevas Excel** : télécharge la structure actuelle dans Excel.",
                            "**Importer depuis Excel** : remplit la structure à partir d'un fichier (voir le module « Les canevas Excel »)."),
                    capture("m2-niveaux", "Onglet « Configuration des niveaux ».",
                            "Ouvrez **Configuration des niveaux**. La liste montre les niveaux du plus haut au plus bas (ex. 1. Axe stratégique, 2. Objectif stratégique, 3. Effet attendu) ; les flèches ↑ ↓ changent leur ordre.",
                            "Pour ajouter un niveau, tapez son nom dans **Ajouter un niveau** (ex. « Résultat ») puis cliquez sur **Ajouter**."),
                    capture("m2-arborescence", "Onglet « Arborescence & saisie ».",
                            "Ouvrez **Arborescence & saisie** : vous voyez les éléments, avec leur code, leur programmation par trimestre, leur budget et leur taux.",
                            "Le bouton vert porte le nom de votre premier niveau (ici **Ajouter Axe stratégique**) : il crée un élément de ce niveau. Pour ajouter un élément en dessous d'un autre, passez en mode **Éditer** et utilisez le « + » de sa ligne."),
                    {"type": "astuce", "texte": "Une structure longue se remplit bien plus vite par Excel : **Importer depuis Excel → Télécharger le modèle Excel**, remplissez une colonne par niveau, puis importez (détails dans le module « Les canevas Excel »)."},
                    {"type": "exercice", "items": ["Ouvrez une stratégie, regardez sa Configuration des niveaux, puis son Arborescence.", "Cliquez sur Exporter le canevas Excel et ouvrez le fichier téléchargé."]},
                ],
            },
            {
                "code": "programme", "titre": "Les programmes et leur fiche", "duree": 6,
                "objectif": "Créer un programme rattaché à une stratégie et remplir sa fiche.",
                "blocs": [
                    {"type": "etapes", "items": [
                        "Ouvrez la rubrique **Programmes** du menu, puis **Nouveau document — Programme**.",
                        "Donnez son **nom** et choisissez **le document au-dessus** auquel il se rattache (la stratégie), et si besoin l'élément précis de cette stratégie (ex. « AXE1 — Développer le capital humain »).",
                        "Créez-le, puis ouvrez-le : sa page a les mêmes onglets qu'une stratégie, plus l'onglet **Fiche**.",
                    ]},
                    capture("m2-programme", "La page d'un programme.",
                            "Les onglets du programme. **Fiche** montre son code, son statut, sa période, son responsable, son financement (budget, fonds propres, bailleurs), ses cibles et ses éléments de capitalisation ; **Modifier la fiche** permet de les remplir comme pour un projet."),
                    {"type": "texte", "texte": "Sous le titre, la ligne **Rattaché à …** rappelle la stratégie et l'élément dont le programme relève. Les projets se rattachent ensuite à un élément du programme (onglet Stratégie & capitalisation de chaque projet)."},
                ],
            },
        ],
        "quiz": [
            {"question": "Dans quel ordre s'enchaînent les documents ?", "choix": ["Projet → Programme → Stratégie", "Stratégie → Programme → Projet", "Programme → Projet → Stratégie"], "bonne": 1,
             "explication": "De la stratégie au projet."},
            {"question": "Où ajoute-t-on un niveau (ex. « Résultat ») à une stratégie ?", "choix": [
                "Onglet Configuration des niveaux → Ajouter un niveau → Ajouter", "Dans le menu Utilisateurs", "Dans la Corbeille"], "bonne": 0,
             "explication": "Les niveaux se nomment et s'ordonnent dans Configuration des niveaux."},
            {"question": "Le bouton vert « Ajouter Axe stratégique » s'appelle ainsi parce que…", "choix": [
                "c'est un nom fixe", "il porte le nom du premier niveau de votre structure", "c'est une erreur"], "bonne": 1,
             "explication": "Il prend le nom de votre premier niveau."},
            {"question": "Comment remplir rapidement une structure de 80 éléments ?", "choix": [
                "Un par un, obligatoirement", "Importer depuis Excel, à partir du modèle téléchargé", "En copiant une autre organisation"], "bonne": 1,
             "explication": "Le modèle Excel : une colonne par niveau, puis Importer."},
            {"question": "Où remplit-on le budget et les bailleurs d'un programme ?", "choix": [
                "Onglet Fiche → Modifier la fiche", "Dans le tableau de bord", "Dans le journal d'audit"], "bonne": 0,
             "explication": "La fiche d'un programme se remplit comme celle d'un projet."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "projets", "titre": "Créer un projet", "icone": "FolderKanban",
        "description": "Le formulaire « Nouveau projet » onglet par onglet, puis l'équipe et le financement du projet.",
        "lecons": [
            {
                "code": "ouvrir-formulaire", "titre": "Ouvrir le formulaire « Nouveau projet »", "duree": 3,
                "objectif": "Trouver la liste des projets et ouvrir le formulaire de création.",
                "blocs": [
                    capture("projets-01-liste", "La liste des projets.",
                            "Cliquez sur **Projets** dans le menu.",
                            "Cliquez sur le bouton vert **Nouveau projet** : le formulaire s'ouvre.",
                            "**Importer depuis Excel** : pour créer un projet complet (fiche + planification) à partir du modèle Excel (voir le module « Les canevas Excel »)."),
                    {"type": "texte", "texte": "En haut de la liste, les compteurs **Tous les projets / En cours / En préparation / Clôturé** servent aussi de filtres. La barre de recherche trouve un projet par son nom ou son code."},
                    {"type": "video", "chapitre": "projets"},
                ],
            },
            {
                "code": "onglet-general", "titre": "Onglet « Général » : l'identité du projet", "duree": 10,
                "objectif": "Remplir le nom, le code, les dates, le budget, les responsables et les zones du projet.",
                "blocs": [
                    capture("projets-02-general", "Onglet Général, haut du formulaire.",
                            "L'onglet **Général** est ouvert par défaut.",
                            "**Nom du projet** (obligatoire) : le titre complet, ex. « Projet d'appui à l'éducation des filles — Koulsé ».",
                            "**Code** (obligatoire, unique) : un code court, ex. « PEF-KOU-2026 ». Il sert à retrouver le projet et dans les fichiers Excel.",
                            "**Date de début prévue** (obligatoire) : cliquez dans le champ et choisissez la date dans le calendrier.",
                            "**Date de fin prévue** (obligatoire).",
                            "**Statut** : En préparation, En cours ou Clôturé."),
                    {"type": "texte", "texte": "Sur la même partie : **Budget total (FCFA)** et **Fonds propres (FCFA)** (le budget se recalcule tout seul dès que vous ajoutez des bailleurs), **Date de rappel (optionnel)** (une alerte à cette date), **Type de mise en œuvre** (Direct, ou Consortium si plusieurs partenaires le portent)."},
                    capture("projets-03-general-suite", "Onglet Général, faites défiler vers le bas.",
                            "**Chef de projet** : choisissez une personne de la liste ou tapez librement un nom. C'est **seulement un intitulé** affiché : il ne donne aucun accès.",
                            "**Utilisateurs affectés (accès à la plateforme)** : choisissez les comptes qui doivent voir et travailler sur ce projet (chef de projet, animateurs…). **C'est ce champ qui donne l'accès** aux personnes qui ne voient pas tous les projets."),
                    capture("projets-03b-zones", "Bas de l'onglet Général : bailleurs, partenaire, pays et zones.",
                            "**Pays d'intervention** : tapez et choisissez un ou plusieurs pays. Au-dessus : **Ajouter un bailleur** (un bailleur et son montant par ligne) et **Partenaire de mise en œuvre** (choisissez-le, ou tapez son nom dans « Ou créer un nouveau » puis **+ Créer**).",
                            "**Zones d'intervention** : cochez **Tout le pays**, ou choisissez une région/province/commune puis **Ajouter cette zone** (autant de fois que nécessaire)."),
                ],
            },
            {
                "code": "autres-onglets", "titre": "Onglets Cibles, Stratégie & capitalisation, Organisation", "duree": 8,
                "objectif": "Indiquer les cibles, le rattachement stratégique, les règles de saisie, puis créer le projet.",
                "blocs": [
                    capture("projets-04-cibles", "Onglet « Cibles bénéficiaires ».",
                            "Cliquez sur l'onglet **Cibles bénéficiaires**.",
                            "**Cible totale** : le nombre de personnes que le projet doit toucher, ex. 1200.",
                            "**Dont hommes / Dont femmes / Dont jeunes / Dont PDI** : la répartition, ex. 800 femmes."),
                    {"type": "astuce", "texte": "Les bénéficiaires eux-mêmes (les personnes) s'ajoutent **après** la création du projet, depuis le menu Bénéficiaires ou par import Excel."},
                    capture("projets-05-strategie", "Onglet « Stratégie & capitalisation ».",
                            "Cliquez sur l'onglet **Stratégie & capitalisation**.",
                            "**Cadre stratégique** : choisissez la stratégie ou le programme dont relève le projet.",
                            "**Rattachement dans le cadre stratégique** : choisissez ensuite l'élément précis (un axe, un objectif…). Il faut d'abord avoir choisi le cadre.",
                            "**Méthode de calcul des taux** : laissez « Hériter de l'organisation » sauf consigne contraire (voir Paramètres d'alerte)."),
                    capture("projets-05b-approbations", "Bas de l'onglet « Stratégie & capitalisation ».",
                            "**Les saisies de réalisations doivent être approuvées** : cochez si chaque saisie de suivi doit être validée (menu Approbations) avant de compter.",
                            "**Les changements de planification doivent être approuvés** : cochez si les ajouts et modifications de la planification doivent être validés.",
                            "**Éléments de capitalisation** : à remplir en fin de projet (leçons apprises, bonnes pratiques)."),
                    capture("projets-06-organisation", "Onglet « Organisation », puis Créer.",
                            "Cliquez sur l'onglet **Organisation**.",
                            "**Services chargés du projet** : les directions ou services de votre organisation qui le portent (ils se créent dans Organisation › Structure). **Parties prenantes** : facultatif.",
                            "",
                            "Cliquez sur **Créer**. Le projet s'ouvre sur sa page : vous pouvez construire sa planification."),
                    {"type": "attention", "texte": "Le bouton **Créer** reste utilisable depuis n'importe quel onglet. Si un champ obligatoire manque (nom, code, dates), l'onglet concerné l'indique en rouge."},
                    {"type": "exercice", "items": ["Créez un projet d'essai complet en remplissant les 4 onglets, puis retrouvez-le dans la liste avec la recherche par code."]},
                ],
            },
            {
                "code": "equipe-financement", "titre": "Après la création : équipe et financement", "duree": 7,
                "objectif": "Constituer l'équipe du projet et enregistrer ses financements et rallonges.",
                "blocs": [
                    capture("projets-08-onglets", "La page d'un projet.",
                            "",
                            "Les onglets du projet : **Planification**, **Cadre logique**, **Équipe**, **Indicateurs**, **Financement**, **Documents**, **Retours des communautés**, **Contrôle**. Le bouton **Éditer** (en haut) passe la page en modification ; **Exporter** télécharge le projet."),
                    capture("planif-11-equipe", "Onglet « Équipe ».",
                            "Ouvrez l'onglet **Équipe**. Le sous-onglet **Équipe de projet** liste les équipes rattachées aux activités ; **Partenaires** liste les partenaires du projet. **Ajouter un membre existant** ajoute une personne déjà enregistrée à l'équipe choisie dans « Rattacher aussi à une équipe »."),
                    capture("planif-12-financement", "Onglet « Financement ».",
                            "Ouvrez l'onglet **Financement** : les cases du haut montrent le coût total, les fonds propres et les financements des bailleurs. Pour ajouter un financement : choisissez le **Bailleur** (ou créez-le avec « Ou créer un nouveau » + **+ Créer**), tapez le **Montant financé (FCFA)**, puis **Ajouter**. Dans le tableau, **+ Rallonge** ajoute un complément à un bailleur existant."),
                    {"type": "texte", "texte": "Le **coût total** du projet se recalcule tout seul : fonds propres + somme des financements des bailleurs."},
                ],
            },
        ],
        "quiz": [
            {"question": "Quels champs sont obligatoires pour créer un projet ?", "choix": [
                "Nom, code, date de début et date de fin", "Seulement le nom", "Le budget et les bailleurs"], "bonne": 0,
             "explication": "Nom du projet, Code, Date de début prévue et Date de fin prévue."},
            {"question": "Quel champ donne réellement accès au projet à un animateur ?", "choix": [
                "Chef de projet", "Utilisateurs affectés (accès à la plateforme)", "Parties prenantes"], "bonne": 1,
             "explication": "« Chef de projet » n'est qu'un intitulé ; « Utilisateurs affectés » donne l'accès."},
            {"question": "Où rattache-t-on le projet à un axe de la stratégie ?", "choix": [
                "Onglet Stratégie & capitalisation : Cadre stratégique puis Rattachement", "Onglet Cibles bénéficiaires", "Dans la Corbeille"], "bonne": 0,
             "explication": "Choisissez d'abord le cadre, puis l'élément précis."},
            {"question": "Vous voulez que chaque saisie de suivi soit validée avant de compter. Que cochez-vous ?", "choix": [
                "Les saisies de réalisations doivent être approuvées", "Tout le pays", "Hériter de l'organisation"], "bonne": 0,
             "explication": "Les saisies attendent alors dans le menu Approbations."},
            {"question": "Comment le coût total du projet est-il calculé quand on ajoute des bailleurs ?", "choix": [
                "On le tape à la main à chaque fois", "Fonds propres + somme des financements des bailleurs", "Il ne change jamais"], "bonne": 1,
             "explication": "Il se recalcule tout seul."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "planification", "titre": "Planifier un projet", "icone": "ListTree",
        "description": "Nommer les niveaux, ajouter et modifier les éléments, les sous-activités, programmer par période, lire le cadre logique.",
        "lecons": [
            {
                "code": "niveaux", "titre": "Nommer les niveaux de la planification", "duree": 5,
                "objectif": "Adapter les niveaux du projet à votre document de projet (ex. Effet → Extrant → Activité).",
                "blocs": [
                    {"type": "texte", "texte": "**Aucun niveau n'est imposé** : nommez-les comme dans votre document de projet. Exemples : « Objectif général → Objectif spécifique → Activité », ou « Effet → Extrant → Activité »."},
                    capture("planif-07-niveaux", "Planification › Configuration des niveaux.",
                            "Dans l'onglet Planification du projet, cliquez sur le sous-onglet **Configuration des niveaux**. La liste montre les niveaux, du plus haut au plus bas.",
                            "Le crayon d'un niveau le **renomme** (en mode Éditer) ; la corbeille le supprime s'il est vide. Pour en ajouter un, tapez son nom dans **Ajouter un niveau** (ex. « Résultat ») puis cliquez sur **Ajouter**."),
                    {"type": "astuce", "texte": "Renommer un niveau change seulement son nom affiché, jamais les éléments déjà saisis."},
                ],
            },
            {
                "code": "ajouter-elements", "titre": "Ajouter les éléments, du plus haut au plus bas", "duree": 8,
                "objectif": "Construire l'arbre de la planification : effets, extrants, activités.",
                "blocs": [
                    capture("planif-01-ajouter", "Planification › Planification : ajouter un élément du premier niveau.",
                            "Restez sur le sous-onglet **Planification**.",
                            "Tapez le libellé du nouvel élément dans le champ **Nouveau « Effet »…** (le nom suit votre premier niveau), ex. « Améliorer l'accès à l'eau potable dans les écoles ».",
                            "Cliquez sur **Ajouter** : l'élément apparaît dans la liste."),
                    capture("planif-02-arbre", "Vue Arbre : ajouter en dessous.",
                            "Cliquez sur **Arbre** pour voir la planification en arbre (**Tableau** montre la programmation et les budgets en colonnes).",
                            "Le **+** d'une ligne ajoute un élément du niveau **en dessous** (ex. un extrant sous un effet, une activité sous un extrant).",
                            "L'icône **liste +** ajoute une **sous-activité** (une tâche concrète de l'activité).",
                            "Pour **modifier** ou **supprimer** un élément, cliquez d'abord sur **Éditer** en haut de la page."),
                    {"type": "video", "chapitre": "planification"},
                    {"type": "texte", "texte": "Sur chaque ligne de l'arbre, d'autres icônes : le **trombone** (documents liés à l'élément), les **personnes** (équipe responsable), les **deux carrés** (dupliquer l'élément)."},
                ],
            },
            {
                "code": "modifier-element", "titre": "Remplir la fiche d'un élément", "duree": 10,
                "objectif": "Donner à une activité ses dates, son budget, sa cible, son mode de calcul et ses responsables.",
                "blocs": [
                    capture("planif-02b-edition", "Mode édition.",
                            "Cliquez sur **Éditer** (en haut de la page) : le bouton devient **Terminer l'édition**.",
                            "Le **crayon** d'une ligne ouvre la fiche de l'élément.",
                            "La **corbeille** d'une ligne le supprime (il va dans la Corbeille, récupérable 30 jours)."),
                    capture("planif-03-element", "La fiche « Modifier l'élément », haut.",
                            "**Libellé** (obligatoire) : l'intitulé de l'élément ; la liste propose les libellés du cadre stratégique, mais vous pouvez taper le vôtre.",
                            "**Description** : précisions sur ce qui sera fait.",
                            "**Date de début prévue**.",
                            "**Date de fin prévue** : la durée s'affiche en jours."),
                    capture("planif-04-element-suite", "La fiche, faites défiler : la cible et le calcul.",
                            "**Unité** : ce qu'on compte, ex. « producteurs », « latrines ». (Juste au-dessus : **Budget alloué (FCFA)** ; un message orange prévient s'il dépasse le budget restant du projet.)",
                            "**Valeur de base** : le niveau avant le démarrage (souvent 0).",
                            "**Quantité prévue (cible)** : ce que l'activité doit atteindre, ex. 300 producteurs.",
                            "**Méthode de calcul** : comment calculer le taux de réalisation (par quantité, par tâches pondérées, par jalons, binaire, saisie manuelle…). Laissez « Hériter » si vous ne savez pas."),
                    capture("planif-05-element-fin", "La fiche, bas.",
                            "**Services chargés** : le service de votre organisation responsable de cette partie.",
                            "**Responsables** : les personnes chargées de l'activité (choisissez-les, ou **+ Créer une nouvelle personne**). Dessous : **Équipe responsable** (ou **+ Créer une nouvelle équipe**).",
                            "Cliquez sur **Enregistrer**."),
                    capture("planif-06-sous-activite", "Ajouter une sous-activité (icône liste +).",
                            "**Libellé** (obligatoire) de la sous-activité, ex. « Session de formation en zone rurale », puis ses dates, sa quantité prévue et son unité ; **Créer**."),
                    {"type": "exercice", "items": ["Dans votre projet d'essai, ajoutez un effet, un extrant en dessous, puis une activité avec ses dates, son unité et sa quantité prévue.", "Ajoutez deux sous-activités à cette activité."]},
                ],
            },
            {
                "code": "par-periode", "titre": "Programmer par période", "duree": 5,
                "objectif": "Répartir quantités et budgets sur l'année et les trimestres.",
                "blocs": [
                    capture("planif-08-periode", "Planification › Planification par période.",
                            "Cliquez sur le sous-onglet **Planification par période**. Choisissez la **Période** dans la liste (ex. « Année 2026 »).",
                            "**Nouvelle période** crée une période (ex. un trimestre, une phase) avec ses dates. **Modifier la période**, **Supprimer**, **Saisie par Excel** et **Exporter** agissent sur la période choisie."),
                    {"type": "texte", "texte": "Pour la période choisie, fixez l'objectif de chaque activité (quantité et budget prévus) : les cases du haut montrent le budget prévu, le budget réalisé et le nombre d'éléments qui ont un objectif."},
                ],
            },
            {
                "code": "cadre-logique", "titre": "Le cadre logique et les risques", "duree": 6,
                "objectif": "Lire le cadre logique construit tout seul, l'exporter, et enregistrer les risques.",
                "blocs": [
                    capture("planif-09-cadre-logique", "Onglet Cadre logique.",
                            "Ouvrez l'onglet **Cadre logique** : il se construit **tout seul** à partir de la planification et des indicateurs (logique d'intervention ; indicateurs avec référence, cible, réalisé ; sources de vérification ; hypothèses).",
                            "**Exporter** le télécharge (Excel ou Word) pour vos rapports.",
                            "Le sous-onglet **Risques** donne la matrice des risques."),
                    capture("planif-10-risques", "Sous-onglet Risques.",
                            "**Nouveau risque** : décrivez le risque, sa **probabilité** et son **impact** (de 1 à 5) et la mesure prévue. La matrice colore les risques du plus faible (vert) au plus critique (rouge)."),
                    {"type": "video", "chapitre": "cadre_logique"},
                    {"type": "astuce", "texte": "Les sources de vérification et les hypothèses se remplissent dans la fiche de l'élément (ou par les colonnes « Attribut : Sources de vérification » et « Attribut : Hypothèses » du canevas Excel)."},
                ],
            },
        ],
        "quiz": [
            {"question": "Où renomme-t-on les niveaux d'un projet (Effet, Extrant, Activité…) ?", "choix": [
                "Planification › Configuration des niveaux", "Onglet Financement", "Menu Utilisateurs"], "bonne": 0,
             "explication": "Les niveaux se nomment dans Configuration des niveaux."},
            {"question": "Dans la vue Arbre, que fait le « + » d'une ligne ?", "choix": [
                "Supprime la ligne", "Ajoute un élément du niveau en dessous", "Ajoute un bailleur"], "bonne": 1,
             "explication": "Il crée un élément enfant (ex. une activité sous un extrant)."},
            {"question": "Vous ne voyez pas le crayon pour modifier une activité. Que faites-vous ?", "choix": [
                "Je cherche dans la Corbeille", "Je clique sur « Éditer » en haut de la page", "Je recrée le projet"], "bonne": 1,
             "explication": "Les crayons et corbeilles n'apparaissent qu'en mode Éditer."},
            {"question": "Dans la fiche d'une activité, où indique-t-on « 300 producteurs » ?", "choix": [
                "Unité = producteurs, Quantité prévue = 300", "Libellé = 300", "Commentaire = 300 producteurs"], "bonne": 0,
             "explication": "L'unité dit ce qu'on compte, la quantité prévue la cible."},
            {"question": "Le cadre logique…", "choix": [
                "se remplit case par case à la main", "se construit tout seul à partir de la planification et des indicateurs", "n'existe que dans Excel"], "bonne": 1,
             "explication": "Il est automatique et s'exporte."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "excel", "titre": "Les canevas Excel, colonne par colonne", "icone": "FileSpreadsheet",
        "description": "Télécharger, remplir et importer chaque modèle Excel : planification complète, projet, indicateurs, bénéficiaires, stratégie, suivi.",
        "lecons": [
            {
                "code": "principes", "titre": "Les règles communes à tous les canevas", "duree": 6,
                "objectif": "Savoir où télécharger un modèle, comment le remplir sans erreur et comment l'importer.",
                "blocs": [
                    {"type": "etapes", "items": [
                        "**Toujours partir du modèle de la plateforme** : bouton **Télécharger le modèle Excel** de l'écran concerné. Il contient un exemple et une feuille **Instructions**.",
                        "**Ne renommez pas** les feuilles et ne changez pas l'ordre des colonnes, sauf les colonnes de niveau (en **jaune**) que vous pouvez renommer, ajouter ou supprimer.",
                        "**Les dates** s'écrivent AAAA-MM-JJ (ex. 2026-03-31). **Les montants** en chiffres, sans espace ni « FCFA » (ex. 2000000).",
                        "**Plusieurs valeurs dans une cellule** se séparent par un point-virgule (ex. Femme;Jeune).",
                        "Effacez les lignes d'exemple avant d'importer, sauf si vous voulez les garder.",
                        "Revenez sur l'écran, cliquez dans **Fichier à importer**, choisissez votre fichier (.xlsx), puis **Importer**. Un compte rendu dit ce qui a été créé et signale chaque ligne refusée avec sa raison.",
                    ]},
                    capture("projets-07-import", "Une fenêtre d'import (ici « Importer un projet depuis Excel »).",
                            "**Télécharger le modèle Excel** : le canevas à remplir.",
                            "**Fichier à importer** : choisissez votre fichier rempli, puis **Importer**."),
                    {"type": "astuce", "texte": "Réimporter le même fichier **met à jour** les éléments déjà importés (même nom, même position) au lieu de les dupliquer : vous pouvez corriger votre fichier et le réimporter."},
                    {"type": "tableau", "titre": "Où trouver chaque modèle", "colonnes": ["Modèle", "Écran", "Bouton"], "lignes": [
                        ["Planification complète (tout en un)", "Menu Planification complète", "Télécharger le modèle Excel complet"],
                        ["Projet (fiche + planification)", "Menu Projets", "Importer depuis Excel → Télécharger le modèle Excel"],
                        ["Indicateurs", "Menu Indicateurs", "Importer depuis Excel → Télécharger le modèle Excel"],
                        ["Bénéficiaires", "Menu Bénéficiaires", "Importer depuis Excel → Télécharger le modèle Excel"],
                        ["Structure d'une stratégie", "Page de la stratégie", "Importer depuis Excel → Télécharger le modèle Excel"],
                        ["Canevas de suivi (réalisations)", "Menu Suivi → un projet", "Saisie par Excel → Télécharger le canevas de suivi"],
                    ]},
                ],
            },
            {
                "code": "planification-complete", "titre": "La planification complète, en un seul fichier", "duree": 12,
                "objectif": "Créer en une fois un cadre stratégique, un projet, sa planification, ses indicateurs et ses bénéficiaires.",
                "blocs": [
                    capture("planif-13-complete", "Le menu Planification complète.",
                            "Cliquez sur **Planification complète** dans le menu.",
                            "**Télécharger le modèle Excel complet** : un classeur de 9 feuilles.",
                            "Une fois rempli : **Fichier à importer** → choisissez le fichier → **Importer**."),
                    {"type": "attention", "texte": "Seule la feuille **Projet** est obligatoire (Nom du projet, Code du projet, Date de début, Date de fin). Les autres feuilles laissées vides sont simplement ignorées."},
                    {"type": "tableau", "titre": "Feuille « Cadre stratégique » (facultative)", "colonnes": ["Ligne", "Quoi écrire", "Exemple"], "lignes": [
                        ["Nom du cadre stratégique", "Le nom du cadre à créer ; vide = pas de cadre créé", "Plan stratégique 2026-2030"],
                        ["Description", "Facultatif", "Cadre de référence de l'organisation pour la période"],
                    ]},
                    {"type": "tableau", "titre": "Feuille « Structuration » (facultative)", "colonnes": ["Règle", "Explication"], "lignes": [
                        ["Une colonne = un niveau", "En jaune, de gauche à droite (ex. Orientation stratégique | Axe d'intervention). Renommez, ajoutez ou supprimez des colonnes."],
                        ["Une ligne = un élément", "Écrivez-le dans UNE SEULE colonne : celle de son niveau."],
                        ["Le parent est deviné", "C'est le dernier élément écrit au-dessus, dans la colonne juste à gauche."],
                    ]},
                    {"type": "tableau", "titre": "Feuille « Projet » (obligatoire) — colonne A le champ, colonne B la valeur", "colonnes": ["Champ", "Quoi écrire", "Exemple"], "lignes": [
                        ["Nom du projet *", "Le titre complet", "Programme d'appui à la résilience communautaire"],
                        ["Code du projet *", "Unique ; refusé s'il existe déjà", "PRJ-2026-001"],
                        ["Rattachement dans le cadre stratégique", "Nom exact d'un élément du cadre", "Axe 1 — Capital humain"],
                        ["Pays", "Codes ISO séparés par ;", "BF"],
                        ["Budget total / Fonds propres (FCFA)", "En chiffres", "100000000 / 10000000"],
                        ["Date de début * / Date de fin *", "AAAA-MM-JJ", "2026-01-01 / 2027-12-31"],
                        ["Statut", "EN_PREPARATION, EN_COURS ou CLOTURE", "EN_PREPARATION"],
                        ["Type de mise en œuvre", "DIRECT ou CONSORTIUM", "DIRECT"],
                        ["Partenaire de mise en œuvre / du consortium", "Noms (séparés par ; pour le consortium)", "ONG Sahel Solidarité"],
                        ["Chef de projet", "Un nom (intitulé seulement, ne donne pas d'accès)", "OUEDRAOGO Fatimata"],
                        ["Utilisateurs affectés", "Identifiants de comptes existants séparés par ; — c'est ce qui donne l'accès", "a.ouedraogo;b.traore"],
                        ["Cible totale / hommes / femmes / jeunes / PDI", "Nombres", "1000 / 400 / 600 / 300 / 100"],
                    ]},
                    {"type": "tableau", "titre": "Feuille « Financements »", "colonnes": ["Bailleur", "Type de bailleur", "Montant financé (FCFA)"], "lignes": [
                        ["Union européenne", "Institutionnel", "60000000"], ["Fondation Grameen", "Fondation", "30000000"],
                    ]},
                    {"type": "texte", "texte": "Une ligne par bailleur. Un bailleur inconnu est créé. Dès qu'un montant est rempli, le coût total = fonds propres + somme des financements."},
                    {"type": "tableau", "titre": "Feuille « Planification »", "colonnes": ["Colonne", "Quoi écrire"], "lignes": [
                        ["Colonnes de niveau (jaunes) : Objectif général | Objectif spécifique | Activité…", "Leurs noms sont libres. Sur chaque ligne, remplissez UNE SEULE colonne de niveau : le rattachement est déduit (dernier élément du niveau au-dessus)."],
                        ["Code activité", "Le code de l'élément de la ligne (ex. A1.1)"],
                        ["Attribut : Responsable (bleue)", "Jamais un niveau : une information sur l'élément de la ligne. Ajoutez-en (Attribut : Lieu, Attribut : Sources de vérification, Attribut : Hypothèses…)."],
                        ["Sous-activité", "Le libellé d'une tâche de l'activité au-dessus"],
                        ["Valeur de base / Budget alloué (FCFA) / Quantité prévue / Unité", "Chiffres et unité (ex. 0 / 2000000 / 300 / producteurs)"],
                        ["Date début / Date fin", "AAAA-MM-JJ"],
                        ["Commentaire", "Note libre"],
                        ["Méthode de calcul", "Liste : Par quantité, Par tâches pondérées, Par jalons pondérés, Par livrables, Binaire, Saisie manuelle"],
                        ["Poids (%)", "Pour une sous-activité en « tâches pondérées » : son poids (les poids d'une activité font 100)"],
                    ]},
                    {"type": "tableau", "titre": "Feuille « Indicateurs »", "colonnes": ["Colonne", "Quoi écrire", "Exemple"], "lignes": [
                        ["Libellé / Unité", "L'indicateur et ce qu'il mesure", "Pourcentage de ménages ayant adopté… / %"],
                        ["Valeur de référence / Valeur cible", "Chiffres", "0 / 60"],
                        ["Fréquence de collecte", "MENSUELLE, TRIMESTRIELLE, SEMESTRIELLE ou ANNUELLE", "TRIMESTRIELLE"],
                        ["Niveau de rattachement", "Aucun, Projet, ou le nom d'un niveau de la planification", "Activité"],
                        ["Nom de l'élément rattaché", "Le libellé exact de l'élément (vide si Projet)", "Former les producteurs aux techniques agroécologiques"],
                    ]},
                    {"type": "texte", "texte": "Feuille **Bénéficiaires** : même format que le modèle Bénéficiaires (leçon suivante) ; chaque personne est inscrite au projet créé. Feuille **Grilles d'alerte** (facultative) : une ligne par palier (Portée, Nom de l'élément, Seuil (%), Libellé, Couleur), ex. Projet | | 0 | Critique | #d03b3b."},
                ],
            },
            {
                "code": "projet-indicateurs-beneficiaires", "titre": "Les modèles Projet, Indicateurs et Bénéficiaires", "duree": 10,
                "objectif": "Importer séparément un projet, des indicateurs ou une liste de bénéficiaires.",
                "blocs": [
                    {"type": "texte", "texte": "**Modèle Projet** (menu Projets → Importer depuis Excel) : feuilles Projet, Financements, Planification, Grilles d'alerte et Instructions — les mêmes colonnes que dans la planification complète, avec en plus la ligne **Cadre stratégique** (nom exact d'un cadre déjà créé) dans la feuille Projet."},
                    {"type": "tableau", "titre": "Modèle Indicateurs (menu Indicateurs → Importer depuis Excel)", "colonnes": ["Colonne", "Règle"], "lignes": [
                        ["Libellé *, Unité *, Valeur cible *, Fréquence de collecte *", "Obligatoires"],
                        ["Valeur de référence", "Facultative (souvent 0)"],
                        ["Code projet", "Requis dès que le rattachement n'est pas « Aucun » : code exact d'un projet déjà créé"],
                        ["Niveau de rattachement", "Aucun (indicateur stratégique), Projet, ou nom d'un niveau tel qu'il est nommé dans le projet"],
                        ["Nom de l'élément rattaché", "Vide pour « Projet » ; sinon libellé exact de l'élément"],
                    ]},
                    capture("m5-import", "Importer des bénéficiaires depuis Excel.",
                            "**Télécharger le modèle Excel**, remplissez-le, puis **Fichier à importer** → **Importer**."),
                    {"type": "tableau", "titre": "Modèle Bénéficiaires (menu Bénéficiaires → Importer depuis Excel)", "colonnes": ["Colonne", "Règle", "Exemple"], "lignes": [
                        ["Nom *, Prénom *, Sexe *", "Obligatoires ; Sexe = F ou M", "Traoré | Awa | F"],
                        ["Pays", "Code ISO (BF par défaut si vide)", "BF"],
                        ["Région, Province, Commune", "Noms connus de la plateforme (menu Zones administratives) ; une commune inconnue est créée", "Kadiogo | Kadiogo | Koubri"],
                        ["Date de naissance", "AAAA-MM-JJ", "1990-05-12"],
                        ["Téléphone, N° pièce d'identité, Type de pièce", "Facultatifs", "70000001 | CNIB123456 | CNIB"],
                        ["Statuts particuliers", "Séparés par ;", "Femme;Jeune"],
                        ["Types d'activité menée", "Séparés par ; — un type inconnu est ignoré (créez-le d'abord)", "Maraîchage"],
                        ["Latitude, Longitude", "Degrés décimaux (facultatif)", "12.3714 | -1.5197"],
                        ["Code projet", "Code exact d'un projet : la personne y est inscrite", "PRJ-2026-001"],
                        ["Colonnes de vos variables", "Celles choisies dans « Variables à collecter » (ex. Taille du ménage, Source principale d'eau) ; « NA » si sans objet", "6 | Forage"],
                    ]},
                    {"type": "attention", "texte": "Pour les bénéficiaires, **ne modifiez ni l'ordre ni le nom des colonnes**. Les doublons possibles sont signalés automatiquement après l'import (menu Doublons d'enregistrement)."},
                ],
            },
            {
                "code": "canevas-suivi", "titre": "Le canevas de suivi : saisir les réalisations par Excel", "duree": 10,
                "objectif": "Télécharger le canevas prérempli d'un projet, saisir quantités, budgets et valeurs d'indicateurs, l'importer.",
                "blocs": [
                    capture("m4-saisie-excel", "Menu Suivi → un projet → Saisie par Excel.",
                            "1) **Télécharger le canevas de suivi** : il est prérempli avec la planification du projet et ses indicateurs. 2) Complétez les colonnes **bleues**. 3) **Canevas complété** : choisissez le fichier ; **Saisies déjà existantes** : « Conserver (ajouter seulement) » ou « Mettre à jour » ; puis **Analyser** : un aperçu montre ce qui sera ajouté ou modifié avant validation."),
                    {"type": "tableau", "titre": "Feuille « Suivi »", "colonnes": ["Colonne", "À faire"], "lignes": [
                        ["Identifiant, Niveau, Code, Libellé, Méthode, Unité, Quantité prévue, Réalisé cumulé, Taux actuel (gris)", "Ne pas modifier : ils relient la ligne à la plateforme"],
                        ["Période début / Période fin", "Les dates de la période saisie (AAAA-MM-JJ)"],
                        ["Quantité réalisée sur la période", "Ce qui a été fait PENDANT la période (pas un cumul)"],
                        ["Budget réalisé sur la période (FCFA)", "Les dépenses de la période (éléments seulement)"],
                        ["Statut", "Non démarré, En cours, Réalisé…"],
                        ["Taux manuel (%)", "Seulement pour un élément en « Saisie manuelle » (0 à 100)"],
                        ["Avancement (%) / Poids (%)", "Pour les sous-activités en « tâches pondérées »"],
                        ["Commentaire", "Note libre"],
                    ]},
                    {"type": "tableau", "titre": "Feuilles « Jalons et livrables » et « Indicateurs »", "colonnes": ["Feuille", "À faire"], "lignes": [
                        ["Jalons et livrables", "Modifiez Poids, Achèvement (%) ou Validé (Oui/Non). Pour en ajouter un : laissez l'identifiant vide, indiquez l'identifiant de l'élément (Exx), le type (Jalon/Livrable) et le libellé."],
                        ["Indicateurs", "Période début / fin, puis Valeur réalisée sur la période (ce qui a été atteint PENDANT la période), Commentaire."],
                    ]},
                    {"type": "astuce", "texte": "Une ligne sans saisie est ignorée : vous pouvez ne remplir que les activités qui ont avancé. En mode « Conserver », une saisie déjà existante pour la même période n'est jamais remplacée ; en mode « Mettre à jour », elle l'est, avec une trace dans l'historique."},
                    {"type": "exercice", "items": ["Téléchargez le canevas de suivi d'un de vos projets, saisissez la quantité réalisée d'une activité pour le mois dernier, puis importez-le en regardant l'aperçu."]},
                ],
            },
            {
                "code": "structure-excel", "titre": "Importer la structure d'une stratégie", "duree": 5,
                "objectif": "Remplir la structure d'une stratégie avec le modèle « Structuration ».",
                "blocs": [
                    capture("m2-import", "Page d'une stratégie → Importer depuis Excel.",
                            "**Télécharger le modèle Excel**, remplissez-le, puis importez-le depuis la même fenêtre."),
                    {"type": "etapes", "items": [
                        "Une colonne = un niveau, de gauche à droite (en jaune). Ajoutez une colonne pour un niveau plus fin ; un niveau qui n'existe pas encore est créé.",
                        "Sur chaque ligne, écrivez le nom de l'élément dans UNE SEULE colonne : celle de son niveau.",
                        "Le parent est le dernier élément écrit au-dessus, dans la colonne juste à gauche (ex. un « Axe d'intervention » se rattache au dernier « Orientation stratégique » au-dessus).",
                        "Dernière colonne facultative **Contribue à (code)** : le code d'un élément d'un document du maillon au-dessus auquel l'élément contribue.",
                    ]},
                    {"type": "tableau", "titre": "Exemple de feuille « Structuration »", "colonnes": ["Axe stratégique", "Objectif stratégique", "Effet attendu"], "lignes": [
                        ["Développer le capital humain", "", ""], ["", "Améliorer l'accès à l'éducation de base", ""],
                        ["", "", "Les capacités d'accueil des écoles sont renforcées"], ["", "", "Les enfants hors école sont réinsérés"],
                    ]},
                ],
            },
        ],
        "quiz": [
            {"question": "Comment écrit-on une date dans un canevas Excel ?", "choix": ["31/03/2026", "2026-03-31", "31 mars 2026"], "bonne": 1, "explication": "Toujours AAAA-MM-JJ."},
            {"question": "Dans la feuille Planification, combien de colonnes de niveau remplit-on par ligne ?", "choix": ["Toutes", "Une seule : celle du niveau de l'élément", "Aucune"], "bonne": 1,
             "explication": "Le rattachement est déduit du dernier élément du niveau au-dessus."},
            {"question": "Une colonne « Attribut : Lieu » placée avant « Sous-activité »…", "choix": [
                "devient un niveau", "est une information sur l'élément de la ligne, jamais un niveau", "fait échouer l'import"], "bonne": 1,
             "explication": "Les colonnes « Attribut : … » ne sont jamais des niveaux."},
            {"question": "Dans le canevas de suivi, « Quantité réalisée sur la période » c'est…", "choix": [
                "le cumul depuis le début du projet", "ce qui a été fait pendant la période indiquée", "la cible"], "bonne": 1,
             "explication": "Jamais un cumul : seulement la période."},
            {"question": "Quelle feuille est obligatoire dans la planification complète ?", "choix": ["Bénéficiaires", "Projet", "Grilles d'alerte"], "bonne": 1,
             "explication": "Seule la feuille Projet (nom, code, dates) est obligatoire."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "indicateurs-suivi", "titre": "Indicateurs, suivi et approbations", "icone": "Gauge",
        "description": "Créer un indicateur, fixer ses cibles par période, saisir les réalisations et les valeurs, les faire approuver.",
        "lecons": [
            {
                "code": "creer-indicateur", "titre": "Créer un indicateur", "duree": 7,
                "objectif": "Créer un indicateur et le rattacher au projet ou à une activité.",
                "blocs": [
                    capture("m4-liste", "Le menu Indicateurs.",
                            "Cliquez sur **Indicateurs** dans le menu. En haut, les compteurs Conforme / Critique servent de filtres.",
                            "Cliquez sur **Nouvel indicateur**.",
                            "**Importer depuis Excel** : pour en créer beaucoup d'un coup (voir le module Excel)."),
                    capture("m4-nouveau", "La fenêtre « Nouvel indicateur ».",
                            "**Libellé** (obligatoire) : ce que mesure l'indicateur, ex. « Nombre de bénéficiaires directs touchés par le projet ».",
                            "**Unité** (obligatoire) : personnes, %, écoles…",
                            "**Valeur de base** : la situation de départ (souvent 0).",
                            "**Valeur cible** (obligatoire) : ce qu'il faut atteindre, ex. 7800."),
                    capture("m4-nouveau-suite", "Suite de la fenêtre.",
                            "**Fréquence de collecte** (obligatoire) : mensuelle, trimestrielle, semestrielle ou annuelle.",
                            "**Rattaché à** : cherchez et choisissez le projet, ou un élément précis de sa planification (une activité…). Vide = indicateur stratégique sans projet. **Éléments stratégiques rattachés** : facultatif.",
                            "Cliquez sur **Créer**."),
                ],
            },
            {
                "code": "cibles", "titre": "Fixer les cibles par période", "duree": 5,
                "objectif": "Découper la cible d'un indicateur par année ou par trimestre.",
                "blocs": [
                    capture("m4-fiche", "La fiche d'un indicateur (clic sur son nom dans la liste), partie « Suivi détaillé par période ».",
                            "**Période** : le nom de la tranche, ex. « Année 2027 » ou « T1 2026 ».",
                            "**Du** : la date de début de la tranche.",
                            "**Au** : la date de fin.",
                            "**Cible** : ce qu'il faut atteindre pendant cette tranche.",
                            "**+ Ajouter** : la tranche s'ajoute au tableau, qui montre ensuite sa progression et son statut (En cours, En retard…)."),
                    {"type": "astuce", "texte": "En bas, « Somme des cibles de toutes les tranches » se compare à la cible globale : elles doivent correspondre."},
                ],
            },
            {
                "code": "saisir", "titre": "Saisir les réalisations et les valeurs", "duree": 10,
                "objectif": "Saisir ce qui a été réalisé pour une activité et la valeur atteinte par un indicateur.",
                "blocs": [
                    capture("m4-suivi-liste", "Le menu Suivi.",
                            "Cliquez sur **Suivi** dans le menu.",
                            "Choisissez le projet dans la liste (un clic sur sa ligne)."),
                    capture("m4-suivi-projet", "Le suivi d'un projet.",
                            "**Suivi global** : toutes les activités et les indicateurs, avec l'exécution physique et financière.",
                            "**Suivi par période** : la même chose, limitée à une période de planification.",
                            "**Saisir un suivi** sur la carte d'une activité ouvre la saisie."),
                    capture("m4-saisir-suivi", "La fenêtre « Saisir un suivi ».",
                            "Remplissez **Début de période** et **Fin de période** (obligatoires), la **quantité réalisée pendant cette période** (pas un cumul), le **Budget dépensé pendant cette période (FCFA)**, le **Statut à cette date** et un **Commentaire**, puis **Enregistrer**. **Ajouter un document** joint une preuve (photo, liste de présence…)."),
                    {"type": "texte", "texte": "Pour une activité « agrégée » (calculée à partir des éléments en dessous), la fenêtre ne demande que le budget, le statut et le commentaire : son taux vient des éléments en dessous."},
                    capture("m4-suivi-indicateurs", "Plus bas dans la même page : les indicateurs.",
                            "**Saisir une valeur** sur la carte d'un indicateur."),
                    capture("m4-saisir-valeur", "La fenêtre « Nouvelle saisie — indicateur ».",
                            "**Début de période**, **Fin de période**, puis **Valeur réalisée pendant cette période** (ce qui a été atteint entre ces deux dates, pas le total), un **Commentaire** et une **Pièce justificative (optionnel)** ; **Enregistrer**."),
                    {"type": "video", "chapitre": "indicateurs"},
                    {"type": "exercice", "items": ["Saisissez le réalisé du mois dernier pour une activité de votre projet, puis la valeur d'un indicateur avec une pièce justificative."]},
                ],
            },
            {
                "code": "approbations", "titre": "Approbations et seuils d'alerte", "duree": 6,
                "objectif": "Approuver les saisies en attente et comprendre les seuils conforme / à risque / critique.",
                "blocs": [
                    capture("m4-approbations", "Le menu Approbations.",
                            "Cliquez sur **Approbations**. Deux listes : **Saisies de réalisations** et **Changements de planification** en attente (seulement pour les projets qui l'exigent). Pour chaque demande : **Approuver**, ou rejeter avec un motif qui est montré à l'auteur."),
                    capture("m4-seuils", "Paramètres d'alerte (administrateur).",
                            "Menu **Paramètres d'alerte** : la **méthode de calcul par défaut** des taux, l'**agrégation par défaut**, le plafonnement à 100 %, les **périodes de rapportage**, et la grille des paliers (ex. moins de 50 % = Critique, 50 à 80 % = À risque, plus de 80 % = Conforme) avec leurs couleurs."),
                ],
            },
        ],
        "quiz": [
            {"question": "Quels champs sont obligatoires pour créer un indicateur ?", "choix": [
                "Libellé, Unité, Valeur cible et Fréquence de collecte", "Seulement le libellé", "Le projet et la photo"], "bonne": 0, "explication": "Ces quatre champs sont marqués d'un astérisque."},
            {"question": "Où découpe-t-on la cible d'un indicateur par année ?", "choix": [
                "Fiche de l'indicateur → Suivi détaillé par période → Ajouter", "Dans le tableau de bord", "Dans le menu Organisation"], "bonne": 0,
             "explication": "Une ligne par période, avec sa cible."},
            {"question": "Dans « Saisir un suivi », la quantité à saisir est…", "choix": [
                "le cumul depuis le début", "ce qui a été fait pendant la période indiquée", "la cible"], "bonne": 1, "explication": "Toujours la période seulement."},
            {"question": "Où saisit-on la valeur atteinte par un indicateur ?", "choix": [
                "Menu Suivi → le projet → Saisir une valeur sur la carte de l'indicateur", "Menu Utilisateurs", "Dans la Corbeille"], "bonne": 0,
             "explication": "Les valeurs se saisissent dans le suivi du projet."},
            {"question": "Où approuve-t-on une saisie en attente ?", "choix": ["Menu Approbations", "Menu Cartographie", "Page de connexion"], "bonne": 0, "explication": "Approuver, ou rejeter avec un motif."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "beneficiaires-carte", "titre": "Bénéficiaires et carte", "icone": "MapPinned",
        "description": "Enregistrer un bénéficiaire, choisir les variables à collecter, traiter les doublons, lire et télécharger la carte.",
        "lecons": [
            {
                "code": "enregistrer", "titre": "Enregistrer un bénéficiaire", "duree": 8,
                "objectif": "Ajouter une personne au registre avec sa localisation et ses informations.",
                "blocs": [
                    capture("m5-liste", "Le menu Bénéficiaires.",
                            "Cliquez sur **Bénéficiaires** dans le menu : le registre est rangé projet par projet.",
                            "**Nouveau bénéficiaire** ouvre le formulaire.",
                            "**Importer depuis Excel** : pour une liste entière (voir le module Excel).",
                            "**Variables à collecter** (administrateur) : choisir les informations demandées pour chaque personne (taille du ménage, source d'eau…)."),
                    capture("m5-nouveau", "Le formulaire « Nouveau bénéficiaire ».",
                            "**Nom** (obligatoire).",
                            "**Prénom** (obligatoire).",
                            "**Sexe** : Féminin ou Masculin.",
                            "**Téléphone**. Au-dessus : **Pays**, **Région**, **Province**, **Commune** (choisissez dans les listes) et **Latitude / Longitude** (ou le bouton **Ma position actuelle** sur téléphone)."),
                    {"type": "texte", "texte": "Plus bas : **Date de naissance**, **N° pièce d'identité**, **Statuts particuliers** (PDI, jeune, femme cheffe de ménage… ; tapez un nouveau statut puis **+ Ajouter**), vos variables, et le **projet** auquel inscrire la personne. Cliquez sur **Créer** (ou **Ajouter un autre bénéficiaire** pour enchaîner)."},
                    {"type": "astuce", "texte": "Chaque personne reçoit un **identifiant unique** et un **QR code** ; « Imprimer les cartes de ce projet » produit les cartes de bénéficiaire à distribuer."},
                ],
            },
            {
                "code": "doublons", "titre": "Les doublons d'enregistrement", "duree": 3,
                "objectif": "Repérer et régler les personnes enregistrées deux fois.",
                "blocs": [
                    capture("m5-doublons", "Le menu Doublons d'enregistrement.",
                            "Cliquez sur **Doublons d'enregistrement** : la plateforme rapproche les personnes qui se ressemblent (nom, prénom, date de naissance, téléphone, pièce). Pour chaque paire, vérifiez et gardez la bonne fiche."),
                ],
            },
            {
                "code": "carte", "titre": "Lire et télécharger la carte", "duree": 8,
                "objectif": "Filtrer la carte, choisir couches et fond, et la télécharger en PDF ou en image.",
                "blocs": [
                    capture("m5-carte", "Le menu Cartographie.",
                            "**Période** : Toutes, Année ou Plage de dates ; à côté, **Statut des projets**.",
                            "**Tous les projets** / **Toutes les zones** : limitez la carte à un projet ou une zone. Les compteurs (bénéficiaires, positionnés par GPS, placés selon leur localité, sans localisation) suivent les filtres.",
                            "**Importer une couche** : ajoutez vos données (Shapefile en .zip, GeoPackage, GeoJSON ou KML).",
                            "**Télécharger la carte**."),
                    {"type": "texte", "texte": "Sous les filtres : **Couches** (Bénéficiaires, Régions, Provinces, Routes, Villes et villages, Noms… — la croix retire une couche, la liste en ajoute), **Par zone** (colorer les zones selon des indicateurs : projets, bénéficiaires, budget, dépenses, taux d'exécution…) et **Fond** (Neutre, OpenStreetMap, Satellite, Aucun). Molette ou + / − pour zoomer."},
                    {"type": "video", "chapitre": "carte"},
                    capture("m5-carte-telecharger", "La fenêtre « Télécharger la carte ».",
                            "Remplissez **Titre de la carte** et **Sous-titre** (obligatoires), choisissez le **Format papier** (A4, A3, A1, A0), l'**Orientation**, le **Fichier** (PDF ou Image PNG), l'**Étendue** (tout le pays ou autour des bénéficiaires), le **Fond** et les **Couches**, puis **Télécharger**. La carte sort à l'échelle, avec grille de coordonnées, légende, chiffres clés et tableau des localités."),
                    {"type": "exercice", "items": ["Affichez la carte d'un seul de vos projets sur fond Satellite, puis téléchargez-la en PDF A4 avec un titre."]},
                ],
            },
        ],
        "quiz": [
            {"question": "Quels champs sont obligatoires pour un nouveau bénéficiaire ?", "choix": ["Nom et Prénom (et le sexe)", "Le téléphone", "La photo"], "bonne": 0, "explication": "Nom, Prénom et Sexe."},
            {"question": "Qui choisit les informations demandées pour chaque bénéficiaire ?", "choix": [
                "L'administrateur, dans « Variables à collecter »", "Le bénéficiaire", "Personne"], "bonne": 0, "explication": "Bouton Variables à collecter."},
            {"question": "Que signale « Doublons d'enregistrement » ?", "choix": ["Les projets en double", "Les personnes enregistrées deux fois", "Les cartes imprimées"], "bonne": 1,
             "explication": "Il rapproche les fiches qui se ressemblent."},
            {"question": "Dans « Télécharger la carte », quels champs faut-il remplir obligatoirement ?", "choix": ["Titre et Sous-titre", "Aucun", "Le nom du bailleur"], "bonne": 0,
             "explication": "Titre et sous-titre apparaissent sur la carte."},
            {"question": "Quels fichiers peut-on importer comme couche ?", "choix": ["Word", "Shapefile (.zip), GeoPackage, GeoJSON ou KML", "PDF"], "bonne": 1,
             "explication": "Les formats cartographiques courants."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "documents", "titre": "Documents, partage et corbeille", "icone": "FolderOpen",
        "description": "Ajouter et ranger les documents, gérer leurs versions, les partager par lien, les restaurer.",
        "lecons": [
            {
                "code": "ajouter", "titre": "Ajouter et ranger un document", "duree": 6,
                "objectif": "Créer un dossier, ajouter un document, le déplacer.",
                "blocs": [
                    capture("m6-documents-projet", "Onglet Documents d'un projet.",
                            "Dans un projet, ouvrez l'onglet **Documents** (le menu **Documents** donne la bibliothèque libre, sans projet).",
                            "**Nouveau dossier** : tapez son nom, ex. « 02 - Rapports ». Un clic sur un dossier l'ouvre ; le fil « Documents › 02 - Rapports » permet de remonter.",
                            "**Ajouter un document** ouvre la fenêtre ci-dessous."),
                    capture("m6-ajouter", "La fenêtre « Nouveau document ».",
                            "**Fichier** (obligatoire) : cliquez et choisissez le fichier sur votre ordinateur. **Nom du document** (sinon, le nom du fichier) et **Type** (ex. Rapport bailleur) sont facultatifs. Cliquez sur **Ajouter**."),
                    {"type": "astuce", "texte": "Les petites icônes en haut à droite passent de l'affichage en **grille** à l'affichage en **liste**. Cochez plusieurs éléments (ou « Tout sélectionner ») pour les **télécharger en zip** ou les **supprimer** d'un coup."},
                ],
            },
            {
                "code": "menu-document", "titre": "Le menu d'un document : versions, renommer, déplacer", "duree": 5,
                "objectif": "Utiliser le menu « … » d'un document.",
                "blocs": [
                    capture("m6-dans-dossier", "Un document dans un dossier.", "Les **trois points** en haut à droite d'un document ouvrent son menu. Un clic sur le document lui-même l'ouvre."),
                    capture("m6-menu-document", "Le menu d'un document.",
                            "**Partager par lien** : voir la leçon suivante.",
                            "**Versions** : déposez une nouvelle version (l'ancienne est gardée) et retrouvez les précédentes. Dessous : **Renommer** et **Déplacer** (vers un autre dossier).",
                            "**Supprimer** : le document va dans la Corbeille (30 jours)."),
                ],
            },
            {
                "code": "partager", "titre": "Partager un document par lien", "duree": 7,
                "objectif": "Envoyer un document à une personne sans compte, avec droit, expiration et mot de passe.",
                "blocs": [
                    capture("m6-partager", "La fenêtre « Partager … par lien ».",
                            "Choisissez le droit : **Consulter seulement** (voir dans le navigateur) ou **Consulter et télécharger**.",
                            "**Pour qui ?** (facultatif) : ex. « Bailleur — rapport annuel », pour vous y retrouver.",
                            "**Expire dans** : 1 jour, **7 jours**, 30 jours ou **Date précise** (au plus un an).",
                            "**Mot de passe** (facultatif) : demandé à l'ouverture. À côté : **Nombre d'ouvertures** (vide = sans limite).",
                            "Cliquez sur **Créer le lien**, puis sur l'icône de copie, et collez le lien dans votre courriel ou message."),
                    {"type": "attention", "texte": "Envoyez le **mot de passe séparément** (téléphone, autre message), jamais avec le lien. « Consulter seulement » enlève le bouton de téléchargement, mais un document affiché peut toujours être photographié."},
                    {"type": "texte", "texte": "La liste **Liens de ce document** montre chaque lien : pour qui, droit, date d'expiration, nombre d'ouvertures et état (Actif, Expiré, Ouvertures épuisées, Révoqué). L'icône rouge **Révoquer** coupe l'accès immédiatement."},
                    {"type": "exercice", "items": ["Partagez un document en « Consulter seulement » pour 1 jour avec un mot de passe, ouvrez le lien dans une fenêtre de navigation privée, puis révoquez-le."]},
                ],
            },
            {
                "code": "corbeille", "titre": "La corbeille", "duree": 3,
                "objectif": "Restaurer un élément supprimé par erreur.",
                "blocs": [
                    capture("m6-corbeille", "Le menu Corbeille.",
                            "Cliquez sur **Corbeille** (en bas du menu) : ce qui a été supprimé y reste **30 jours**. Cochez un élément puis **Restaurer** (il revient à sa place) ou **Supprimer définitivement** ; **Vider** efface tout. Après 30 jours, l'effacement est automatique."),
                ],
            },
        ],
        "quiz": [
            {"question": "Comment ajouter un document à un projet ?", "choix": [
                "Onglet Documents du projet → Ajouter un document → choisir le fichier → Ajouter", "Par courriel à Expertise-ID", "Dans le menu Cartographie"], "bonne": 0,
             "explication": "Le champ Fichier est obligatoire."},
            {"question": "Où trouve-t-on « Partager par lien » ?", "choix": ["Dans le menu « … » du document", "Dans le tableau de bord", "Dans les paramètres d'alerte"], "bonne": 0,
             "explication": "Les trois points en haut à droite du document."},
            {"question": "Comment envoyer le mot de passe d'un lien de partage ?", "choix": ["Dans le même message que le lien", "Séparément (téléphone, autre message)", "On ne peut pas"], "bonne": 1,
             "explication": "Lien et mot de passe ne voyagent jamais ensemble."},
            {"question": "Que fait « Révoquer » ?", "choix": ["Prolonge le lien", "Coupe l'accès immédiatement", "Supprime le document"], "bonne": 1,
             "explication": "Le document lui-même reste dans la plateforme."},
            {"question": "Combien de temps un document supprimé reste-t-il récupérable ?", "choix": ["7 jours", "30 jours", "1 an"], "bonne": 1, "explication": "30 jours dans la Corbeille."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "plaintes", "titre": "Plaintes et retours des communautés", "icone": "MessagesSquare",
        "description": "Enregistrer un retour, classer, affecter, faire avancer et clôturer un dossier.",
        "lecons": [
            {
                "code": "enregistrer", "titre": "Recevoir et enregistrer un retour", "duree": 8,
                "objectif": "Enregistrer une plainte reçue par téléphone, en visite ou en réunion ; connaître le formulaire public.",
                "blocs": [
                    capture("m7-dossiers", "Le menu Plaintes et retours.",
                            "Cliquez sur **Plaintes et retours**. À gauche, les files de travail (Tous, Mes dossiers, À traiter, Urgents, En retard, Sans responsable, Confidentiels…) ; en haut, les onglets **Dossiers**, **Tableau de bord**, **Actions correctives**, **Paramétrage**.",
                            "**Enregistrer un retour** : pour saisir une plainte reçue directement. (**Formulaire public** : le lien et le QR code du formulaire en ligne, à afficher ou distribuer.)"),
                    capture("m7-enregistrer", "La fenêtre « Enregistrer un retour ».",
                            "Remplissez **Canal de réception** (obligatoire : téléphone, visite, réunion, boîte à suggestions…), **Date de réception**, **Priorité**, cochez **Recueilli directement auprès du plaignant** si c'est le cas, choisissez le **Type de retour** (Plainte, Suggestion, Question, Remerciement, Signalement), la **Catégorie**, le **Projet concerné**, le **Lieu**, puis écrivez la **Description du retour** (obligatoire). Plus bas : les coordonnées du plaignant (ou anonymat) et les pièces jointes. **Enregistrer**."),
                    {"type": "texte", "texte": "Le plaignant reçoit un **numéro de dossier** et un **code de suivi** pour suivre sa demande en ligne, sans compte. Un retour sensible (exploitation, abus, fraude…) part automatiquement dans le **circuit confidentiel**."},
                    {"type": "video", "chapitre": "plaintes"},
                ],
            },
            {
                "code": "traiter", "titre": "Traiter un dossier jusqu'à la clôture", "duree": 10,
                "objectif": "Classer, affecter, changer d'étape, décider et clôturer.",
                "blocs": [
                    capture("m7-dossier", "La fiche d'un dossier (clic sur son numéro).",
                            "**Classer** : type, priorité, catégorie, projet.",
                            "**Affecter** (ou **Réaffecter**) : choisir le gestionnaire du dossier.",
                            "**Changer d'étape** : faire avancer le dossier dans son circuit (Réception → Traitement → Retour au plaignant…).",
                            "**Clôturer** : terminer le dossier. Autres boutons : **Note**, **Envoyer un message** au plaignant, **Échange avec le plaignant**, **Décision**, **Prolonger le délai**, **Lier** à un autre dossier, **Exporter (PDF)**."),
                    capture("m7-classer", "« Classer le dossier ».", "Choisissez **Type de retour**, **Priorité**, **Catégorie** et **Projet**, puis **Enregistrer**."),
                    capture("m7-affecter", "« Affecter le dossier ».", "Choisissez le **Gestionnaire du dossier** puis **Enregistrer** : il reçoit une notification."),
                    capture("m7-cloturer", "« Clôturer le dossier ».",
                            "Choisissez l'**Issue** (Réponse apportée, Référée, Hors périmètre…), écrivez la **Décision** et le **Motif de la clôture** (obligatoires), répondez à « **Le plaignant a-t-il été informé de la réponse ?** » (Oui / Non), puis **Clôturer**."),
                    {"type": "attention", "texte": "Chaque étape a un délai : un rappel part quand l'échéance approche ; en retard, le dossier est signalé (file « En retard ») et l'alerte remonte aux superviseurs. À droite de la fiche, le **Journal du dossier** garde toutes les actions."},
                    {"type": "exercice", "items": ["Ouvrez la file « Sans responsable » et affectez un dossier (si vous en avez le droit).", "Ouvrez le Tableau de bord des plaintes et repérez les dossiers en retard."]},
                ],
            },
        ],
        "quiz": [
            {"question": "Quels champs faut-il remplir au minimum pour enregistrer un retour ?", "choix": [
                "Canal de réception, Type de retour et Description du retour", "Seulement la date", "Le nom du bailleur"], "bonne": 0,
             "explication": "Ils sont marqués d'un astérisque."},
            {"question": "À quoi sert le code de suivi remis au plaignant ?", "choix": ["À se connecter à la plateforme", "À suivre sa demande en ligne, sans compte", "À payer"], "bonne": 1,
             "explication": "Il suit sa demande sur la page publique."},
            {"question": "Qui reçoit une notification quand vous cliquez sur « Affecter » ?", "choix": ["Le bailleur", "Le gestionnaire choisi", "Personne"], "bonne": 1,
             "explication": "Le gestionnaire est prévenu."},
            {"question": "Que faut-il pour clôturer ?", "choix": ["Rien", "Issue, Décision, Motif de la clôture et l'information du plaignant", "L'accord du bailleur"], "bonne": 1,
             "explication": "Décision et motif sont obligatoires."},
            {"question": "Où voit-on l'historique de toutes les actions d'un dossier ?", "choix": ["Dans le Journal du dossier, à droite de la fiche", "Dans la Corbeille", "Nulle part"], "bonne": 0,
             "explication": "Le journal garde chaque action."},
        ],
    },
    # ------------------------------------------------------------------------------------------------
    {
        "code": "administration", "titre": "Administrer son espace", "icone": "Settings",
        "description": "Créer les comptes et régler les droits, mettre le logo, personnaliser le menu, consulter le journal d'audit.",
        "lecons": [
            {
                "code": "utilisateurs", "titre": "Créer un compte et régler ses droits", "duree": 10,
                "objectif": "Donner accès à un collègue, avec le bon rôle et le bon niveau d'accès.",
                "blocs": [
                    capture("m8-utilisateurs", "Le menu Utilisateurs (administrateur).",
                            "Cliquez sur **Utilisateurs**.",
                            "**Nouvel utilisateur** ouvre le formulaire.",
                            "L'onglet **Rôles** permet de créer ou renommer des rôles et de dire ce que chacun voit."),
                    capture("m8-nouvel-utilisateur", "La fenêtre « Nouvel utilisateur ».",
                            "**Identifiant** (obligatoire), **Prénom**, **Nom** et **Adresse courriel** (obligatoire : c'est avec elle que la personne se connecte et reçoit son code ; une adresse ne peut appartenir qu'à un seul compte).",
                            "**Rôle** : ce que la personne **voit** (tous les projets, ou seulement ceux auxquels elle est affectée).",
                            "**Niveau d'accès** : **Consulter seulement** ou **Créer et modifier**.",
                            "**Mot de passe** (obligatoire) : communiquez-le à la personne, qui le changera. Puis **Créer**."),
                    {"type": "texte", "texte": "Pour modifier un compte : crayon de sa ligne. **Droits par module** permet de masquer un module ou de le mettre en consultation seule pour une personne. L'**Administrateur** a toujours accès à tout. Un collègue ne voit pas un projet ? Ajoutez-le dans « Utilisateurs affectés » du projet."},
                ],
            },
            {
                "code": "personnaliser", "titre": "Logo, menu et journal d'audit", "duree": 7,
                "objectif": "Mettre le logo de l'organisation, renommer les rubriques du menu, consulter les traces.",
                "blocs": [
                    capture("m8-identite", "Organisation › Identité et logo.",
                            "Menu **Organisation**, onglet **Identité et logo**.",
                            "**Nouveau logo** : choisissez une image (PNG, JPEG ou WebP, 2 Mo au plus ; un logo horizontal sur fond transparent ou blanc rend mieux), corrigez si besoin le **Nom affiché de l'organisation**, puis **Enregistrer**. Le logo apparaît en haut de toutes les pages."),
                    capture("m8-menu", "« Personnaliser le menu » (en bas du menu).",
                            "Onglet **Menu** : pour chaque rubrique, tapez le nom utilisé dans votre organisation et cliquez sur l'icône pour la changer ; la flèche ronde revient au nom par défaut. Onglet **Vocabulaire** : adaptez les mots de toute la plateforme (projet, activité…)."),
                    capture("m8-journal", "Le journal d'audit (administrateur).",
                            "Menu **Journal d'audit** : connexions, consultations sensibles, actions sur les dossiers, exports, changements de droits et partages, sans modification possible. Filtrez par **Action**, **Personne**, **Objet**, **Du** / **Au**.",
                            "**Exporter (Excel)** télécharge les événements filtrés."),
                    {"type": "exercice", "items": ["Vérifiez le logo de votre organisation.", "Ouvrez le journal d'audit et filtrez les connexions de la semaine."]},
                ],
            },
        ],
        "quiz": [
            {"question": "Pourquoi l'adresse courriel d'un compte est-elle obligatoire ?", "choix": [
                "Pour envoyer des publicités", "C'est avec elle que la personne se connecte et reçoit son code", "Elle ne l'est pas"], "bonne": 1,
             "explication": "Une adresse ne peut appartenir qu'à un seul compte."},
            {"question": "Que règle le rôle d'un utilisateur ?", "choix": ["Sa langue", "Ce qu'il voit : tous les projets ou ceux auxquels il est affecté", "Sa photo"], "bonne": 1,
             "explication": "Le niveau d'accès, lui, règle la modification."},
            {"question": "Un collègue doit voir les projets sans pouvoir rien changer. Quel niveau d'accès ?", "choix": ["Consulter seulement", "Créer et modifier", "Administrateur"], "bonne": 0,
             "explication": "Consulter seulement."},
            {"question": "Où met-on le logo de l'organisation ?", "choix": ["Organisation › Identité et logo → Nouveau logo → Enregistrer", "Dans un projet", "Dans la Corbeille"], "bonne": 0,
             "explication": "Il s'affiche ensuite sur toutes les pages."},
            {"question": "Peut-on modifier ou effacer une ligne du journal d'audit ?", "choix": ["Oui, l'administrateur peut", "Non, jamais", "Seulement le lundi"], "bonne": 1,
             "explication": "Le journal est en ajout uniquement."},
        ],
    },
]

PAR_CODE = {m["code"]: m for m in MODULES}
LECONS = {lecon["code"]: (m, lecon) for m in MODULES for lecon in m["lecons"]}
