# Frontend — Plateforme de Suivi-Évaluation

Application React 19 + TypeScript, construite avec Vite et l'interface Mantine 9. Elle
ne communique qu'avec l'API REST du backend (`VITE_API_BASE_URL`).

En local, le frontend tourne dans le conteneur `frontend` (voir le
[README principal](../README.md)) ; aucune installation de Node n'est nécessaire.

## Organisation de `src/`

| Dossier | Contenu |
|---|---|
| `api/` | Appels à l'API, un fichier par domaine ; `client.ts` configure Axios (jeton JWT, renouvellement automatique) |
| `auth/` | Contexte utilisateur, garde des routes (`RequireAuth`), page de connexion |
| `pages/` | Écrans, un dossier par domaine |
| `components/` | Composants réutilisables (graphiques, statuts, sélecteurs, historique, notifications) |
| `layouts/` | Mise en page générale et menu latéral |
| `utils/` | Calculs et utilitaires partagés |
| `types/` | Types TypeScript des objets de l'API |

## Contrôles avant de livrer une modification

```bash
npx tsc --noEmit -p .   # types
npx oxlint src          # analyse statique
npx vite build          # compilation de production
```

Détails (écrans, authentification, règles à respecter) :
[documentation technique, section Frontend](../docs/DOCUMENTATION_TECHNIQUE.md#10-frontend).
