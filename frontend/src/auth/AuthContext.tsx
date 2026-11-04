import { createContext, useEffect, useState, type ReactNode } from "react";
import { apiClient, tokenStorage } from "../api/client";
import type { EtapeDoubleAuth, JetonsConnexion } from "../api/doubleAuth";
import type { User } from "../types";
import { appliquerLangueDuCompte } from "../utils/i18n";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  /** Renvoie l'étape du second facteur à franchir, ou null si la connexion est faite. */
  /** Courriel (ou identifiant, installation unique) et mot de passe ; console : opérateur Expertise-ID. */
  login: (username: string, password: string, console?: boolean) => Promise<EtapeDoubleAuth | null>;
  /** Termine une connexion, après le code reçu par courriel. */
  ouvrirSession: (jetons: JetonsConnexion, destination?: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function fetchMe(destination?: string) {
    const { data } = await apiClient.get<User>("/utilisateurs/me/");
    // La langue choisie dans son compte l'emporte (la page est rechargée si elle diffère).
    appliquerLangueDuCompte(data.langue, destination);
    setUser(data);
  }

  useEffect(() => {
    if (tokenStorage.getAccess()) {
      fetchMe()
        .catch(() => tokenStorage.clear())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  async function ouvrirSession(jetons: JetonsConnexion, destination?: string) {
    tokenStorage.set(jetons.access, jetons.refresh);
    await fetchMe(destination);
  }

  async function login(username: string, password: string, console = false) {
    const { data } = await apiClient.post("/auth/token/", { username, courriel: username, password, ...(console ? { console } : {}) });
    if (data.double_authentification) return data as EtapeDoubleAuth;
    await ouvrirSession(data, "/");
    return null;
  }

  function logout() {
    tokenStorage.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, ouvrirSession, logout }}>{children}</AuthContext.Provider>
  );
}
