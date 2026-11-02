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
| `db` | PostgreSQL 16, volume persistant `suivi-evaluation-3-pgdata` | 5444 → 5432 |
| `backend` | Django (`manage.py runserver`), code monté depuis `./backend` | 8093 → 8000 |
| `scheduler` | Boucle `check_deadlines` toutes les heures | — |
| `frontend` | Serveur de développement Vite, code monté depuis `./frontend` | 5192 → 5173 |

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
| `CORS_ALLOWED_ORIGINS` | Origines autorisées à appeler l'API | `http://localhost:5192` |
| `VITE_API_BASE_URL` | Adresse de l'API vue par le navigateur | `http://localhost:8093/api/v1` |
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
| `plaintes` | Mécanisme de gestion des plaintes et retours : paramétrage (mécanisme, types, priorités, catégories, circuits et étapes), modèles prêts à l'emploi, contrôles d'activation, canevas Excel ; réception des dossiers (formulaire public, saisie agent, suivi par code) |

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
| `TypeDocument` | `nom`, `nom_pluriel`, `ordre`, `icone` | Maillon de la chaîne des documents (Cadre stratégique, Programme, Pilier…) : une rubrique du menu chacun |
| `CadreStrategique` | `nom`, `description`, `type_document`, `document_parent`, `element_parent` | Document stratégique d'un maillon, rattaché à un document d'un maillon au-dessus (ou à l'un de ses éléments) |
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
| `FinancementDocument` | `document`, `bailleur`, `montant` | Bailleurs d'un document de la chaîne (fiche) |
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
- **Import Excel** : toutes les colonnes placées avant « Sous-activité » (sauf « Code » et
  les attributs) sont des niveaux ; leurs noms deviennent les noms des niveaux du projet.
- **Attributs libres** (`Activite.attributs`, `SousActivite.attributs`, `{nom: texte}`,
  `projects/attributs.py`) : informations propres à l'organisation (« Responsable », « Lieu »…).
  - À l'import, une colonne dont l'en-tête commence par « Attribut : » (ou sa traduction :
    « Attribute: », « Atributo: », « سمة: ») n'est jamais un niveau, où qu'elle soit : sa valeur
    va à l'élément ou à la sous-activité de la même ligne. « Attribut : Description »,
    « Sources de vérification » et « Hypothèses » remplissent ces champs de l'élément. Le modèle
    en montre un exemple (« Attribut : Responsable », en bleu).
  - Saisie dans la fiche de l'élément et de la sous-activité (noms déjà utilisés dans le projet
    proposés) ; affichage dans l'arbre de planification, le rapport de suivi (PDF, Word, Excel :
    une colonne par attribut) et le cadre logique.
  - Ordre : JSON stocké sans ordre, l'ordre vient de `Projet.ordre_attributs` (colonnes du fichier
    importé, puis noms ajoutés par la fiche) ; l'API, l'écran et les exports le suivent.
  - Vue Tableau de la planification (format cadre logique de PTA) : une ligne par élément,
    bandeaux par niveau, une colonne par attribut, programmation par trimestre (X) ou dates.
- **Historique** : les anciens « Objectif général » et « Objectif spécifique » ont été
  convertis par la migration `projects.0023` en éléments des deux premiers niveaux, nommés
  ainsi ; les indicateurs qui y étaient rattachés ont suivi.

### 5.4 bis Chaîne des documents stratégiques

- **Maillons** (`strategy.TypeDocument`, paramétrables : « Chaîne des documents » sur la page
  des cadres stratégiques) : par exemple Cadre stratégique → Programme → Pilier 1 → Pilier 2 →
  Pilier 3, puis les projets. Le premier maillon est la rubrique « Cadre stratégique »
  (`/strategie`) ; chaque maillon suivant est une rubrique du menu à part
  (`/strategie/type/<id>`, mêmes droits que « Cadre stratégique »), avec ses propres documents
  (`CadreStrategique.type_document`), chacun avec ses propres niveaux et éléments.
- **Rattachement** : un document se rattache à un document d'un maillon au-dessus
  (`document_parent`), au document lui-même ou à l'un de ses éléments (`element_parent`). Chaque
  élément peut préciser l'élément d'un document au-dessus auquel il contribue
  (`ElementStrategique.contribue_a`, hérité par ce qui est en dessous) ; cela l'emporte sur le
  rattachement du document. Les projets se rattachent au dernier maillon (`Projet.cadre_strategique`).
- **Plusieurs éléments de rattachement** : un document a un élément principal (`element_parent`,
  le seul qui compte dans les budgets et les taux) et, pour information, d'autres éléments du même
  document parent (`elements_parents_secondaires`), affichés mais jamais comptés — pas de double
  compte, comme « Contribue aussi à » d'un projet. En Excel : codes séparés par « ; », le premier
  est le principal (fiche du document et feuille « Documents » de la chaîne). La répartition réelle
  entre plusieurs éléments passe par « Contribue à » sur chaque élément de la structuration.
- **Sauts de maillons** permis (un pilier 3 rattaché au programme, un projet rattaché à un
  pilier 1…) et signalés : `alertes_chaine` du document ou de l'élément (le nom évite
  `avertissements`, que l'interface notifie à chaque réponse), compte rendu d'import, contrôle
  de cohérence du projet. Refusé : un rattachement vers un maillon égal ou en dessous, un élément
  qui n'est pas du document parent.
- **Remontée** (`strategy/chaine.py`) : partant de l'élément d'une activité (ou du rattachement de
  son projet), on monte de document en document (contribution de l'élément ou de son plus proche
  ancêtre, sinon rattachement du document). Axes & budgets, Projets & budgets (avec le document
  par lequel arrive chaque projet) et Suivi stratégique d'un document comptent ainsi tout ce qui
  est rattaché en dessous, sur toute la chaîne, sans double compte.
- **Excel** : un seul fichier pour toute la chaîne (`cadres-strategiques/chaine/modele|export|importer`,
  `strategy/import_chaine.py`) — feuilles « Maillons », « Documents » (document, maillon, document
  parent, code de l'élément parent) et « Éléments » (document, niveau, code, nom, code parent,
  « Contribue à (code) », éventuellement « Document / CODE »). La structuration d'un seul
  document garde son format « plan », avec une dernière colonne facultative « Contribue à (code) ».
- **Fiche du document** (maillons après le premier : Programme, Piliers…) : les mêmes attributs
  qu'un projet, tous facultatifs — code, statut, dates, budget total et fonds propres, bailleurs
  et montants (`strategy.FinancementDocument`, saisis par leur nom via le champ d'écriture
  `bailleurs` ; avec des bailleurs, budget total = fonds propres + financements, recalculé par
  le serveur), responsable, utilisateurs affectés (un rôle restreint voit les documents
  auxquels il est affecté, en plus de ceux de ses projets), partenaire de mise en œuvre et
  consortium, pays et zones, cibles bénéficiaires, éléments de capitalisation. Formulaire à
  onglets comme celui d'un projet (`DocumentModal.tsx`), onglet « Fiche » sur la page du
  document (`FicheDocument.tsx`), résumé sur les cartes de la liste. Dans le fichier Excel de la
  chaîne, colonnes facultatives Code, Statut, Date de début, Date de fin, Budget total, Fonds
  propres et Responsable (feuille « Documents » ; une cellule vide ne change rien).
- **Excel d'un seul document** (page du document › « Importer depuis Excel » / « Exporter en
  Excel », `strategy/fiche_excel.py`) : pour un programme, un pilier…, même présentation que le
  modèle d'import d'un projet — feuilles « Fiche » (un champ par ligne, préremplie avec les
  valeurs actuelles, listes séparées par « ; »), « Financements » (un bailleur par ligne,
  remplace les bailleurs du document), « Structuration » (format plan, puis « Contribue à
  (code) ») et « Instructions » (jamais importée). L'export a le même format et se réimporte
  tel quel. Un cadre stratégique (premier maillon) garde le modèle de structuration seul ; un
  fichier de la chaîne importé depuis la page d'un document est importé comme fichier de la chaîne.
