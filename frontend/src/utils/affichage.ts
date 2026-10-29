import { useState } from "react";

export type ModeAffichage = "arbre" | "tableau";

/** Choix d'affichage parmi `choix`, mémorisé dans ce navigateur sous `cle` (premier choix par défaut). */
export function usePreference<T extends string>(cle: string, choix: readonly T[]): [T, (valeur: T) => void] {
  const stockage = `affichage:${cle}`;
  const [valeur, setValeur] = useState<T>(() => {
    try {
      const lue = localStorage.getItem(stockage);
      return choix.includes(lue as T) ? (lue as T) : choix[0];
    } catch {
      return choix[0];
    }
  });
  function choisir(nouvelle: T) {
    setValeur(nouvelle);
    try {
      localStorage.setItem(stockage, nouvelle);
    } catch {
      /* navigation privée : le choix ne sera pas mémorisé */
    }
  }
  return [valeur, choisir];
}

/** Arbre ou tableau, mémorisé pour chaque écran (`cle`). */
export function useModeAffichage(cle: string) {
  return usePreference<ModeAffichage>(cle, ["arbre", "tableau"]);
}
