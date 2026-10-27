# Plateforme de Suivi-Évaluation — Expertise ID

Plateforme de suivi-évaluation (M&E) pour projets de développement : cadre
stratégique, projets, planification (objectifs → activités → sous-activités,
avec niveaux imbriqués configurables), indicateurs, suivi périodique,
bénéficiaires, documents, alertes.

- **Backend** : Django 5 + Django REST Framework (Python 3.12)
- **Frontend** : React 18 + TypeScript + Vite + Mantine v7 + TanStack Query
- **Base de données** : PostgreSQL 16
- **Tout tourne en Docker Compose** — aucune installation locale de Python/Node
  n'est nécessaire, seul Docker est requis.

Dépôt GitHub : [expertiseid/SuiviEvaluation2](https://github.com/expertiseid/SuiviEvaluation2) (branche `main`)

## Installation sur une machine neuve

1. **Installer [Docker Desktop](https://www.docker.com/products/docker-desktop/)** (macOS) et s'assurer qu'il tourne.

2. **Cloner le dépôt** :

   ```bash
   git clone https://github.com/expertiseid/SuiviEvaluation2.git
   cd SuiviEvaluation2
   ```

3. **Créer le fichier `.env`** à partir du modèle (les valeurs par défaut suffisent pour du développement local) :

   ```bash
   cp .env.example .env
   ```

4. **Démarrer la stack** (premier démarrage : construit les images, peut prendre quelques minutes) :

   ```bash
   docker compose up -d --build
   ```

5. **Appliquer les migrations** :

   ```bash
   docker compose exec backend python manage.py migrate
   ```

6. **Créer un compte administrateur** pour se connecter — **ne pas utiliser**
   `manage.py createsuperuser` seul : l'application vérifie le champ métier
   `role` (pas le `is_superuser` natif de Django), que cette commande
   interactive ne renseigne pas, ce qui créerait un compte inutilisable.
   Passer par le shell à la place :

   ```bash
   docker compose exec backend python manage.py shell -c "
   from django.contrib.auth import get_user_model
   get_user_model().objects.create_superuser(
       username='admin', email='admin@example.com', password='CHANGE_MOI', role='ADMIN'
   )
   "
   ```

   (rôles possibles dans `apps/accounts/constants.py`, ex : `ADMIN`,
   `COORDO_GENERAL`, `CHARGE_SE`, `CHEF_PROJET`...)

7. **Accéder à l'application** :
   - Interface web : <http://localhost:5191>
   - API : <http://localhost:8092/api/v1>
   - Admin Django : <http://localhost:8092/admin>

## Commandes courantes

Au quotidien, la stack reste démarrée en arrière-plan. Si elle est arrêtée :

```bash
docker compose up -d
```

- **Backend — migrations** après avoir modifié un modèle :

  ```bash
  docker compose exec backend python manage.py makemigrations
  docker compose exec backend python manage.py migrate
  ```

- **Backend — tests** :

  ```bash
  docker compose exec backend pytest -q
  ```

- **Backend — vérification Django** (détecte les erreurs de config/modèles) :

  ```bash
  docker compose exec backend python manage.py check
  ```

- **Frontend — type-check / lint / build** (depuis `frontend/`, pas besoin d'être dans le conteneur si Node est installé localement ; sinon via le conteneur) :

  ```bash
  cd frontend
  npx tsc --noEmit -p .
  npx oxlint src
  npx vite build
  ```

- **Logs d'un service** :

  ```bash
  docker compose logs backend --tail 50
  docker compose logs frontend --tail 50
  ```

- **Redémarrer un service** après une modification qui ne se recharge pas tout seul (le backend et le frontend ont tous deux le rechargement à chaud activé, un redémarrage n'est normalement nécessaire qu'après un changement de variable d'environnement) :

  ```bash
  docker compose restart backend
  docker compose restart frontend
  ```

- **Données de démonstration** (optionnel, plusieurs commandes de seed existent) :

  ```bash
  docker compose exec backend python manage.py seed_demo_expertise_id
  ```

## Architecture des services (`docker-compose.yml`)

| Service     | Rôle                                   | Port local |
|-------------|-----------------------------------------|------------|
| `db`        | PostgreSQL 16                           | 5443       |
| `backend`   | Django (API DRF, `manage.py runserver`) | 8092       |
| `frontend`  | Vite dev server (React)                 | 5191       |
| `scheduler` | Boucle `check_deadlines` toutes les heures | —       |

## Déploiement existant

Un serveur de test est déjà déployé (hors de ce dépôt, via transfert de
fichiers direct, pas via CI/CD) : <https://204-168-227-18.sslip.io> — utile pour
comparer un comportement « en ligne » vs local, mais ne pas supposer qu'il est
à jour avec le dernier commit sans vérifier.

## Conventions du projet

- **Tout est en français** : interface, libellés, commentaires de code,
  messages de commit.
- **Avant de considérer un changement terminé** : vérifier avec de vraies
  données (requête réelle en base, appel API réel, import/export Excel
  réel aller-retour) plutôt que de se fier uniquement à la relecture du code
  — puis nettoyer toute donnée de test créée pendant la vérification.
- **Commandes systématiques après une modification backend** :
  `manage.py check`, `pytest -q`.
- **Commandes systématiques après une modification frontend** :
  `tsc --noEmit`, `oxlint`, `vite build`.
- **Ne jamais committer sans que ce soit explicitement demandé.**
- Fichiers Excel/Word générés pendant des sessions de travail (démos, tests
  d'import) ne sont volontairement pas versionnés — voir `.gitignore` et
  les fichiers `*.xlsx`/`*.docx` à la racine, laissés intentionnellement
  non suivis par Git.