- **Export du mode Tableau** (onglet « Arborescence & saisie », bouton « Exporter le tableau »,
  `cadres-strategiques/<id>/tableau/?fichier=xlsx|pdf&programmation=trimestres|dates&annee=`,
  `strategy/tableau.py`) : pour un document de n'importe quel maillon, le tableau complet (tous les
  niveaux, sans le filtre de recherche) avec la programmation affichée, les bandeaux de couleur par
  niveau, les budgets sans double compte et les taux — mêmes calculs qu'à l'écran
  (`donnees_recap_axes`, aussi utilisé par `recap-axes`).
  `?contenu=simple` : export simple, la structure seule (code, niveau, élément en retrait,
  « Contribue à »), sans activités ni chiffres. Le menu « Exporter » (modes Arbre et Tableau)
  propose aussi le canevas de remplissage réimportable (`cadres-strategiques/<id>/export/`).
- **Même menu pour la planification d'un projet** (onglet Planification, modes Arbre et Tableau,
  `projets/<id>/planification/export/?contenu=complet|simple|canevas&fichier=xlsx|pdf`,
  `projects/export_planification.py`) : tableau complet (attributs, services, programmation,
  budget, taux), export simple (structure) et canevas = feuille « Planification » du modèle
  d'import, préremplie ; « Importer depuis Excel » (`projets/<id>/planification/importer/`) la
  réimporte dans le projet (`importer_planification` : met à jour les éléments de même libellé
  et même parent, ajoute les nouveaux, ne supprime rien). Refusé si la planification du projet
  passe par une demande d'approbation ; un projet clôturé reste en lecture seule (verrou).

### 5.5 Suppressions protégées

Les clés étrangères de la hiérarchie (projet, éléments de planification, niveaux du cadre,
indicateurs et valeurs) sont en `PROTECT` : aucune arborescence ne peut disparaître par
accident. Une suppression volontaire passe par les fonctions `supprimer_*_cascade` des
`services.py`, qui suppriment les éléments dans le bon ordre.

### 5.6 Doublons de bénéficiaires

La plateforme ne fusionne jamais automatiquement deux bénéficiaires. Elle **signale** les
doublons probables, traités à la main (écran « Doublons d'enregistrement »,
`services/duplicate_detection.py`), avec leurs motifs (`SignalementDoublon.motifs`) :

1. même numéro de pièce d'identité (espaces, tirets et casse ignorés) : doublon quasi certain ;
2. sinon, nom **et** prénom très proches (accents ignorés, éventuellement inversés ;
   présélection trigramme `pg_trgm`, puis ressemblance ≥ 0,8) **et** au moins une
   confirmation : même téléphone (sans indicatif), même date de naissance ou même localité ;
3. jamais signalés : sexe différent, année de naissance différente, ou deux pièces
   d'identité différentes.

« Revérifier les signalements » (`signalements-doublons/reverifier/`) repasse les signalements
en attente avec ces règles et retire ceux qui ne tiennent plus.

### 5.6 bis Fiche bénéficiaire : identifiant, variables, localisation, carte

- **Identifiant unique** `BEN-000123` attribué à la création (`Beneficiaire.identifiant`).
  Le QR code (`segno`, SVG) contient le lien `<plateforme>/beneficiaires/identifiant/BEN-…`,
  qui ouvre la fiche après connexion. Cartes imprimables (PDF, 8 par page A4) :
  `beneficiaires/cartes/?ids=` ou `?projet=` (`services/carte.py`).
- **Variables personnalisées** (`VariableBeneficiaire`, `services/variables.py`) : texte,
  nombre, date, oui/non, choix unique ou multiple ; pour tous les projets ou certains.
  Réponses gardées une fois par bénéficiaire (`Beneficiaire.reponses`, `{id: valeur}`,
  contrôlées selon le type). Le formulaire ne propose que celles des projets du bénéficiaire ;
  dans les exports Excel, une variable qui ne concerne pas le projet vaut « NA ». Le modèle
  d'import d'un projet (`?projet=`) reprend ses variables en colonnes (« NA » accepté).
- **Localisation aux niveaux du pays** : le modèle d'import a une colonne par niveau
  administratif configuré pour le pays (`?pays=`, ex. Région › Province › Commune) ; l'import
  lit les colonnes entre « Pays » et « Nom » dans l'ordre (anciens fichiers acceptés), crée
  le dernier niveau s'il manque. Export et import font l'aller-retour à l'identique.
- **Position GPS** facultative (latitude, longitude ; bouton « Ma position actuelle »).
- **Carte** (`/beneficiaires/carte`, `beneficiaires/carte/`, Leaflet + OpenStreetMap) :
  bénéficiaires positionnés par GPS, les autres regroupés au centre de leur localité (ou de
  la zone parente placée la plus proche), filtre par projet. Contours : geoBoundaries
  (`apps/geo/services/limites.py`, cache `LimiteAdministrative`, `limites-administratives/`),
  téléchargés au premier affichage ou par `charger_limites`. Le centre des zones
  (`Zone.latitude/longitude`) est trouvé par le nom (orthographe voisine acceptée) et
  **refusé s'il ne tombe pas dans le contour de la zone parente** (certaines sources nomment
  mal leurs contours, ex. les communes du Burkina en 2007) ; les zones absentes de la source
  (découpage plus récent) prennent le centre de leurs zones enfants, ou se placent à la main
  (Zones administratives).
