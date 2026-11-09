import { isAxiosError } from "axios";
import { voc } from "./vocabulaire";

/**
 * Remonte le message de validation renvoyé par l'API (ex : "Un objet Équipe
 * avec ce champ nom existe déjà.") au lieu d'un message générique — pour que
 * l'utilisateur comprenne exactement ce qui bloque (ex : nom déjà pris).
 */
export function messageErreurApi(error: unknown, message: string): string {
  // Messages du serveur et message par défaut : traduits dans la langue de l'interface.
  if (isAxiosError(error) && error.response?.data) {
    const data = error.response.data;
    if (typeof data.detail === "string") return voc(data.detail);
    for (const valeur of Object.values(data)) {
      if (Array.isArray(valeur) && typeof valeur[0] === "string") return voc(valeur[0]);
      if (typeof valeur === "string") return voc(valeur);
    }
  }
  return voc(message);
}

/** Espace de stockage plein : la fenêtre FenetreStockagePlein s'ouvre (au lieu d'une erreur). */
export const EVENEMENT_STOCKAGE_PLEIN = "stockage-plein";
export interface DetailStockagePlein { taille: number; utilise: number; limite: number }

export function signalerStockagePlein(detail: DetailStockagePlein) {
  window.dispatchEvent(new CustomEvent(EVENEMENT_STOCKAGE_PLEIN, { detail }));
}

/** Refus du serveur faute de place : la fenêtre explicative est déjà ouverte, pas de message d'erreur en plus. */
export function estStockagePlein(error: unknown): boolean {
  return isAxiosError(error) && error.response?.data?.code === "stockage_plein";
}
