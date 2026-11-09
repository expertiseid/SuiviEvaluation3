import { randomBytes } from 'node:crypto'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// Politique de sécurité du contenu (CSP). Scripts et styles écrits dans la page ne sont acceptés que
// s'ils portent le jeton (nonce) de la réponse : Vite le pose sur ses balises et dans
// <meta property="csp-nonce">, où Mantine le lit (main.tsx). En production, Nginx remplace JETON_CSP
// par un jeton tiré au hasard à chaque requête (deploiement/securite-application.inc) ; sur le poste
// de développement, un jeton est tiré à chaque démarrage du serveur.
const JETON_CSP_PRODUCTION = "JETON_CSP"
const jetonDeveloppement = randomBytes(18).toString("base64url")

// Fonds de carte autorisés : OpenStreetMap et Esri (satellite, neutre).
const CARTES = "https://a.tile.openstreetmap.org https://b.tile.openstreetmap.org https://c.tile.openstreetmap.org https://server.arcgisonline.com"
const politique = (jeton: string) => [
  "default-src 'self'",
  `script-src 'self' 'nonce-${jeton}'`,
  `style-src 'self' 'nonce-${jeton}'`,
  `img-src 'self' data: blob: ${CARTES}`,
  "font-src 'self' data:",
  `connect-src 'self' ${CARTES}`,
  "frame-src 'self' blob:",
  "worker-src 'self' blob:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ")

/** En-têtes de sécurité du serveur de développement (en production : deploiement/securite-application.inc). */
function entetesSecurite(): Plugin {
  return {
    name: "entetes-securite",
    configureServer(serveur) {
      serveur.middlewares.use((_req, res, next) => {
        res.setHeader("Content-Security-Policy", politique(jetonDeveloppement))
        res.setHeader("X-Frame-Options", "DENY")
        res.setHeader("X-Content-Type-Options", "nosniff")
        res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin")
        next()
      })
    },
  }
}

export default defineConfig(({ command }) => ({
  plugins: [react(), entetesSecurite()],
  html: { cspNonce: command === "build" ? JETON_CSP_PRODUCTION : jetonDeveloppement },
  server: {
    watch: {
      usePolling: true,
      interval: 300,
    },
    allowedHosts: process.env.VITE_ALLOWED_HOSTS
      ? process.env.VITE_ALLOWED_HOSTS.split(",")
      : undefined,
    // Plateforme multi-organisations en développement (VITE_API_BASE_URL=/api/v1) : l'API est servie
    // sous la même adresse que l'interface (ong-a.localhost:5192/api/…), comme en production ; l'hôte
    // d'origine est conservé pour que le serveur reconnaisse l'organisation.
    proxy: {
      "/api": { target: process.env.VITE_PROXY_API || "http://backend:8000", changeOrigin: false },
    },
  },
}))
