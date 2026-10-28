# Documentation technique — Plateforme de Suivi-Évaluation

Ce document décrit le fonctionnement interne de la plateforme : architecture, modèle de
données, règles métier, API, frontend, sécurité, imports et exports, exploitation. Pour
l'installation, voir le [README](../README.md).

## Sommaire

1. [Architecture générale](#1-architecture-générale)
2. [Services Docker et configuration](#2-services-docker-et-configuration)
3. [Backend : organisation](#3-backend--organisation)
4. [Modèle de données](#4-modèle-de-données)
5. [Règles métier essentielles](#5-règles-métier-essentielles)
6. [Utilisateurs, rôles et permissions](#6-utilisateurs-rôles-et-permissions)
7. [API REST](#7-api-rest)
8. [Imports et exports](#8-imports-et-exports)
9. [Notifications et échéances](#9-notifications-et-échéances)
10. [Frontend](#10-frontend)
11. [Commandes de gestion](#11-commandes-de-gestion)
12. [Tests et contrôles qualité](#12-tests-et-contrôles-qualité)
13. [Conventions de développement](#13-conventions-de-développement)
14. [Mise en production](#14-mise-en-production)
15. [Dépannage](#15-dépannage)

---

## 1. Architecture générale

```
┌────────────────────┐   HTTP/JSON + JWT   ┌──────────────────────┐    SQL    ┌──────────────┐
│ Frontend React     │ ──────────────────► │ Backend Django / DRF │ ────────► │ PostgreSQL 16│
│ (Vite, Mantine)    │ ◄────────────────── │ API /api/v1/         │ ◄──────── │              │
└────────────────────┘                     └──────────────────────┘           └──────────────┘
                                                      ▲
                                           ┌──────────┴───────────┐
                                           │ scheduler            │
                                           │ check_deadlines / 1h │
                                           └──────────────────────┘
```

- Le **frontend** est une application monopage (SPA) qui ne parle qu'à l'API REST.
- Le **backend** expose une API REST versionnée (`/api/v1/`), documentée automatiquement
  au format OpenAPI. Il porte toute la logique métier : calculs, imports, exports Excel et
  PDF, notifications.
- Le **scheduler** est un second conteneur basé sur la même image que le backend ; il
  exécute toutes les heures la vérification des échéances.
- Toutes les modifications des données métier sont historisées (django-simple-history).

## 2. Services Docker et configuration

| Service | Rôle | Port hôte → conteneur |
|---|---|---|
| `db` | PostgreSQL 16, volume persistant `suivi-evaluation-2-pgdata` | 5443 → 5432 |
| `backend` | Django (`manage.py runserver`), code monté depuis `./backend` | 8092 → 8000 |
| `scheduler` | Boucle `check_deadlines` toutes les heures | — |
| `frontend` | Serveur de développement Vite, code monté depuis `./frontend` | 5191 → 5173 |

Le backend et le frontend se rechargent automatiquement à chaque modification du code.
Un redémarrage (`docker compose restart <service>`) n'est utile qu'après un changement
du fichier `.env`.

### Variables d'environnement (`.env`)

| Variable | Rôle | Valeur locale par défaut |
|---|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Base créée par le conteneur `db` | `se_platform` |
| `DATABASE_URL` | Connexion Django à la base | `postgres://se_platform:…@db:5432/se_platform` |
| `DJANGO_SECRET_KEY` | Clé secrète Django | à changer en production |
| `DJANGO_DEBUG` | Mode débogage | `True` en local |
| `DJANGO_ALLOWED_HOSTS` | Noms d'hôte acceptés | `localhost,127.0.0.1,backend` |
| `JWT_ACCESS_LIFETIME_MIN` | Durée du jeton d'accès (minutes) | 45 |
| `JWT_REFRESH_LIFETIME_DAYS` | Durée du jeton de rafraîchissement (jours) | 7 |
| `CORS_ALLOWED_ORIGINS` | Origines autorisées à appeler l'API | `http://localhost:5191` |
| `VITE_API_BASE_URL` | Adresse de l'API vue par le navigateur | `http://localhost:8092/api/v1` |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Envoi des courriels de notification | backend « console » : les courriels sont écrits dans les journaux du conteneur |

### Réglages Django

- `config/settings/base.py` : réglages communs (applications, DRF, JWT, CORS, courriel).
  Langue `fr-fr`, fuseau `Africa/Ouagadougou`.
- `config/settings/dev.py` : surcharges de développement.
- `config/settings/prod.py` : `DEBUG = False`, redirection HTTPS, cookies sécurisés.

## 3. Backend : organisation

Une application Django par domaine métier, dans `backend/apps/` :

| Application | Contenu |
|---|---|
| `core` | Modèle abstrait `TimestampedModel` (dates de création et de modification), permissions communes, pagination, utilitaires Excel, commandes de données de démonstration |
| `accounts` | Utilisateur personnalisé (`User`), référentiel des rôles (`Role`) |
| `geo` | Niveaux administratifs par pays et zones (régions, provinces…), référentiel du Burkina Faso |
| `strategy` | Cadres stratégiques, niveaux et éléments de la structuration, import et export Excel |
| `partners` | Partenaires, bailleurs, financements par projet |
| `intervenants` | Intervenants de mise en œuvre (avec ou sans compte utilisateur) |
| `projects` | Projets, planification à niveaux libres (Activite), noms des niveaux, sous-activités, équipes, import Excel |
| `indicators` | Indicateurs, valeurs saisies, grilles d'alerte, import Excel |
| `suivi` | Points de suivi, périodes de planification, tranches planifiées, tableau de suivi, exports Excel et PDF |
| `beneficiaries` | Bénéficiaires, participations aux projets, détection des doublons, import et export |
| `documents` | Pièces justificatives, bibliothèque documentaire (dossiers, documents, versions) |
| `notifications` | Notifications dans l'application et par courriel, vérification des échéances |
| `dashboard` | Tableaux de bord consolidé et par projet, filtres, configuration partagée |
| `planification` | Import combiné « planification complète » (un seul classeur Excel) |
| `reports` | Calculs agrégés de progression d'un projet |
| `audit` | Consultation de l'historique des modifications de n'importe quel objet |

Dans chaque application, on retrouve les fichiers Django habituels : `models.py`,
`serializers.py`, `views.py`, `urls.py`, `admin.py`, `tests.py`. La logique métier qui
dépasse un simple CRUD (calculs, suppressions en cascade, imports, exports) est placée
dans `services.py` ou dans un dossier `services/`, jamais dans les vues.

## 4. Modèle de données

### 4.1 Vue d'ensemble

```
CadreStrategique ─┬─ TypeNiveau (niveaux nommés librement, ordonnés)
                  └─ ElementStrategique (arborescence : element_parent)

Projet ──┬─ Activite (tous les niveaux de la planification, imbriqués via activite_parent)
         │        └── SousActivite
         ├─ NiveauActivite (nom de chaque niveau : « Objectif général », « Résultat », « Pilier »…)
         ├─ element_strategique → ElementStrategique (rattachement du projet dans le cadre)
         ├─ Financement ── Bailleur
         ├─ Indicateur ── ValeurIndicateur ── PieceJustificative
         ├─ PeriodePlanification ── TranchePlanifiee
         ├─ ParticipationProjet ── Beneficiaire
         └─ Dossier / Document ── DocumentVersion

Activite / SousActivite ── PointSuivi (saisies périodiques)
Indicateur ── IndicateurElement ── ElementStrategique
PalierAlerte : grille globale, ou propre à un Projet, un Indicateur ou une Activite
NiveauAdministratif ── Zone (arborescence : parent)
```

### 4.2 Détail par domaine

**Comptes (`accounts`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `User` | `role`, `niveau_acces`, `telephone`, `zones_affectees` | `role` contient le code d'un `Role` (texte, pas de clé étrangère) |
| `Role` | `code`, `libelle`, `visibilite_globale`, `peut_personnaliser_tableau_de_bord`, `systeme` | Les rôles « système » sont créés par migration et ne peuvent pas être supprimés |

**Référentiel géographique (`geo`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `NiveauAdministratif` | `pays` (code ISO), `nom_niveau`, `ordre`, `niveau_parent`, `saut_niveau_autorise` | Gabarit par pays : Région → Province → Commune… |
| `Zone` | `niveau_administratif`, `parent`, `code` (pcode), `nom` | Les 17 régions et 47 provinces du Burkina Faso sont chargées par migration |

**Cadre stratégique (`strategy`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `CadreStrategique` | `nom`, `description` | Plusieurs cadres indépendants peuvent coexister |
| `TypeNiveau` | `cadre_strategique`, `nom_niveau`, `ordre`, `niveau_parent`, `saut_niveau_autorise`, `aide_code` | Aucun nom de niveau imposé |
| `ElementStrategique` | `type_niveau`, `element_parent`, `code`, `nom`, `description` | Tri par ordre de création, pour respecter l'ordre des fichiers importés |

**Projets et planification (`projects`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `Projet` | `nom`, `code`, bailleur, partenaires, `cadre_strategique`, `element_strategique` (rattachement à un élément du cadre, à n'importe quel niveau), `budget_total`, `fonds_propres`, `date_debut`, `date_fin`, `date_rappel`, `statut`, `type_mise_en_oeuvre`, `zones`, `utilisateurs_affectes`, cibles (totale, hommes, femmes, jeunes, PDI) | Statuts : En préparation, En cours, Clôturé |
| `Activite` | `projet`, `activite_parent`, `code_activite`, `libelle`, `description`, `statut`, `axe_strategique`, budgets, quantités, dates prévues et réelles, `responsables`, `equipe_responsable` | **Élément de la planification à n'importe quel niveau** (objectif, résultat, pilier, activité…). Aucun niveau n'est imposé ; profondeur illimitée via `activite_parent`. Statuts : Non réalisée, En cours, Réalisée |
| `NiveauActivite` | `projet`, `profondeur`, `nom_niveau` | Nom de chaque niveau (profondeur 0 = premier niveau sous le projet), purement d'affichage. Sans nom : « Activité » |
| `SousActivite` | `activite`, `libelle`, quantités, dates, `statut` | Statuts : Planifiée, En cours, Terminée |
| `Equipe` | `nom`, `membres`, dates de contrat | |

**Partenaires et intervenants (`partners`, `intervenants`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `Partenaire` | `nom`, `type` (bailleur, mise en œuvre), contacts | |
| `Bailleur` | `nom`, `type` (institutionnel, fondation, coopération bilatérale, autre) | Modèle recommandé pour les financements |
| `Financement` | `projet`, `bailleur`, `montant_finance` | Plusieurs bailleurs par projet |
| `Intervenant` | `nom`, `prenom`, `fonction`, `utilisateur` (facultatif), projets et activités associés | Couvre les personnes sans compte sur la plateforme |

**Indicateurs (`indicators`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `Indicateur` | `libelle`, `unite`, `valeur_reference`, `valeur_cible`, `frequence_collecte`, rattachement (le projet, ou un élément de sa planification à n'importe quel niveau ; éléments stratégiques) | Fréquences : mensuelle, trimestrielle, semestrielle, annuelle |
| `ValeurIndicateur` | `indicateur`, `periode_debut`, `periode_fin`, `valeur_realisee`, `saisi_par`, `commentaire` | Une saisie = ce qui a été réalisé pendant la période |
| `IndicateurElement` | `indicateur`, `element_strategique` | Rattachement à n'importe quel niveau du cadre |
| `PalierAlerte` | `borne_min` (%), `libelle`, `couleur`, portée (`projet`, `indicateur` ou `activite`, ou aucune = grille globale) | Nombre de paliers libre |
| `ParametresAlerte` | `seuil_echeance_jours` | Ligne unique : délai d'alerte avant échéance |

**Suivi (`suivi`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `PointSuivi` | `activite` **ou** `sous_activite`, `periode_debut`, `periode_fin`, `quantite_realisee`, `budget_realise`, `statut`, `commentaire` | Une saisie = ce qui a été accompli pendant la période |
| `PeriodePlanification` | `projet`, `libelle`, `date_debut`, `date_fin` | Ex. : « T1 2026 », « Année 2027 » |
| `TranchePlanifiee` | `periode`, cible (`activite`, `sous_activite` ou `indicateur`), `cible`, `budget`, dates prévues, `commentaire` | Découpe une cible globale en cibles par période |

**Bénéficiaires (`beneficiaries`)**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `Beneficiaire` | identité, `sexe`, `date_naissance`, `telephone`, pièce d'identité, `pays`, `zone`, statuts particuliers, types d'activité | |
| `ParticipationProjet` | `beneficiaire`, `projet`, `activite`, `sous_activite`, `date_inscription`, `role_dans_projet` | Permet de suivre un bénéficiaire sur plusieurs projets |
| `StatutParticulier`, `TypeActiviteBeneficiaire` | `code`, `libelle` | Référentiels extensibles, créables depuis le formulaire |
| `SignalementDoublon` | deux bénéficiaires, `score`, `methode`, `statut` | Statuts : Signalé, Écarté, Fusionné |

**Documents, notifications, tableau de bord**

| Modèle | Champs principaux | Remarques |
|---|---|---|
| `PieceJustificative` | `fichier`, `nom`, `type_document`, `valeur_indicateur` | Justificatif d'une saisie d'indicateur |
| `Dossier` | `nom`, `projet`, `parent` | Arborescence de la bibliothèque, avec ou sans projet |
| `Document` / `DocumentVersion` | métadonnées / fichier et numéro de version | Le contenu réel est dans les versions |
| `Notification` | `destinataire`, `type`, `titre`, `message`, `lien`, `lu` | |
| `ConfigurationTableauDeBord` | `blocs_masques`, `types_graphiques` | Ligne unique, commune à tous les utilisateurs |

## 5. Règles métier essentielles

### 5.1 Les valeurs calculées ne sont jamais stockées

Taux de réalisation, statut d'alerte, taux d'exécution physique et financière : tout est
recalculé à la volée (`indicators/services.py`, `reports/services.py`,
`suivi/services.py`). Un changement de cible ou de grille d'alerte se répercute donc
immédiatement, sans désynchronisation possible.

### 5.2 Une saisie représente une période, pas un cumul

Une `ValeurIndicateur` ou un `PointSuivi` contient ce qui a été réalisé **pendant** sa
période. Le réalisé total est la **somme** des saisies, pas la dernière valeur.

- Taux de réalisation d'un indicateur = somme des valeurs saisies ÷ valeur cible × 100.
- Les champs `quantite_realisee`, `budget_realise` et `statut` d'une activité ou d'une
  sous-activité sont recalculés automatiquement à partir de ses points de suivi
  (`synchroniser_activite_depuis_suivi`). Ils servent de cache pour les écrans qui n'ont
  pas besoin de l'historique.
- Le réalisé d'une tranche planifiée est la somme des saisies dont la période est
  entièrement contenue dans celle de la tranche (`realise_tranche`). Statut d'une tranche :
  atteinte si réalisé ≥ cible, en retard si l'échéance est passée, en cours sinon.

### 5.3 Grilles d'alerte héritées

Chaque taux de réalisation est interprété par une grille de paliers (par exemple 0 % =
rouge « Critique », 50 % = orange, 80 % = vert). La grille appliquée suit l'ordre
d'héritage :

```
Indicateur (ou Activité)  →  Projet  →  Grille globale
```

Un élément sans grille propre prend celle du niveau supérieur. La grille globale, créée
par migration, n'est jamais vide. Le palier retenu est celui dont la borne minimale est
la plus haute tout en restant inférieure ou égale au taux.

### 5.4 Planification à niveaux libres

Aucun niveau n'est imposé, ni au-dessus du projet ni en dessous :

- **Au-dessus** : le cadre stratégique a ses propres niveaux (`TypeNiveau`), et chaque
  projet peut être rattaché à un élément de n'importe lequel de ces niveaux
  (`Projet.element_strategique`). Une activité sans axe propre hérite de cet élément dans
  le récapitulatif « Axes & budgets ».
- **En dessous** : tous les niveaux de la planification sont des `Activite` imbriquées
  (`activite_parent`), nommées par projet (`NiveauActivite`). Un projet peut avoir un
  seul niveau (« Activité ») ou autant qu'il veut (« Résultat » → « Pilier » → « Activité »…).
- **Import Excel** : toutes les colonnes placées avant « Sous-activité » (sauf « Code »)
  sont des niveaux ; leurs noms deviennent les noms des niveaux du projet.
- **Historique** : les anciens « Objectif général » et « Objectif spécifique » ont été
  convertis par la migration `projects.0023` en éléments des deux premiers niveaux, nommés
  ainsi ; les indicateurs qui y étaient rattachés ont suivi.

### 5.5 Suppressions protégées

Les clés étrangères de la hiérarchie (projet, éléments de planification, niveaux du cadre,
indicateurs et valeurs) sont en `PROTECT` : aucune arborescence ne peut disparaître par
accident. Une suppression volontaire passe par les fonctions `supprimer_*_cascade` des
`services.py`, qui suppriment les éléments dans le bon ordre.

### 5.6 Doublons de bénéficiaires

La plateforme ne fusionne jamais automatiquement deux bénéficiaires. Elle **signale** les
doublons probables, qui sont ensuite traités à la main (écran « Doublons signalés ») :

1. même numéro de pièce d'identité : doublon quasi certain ;
2. noms et prénoms proches (similarité trigramme PostgreSQL `pg_trgm`) croisés avec le
   numéro de téléphone.

### 5.7 Imports « au mieux »

Tous les imports Excel suivent la même règle : une ligne en erreur est ignorée sans
bloquer les autres, et le rapport renvoyé indique les lignes créées et les erreurs ligne
par ligne.

### 5.8 Méthodes de calcul du taux d'exécution physique

Moteur : `apps/projects/taux.py` (formules détaillées en tête du fichier), tests chiffrés
dans `apps/projects/test_taux.py`. Rien n'est stocké : tout est recalculé à la volée.

- **Méthodes** (élément du dernier niveau) : par quantité (défaut), tâches pondérées
  (sous-activités : `poids`, `avancement`), jalons pondérés et livrables (`JalonLivrable`),
  binaire (statut « Réalisée »), saisie manuelle (`TauxManuel`, historisé, jamais recalculé).
- **Héritage** : élément → éléments parents → projet → organisation (`ParametresCalcul`,
  écran Paramètres d'alerte). « Saisie manuelle » sur un parent ne se propage pas.
- **Agrégation** (élément avec des éléments en dessous, et projet) : moyenne simple des
  éléments du dernier niveau (défaut, identique au calcul d'avant), pondérée par le budget,
  ou pondérée par les poids des éléments directement en dessous. Dépassements plafonnés à
  100 % dans les agrégations (réglable).
- **Canevas de planification** : colonnes « Méthode de calcul » et « Poids (%) ».
- **Canevas de suivi** (`apps/suivi/canevas.py`, routes `suivi/projets/{id}/canevas/…`) :
  Excel prérempli à compléter hors ligne ; import en deux temps (aperçu sans enregistrement,
  puis import des lignes valides), erreurs par cellule, rapport d'erreurs Excel, mode
  « ajouter » (aucun écrasement) ou « mettre à jour » (ancienne → nouvelle valeur, historique).
- **Taux à une date** (`ArbreTaux(projet, a_la_date=…)`) : où en était chaque élément à une
  date passée — saisies de suivi datées, historique des modifications (avancement des tâches,
  achèvement des jalons), date de validation des livrables, taux manuels datés. Méthodes,
  poids et quantités prévues : ceux d'aujourd'hui.
- **Suivi et planification par période** (`construire_planification_periode`) : élément
  « Par quantité » → objectif et réalisé en quantité sur la période ; toute autre méthode et
  niveaux agrégés (mode `avancement`) → objectif = avancement visé à la fin de la période
  (%), réalisé = taux atteint à cette date (ou aujourd'hui si la période est en cours).
- **Pages et exports** : page Suivi (barre, méthode expliquée et modifiable, saisie adaptée),
  exports PDF/Excel du suivi global et de la période affichent la méthode et un avancement
  en % pour les éléments hors quantité.

### 5.8 bis Budgets sans double compte

Module : `apps/projects/budgets.py` (tests : `apps/projects/test_budgets.py`). Un budget peut
être saisi à n'importe quel niveau ; dans chaque branche, **seul compte le budget du niveau
le plus bas où il est saisi** (règle appliquée séparément au budget alloué et au dépensé).
Le budget d'un niveau dont le détail est saisi en dessous sert de contrôle : avertissement
(`budget_avertissements` de l'API des activités, affiché dans l'arbre de planification) si
la somme d'en dessous le dépasse, ou si une partie n'est répartie nulle part (non comptée).

Appliqué à : taux d'exécution financière du projet (`reports.services`), tableau de bord
consolidé (budgets et dépenses par mois), récapitulatif du cadre stratégique, onglet
« Axes & budgets » (`budget_alloue_compte` / `budget_realise_compte` ; moyennes de taux sur
les éléments les plus bas de chaque groupe, via `ancetres`) et totaux d'une période
(budgets et taux physique de la période).

### 5.9 Menu et vocabulaire personnalisables

L'Administrateur adapte la plateforme au langage de son organisation (« Personnaliser le
menu », modèle `ConfigurationMenu`, route `interface/menu/`) :

- **Menu** : nom et icône de chaque rubrique ; le titre de la page suit le nom choisi.
- **Vocabulaire** : pour 12 termes (projet, indicateur, cadre stratégique, bénéficiaire…),
  singulier, pluriel et genre. Le terme change partout : écrans, formulaires,
  rattachements, messages, modèles d'import, exports Excel et PDF.

Fonctionnement :

- Moteur identique côté serveur (`apps/core/vocabulaire.py`, fonction `v()`) et côté
  navigateur (`frontend/src/utils/vocabulaire.ts`, fonction `voc`) : garde les majuscules
  et accorde les petits mots qui précèdent le terme (un/une, le/la/l', ce/cette, du/de la…).
  Les adjectifs placés après le terme ne sont pas accordés.
- Seuls les **textes de l'interface** sont adaptés, jamais les données saisies. Tout
  nouveau texte contenant un terme doit passer par `voc("…")` (frontend) ou `v("…")`
  (backend) ; dans un gabarit, seules les parties fixes : voc`Projet ${nom} créé`.
- **Modèles d'import** : générés avec le vocabulaire (`adapter_classeur`) ; à l'import,
  `ramener_classeur` ramène noms de feuilles et en-têtes aux noms par défaut, et
  `ramener_terme` les valeurs (« Action » → « Projet »). Un ancien fichier reste importable.
- Les constantes de module (noms de colonnes, champs) restent aux noms par défaut : elles
  servent de référence à l'import.

### 5.10 Contrôle de la saisie

Verrous d'enregistrement : signaux `pre_save` / `pre_delete` (`apps/projects/verrou.py`) sur
tous les modèles rattachés à un projet. Ils s'appliquent quel que soit le chemin (API,
import, canevas). `verrou_desactive()` les suspend (suppression d'un projet en cascade).
L'utilisateur courant vient de la requête (middleware de `simple_history`,
`utilisateur_courant()`) ; sans requête (commandes, migrations), rien n'est bloqué.

- **Projet clôturé** : lecture seule pour tous (`ProjetClotureError`, HTTP 403) ; seul
  l'Administrateur peut le rouvrir (changer son statut).
- **Périodes de rapportage** (`apps/projects/rapportage.py`, tests `test_rapportage.py`) :
  - `ParametresRapportage` (singleton) : contrôle actif ou non, et périmètre fermé hors
    période : réalisations seulement (`REALISATIONS`) ou tout le projet (`TOUT`).
  - `FenetreRapportage` : période d'ouverture générale (`projet` vide) ou propre à un projet.
  - Par projet (Administrateur) : `saisie` (`HERITE` selon le réglage général, `OUVERTE`
    toujours, `FERMEE` sauf ses propres périodes) et `perimetre_fermeture`.
  - `etat_saisie(projet)` dit si la saisie est ouverte, pourquoi, et la prochaine période.
    Saisie fermée : `SaisieFermeeError` (403) pour une réalisation (`est_une_realisation` :
    point de suivi, valeur d'indicateur, taux manuel, avancement ou quantité réalisée d'une
    sous-activité, achèvement d'un jalon), ou pour tout si le périmètre est `TOUT`.
    L'Administrateur n'est jamais bloqué.
- **Approbations**, activables par projet (`apps/projects/approbation.py`, tests
  `test_approbation.py`). Droit d'approuver : Administrateur, ou rôle avec `peut_approuver`
  (`core.permissions.peut_approuver`).
  - `Projet.approbation_realisations` : une saisie (modèles `SaisieApprouvable` :
    `PointSuivi`, `ValeurIndicateur`, `TauxManuel`) d'un non-approbateur est `EN_ATTENTE`.
    Le gestionnaire `objects` ne renvoie que les saisies approuvées : tous les calculs
    ignorent donc les saisies en attente ou rejetées. `tous` renvoie tout (suppression,
    modification, contrôles de doublon, historique du suivi). Une saisie modifiée repart en
    attente ; une saisie approuvée ne peut être supprimée que par un approbateur.
  - `Projet.approbation_planification` : ajout, modification ou suppression d'un élément de
    planification ou d'une sous-activité par un non-approbateur → `DemandeModification`
    (HTTP 202, rien n'est changé). Les données sont validées tout de suite ; l'approbation
    applique le changement avec les sérialiseurs habituels. La duplication est réservée aux
    approbateurs.
  - Un rejet exige un motif, montré à l'auteur.
- **Contrôle de cohérence** (`apps/projects/coherence.py`, tests `test_coherence.py`) : rien
  n'est bloqué.
  - À la saisie d'un point de suivi ou d'une valeur d'indicateur, la réponse contient
    `avertissements` (période future ou à l'envers, chevauchement, hors des dates de
    l'activité ou du projet, dépassement de la quantité prévue ou du budget, plus de 100 en %,
    valeur négative), affichés en notification par `api/client.ts`.
  - `controler_projet(projet)` : rapport complet (planification, suivi, indicateurs, budgets),
    chaque point avec sa gravité (`erreur` ou `attention`), les erreurs d'abord.

## 6. Utilisateurs, rôles et permissions

Deux notions indépendantes définissent les droits d'un utilisateur :

| Notion | Définit | Valeurs |
|---|---|---|
| **Rôle** (`User.role`) | Ce que l'utilisateur **voit** | Rôle à visibilité globale : tous les projets. Sinon : seulement les projets auxquels il est affecté ou dont une zone recoupe ses zones |
| **Niveau d'accès** (`User.niveau_acces`) | Ce que l'utilisateur **peut modifier** | Lecture seule, ou lecture et écriture |

L'Administrateur a toujours tous les droits.

Rôles système (créés par migration, dans `apps/accounts/constants.py`) :

| Code | Libellé |
|---|---|
| `ADMIN` | Administrateur |
| `COORDO_GENERAL` | Coordonnateur général |
| `CHARGE_SE` | Chargé de Suivi-Évaluation |
| `CHEF_PROJET` | Chef de projet |
| `CHEF_SERVICE` | Chef de service |
| `ANIMATEUR_TERRAIN` | Animateur de terrain |

L'Administrateur peut créer d'autres rôles et régler leur visibilité depuis l'écran
Utilisateurs > Rôles. Un rôle peut aussi **approuver** (`Role.peut_approuver`, voir § 5.10).

**Droits par module, utilisateur par utilisateur** (`User.acces_modules`, fiche de
l'utilisateur dans l'écran Utilisateurs ; `apps/core/modules.py`, tests
`apps/accounts/test_modules.py`) :

- Pour chaque module : **Masqué**, **Consultation** ou **Création et modification**. Les
  onglets (`projet:…`, `suivi:…`) peuvent seulement être masqués. Liste des modules et
  onglets : `frontend/src/utils/modules.ts` (mêmes clés que `API_PAR_MODULE`).
- Un module non réglé suit le **niveau d'accès par défaut** de l'utilisateur (par défaut :
  tout). Seuls les écarts sont enregistrés ({clé: `MASQUE` | `LECTURE` | `ECRITURE`}).
  L'Administrateur a toujours tout.
- Côté serveur, `ModulesMasquesMiddleware` relie chaque préfixe d'API à son module :
  - écriture refusée (403) dans un module qui n'est pas en création / modification ;
  - dans un module en écriture, l'utilisateur peut écrire même si son niveau par défaut est
    « lecture seule » (`peut_modifier` lit le module de la requête, `module_courant`) ;
  - Bénéficiaires, Documents et Financement masqués sont refusés même en lecture ; les
    autres modules masqués (projets, zones…) restent lisibles, car ils alimentent les
    formulaires communs.
- Côté navigateur (`useAccesModules` : `estMasque`, `peutEcrire`) : menu, onglets et icônes
  liées cachés, page masquée remplacée par « Module non accessible », boutons de création et
  de modification masqués en consultation. Masquer Documents masque aussi l'onglet Documents
  des projets ; masquer Bénéficiaires masque aussi les doublons.

Classes de permission DRF (`apps/core/permissions.py`) :

| Classe | Lecture | Création | Modification et suppression |
|---|---|---|---|
| `IsAdmin` | Administrateur | Administrateur | Administrateur |
| `IsAdminOrReadOnly` | Tout utilisateur connecté | Administrateur | Administrateur |
| `IsAdminOrCreateForAuthenticated` | Tout utilisateur connecté | Utilisateur avec droit d'écriture | Administrateur |
| `HasGlobalVisibilityOrAssigned` | Tout utilisateur connecté (filtré par visibilité) | Droit d'écriture | Droit d'écriture |

Le filtrage des projets visibles est fait dans `get_queryset()` de chaque vue, à l'aide
de `visible_projets_ids()` (`apps/projects/queryset_filters.py`).

## 7. API REST

- Préfixe : `/api/v1/`. Documentation interactive : `/api/docs/` (Swagger) et
  `/api/redoc/`. Schéma OpenAPI : `/api/schema/`.
- Authentification : jeton JWT dans l'en-tête `Authorization: Bearer <jeton>`.
- Pagination : 25 éléments par page par défaut.
- Filtres : paramètres de filtrage (`django-filter`), `?search=` et `?ordering=` sur la
  plupart des listes.

### 7.1 Authentification

| Méthode | Route | Rôle |
|---|---|---|
| POST | `auth/token/` | Obtenir les jetons d'accès et de rafraîchissement (`username`, `password`) |
| POST | `auth/token/refresh/` | Renouveler le jeton d'accès (rotation du jeton de rafraîchissement) |
| POST | `auth/token/verify/` | Vérifier un jeton |
| GET | `utilisateurs/me/` | Utilisateur connecté |

### 7.2 Ressources (CRUD complet : liste, détail, création, modification, suppression)

| Domaine | Routes |
|---|---|
| Comptes | `utilisateurs/`, `roles/` |
| Géographie | `zones/`, `niveaux-administratifs/` |
| Cadre stratégique | `cadres-strategiques/`, `types-niveaux/`, `elements-strategiques/` |
| Partenaires | `partenaires/`, `bailleurs/`, `financements/`, `intervenants/` |
| Projets | `projets/`, `activites/` (éléments de planification, tous niveaux), `sous-activites/`, `niveaux-activite/`, `equipes/` |
| Indicateurs | `indicateurs/`, `valeurs-indicateurs/` |
| Suivi | `points-suivi/`, `periodes-planification/`, `tranches-planifiees/` |
| Bénéficiaires | `beneficiaires/`, `participations-projet/`, `statuts-particuliers/`, `types-activite-beneficiaire/`, `signalements-doublons/` |
| Documents | `pieces-justificatives/`, `dossiers/`, `documents/` |
| Notifications | `notifications/` |

### 7.3 Actions particulières

| Méthode | Route | Rôle |
|---|---|---|
| GET | `cadres-strategiques/{id}/export/` | Export Excel de la structuration |
| GET | `cadres-strategiques/{id}/recap/`, `…/recap-axes/` | Récapitulatifs (projets et budgets, axes et budgets) |
| GET / POST | `elements-strategiques/modele-import/`, `…/importer/` | Modèle et import Excel de la structuration |
| GET / POST | `projets/modele-import/`, `projets/importer/` | Modèle et import Excel d'un projet et de sa planification |
| GET | `projets/{id}/export/xlsform/` | Export du projet au format XLSForm (formulaire de collecte) |
| GET | `activites/pour-projet/`, `indicateurs/pour-projet/` | Listes complètes d'un projet |
| GET / POST | `indicateurs/modele-import/`, `indicateurs/importer/` | Modèle et import Excel des indicateurs |
| GET / PUT / PATCH | `parametres-alerte/` | Délai d'alerte avant échéance |
| GET / PUT | `paliers-alerte/` | Grilles d'alerte (globale ou par portée) |
| GET / POST | `beneficiaires/modele-import/`, `beneficiaires/importer/` | Modèle et import Excel des bénéficiaires |
| GET | `beneficiaires/exporter/` | Export des bénéficiaires : `?fichier=excel` ou `pdf`, `?projets=1,3` pour choisir les projets |
| POST | `beneficiaires/{id}/verifier-doublons/` | Recherche des doublons d'un bénéficiaire |
| GET / POST | `documents/{id}/versions/`, `documents/{id}/nouvelle-version/` | Versions d'un document |
| GET / POST | `notifications/non-lues-count/`, `…/{id}/marquer-lu/`, `…/tout-marquer-lu/` | Gestion des notifications |
| GET | `periodes-planification/{id}/valeurs/` | Données de l'onglet « Planification par période » |
| GET | `periodes-planification/{id}/exporter/excel/`, `…/exporter/pdf/` | Export de la planification d'une période |
| GET | `periodes-planification/{id}/exporter-suivi/excel/`, `…/exporter-suivi/pdf/` | Export du suivi d'une période |
| GET | `suivi/projets/{id}/dashboard/` | Tableau de suivi d'un projet |
| GET | `suivi/projets/{id}/exporter/excel/`, `…/exporter/pdf/` | Export du suivi d'un projet |
| GET | `dashboard/consolide/` | Tableau de bord consolidé (filtres : `annee` ou `date_debut` et `date_fin`, `periode`, `statuts` séparés par des virgules) |
| GET | `dashboard/projet/{id}/` | Tableau de bord d'un projet |
| GET | `dashboard/echeances/` | Échéances proches ou dépassées |
| GET / PUT | `dashboard/configuration/` | Blocs masqués et types de graphiques |
| GET / PUT / PATCH | `parametres-calcul/` | Méthode de calcul et d'agrégation par défaut de l'organisation (modification : Administrateur) |
| CRUD | `jalons-livrables/`, `taux-manuels/` | Jalons et livrables d'un élément, taux saisis manuellement |
| GET | `suivi/projets/{id}/canevas/` | Canevas de suivi prérempli (Excel) |
| POST | `suivi/projets/{id}/canevas/apercu/`, `…/importer/`, `…/rapport-erreurs/` | Aperçu, import et rapport d'erreurs du canevas de suivi (`fichier`, `mode` : ajout ou mise_a_jour) |
| GET / PUT | `interface/menu/` | Noms et icônes des rubriques du menu, vocabulaire de l'organisation (modification : Administrateur) |
| GET / POST | `planification/modele-import/`, `planification/importer/` | Import combiné « planification complète » |
| GET | `audit/{app}/{modele}/{id}/historique/` | Historique des modifications d'un objet |
| GET / PUT / PATCH | `parametres-rapportage/` | Contrôle des périodes de rapportage et périmètre fermé (modification : Administrateur) |
| CRUD | `periodes-rapportage/` | Périodes d'ouverture de la saisie, générales ou par projet (`?projet=`) |
| GET | `projets/{id}/coherence/` | Rapport de cohérence du projet |
| GET | `approbations/` | Saisies et demandes en attente (approbateur : toutes ; autres : les siennes, avec les rejets) |
| POST | `approbations/saisies/{point\|valeur\|taux}/{id}/`, `approbations/demandes/{id}/` | Approuver ou rejeter : `{approuver, motif}` (motif obligatoire pour un rejet) |

## 8. Imports et exports

| Import ou export | Format | Code |
|---|---|---|
| Structuration stratégique | Excel au format « plan » (une colonne par niveau) ; l'export est réimportable | `strategy/services.py` |
| Projet et planification | Excel, feuilles « Projet » et « Planification » (niveaux d'activité en nombre libre) | `projects/import_excel.py` |
| Indicateurs et grilles d'alerte | Excel | `indicators/import_excel.py` |
| Bénéficiaires | Excel (import) ; Excel et PDF (export, une feuille par projet) | `beneficiaries/services/` |
| Planification complète | Un classeur : cadre, projet, planification, indicateurs, bénéficiaires, grilles d'alerte | `planification/services.py` |
| Suivi d'un projet ou d'une période | Excel et PDF (WeasyPrint) | `suivi/export_excel.py`, `export_pdf.py`, `export_periode.py` |
| Formulaire de collecte | XLSForm | `projects/views.py` (`export_xlsform`) |

Les utilitaires communs de mise en forme (bordures, en-têtes figés) sont dans
`core/excel_utils.py`. Des exemples de fichiers se trouvent dans `docs/`.

## 9. Notifications et échéances

- `notifier()` (`notifications/services.py`) crée une notification dans l'application
  pour chaque destinataire et tente un envoi par courriel. Un échec d'envoi ne bloque
  jamais l'action qui l'a déclenché.
- La commande `check_deadlines`, lancée toutes les heures par le service `scheduler`,
  repère les activités, sous-activités et projets dont l'échéance est proche (délai réglé
  dans les paramètres d'alerte) ou dépassée, et notifie tous les utilisateurs actifs.
- La modification d'une activité déjà planifiée notifie le Coordonnateur général et le
  Chargé de Suivi-Évaluation.
- Types de notification : indicateur en alerte, échéance d'activité, activité modifiée,
  doublon signalé, rapport soumis, rapport validé.

## 10. Frontend

### 10.1 Organisation

| Dossier | Contenu |
|---|---|
| `src/api/` | Un fichier par domaine (`projects.ts`, `indicators.ts`…) ; `client.ts` configure Axios |
| `src/auth/` | `AuthContext` (utilisateur connecté), `RequireAuth` (garde des routes, avec rôles exigés), page de connexion |
| `src/pages/` | Écrans, regroupés par domaine |
| `src/components/` | Composants réutilisables : graphiques, badges de statut, sélecteurs « choisir ou créer », cascade de zones, historique, notifications |
| `src/layouts/AppLayout.tsx` | Mise en page générale et menu latéral |
| `src/utils/` | Calculs partagés (`suivi.ts`, `periode.ts`), filtres du tableau de bord, recherche, palettes de statut |
| `src/types/index.ts` | Types TypeScript des objets de l'API |

### 10.2 Authentification côté navigateur

Les jetons sont conservés dans le `localStorage` (`se_access_token`,
`se_refresh_token`). L'intercepteur Axios ajoute le jeton à chaque requête ; sur une
réponse 401, il renouvelle le jeton d'accès une seule fois (requêtes concurrentes
mutualisées) puis rejoue la requête, ou renvoie vers la page de connexion.

### 10.3 Écrans

| Route | Écran |
|---|---|
| `/login` | Connexion |
| `/` | Tableau de bord consolidé |
| `/planification` | Import « planification complète » |
| `/strategie`, `/strategie/:id` | Cadres stratégiques ; onglets Configuration des niveaux, Arborescence et saisie, Axes et budgets, Projets et budgets |
| `/projets`, `/projets/:id` | Projets ; onglets Configuration des niveaux, Planification, Planification par période, Équipe de projet, Indicateurs, Financement, Documents, Contrôle de cohérence, Historique |
| `/indicateurs`, `/indicateurs/:id` | Indicateurs et saisie des valeurs |
| `/suivi`, `/suivi/:id` | Suivi des projets et tableau de suivi d'un projet |
| `/beneficiaires`, `/beneficiaires/:id` | Bénéficiaires |
| `/approbations` | Saisies et changements de planification à approuver, ou suivi de ses demandes |
| `/doublons` | Doublons signalés |
| `/zones-administratives` | Référentiel administratif |
| `/documents` | Bibliothèque documentaire |
| `/utilisateurs` | Utilisateurs et rôles (Administrateur) |
| `/parametres-alerte` | Grilles d'alerte, délai d'échéance et périodes de rapportage (Administrateur) |

### 10.4 Points d'attention

- Les données serveur sont gérées par TanStack Query : après une modification, invalider
  les requêtes concernées plutôt que de mettre à jour l'état à la main.
- `valeurAttendueA` (`utils/suivi.ts`) et `valeur_attendue_a` (`suivi/services.py`)
  calculent la même valeur attendue à une date (interpolation linéaire). Ils doivent
  rester identiques : toute modification de l'un doit être reportée dans l'autre.

## 11. Commandes de gestion

| Commande | Effet |
|---|---|
| `check_deadlines` | Vérifie les échéances et envoie les notifications (lancée par le scheduler) |
| `seed_zones_bfa` | Charge les niveaux administratifs et les régions et provinces du Burkina Faso |
| `seed_demo_users` | Crée un utilisateur de test par rôle (mot de passe `demo1234!`) |
| `seed_demo_expertise_id` | **Vide les données métier** et charge un jeu de démonstration complet |
| `seed_5_projets_complets` | **Vide les données métier** et charge 5 cadres et 5 projets complets |
| `seed_projets_complementaires` | Ajoute 4 projets de démonstration, sans rien supprimer |
| `seed_projets_filtres` | Ajoute (ou supprime avec `--supprimer`) des projets `TEST-…` pour tester les filtres |
| `seed_points_suivi` | Ajoute des points de suivi de démonstration |

Exécution : `docker compose exec backend python manage.py <commande>`.

## 12. Tests et contrôles qualité

```bash
# Backend
docker compose exec backend python manage.py check
docker compose exec backend pytest -q

# Frontend (depuis frontend/)
npx tsc --noEmit -p .     # vérification des types
npx oxlint src            # analyse statique
npx vite build            # compilation de production
```

Les tests backend (pytest + pytest-django, réglages `config.settings.dev`) se trouvent
dans les fichiers `tests.py` des applications `accounts`, `beneficiaries`, `dashboard`,
`indicators`, `projects` et `suivi`.

## 13. Conventions de développement

- **Tout est en français** : interface, libellés, noms des modèles et des champs,
  commentaires, messages de commit.
- Les calculs et traitements vont dans `services.py`, pas dans les vues ni les
  serializers.
- Les valeurs dérivées ne sont pas stockées (voir 5.1), sauf cache explicitement
  synchronisé (voir 5.2).
- Toute nouvelle relation de hiérarchie est en `PROTECT`, avec une fonction de
  suppression en cascade dédiée.
- Toute nouvelle entité métier hérite de `TimestampedModel` et, si son historique est
  utile, déclare `HistoricalRecords()`.
- Avant de considérer un changement terminé : vérifier avec de vraies données (requête
  en base, appel à l'API, import et export Excel aller-retour), puis supprimer les
  données de test créées.
- Ne jamais committer sans demande explicite. Les fichiers Excel et Word produits pendant
  le travail ne sont pas versionnés.

## 14. Mise en production

La configuration Docker Compose fournie est une configuration de **développement**
(`runserver`, serveur Vite). Pour une mise en production :

1. Utiliser `config.settings.prod` (`DJANGO_SETTINGS_MODULE=config.settings.prod`) et
   `requirements/prod.txt`.
2. Définir une vraie `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, les
   `DJANGO_ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS` du domaine réel.
3. Servir Django avec un serveur d'application (par exemple Gunicorn) derrière un proxy
   HTTPS (par exemple Nginx), et exécuter `collectstatic`.
4. Compiler le frontend (`npx vite build`, avec `VITE_API_BASE_URL` pointant vers l'API
   de production) et servir le dossier `frontend/dist/` en statique.
5. Configurer un vrai serveur de courriel (`EMAIL_BACKEND` SMTP et `EMAIL_HOST*`).
6. Garder un équivalent du service `scheduler` (ou une tâche cron) pour
   `check_deadlines`.
7. Mettre en place des sauvegardes régulières de la base (`pg_dump`) et du dossier
   `backend/media/` (fichiers téléversés).

## 15. Dépannage

| Symptôme | Cause probable et solution |
|---|---|
| Connexion impossible avec un compte créé par `createsuperuser` | Le champ `role` est vide : créer le compte avec `role='ADMIN'` (voir le README) |
| Le frontend affiche des erreurs réseau ou CORS | Vérifier `VITE_API_BASE_URL` et `CORS_ALLOWED_ORIGINS` dans `.env`, puis `docker compose restart backend frontend` |
| « port is already allocated » au démarrage | Un autre service utilise le port : arrêter l'autre stack ou changer le port dans `docker-compose.yml` et `.env` |
| Les courriels ne partent pas | En local c'est normal : ils sont écrits dans `docker compose logs backend` |
| Erreur de migration après un changement de modèle | `docker compose exec backend python manage.py makemigrations` puis `migrate` |
| Un projet n'apparaît pas pour un utilisateur | Son rôle n'a pas la visibilité globale et il n'est ni affecté au projet ni dans une de ses zones |
