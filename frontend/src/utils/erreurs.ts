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
