import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
})