- **Base topographique nationale** (BNDT de l'IGB pour le Burkina Faso, shapefiles WGS84) :
  `importer_bndt` (`apps/geo/services/bndt.py`, bibliothèque `pyshp`) remplace les contours
  geoBoundaries par ceux de la base, à jour du découpage de 2025 (17 régions, 47 provinces,
  352 communes, noms et point d'étiquette dans chaque contour), ajoute le réseau routier
  (`CoucheCarte` « routes », classes nationale / régionale / départementale) et les villes et
  villages nommés (`Localite`, sans l'habitat dispersé), puis place les zones. Contours et
  routes sont simplifiés (Douglas-Peucker) ; les localités sont servies par zone visible
  (`localites/?bbox=`, 3 000 au plus, villes d'abord). Les fichiers sources ne sont pas
  versionnés.
- **Rubrique « Carte »** (`/carte`, module `/carte` dans les droits ; l'ancienne adresse
  `/beneficiaires/carte` y renvoie) : filtres sur un ou plusieurs projets et une ou plusieurs
  zones (`?projet=1,2&zone=3,4` : les zones et celles en dessous, plus les points GPS sans
  localité tombant dans leurs contours, réunis pour le cadrage et la carte imprimée ;
  `beneficiaries/services/carte_donnees.py`).
- **Couches importées** (`geo.CoucheImportee`, `geo/services/import_sig.py`) : shapefile en
  .zip (avec .prj), GeoPackage, GeoJSON ou KML, lus avec geopandas, reprojetés en WGS 84,
  simplifiés et réparés ; colonnes techniques écartées, attribut des noms reconnu (modifiable),
  20 000 objets au plus. Affichées en couches à cocher (survol : nom, clic : attributs).
- **Carte imprimable** (`beneficiaries/services/carte_officielle.py`,
  `beneficiaires/carte/export/`) : modèle des cartes officielles de la plateforme HIMO —
  mise en page A0 mise à l'échelle pour A1/A3/A4, orientation la plus lisible ou imposée,
  échelle réelle, grille degrés-minutes, nord, situation, chiffres clés, légende, tableau des
  localités, cartouche ; projection UTM de la zone ; PDF vectoriel ou PNG ; deux générations
  à la fois au plus. Fond au choix comme à l'écran (`fond=neutre|osm|satellite|aucun`, tuiles
  intégrées par contextily, ≈ 200 points par pouce en A4/A3 et 100 au-delà, 300 tuiles au
  plus ; une tuile test est vérifiée d'abord : si le service refuse ou ne répond pas, la carte
  sort sur fond clair avec une note). Les serveurs d'OpenStreetMap interdisent ce
  téléchargement (tuiles « Access blocked ») : à l'impression, « OpenStreetMap » utilise la
  carte routière Esri World Street Map ; noms des bénéficiaires GPS
  (`couches=…,beneficiaires`).
- **Bénéficiaires sur la carte** : au clic sur une localité, la liste nominative (identifiant,
  sexe, tranche d'âge, téléphone, projets, lien vers la fiche ; 300 au plus) ; au clic sur un
  point GPS, sa fiche ; couche « Noms des bénéficiaires ».
- **Carte par zone** (`geo/services/synthese.py`, `carte/synthese/?pays=&niveau=&projet=&zone=`) :
  régions, provinces ou communes coloriées selon un indicateur du catalogue `CATALOGUE`
  (regroupé comme le tableau de bord : vue d'ensemble, budget et financements, projets,
  bénéficiaires, évolution ; même catalogue dans `frontend/src/utils/carteParZone.ts`), valeurs
  de chaque zone dans `valeurs`. À l'écran, plusieurs indicateurs à la fois : le premier colorie
  les zones (5 classes, couleurs par famille, mêmes qu'à l'impression : `par_zone=…&niveau_zone=…`),
  tous sont écrits sur chaque zone ; au clic, leurs valeurs et les projets présents (taux,
  budget, bénéficiaires). Sommes projet par projet (budgets, activités, cibles…), bailleurs et
  partenaires comptés sans doublon. La carte imprimée reprend les mêmes indicateurs
  (`par_zone=projets,budget,…`) : couleur du premier, tous écrits sur chaque zone et dans le
  tableau (4 colonnes au plus).
- **Filtres du tableau de bord sur la carte** (`?statuts=`, `?annee=` ou `?date_debut=&date_fin=`,
  `?periode=`, voir `dashboard/filtres.py` : `projets_retenus`) : la carte, la synthèse par
  zone et la carte imprimée ne portent que sur les projets retenus et leurs bénéficiaires. Un projet est présent dans sa zone, dans
  les zones qu'elle contient ou qui la contiennent, sur tout le pays, ou là où habitent ses
  bénéficiaires ; son budget n'est pas réparti entre les zones.
- **Projets d'une zone** (`projets_zone` dans `beneficiaires/carte/?zone=`) : projets visibles
  qui interviennent dans la zone (zones d'intervention, tout le pays, ou bénéficiaires sur
  place) avec leur nombre de bénéficiaires ; la liste des projets de la carte s'y limite.
- **Couches de la carte** au choix : régions, provinces, communes, routes, villes et villages
  (à partir du zoom 10), noms (selon le zoom : régions, puis provinces, communes, villages à
  partir du zoom 12) ; fond neutre sans noms (Esri, par défaut quand une base nationale est
  importée), OpenStreetMap, satellite (Esri) ou aucun.

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

### 5.11 Organisation, partenaires et liens multiples

Modèles dans `apps/partners` (tests : `apps/partners/test_organisation.py`) :

- **Structure de l'organisation** (`StructureOrganisation`) : une ou plusieurs organisations
  (structures de premier niveau), chacune avec ses services, directions, secteurs… en arbre
  de profondeur libre (`parent`, `type` libre, nouveaux types tapés à la volée). Paramétrée
  par l'Administrateur (écran Organisation : organigramme avec, pour chaque structure, ses
  projets et ses membres, et vue « par projet »). Projets et membres d'une structure se
  règlent aussi en une fois : `structures-organisation/{id}/affectations/` (un membre devient
  « Organisation (interne) » de cette structure). Les services qui travaillent sur un projet
  et leurs membres : `Projet.services_detail`. Affectation à une ou plusieurs structures :
  `Projet.structures`, `Activite.structures` (une partie du projet), `CadreStrategique.structures`,
  `ElementStrategique.structures`.
- **Parties prenantes** (`PartiePrenante`, catégories `CategoriePartiePrenante`) : répertoire
  unique, puis sélection sur les projets, cadres et éléments stratégiques (`parties_prenantes`).
  Créables à la volée par un utilisateur qui peut écrire ; modifiées par l'Administrateur.
- **Types de partenaires** : mise en œuvre, consortium, bailleur. Le type n'est qu'une valeur
  par défaut : une même organisation peut être de mise en œuvre sur un projet et du consortium
  sur un autre ; c'est son rôle dans chaque projet qui compte (`projets_mise_en_oeuvre_codes`,
  `projets_consortium_codes`).
- **Rôle des partenaires dans un projet** (`projects.PartenaireProjet`) : partenaire, nature
  (consortium ou mise en œuvre), chef de file, rôle, et `elements` = éléments de la
  planification qu'il réalise. Créer un rôle ajoute le partenaire au projet (consortium, ou
  mise en œuvre si le projet n'en a pas). Les partenaires du projet sans rôle sont affichés
  « rôle non précisé » dans l'onglet Partenaires.
- **Structure des utilisateurs** (`User.type_structure` : interne, consortium, mise en œuvre,
  partie prenante, bailleur) avec le lien correspondant (`structure_interne`, `partenaire` ou
  `partie_prenante`) ; les autres liens sont vidés à l'enregistrement.

**Liens multiples entre niveaux** : un élément peut contribuer à plusieurs éléments d'un
niveau supérieur, du même cadre ou d'un autre document (`ElementStrategique.parents_secondaires`,
`Projet.elements_strategiques_secondaires`, `Activite.axes_strategiques_secondaires`). Le lien
principal (`element_parent`, `element_strategique`, `axe_strategique`) reste le seul qui
structure l'arbre et compte dans les budgets et les taux : les autres liens sont informatifs
(« contribue aussi à »), pour éviter le double compte. Dans un même cadre, un lien
secondaire ne peut viser qu'un niveau supérieur, jamais le parent principal ni un descendant.

### 5.12 Rapports, cadre logique, risques, suivi stratégique, partage

- **Plusieurs bailleurs par projet** : un `Financement` par bailleur, avec son montant. Ils se
  saisissent dans le formulaire du projet (bloc « Bailleurs et montants », autant de lignes que
  de bailleurs ; un nom inconnu crée le bailleur) ou dans l'onglet Financement, et à l'import
  Excel par la feuille « Financements » (Bailleur, Type de bailleur, Montant financé) des modèles
  projet et planification complète (`importer_financements`). Dès qu'il y a des financements,
  `budget_total` = fonds propres + financements (rallonges comprises). L'ancien champ unique
  `partenaire_bailleur` reste lu pour les fichiers antérieurs.
- **Rallonges de fonds** (`partners.RallongeFinancement`) : un bailleur ajoute des fonds en
  cours de projet, avec date et motif obligatoire. Le total d'un financement est
  `montant_finance` + rallonges ; le coût total du projet (`budget_total`) et les répartitions
  du tableau de bord les comptent.
- **Rapport financier seul** (`reports/financier.py`, `rapports/financier/{projet}/`) : sources
  (fonds propres, bailleurs, rallonges), rallonges et motifs, exécution par composante (premier
  niveau qui compte plusieurs éléments), détail par élément, dépenses par trimestre ; sections
  et période des dépenses au choix ; PDF, Word ou Excel. Mêmes règles que le reste : saisies
  approuvées seulement, budget compté au niveau le plus bas où il est saisi.
- **Version Word des rapports** (`reports/word.py`) : un convertisseur unique transforme le HTML
  des exports PDF en .docx (titres, tableaux, gras/couleurs, paysage) — PDF et Word ont donc
  toujours le même contenu. Les exports PDF sont séparés en `html_…()` + `exporter_…_pdf()`.
- **Cadre logique** (`reports/cadre_logique.py`, onglet du projet) : une ligne par élément de la
  planification (niveaux libres) avec ses indicateurs (référence, cible, réalisé), les
  champs `Activite.sources_verification` et `Activite.hypotheses`, saisis sur place ; les
  indicateurs rattachés au projet forment la première ligne. Export PDF et Word (paysage).
- **Risques** (`projects.Risque`, `projects.EvaluationRisque`, onglet du projet) : nature
  interne ou externe, catégorie, élément exposé, probabilité × impact de 1 à 5 (niveau faible
  1-4, moyen 5-9, élevé 10-15, critique 16-25), atténuation, contingence, responsable
  (intervenant), prochaine revue. Chaque réévaluation est gardée ; la plus récente (par date)
  donne la cotation et le statut courants, en supprimer une rétablit la précédente. Codes
  R1, R2… ; registre exportable (matrice, registre, suivi) en PDF et Word.
- **Suivi propre aux documents stratégiques** (`strategy/suivi.py`, onglet « Suivi
  stratégique ») : pour chaque élément, l'avancement calculé depuis les projets qui y
  contribuent (activités rattachées à lui ou à un élément en dessous, sans double compte),
  ses indicateurs (ceux sans projet se saisissent directement), des appréciations par période
  (`strategy.AppreciationStrategique` : état, analyse, difficultés, recommandations) et des
  pièces justificatives (`PieceJustificative`, rattachée à une valeur d'indicateur ou à une
  appréciation, téléchargée par `pieces-justificatives/{id}/telecharger/`, compte connecté).
  Rapport de suivi du document en PDF et Word. Correction au passage : le rattachement
  indicateur ↔ élément stratégique (table `IndicateurElement`) est maintenant enregistré par
  l'API (il était ignoré en silence).
- **Liens de partage** (`reports.LienPartage`, `reports/partage.py`) : lien secret (jeton de
  32 octets) vers le tableau de bord (projets visibles par le créateur, filtres du moment)
  ou le suivi d'un projet (tout, activités ou indicateurs), en lecture seule et sans compte,
  avec expiration facultative, désactivable, et un compteur de consultations. La page
  publique `/partage/{jeton}` réutilise les écrans habituels : `utils/partage.ts` fournit le
  jeton, les hooks lisent alors `public/partage/{jeton}/{ressource}/` (sans authentification)
  et les actions d'écriture et d'export sont masquées.

### 5.13 Langues de l'interface

- **Langues** : français (langue source), anglais, arabe (affichage de droite à gauche),
  espagnol, allemand (`core.models.LANGUES`). Chaque utilisateur choisit la sienne
  (`User.langue`, sélecteur en haut de l'écran) ; à défaut, la langue par défaut de
  l'organisation (`ConfigurationMenu.langue_defaut`) s'applique, y compris sur la page de
  connexion. Juste après la connexion, la langue du compte l'emporte : la page est chargée
  sur `/` dans cette langue (recharger `/login` y ramènerait l'utilisateur).
- **Textes de l'interface** : tout texte affiché passe par `voc("…")` ou `` voc`…${x}…` ``
  (`utils/vocabulaire.ts`), qui applique le vocabulaire de l'organisation puis la traduction
  (`utils/i18n.ts`). Les valeurs insérées deviennent `{0}`, `{1}`… dans les catalogues
  `src/i18n/{en,ar,es,de}.json`, clés = texte français exact. Pas de pluriel fabriqué
  (`projet{n > 1 ? "s" : ""}`) : écrire les deux phrases complètes, faux sinon en arabe ou
  en allemand.
- **Messages du serveur** (erreurs de validation, contrôles de cohérence) : envoyés en
  français ; l'interface les traduit, y compris ceux qui contiennent des valeurs, en les
  reconnaissant d'après leur modèle `{0}`. Les données saisies (noms de projets, de niveaux,
  de rôles créés par l'organisation) ne sont pas traduites ; `traduireDonnee()` ne traduit
  que celles qui figurent telles quelles au catalogue (« Région », rôles système…).
- **Mettre à jour les traductions** après avoir ajouté ou modifié des textes :
  1. relever les messages du serveur :
     `docker compose exec -T backend python - < frontend/scripts/textes_serveur.py > frontend/src/i18n/serveur.json` ;
  2. dans le conteneur frontend, `node scripts/extraire-textes.cjs` : écrit `sources.json`
     (liste des textes), `contextes.json` (fichiers où chaque texte apparaît) et indique les
     textes encore sans traduction pour chaque langue ;
  3. compléter les catalogues : même clé, mêmes `{0}`, `{1}`.
- **Corrections par l'Administrateur** (écran Langues, `core.TraductionCorrigee`) : une
  correction remplace la traduction livrée pour tous, au chargement suivant de la page. Elle
  doit garder exactement les emplacements `{0}`, `{1}`… du texte français (contrôlé à la saisie
  et par le serveur). Export CSV d'une langue entière (séparateur `;`, BOM UTF-8 pour Excel),
  import tout-ou-rien du fichier complété, historique des corrections et retraits
  (`django-simple-history`), écran d'apparition de chaque texte et filtre par écran.
- **Fichiers produits par le serveur** (rapports PDF et Word, exports Excel, modèles d'import,
  carte imprimée, `core/langues.py`) : produits dans la langue de l'interface de la personne
  qui les télécharge (en-tête `Accept-Language` envoyé par `api/client.ts`, ou `?langue=`).
  - Les vues concernées sont décorées par `@dans_la_langue_demandee` ; ailleurs (imports,
    messages d'erreur), le serveur reste en français.
  - Le texte est écrit en français dans le code et traduit au moment où le fichier est produit :
    `traduire_html()` (PDF, Word ; en arabe, `dir="rtl"` et paragraphes Word de droite à gauche),
    `traduire_classeur()` (cellules, feuilles, listes déroulantes ; feuilles de droite à gauche
    en arabe), `traduire_figure()` (carte matplotlib ; lettres arabes liées par
    `arabic-reshaper` et `python-bidi`). `v()` traduit aussi, et ce qu'il a traduit n'est pas
    retraduit avec le document (« Prénom » → « Nombre » ne doit pas devenir « Número »).
  - Catalogues `backend/apps/core/i18n/{en,ar,es,de}.json` (clé = texte français, valeurs
    insérées `{0}`), complétés par les corrections de l'écran Langues (cache de 10 s). Une
    clé à valeurs insérées n'est reconnue seule que si son texte fixe est assez précis
    (`_modele_assez_precis`) ; sinon, appeler `traduire_modele("Par {0}", valeur)`.
  - Mise à jour : `docker compose exec backend python manage.py extraire_textes_fichiers`
    (écrit `sources.json`, liste les textes sans traduction et signale deux en-têtes de modèle
    traduits pareil) ; contrôle : `manage.py verifier_traductions_fichiers en` produit chaque
    fichier et liste les textes restés en français (hors données saisies).
- **Modèles d'import dans une autre langue** : téléchargés traduits (feuilles, en-têtes,
  consignes, exemples), ils se réimportent tels quels. `ramener_classeur()` ramène noms de
  feuilles et en-têtes au français (toutes langues, noms de feuilles raccourcis à 31 caractères
  compris) ; `vers_francais()` ramène les valeurs à choix saisies dans une autre langue (« Yes »,
  « In progress », « Quarterly », « Female »…). Les codes (`EN_COURS`, `DIRECT`…) ne se traduisent
  pas. L'export Excel des bénéficiaires ne traduit que ses en-têtes : ses données se réimportent
  telles quelles. Tests : `core/test_modeles_traduits.py`, `suivi/test_canevas.py`.

### 5.14 Mécanisme de gestion des plaintes et retours (lots 1 à 5 : paramétrage, réception, traitement, délais, confidentialité)

Une installation = une organisation : tout le mécanisme se paramètre, sans rien coder, pour
des communautés, des bénéficiaires, le personnel ou tout autre public. Application `plaintes`,
écran `/plaintes`, droit du module « Plaintes et retours » (`/plaintes`).

- **Mécanisme** (`Mecanisme`, une seule ligne, `Mecanisme.courant()`) : nom, anonymat
  autorisé, langues du formulaire public, texte d'information, préfixe des numéros de dossier,
  délais en jours ouvrés ou calendaires, durées de conservation (ordinaire / sensible, à fixer
  par l'organisation : aucune valeur imposée), projets couverts (vide = tous).
- **Listes** : types de retours (`TypeRetour`), priorités avec délai (`Priorite`, drapeau
  `urgente`), catégories sur deux niveaux (`Categorie`, drapeau `sensible`, circuit et délai
  propres facultatifs), circuits de traitement (`Circuit`, ordinaire ou confidentiel, un par
  défaut par nature) et leurs étapes (`EtapeCircuit` : délai, rôle ou personne responsable,
  étape de clôture). Désactiver plutôt que supprimer : rien n'est effacé.
- **Modèles** (`modeles_mecanisme.py`) : « Mécanisme standard auprès des communautés » et
  « Réclamations internes du personnel ». Un modèle ajoute ce qui manque (par nom, sans doublon)
  et installe toujours le circuit confidentiel et les catégories sensibles.
- **Règles verrouillées** (protection des personnes, non paramétrables) : les catégories
  « Exploitation et abus sexuels » et « Harcèlement sexuel » (`verrouillee`) restent sensibles,
  actives et ne se suppriment pas (renommer reste possible) ; une catégorie sensible (ou
  sous-catégorie d'une catégorie sensible) passe par un circuit confidentiel ; chaque étape d'un
  circuit confidentiel est confiée à une personne nommément désignée, jamais à un rôle ; au moins
  une priorité urgente reste active.
- **Activation contrôlée** (`controles.py`) : `controler_activation()` liste ce qui manque
  (renvoyé dans `controles` du mécanisme, affiché tel quel). Le mécanisme ne s'active que si la
  liste est vide : nom, langue, durées de conservation, un type, une catégorie ordinaire, une
  priorité urgente, un circuit par défaut de chaque nature, circuits valides
  (`controler_circuit()` : au moins une étape, clôture en dernier, un responsable par étape).
- **Canevas Excel** (`excel.py`) : tout le paramétrage dans un classeur (feuilles Mécanisme,
  Types de retours, Priorités, Circuits — une ligne par étape —, Catégories, Instructions),
  prérempli et traduit dans la langue de l'utilisateur ; réimport « au mieux » : éléments
  retrouvés par leur nom, étapes d'un circuit présent remplacées, erreurs ligne par ligne.
  Tests : `plaintes/tests.py`.

**Réception (lot 2)** — `reception.py`, `public.py`, modèle `Dossier` :

- **Interface d'entrée commune** : `recevoir(donnees, canal, saisi_par, public)` applique à tous
  les canaux les mêmes règles (mécanisme ouvert, type et catégorie actifs, projet couvert,
  anonymat, coordonnées cohérentes avec le mode de réponse, consentement), la sensibilité, le
  circuit et la première étape, le numéro et le code de suivi. Les canaux futurs (courriel, SMS,
  import, KoboToolbox…) n'auront qu'à l'appeler.
- **Numéro et code** : numéro lisible `PREFIXE-ANNEE-00001` (séquence par année,
  `CompteurDossiers` verrouillé), identifiant interne `uid` aléatoire ; code de suivi aléatoire
  `XXXX-XXXX-XXXX` (sans caractères ambigus) remis une seule fois, conservé uniquement sous
  forme d'empreinte SHA-256 (`empreinte_code_suivi`). Aucun ne contient de donnée personnelle.
- **Sensibilité automatique** : catégorie sensible (ou sous-catégorie d'une catégorie
  sensible), ou réponse « oui » à la question système « concerne le comportement d'un membre du
  personnel ou d'un partenaire ». Le dossier part alors dans le circuit confidentiel par défaut.
- **Visibilité** (`dossiers_visibles`) : l'Administrateur voit tous les dossiers, confidentiels
  compris (choix de l'organisation, qui s'écarte de la règle 7.3 du cahier des charges) ; les
  autres utilisateurs du module voient les dossiers ordinaires, et les dossiers sensibles
  seulement s'ils sont responsables d'une étape de leur circuit. L'agent qui saisit un dossier
  sensible n'en garde que le numéro (absent de ses listes, de sa recherche et des compteurs, 404 sur la fiche). Le module
  « Plaintes et retours » caché est refusé même en lecture (`LECTURE_BLOQUEE_SI_MASQUE`).
- **Formulaire public** (`/plainte`, `/plainte?projet=ID`) et **page de suivi**
  (`/plainte/suivi`) : sans compte, sur téléphone, dans toutes les langues de l'interface (arabe
  de droite à gauche). Anonymat : aucune coordonnée conservée. Anti-abus : champ piège
  `site_web` et limite d'envois par connexion (10 dépôts et 30 consultations de suivi par heure,
  réglables par `PLAINTES_LIMITE_DEPOTS` / `PLAINTES_LIMITE_SUIVIS`) ; le compteur ne garde
  qu'une empreinte de l'adresse IP, jamais l'adresse. La page de suivi ne renvoie que numéro,
  date et statut général (reçu, en cours, réponse donnée, clôturé).
- **Saisie par un agent** : canal d'origine, date réelle de réception, recueilli directement ou
  non, priorité facultative ; aucun champ ne l'oblige à saisir une information indisponible.
  Avant l'envoi d'un retour sensible, un avertissement rappelle qu'il ne pourra plus le consulter.
- **QR code** du formulaire public (général ou par projet) : `plaintes/qr/`.
- Tests : `plaintes/test_reception.py` (anonymat et suivi par code, règles du formulaire,
  limitation des envois, circuit confidentiel et perte d'accès de l'agent, module caché).
- Limites connues, traitées aux lots suivants : coordonnées et récits non chiffrés (lot 5), pas
  encore de pièces jointes ni d'accusé de réception par message, contenus paramétrés (types,
  catégories, textes) non traduits par l'organisation. Avec plusieurs processus serveur, la
  limite d'envois est comptée par processus tant qu'aucun cache partagé n'est configuré.

**Traitement (lot 3)** — `traitement.py`, modèles `ActionDossier` (journal) et `VueDossiers` :

- **Opérations** (POST `plaintes/dossiers/{id}/<opération>/`), toutes vérifiées côté serveur et
  tracées dans le journal du dossier (auteur, date, détail du changement) :
  `classer` (type, catégorie, priorité, projet), `affecter`, `recuser` (le gestionnaire se retire,
  avec motif), `etape` (toute étape du circuit sauf la clôture), `noter` (note interne ou action
  corrective, possible même clôturé), `communiquer` (échange avec le plaignant : sens, moyen,
  objet — accusé de réception, prise en charge, demande de complément, décision, clôture,
  satisfaction), `decider`, `cloturer`, `rouvrir`, `recours`, `lier`.
- **Statut public** : « Reçu » jusqu'à la première action, « En cours » ensuite, « Réponse
  donnée » quand la décision est communiquée (exige une décision enregistrée), « Clôturé ».
- **Clôture motivée** : issue (réponse apportée, non fondé, référé, hors périmètre, sans suite),
  motif, décision enregistrée et indication du retour au plaignant, ou la raison pour laquelle il
  n'a pas pu être informé. Sortie « Référée » : acteur externe et consentement du plaignant exigés.
- **Réouverture** : dossier clôturé, motif obligatoire, réservée à l'Administrateur et au
  Coordonnateur général (`ROLES_REOUVERTURE`). **Recours** : sur une réponse donnée ; le dossier
  repart sans gestionnaire et ne peut pas être confié au premier gestionnaire (`gestionnaire_initial`).
- **Confidentialité** : un dossier reclassé dans une catégorie sensible passe aussitôt au circuit
  confidentiel (la personne qui l'a reclassé en perd l'accès si elle n'est pas habilitée) ; la
  sensibilité n'est jamais levée automatiquement. Un dossier confidentiel ne peut être confié qu'aux
  points focaux de son circuit ou à un Administrateur (`personnes_habilitees`). Dossiers liés et
  dossiers possiblement liés : seulement parmi les dossiers visibles.
- **Liste** : vues prêtes (`?vue=` : `mes_dossiers`, `a_traiter`, `urgents`, `sans_responsable`,
  `attente_decision`, `a_cloturer`, `recours`), filtres (statut, canal, projet, catégorie — une
  catégorie principale inclut ses sous-catégories —, priorité, gestionnaire, période), recherche
  par numéro, pagination. **Mes vues** : filtres enregistrés par utilisateur (`plaintes-vues/`,
  hors de `/plaintes/` pour qu'un utilisateur en lecture seule puisse aussi enregistrer les siennes).
- **Doublons** : `possiblement-lies/` propose les dossiers du même projet et de la même catégorie
  reçus à moins de 30 jours ; rien n'est jamais fusionné automatiquement.
- Tests : `plaintes/test_traitement.py` (scénario 3 de bout en bout, transitions interdites,
  recours, reclassement sensible, vues, liens, commande de démonstration).

**Délais et alertes (lot 4)** — `delais.py`, modèles `JourFerie` et `RappelDossier` :

- **Échéance du dossier** (`Dossier.echeance`) : le plus court des délais fixés par la catégorie
  (ou sa catégorie principale) et par la priorité, sinon le délai par défaut du mécanisme
  (`delai_defaut_jours`), compté depuis la réception, plus les prolongations accordées.
  **Échéance de l'étape** (`echeance_etape`) : délai de l'étape en cours, compté depuis l'entrée
  dans l'étape (`date_entree_etape`). Jours calendaires ou ouvrés (`Mecanisme.jours_ouvres` : sans
  samedis, dimanches ni jours fériés du calendrier `JourFerie`).
- **Recalcul** (`recalculer`) à la réception, au classement, au changement d'étape, à la
  réouverture, au recours et à la prolongation ; `recalculer_ouverts` après un changement de délai
  dans le paramétrage (priorité, catégorie, étape, délai par défaut, jours ouvrés, jours fériés).
- **Contrôle planifié** (`verifier_echeances`, commande `verifier_echeances_plaintes`, appelée par
  `check_deadlines` toutes les heures — jamais au chargement des pages) : rappel au gestionnaire
  quand l'échéance approche (`rappel_jours_avant`, aux superviseurs si personne n'est affecté) ;
  en retard, notification au gestionnaire et escalade aux superviseurs (`escalade_active`) ; au plus
  un rappel par dossier et par jour (`RappelDossier`, contrainte d'unicité) ; le passage en retard
  est inscrit au journal (action `RETARD`, historique des retards) et marque `en_retard`.
- **Superviseurs** : Administrateurs et Coordonnateur général pour un dossier ordinaire ; pour un
  dossier confidentiel, seulement les personnes habilitées de son circuit et les Administrateurs.
- **Prolongation** (`prolonger`) : 1 à 180 jours, motif obligatoire, réservée à l'Administrateur
  et au Coordonnateur général, tracée au journal (`PROLONGATION`).
- **Notifications d'événements** (type `PLAINTE`, dans l'application et par courriel si
  `notifications_courriel`) : nouveau dossier (responsables de la première étape), dossier urgent
  (superviseurs, aussitôt), affectation (nouveau gestionnaire), recours (superviseurs), échéance
  proche, retard. Envoyées après l'enregistrement (`transaction.on_commit`). Pour un dossier
  confidentiel : titre neutre avec le seul numéro, message « Connectez-vous… », aucun contenu.
- **Vue « En retard »** (`?vue=en_retard`, calculée sur les dates, pas sur le drapeau) et colonne
  Échéance de la liste ; fiche : échéances du dossier et de l'étape, bouton « Prolonger le délai ».
- Paramétrage : délai par défaut, rappel avant l'échéance, escalade, courriel (onglet Mécanisme) ;
  onglet **Calendrier** (jours fériés, bouton pour les jours fériés fixes du Burkina Faso).
- Tests : `plaintes/test_delais.py` (jours ouvrés, échéances et recalcul, retard, rappel unique,
  escalade, échéance proche, prolongation, notifications et confidentialité).

**Circuit confidentiel complet (lot 5)** — `confidentiel.py`, `chiffrement.py`, `export_fiche.py`,
modèles `Prestataire` et `Referencement` :

- **Chiffrement** (`TexteChiffre`) des données protégées : récit, lieu, nom, téléphone, courriel,
  personnes mises en cause (noms libres), décision, motif de clôture, notes du journal
  (`ActionDossier.texte`) — y compris dans l'historique (`HistoricalDossier`). Clé Fernet propre à
  l'installation, hors du code et de la base : `PLAINTES_CLE_CHIFFREMENT` (plusieurs clés séparées
  par des virgules pour une rotation ; vide en développement : clé dérivée de `DJANGO_SECRET_KEY`,
  avertissement `plaintes.W001` hors mode DEBUG). Le vide n'est pas chiffré (filtres « sans
  décision »). Migration `0006` : chiffrement des données existantes. **Ne jamais perdre la clé.**
