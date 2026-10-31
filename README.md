# SuiviEvaluation3 — Plateforme de Suivi-Évaluation (Expertise-ID)

Plateforme web de suivi-évaluation (S&E) des projets et programmes de développement,
conçue et développée par Expertise-ID. Elle couvre toute la chaîne du pilotage : cadre
stratégique, projets, planification, indicateurs, suivi périodique des réalisations,
bénéficiaires, documents, alertes et tableaux de bord.

> **SuiviEvaluation3** est la copie de travail actuelle : toutes les évolutions se font ici.
> [SuiviEvaluation2](https://github.com/expertiseid/SuiviEvaluation2) (version arrêtée au
> commit `ecad790`) et [SuiviEvaluation](https://github.com/expertiseid/SuiviEvaluation) (code
> initial) restent inchangés. Les trois peuvent tourner en même temps sur le même poste (ports
> et conteneurs distincts).

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Pile technique](#pile-technique)
- [Démarrage rapide](#démarrage-rapide)
- [Accès](#accès)
- [Organisation du dépôt](#organisation-du-dépôt)
- [Commandes utiles](#commandes-utiles)
- [Documentation détaillée](#documentation-détaillée)

## Fonctionnalités

- **Cadre stratégique** : plusieurs cadres indépendants, niveaux librement nommés
  (Plan → Orientation → Axe…, ou tout autre découpage), arborescence des éléments,
  récapitulatif des axes et des budgets, import et export Excel.
- **Chaîne des documents stratégiques** : maillons paramétrables (ex. Cadre stratégique →
  Programme → Pilier 1 → Pilier 2 → Pilier 3, puis les projets), chacun une rubrique du menu
  avec ses propres documents ; rattachement au document au-dessus ou à l'un de ses éléments,
  et élément par élément (« Contribue à ») ; sauts de maillons permis avec avertissement ;
  budgets, taux et projets remontés sur toute la chaîne ; toute la chaîne en un fichier Excel ;
  chaque programme ou pilier a sa fiche comme un projet (code, statut, dates, budget et
  bailleurs, responsable, partenaires, zones, cibles, capitalisation).
- **Projets** : fiche projet (bailleurs, partenaires, budget, dates, zones, cibles),
  financements multi-bailleurs, équipe de projet, historique des modifications.
- **Planification à niveaux libres** : aucun niveau imposé — chaque projet nomme et
  empile les siens (ex. Objectif général → Objectif spécifique → Activité, ou Résultat →
  Pilier → Activité), puis des sous-activités ; planification par période (trimestre,
  année…) ; import Excel avec les noms de niveaux du fichier.
- **Rattachement du projet** à n'importe quel élément du cadre stratégique (programme,
  axe, pilier…), pour regrouper les projets par élément.
- **Planification complète** : un seul classeur Excel pour créer d'un coup un cadre
  stratégique, un projet, sa planification, ses indicateurs, ses bénéficiaires et ses
  grilles d'alerte.
- **Indicateurs** : valeur de référence, cible, fréquence, saisies périodiques avec pièces
  justificatives, rattachement à tout niveau du cadre stratégique ou de la planification,
  taux de réalisation et grilles d'alerte colorées paramétrables.
- **Suivi** : points de suivi périodiques des activités et sous-activités (quantité, budget,
  statut), tranches planifiées, comparaison prévu / réalisé, exports Excel et PDF.
- **Bénéficiaires** : fiche individuelle, participation à plusieurs projets dans la durée,
  import et export Excel/PDF, détection des doublons (signalement, jamais de fusion
  automatique).
- **Documents** : bibliothèque documentaire (GED) par dossiers, versions des documents,
  rattachement aux projets, activités et sous-activités.
- **Alertes et notifications** : échéances proches ou dépassées (vérification horaire),
  notifications dans l'application et par courriel.
- **Tableau de bord** consolidé et par projet, filtres (année, dates, statuts), blocs et
  types de graphiques personnalisables.
- **Carte** : bénéficiaires et zones (régions, provinces, communes) coloriées selon un ou
  plusieurs indicateurs du tableau de bord, filtres sur plusieurs projets et plusieurs zones
  et filtres de période et de statut ; carte imprimable (PDF/PNG) avec les mêmes choix.
- **Utilisateurs et sécurité** : rôles personnalisables (visibilité globale ou limitée aux
  projets affectés), niveau d'accès lecture seule ou lecture-écriture, authentification
  JWT, historique de toutes les modifications.
- **Référentiel administratif** : niveaux administratifs paramétrables par pays, régions et
  provinces du Burkina Faso chargées automatiquement.
- **Plaintes et retours** (paramétrage) : mécanisme adaptable à toute organisation — types
  de retours, catégories (dont sensibles), priorités et délais, circuits de traitement par
  étapes, modèles prêts à l'emploi, canevas Excel ; activation contrôlée et règles de
  protection des personnes non modifiables (circuit confidentiel confié à des personnes nommées).

## Pile technique

| Couche | Technologies |
|---|---|
| Backend | Python 3.12, Django 5.0, Django REST Framework 3.15, SimpleJWT, django-filter, django-simple-history, drf-spectacular (OpenAPI), openpyxl (Excel), WeasyPrint (PDF) |
| Frontend | React 19, TypeScript 6, Vite 8, Mantine 9, TanStack Query 5, React Router 7, React Hook Form + Zod, Recharts, Axios |
| Base de données | PostgreSQL 16 |
| Exécution | Docker Compose (aucune installation locale de Python ou Node nécessaire) |

## Démarrage rapide

Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/) démarré.

```bash
git clone https://github.com/expertiseid/SuiviEvaluation3.git
cd SuiviEvaluation3
cp .env.example .env                                   # valeurs par défaut suffisantes en local
docker compose up -d --build                           # premier démarrage : quelques minutes
docker compose exec backend python manage.py migrate
```

Créer un compte administrateur (ne pas utiliser `createsuperuser` seul : l'application
s'appuie sur le champ métier `role`, que cette commande ne renseigne pas) :

```bash
docker compose exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
get_user_model().objects.create_superuser(
    username='admin', email='admin@example.com', password='CHANGE_MOI', role='ADMIN'
)
"
```

Données de démonstration (facultatif, **remplace** les données métier existantes) :

```bash
docker compose exec backend python manage.py seed_demo_expertise_id
```

## Accès

| Service | Adresse locale |
|---|---|
| Interface web | <http://localhost:5192> |
| API REST | <http://localhost:8093/api/v1/> |
| Documentation de l'API (Swagger) | <http://localhost:8093/api/docs/> |
| Documentation de l'API (ReDoc) | <http://localhost:8093/api/redoc/> |
| Administration Django | <http://localhost:8093/admin/> |
| PostgreSQL | `localhost:5444` |

## Organisation du dépôt

```
SuiviEvaluation3/
├── backend/                 API Django
│   ├── config/              réglages (base / dev / prod), URLs racine
│   ├── apps/                une application Django par domaine métier
│   └── requirements/        dépendances (base, dev, prod)
├── frontend/                application React
│   └── src/
│       ├── api/             appels à l'API, un fichier par domaine
│       ├── pages/           écrans, un dossier par domaine
│       ├── components/      composants réutilisables
│       ├── auth/            connexion, garde des routes, contexte utilisateur
│       └── utils/           calculs et utilitaires partagés
├── docs/                    documentation technique et exemples de fichiers Excel
├── docker-compose.yml       services db, backend, scheduler, frontend
└── .env.example             modèle de configuration
```

## Commandes utiles

```bash
docker compose up -d                                          # démarrer la stack
docker compose exec backend python manage.py check            # vérification Django
docker compose exec backend pytest -q                         # tests backend
docker compose exec backend python manage.py makemigrations   # après modification d'un modèle
docker compose exec backend python manage.py migrate
docker compose logs backend --tail 50                         # journaux d'un service
docker compose exec backend python manage.py seed_50_projets         # démo : VIDE les données, 50 projets
docker compose exec backend python manage.py seed_chaine_documents   # démo : programme et piliers

cd frontend && npx tsc --noEmit -p . && npx oxlint src && npx vite build   # contrôles frontend
```

## Documentation détaillée

- [Documentation technique](docs/DOCUMENTATION_TECHNIQUE.md) : architecture, modèle de
  données, règles métier, API, frontend, sécurité, exports, déploiement, dépannage.
- [CLAUDE.md](CLAUDE.md) : instructions d'installation et conventions du projet.
