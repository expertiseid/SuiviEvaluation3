/** Code de connexion envoyé par courriel à chaque connexion (apps/accounts/double_auth.py). */
import { apiClient } from "./client";

export interface JetonsConnexion {
  access: string;
  refresh: string;
}

/** Après le mot de passe : un code est parti par courriel ; le jeton d'étape sert à le valider. */
export interface EtapeDoubleAuth {
  double_authentification: "code";
  jeton: string;
  /** Adresse masquée (al•••@exemple.org). */
  destination: string;
  validite_minutes: number;
}

const ETAPE = "/auth/double-authentification/";

export const connexionCode = async (jeton: string, code: string) =>
  (await apiClient.post<JetonsConnexion>(`${ETAPE}code/`, { jeton, code })).data;
export const renvoyerCode = async (jeton: string) =>
  (await apiClient.post<EtapeDoubleAuth>(`${ETAPE}renvoyer/`, { jeton })).data;

// Mot de passe oublié (apps/accounts/mot_de_passe.py) : lien envoyé par courriel, puis nouveau mot de passe.
const OUBLI = "/public/mot-de-passe-oublie/";
export const demanderNouveauMotDePasse = async (courriel: string, langue: string) =>
  (await apiClient.post<{ detail: string }>(OUBLI, { courriel, langue })).data;
export const verifierLienMotDePasse = async (jeton: string) =>
  (await apiClient.post<{ compte: string }>(`${OUBLI}verifier/`, { jeton })).data;
export const changerMotDePasse = async (jeton: string, mot_de_passe: string) =>
  (await apiClient.post<{ detail: string }>(`${OUBLI}changer/`, { jeton, mot_de_passe })).data;
