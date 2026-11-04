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
