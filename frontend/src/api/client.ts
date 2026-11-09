import axios from "axios";
import { notifications } from "@mantine/notifications";
import { langue } from "../utils/i18n";
import { signalerStockagePlein } from "../utils/erreurs";
import { voc } from "../utils/vocabulaire";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "se_access_token";
const REFRESH_TOKEN_KEY = "se_refresh_token";

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  },
  setAccess: (access: string) => localStorage.setItem(ACCESS_TOKEN_KEY, access),
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

export const apiClient = axios.create({ baseURL: API_BASE_URL });

const estPagePublique = () => /^\/(plainte|partage|document)(\/|$)/.test(window.location.pathname);

const CLE_ORG_PUBLIQUE = "se_org_publique";

/**
 * Plateforme multi-organisations (adresse unique) : organisation du compte connecté, lue dans son
 * jeton (marque « org » posée par le serveur), ou « » (opérateur Expertise-ID, pas de session).
 */
export function organisationConnectee(): string {
  const jeton = tokenStorage.getAccess();
  if (!jeton) return "";
  try {
    const charge = JSON.parse(atob(jeton.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof charge.org === "string" ? charge.org : "";
  } catch {
    return "";
  }
}

/** Pages publiques d'une organisation (plainte, partage) : son identifiant, venu du lien (?org=). */
export function organisationPublique(): string {
  const dansLien = new URLSearchParams(window.location.search).get("org");
  try {
    if (dansLien) sessionStorage.setItem(CLE_ORG_PUBLIQUE, dansLien);
    return dansLien || sessionStorage.getItem(CLE_ORG_PUBLIQUE) || "";
  } catch {
    return dansLien || "";
  }
}

/** Ajoute ?org= de l'organisation connectée à un lien public (formulaire de plainte, partage). */
export function avecOrganisation(lien: string): string {
  const org = organisationConnectee();
  return org ? `${lien}${lien.includes("?") ? "&" : "?"}org=${encodeURIComponent(org)}` : lien;
}

// Connexion, inscription, paiement : jamais avec le jeton d'une session déjà ouverte dans ce navigateur
// (ex. visiteur de la démo, en lecture seule, dont le jeton ferait refuser la connexion).
const SANS_SESSION = /^\/(auth\/token|auth\/double-authentification|public)\//;

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess();
  if (SANS_SESSION.test(config.url ?? "")) {
    // rien : requête anonyme
  } else if (estPagePublique()) {
    // Page publique d'une organisation : l'organisation du lien, jamais celle d'une session ouverte
    // dans ce navigateur (le jeton l'emporterait côté serveur).
    const org = organisationPublique();
    if (org) config.headers["X-Organisation"] = org;
  } else if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Langue des fichiers produits par le serveur (rapports, exports, modèles d'import).
  config.headers["Accept-Language"] = langue();
  return config;
});

let refreshingPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStorage.getRefresh();
  if (!refresh) return null;
  try {
    const { data } = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, { refresh });
    // Le serveur remplace aussi le jeton de rafraîchissement (l'ancien devient inutilisable) : on le garde.
    if (data.refresh) tokenStorage.set(data.access, data.refresh);
    else tokenStorage.setAccess(data.access);
    return data.access as string;
  } catch {
    tokenStorage.clear();
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => {
    // 202 : changement envoyé pour approbation (projets qui l'exigent) — dit clairement qu'il
    // n'est pas encore appliqué, quel que soit l'écran d'où il part.
    if (response.status === 202 && response.data?.message) {
      notifications.show({ title: voc("Envoyé pour approbation"), message: voc(response.data.message), color: "orange", autoClose: 8000 });
    }
    // Incohérences repérées dans une saisie qu'on vient d'enregistrer (non bloquant).
    // (textes seuls : les rapports d'import ont leurs propres avertissements, affichés par leur fenêtre).
    const avertissements = Array.isArray(response.data?.avertissements)
      ? response.data.avertissements.filter((a: unknown): a is string => typeof a === "string")
      : [];
    if (avertissements.length > 0) {
      notifications.show({
        title: voc("Saisie enregistrée — à vérifier"),
        message: avertissements.map((a: string) => voc(a)).join("\n"),
        color: "orange",
        autoClose: 12000,
        style: { whiteSpace: "pre-line" },
      });
    }
    return response;
  },
  async (error) => {
    const original = error.config;
    // Abonnement terminé depuis plus de 7 jours : seule la page Abonnement reste ouverte (pour payer).
    if (error.response?.data?.code === "abonnement_expire" && window.location.pathname !== "/mon-abonnement") {
      window.location.href = "/mon-abonnement";
      return Promise.reject(error);
    }
    // Fichier refusé faute de place : fenêtre explicative (FenetreStockagePlein).
    if (error.response?.data?.code === "stockage_plein") {
      const { taille, utilise, limite } = error.response.data;
      signalerStockagePlein({ taille: Number(taille) || 0, utilise: Number(utilise) || 0, limite: Number(limite) || 0 });
      return Promise.reject(error);
    }
    // Installation de démonstration : l'enregistrement n'est que simulé.
    if (error.response?.status === 403 && error.response.data?.code === "mode_demo") {
      notifications.show({
        title: voc("Mode démonstration"),
        message: voc("Enregistrement simulé : en démonstration, rien n'est conservé. Abonnez-vous pour utiliser la plateforme."),
        color: "orange",
        autoClose: 6000,
      });
      return Promise.reject(error);
    }
    // Jeton obtenu sans le second facteur alors que le compte l'exige : nouvelle connexion obligatoire.
    if (error.response?.status === 401 && error.response.data?.code === "double_authentification_requise") {
      tokenStorage.clear();
      if (!estPagePublique()) window.location.href = "/login";
      return Promise.reject(error);
    }
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      if (!refreshingPromise) {
        refreshingPromise = refreshAccessToken().finally(() => {
          refreshingPromise = null;
        });
      }
      const newToken = await refreshingPromise;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(original);
      }
      // Pages publiques (formulaire de plainte, suivi par code, lien de partage) : une session
      // expirée dans ce navigateur ne doit pas les fermer ; elles restent utilisables sans compte.
      if (!estPagePublique()) window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
