import axios from "axios";
import { notifications } from "@mantine/notifications";
import { langue } from "../utils/i18n";
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

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess();
  if (token) {
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
    tokenStorage.setAccess(data.access);
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
    if (Array.isArray(response.data?.avertissements) && response.data.avertissements.length > 0) {
      notifications.show({
        title: voc("Saisie enregistrée — à vérifier"),
        message: response.data.avertissements.map((a: string) => voc(a)).join("\n"),
        color: "orange",
        autoClose: 12000,
        style: { whiteSpace: "pre-line" },
      });
    }
    return response;
  },
  async (error) => {
    const original = error.config;
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
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