- **Marquage manuel** : `plaintes-signaler/{id}/` (hors de `/plaintes/`, possible même en lecture
  seule) ; effet immédiat, le signalant perd l'accès s'il n'est pas habilité. **Levée** :
  `lever-sensibilite`, par un point focal du circuit ou un Administrateur, motif obligatoire ;
  refusée si la catégorie est sensible, si des personnes sont mises en cause ou si le retour vise le
  personnel. Jamais automatique.
- **Personnes mises en cause** (`mis_en_cause_utilisateurs`, `mis_en_cause_libre`), à la saisie ou
  par `mettre-en-cause` : exclues du dossier quel que soit leur rôle (`dossiers_visibles`), de ses
  notifications, de l'affectation et des escalades ; le dossier devient confidentiel ; si l'une
  d'elles est responsable d'une étape du circuit confidentiel, il part au **circuit alternatif**
  (`Mecanisme.circuit_alternatif`, installé par les modèles, obligatoire pour l'activation).
- **Assistance et référencement** : annuaire `Prestataire` (paramétrage, onglet « Prestataires
  d'assistance ») ; `assistance` enregistre prestataire, type, date et consentement (obligatoire),
  jamais le contenu des échanges.
- **Export** `exporter` (POST, PDF) : filigrane au nom de la personne et à la date sur chaque page,
  mention « Confidentiel » ; pour un dossier confidentiel, motif et confirmation exigés ; tracé au
  journal (`EXPORT`).
- **Conservation** : `fin_de_conservation` (date de clôture + durée ordinaire ou sensible) ;
  `a_anonymiser` ; la tâche planifiée prévient les Administrateurs une fois par jour (vue
  `?vue=a_anonymiser`) ; `anonymiser` (Administrateur, confirmation) efface récit, identité,
  coordonnées, personnes mises en cause, notes, décision et l'historique détaillé, et garde numéro,
  dates, type, catégorie, canal, statut et issue pour les statistiques. **Suspension légale**
  (`suspendre`, Administrateur, motif) : bloque l'anonymisation tant qu'elle dure.
- « Anonyme vis-à-vis de l'organisation » : dossier anonyme saisi par un agent.
- Tests : `plaintes/test_confidentiel.py` (chiffrement en base et dans l'historique, scénario 7 et
  circuit alternatif, marquage par un utilisateur en lecture seule et levée, assistance, export,
  conservation, suspension et anonymisation).
- Non couvert à ce stade : habilitation « sensible » distincte validée par une deuxième personne,
  double authentification, pièces jointes chiffrées (à prévoir avec les pièces jointes).

Lots suivants prévus : pilotage (tableaux de bord, indicateurs, rapports), modèles de messages.

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
| Cadre stratégique | `cadres-strategiques/`, `types-niveaux/`, `elements-strategiques/`, `appreciations-strategiques/` |
| Partenaires | `partenaires/`, `bailleurs/`, `financements/`, `rallonges-financement/`, `intervenants/` |
| Projets | `projets/`, `activites/` (éléments de planification, tous niveaux), `sous-activites/`, `niveaux-activite/`, `equipes/`, `risques/`, `evaluations-risques/` |
| Partage | `liens-partage/` (les siens ; tous pour l'Administrateur) |
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
| GET | `projets/` | Liste allégée, sans la planification ni les services de chaque projet (`?planification=1` pour les avoir) ; la fiche `projets/{id}/` les renvoie toujours |
| GET / POST | `cadres-strategiques/chaine/modele/`, `…/chaine/export/`, `…/chaine/importer/` | Chaîne des documents en Excel (maillons, documents, éléments) |
| CRUD | `types-documents/` | Maillons de la chaîne (écriture : Administrateur) |
| GET | `activites/arborescence/` | Tous les éléments de planification visibles en version allégée (id, projet, parent, libellé), pour les sélecteurs |
| GET / POST | `indicateurs/modele-import/`, `indicateurs/importer/` | Modèle et import Excel des indicateurs |
| GET / PUT / PATCH | `parametres-alerte/` | Délai d'alerte avant échéance |
| GET / PUT | `paliers-alerte/` | Grilles d'alerte (globale ou par portée) |
| GET / POST | `beneficiaires/modele-import/`, `beneficiaires/importer/` | Modèle et import Excel des bénéficiaires |
| GET | `beneficiaires/{id}/qr/`, `beneficiaires/cartes/` | QR code (SVG) d'une fiche ; cartes à imprimer (PDF, `?ids=` ou `?projet=`) |
| GET | `beneficiaires/identifiant/{BEN-…}/` | Fiche retrouvée par son identifiant (lien du QR code) |
| GET | `beneficiaires/carte/` | Données de la carte des bénéficiaires (`?projet=`) |
| CRUD | `variables-beneficiaires/` | Variables personnalisées (modification : Administrateur) |
| POST | `signalements-doublons/reverifier/` | Repasse les signalements en attente avec les règles actuelles |
| GET | `limites-administratives/` | Contours GeoJSON d'un niveau (`?pays=BF&niveau=2`) et leur source |
| GET | `couches-carte/` | Couche d'habillage importée (`?pays=BF&cle=routes`) |
| GET | `localites/` | Villes et villages d'une zone (`?pays=BF&bbox=sud,ouest,nord,est`) |
| GET / POST / PATCH / DELETE | `couches-importees/`, `couches-importees/{id}/geojson/` | Couches SIG importées (création : envoi multipart du fichier) et leurs objets |
| GET | `beneficiaires/carte/export/` | Carte imprimable : `?projet=&zone=&sortie=pdf` ou `png`, `papier=A0` à `A4`, `orientation=auto`, `portrait` ou `paysage`, `couches=…`, `importees=1,2` |
| GET | `rapports/financier/{projet}/` | Rapport financier : `?fichier=pdf, docx ou xlsx&sections=sources,rallonges,execution,detail,trimestres&debut=&fin=` |
| GET | `rapports/cadre-logique/{projet}/` | Cadre logique (JSON), ou `?fichier=pdf` ou `docx` |
| GET | `rapports/risques/{projet}/` | Registre des risques : `?fichier=pdf` ou `docx` |
| GET | `rapports/suivi-strategique/{cadre}/` | Suivi d'un document stratégique : `?fichier=pdf` ou `docx` |
| GET | `suivi/projets/{id}/exporter/word/`, `periodes-planification/{id}/exporter/word/`, `…/exporter-suivi/word/` | Versions Word des exports de suivi et de planification |
| GET | `cadres-strategiques/{id}/suivi/`, `elements-strategiques/{id}/suivi/` | Suivi stratégique : vue d'ensemble, détail d'un élément |
| GET | `pieces-justificatives/{id}/telecharger/` | Fichier d'une pièce justificative (compte connecté) |
| GET | `public/partage/{jeton}/[ressource/]` | Page partagée, sans authentification : description, puis `dashboard`, `configuration`, `menu`, `suivi`, `parametres-alerte` |
| GET / PATCH | `plaintes/mecanisme/` | Réglages du mécanisme et `controles` (ce qui manque pour l'activer) |
| POST | `plaintes/mecanisme/activer/`, `…/desactiver/` | Activation (refusée avec la liste des `controles` tant qu'elle n'est pas vide) |
| GET / POST | `plaintes/modeles/` | Modèles prêts à l'emploi ; POST `{modele}` les copie dans le paramétrage |
| GET / POST | `plaintes/canevas/`, `plaintes/canevas/importer/` | Canevas Excel du paramétrage et son import |
| CRUD | `plaintes/types/`, `plaintes/priorites/`, `plaintes/categories/`, `plaintes/circuits/`, `plaintes/etapes/` | Listes du paramétrage (sans pagination) |
| GET / POST | `plaintes/dossiers/` | Dossiers visibles (vues `?vue=`, filtres `statut`, `canal`, `projet`, `categorie`, `priorite`, `responsable`, `date_du`, `date_au`, recherche par numéro) ; POST = saisie par un agent, renvoie numéro et code de suivi |
| GET | `plaintes/dossiers/{id}/` | Fiche complète : journal (`actions`), dossiers liés visibles |
| POST | `plaintes/dossiers/{id}/{classer,affecter,recuser,etape,noter,communiquer,decider,cloturer,rouvrir,recours,lier}/` | Opérations de traitement (règles dans `traitement.py`) |
| GET | `plaintes/dossiers/{id}/responsables-possibles/`, `…/possiblement-lies/` | Personnes à qui confier le dossier ; dossiers proches à lier |
| CRUD | `plaintes-vues/` | Filtres enregistrés de l'utilisateur connecté |
| POST | `plaintes/dossiers/{id}/prolonger/` | Prolongation motivée du délai (`jours`, `motif`) |
| CRUD | `plaintes/jours-feries/` | Calendrier des jours fériés (délais en jours ouvrés) |
| POST | `plaintes/dossiers/{id}/{lever-sensibilite,mettre-en-cause,assistance,suspendre,anonymiser}/` | Circuit confidentiel (règles dans `confidentiel.py`) |
| POST | `plaintes/dossiers/{id}/exporter/` | Fiche PDF en filigrane (motif et confirmation pour un dossier confidentiel), tracée au journal |
| POST | `plaintes-signaler/{id}/` | Signaler un dossier comme sensible (tout utilisateur qui le voit) |
| CRUD | `plaintes/prestataires/` | Annuaire des prestataires d'assistance |
| GET | `plaintes/qr/?projet=` | QR code (PNG) du formulaire public |
| GET / POST | `public/plaintes/formulaire/`, `public/plaintes/deposer/`, `public/plaintes/suivi/` | Sans authentification : contenu du formulaire, dépôt d'un retour, état d'un dossier par son code |
| GET | `beneficiaires/exporter/` | Export des bénéficiaires : `?fichier=excel` ou `pdf`, `?projets=1,3` pour choisir les projets |
| POST | `beneficiaires/{id}/verifier-doublons/` | Recherche des doublons d'un bénéficiaire |
| GET / POST | `documents/{id}/versions/`, `documents/{id}/nouvelle-version/` | Versions d'un document |
| GET / POST | `notifications/non-lues-count/`, `…/{id}/marquer-lu/`, `…/tout-marquer-lu/` | Gestion des notifications |
| GET | `periodes-planification/{id}/valeurs/` | Données de l'onglet « Planification par période » |
| GET | `suivi/projets/{id}/exporter/word/` · `periodes-planification/{id}/exporter-suivi/word/` | Suivi du projet / suivi par période en Word : mise en page propre à Word, en tableaux (résumé, activités par niveau, saisies, indicateurs) — `suivi/export_word.py` ; le PDF garde ses cartes |
| GET | `periodes-planification/{id}/canevas/` | Canevas des objectifs de la période (planification et indicateurs préremplis, objectifs à saisir) — `suivi/canevas_periode.py`, même présentation que le canevas de suivi |
| POST | `periodes-planification/{id}/canevas/apercu/` · `importer/` · `rapport-erreurs/` | Import du canevas des objectifs en deux temps (aperçu puis validation), modes `ajout` / `mise_a_jour`, mêmes contrôles que la saisie à l'écran (`TranchePlanifieeSerializer`) |
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
| CRUD | `structures-organisation/` | Structure de l'organisation (modification : Administrateur) |
| CRUD | `parties-prenantes/`, `categories-parties-prenantes/` | Parties prenantes et leurs catégories |
| CRUD | `partenaires-projet/` | Rôle des partenaires dans un projet (`?projet=`) |
| GET / PUT / PATCH | `parametres-rapportage/` | Contrôle des périodes de rapportage et périmètre fermé (modification : Administrateur) |
| CRUD | `periodes-rapportage/` | Périodes d'ouverture de la saisie, générales ou par projet (`?projet=`) |
| GET | `projets/{id}/coherence/` | Rapport de cohérence du projet |
| GET | `approbations/` | Saisies et demandes en attente (approbateur : toutes ; autres : les siennes, avec les rejets) |
| POST | `approbations/saisies/{point\|valeur\|taux}/{id}/`, `approbations/demandes/{id}/` | Approuver ou rejeter : `{approuver, motif}` (motif obligatoire pour un rejet) |
| GET | `traductions/?langue=` | Sans authentification : langues, langue par défaut, corrections de la langue demandée |
| CRUD | `traductions-corrigees/` | Traductions corrigées (`?langue=` ; modification : Administrateur) |
| POST | `traductions-corrigees/importer/` | Import tout-ou-rien : `{langue, lignes: [{source, traduction}]}`, traduction `null` = retrait (Administrateur) |
| GET | `traductions-corrigees/journal/?langue=` | 200 dernières corrections et retraits, avec auteur (Administrateur) |

## 8. Imports et exports

| Import ou export | Format | Code |
|---|---|---|
| Structuration stratégique | Excel au format « plan » (une colonne par niveau) ; l'export est réimportable | `strategy/services.py` |
| Projet et planification | Excel, feuilles « Projet » et « Planification » (niveaux d'activité en nombre libre) | `projects/import_excel.py` |
| Indicateurs et grilles d'alerte | Excel | `indicators/import_excel.py` |
| Bénéficiaires | Excel (import) ; Excel et PDF (export, une feuille par projet) | `beneficiaries/services/` |
| Planification complète | Un classeur : cadre, projet, planification, indicateurs, bénéficiaires, grilles d'alerte | `planification/services.py` |
| Suivi d'un projet ou d'une période | Excel, PDF (WeasyPrint) et Word | `suivi/export_excel.py`, `export_pdf.py`, `export_periode.py`, `reports/word.py` |
| Rapport financier | PDF, Word, Excel (sections et période au choix) | `reports/financier.py` |
| Cadre logique, registre des risques, suivi stratégique | PDF et Word | `reports/cadre_logique.py`, `risques.py`, `suivi_strategique.py` |
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
- `check_deadlines` lance aussi `verifier_echeances_plaintes` : rappels, retards et escalades des
  dossiers de plaintes (voir 5.14, lot 4).
- Types de notification : indicateur en alerte, échéance d'activité, activité modifiée,
  doublon signalé, rapport soumis, rapport validé, plaintes et retours.

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
| `/strategie`, `/strategie/:id` | Cadres stratégiques ; onglets Configuration des niveaux, Arborescence et saisie, Axes et budgets, Suivi stratégique, Projets et budgets |
| `/projets`, `/projets/:id` | Projets ; onglets Configuration des niveaux, Planification, Planification par période, Cadre logique, Risques, Équipe de projet, Partenaires, Indicateurs, Financement (rallonges), Documents, Contrôle de cohérence, Historique ; menu Exporter (Word, rapport financier) |
| `/indicateurs`, `/indicateurs/:id` | Indicateurs et saisie des valeurs |
| `/suivi`, `/suivi/:id` | Suivi des projets et tableau de suivi d'un projet |
| `/beneficiaires`, `/beneficiaires/:id` | Bénéficiaires (identifiant, QR code, carte à imprimer, variables) |
| `/carte` | Carte : bénéficiaires filtrés par projet et zone, couches de fond et importées, carte imprimable |
| `/beneficiaires/identifiant/:identifiant` | Lien du QR code : ouvre la fiche |
| `/approbations` | Saisies et changements de planification à approuver, ou suivi de ses demandes |
| `/doublons` | Doublons signalés |
| `/zones-administratives` | Référentiel administratif |
| `/documents` | Bibliothèque documentaire |
| `/plaintes` | Plaintes et retours : dossiers (vues prêtes, filtres, mes vues), saisie d'un retour par un agent, adresse et QR code du formulaire public |
| `/plaintes/dossiers/:id` | Dossier : informations, décision et clôture, dossiers liés, journal ; actions de traitement selon l'état du dossier |
| `/plaintes/parametrage` | Paramétrage du mécanisme : onglets Mécanisme (modèles, réglages, activation), Types de retours, Catégories, Priorités, Circuits de traitement, Canevas Excel |
| `/plainte`, `/plainte/suivi` | Formulaire public de dépôt et suivi par code (sans compte, hors du menu) |
| `/utilisateurs` | Utilisateurs et rôles (Administrateur) |
| `/organisation` | Structure de l'organisation, parties prenantes, partenaires (Administrateur) |
| `/parametres-alerte` | Grilles d'alerte, délai d'échéance et périodes de rapportage (Administrateur) |
| `/langues` | Langue par défaut, correction, export et import des traductions, historique (Administrateur) |
| `/partage/:jeton` | Page partagée par lien, sans compte et en lecture seule (hors du menu) |

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
| `seed_50_projets` | **Vide les données métier** et charge 4 cadres stratégiques et 50 projets entièrement renseignés (planification par période, suivi, indicateurs, financements multi-bailleurs, partenaires, équipe, risques, documents, bénéficiaires) ; graine fixe |
| `seed_chaine_documents` | Après `seed_50_projets` : chaîne des documents (Programme → Piliers 1 à 3, avec un saut de maillon), projets éducation et santé rattachés aux Piliers 3 et un projet complet au dernier maillon (PEQR-KOU-2025) ; rejouable |
| `seed_projets_complementaires` | Ajoute 4 projets de démonstration, sans rien supprimer |
| `seed_projets_filtres` | Ajoute (ou supprime avec `--supprimer`) des projets `TEST-…` pour tester les filtres |
| `seed_points_suivi` | Ajoute des points de suivi de démonstration |
| `verifier_echeances_plaintes [--recalculer]` | Rappels, retards et escalades des dossiers de plaintes (lancée par `check_deadlines`) ; `--recalculer` recalcule d'abord toutes les échéances |
| `seed_demo_complements` | Complète la démonstration sans rien supprimer : variables des bénéficiaires et réponses, doublons signalés, liens de partage, pièces justificatives des valeurs d'indicateurs ; relançable |
| `seed_demo_plaintes [--reinitialiser \| --historique \| --confidentiel]` | Mécanisme de plaintes « standard » activé, points focaux du circuit confidentiel `admin` et `pf_psea` (`demo1234!`) ; les dossiers confidentiels sont visibles de l'Administrateur et de `pf_psea` et 42 dossiers sur six mois, tous canaux et états d'avancement, créés par l'interface d'entrée commune puis traités par les vraies opérations (journal daté, un recours) ; `--historique` complète seulement le journal des dossiers qui n'en ont pas ; `--confidentiel` ajoute seulement la démonstration du circuit confidentiel (circuit alternatif, prestataires, mise en cause, suspension légale) |
| `charger_limites BF [--niveaux 1 2 3] [--recalculer]` | Télécharge les limites administratives d'un pays (geoBoundaries) et place les zones sur la carte |
| `importer_bndt WGS84.zip [--pays BF] [--recalculer]` | Importe une base topographique en shapefiles (archive ou dossier) : contours, routes, localités, puis place les zones |

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
