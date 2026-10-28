import { createContext, useContext } from "react";

/** Page ouverte par un lien de partage public : lecture seule, données servies par le jeton. */
export interface Partage {
  jeton: string;
  type: "TABLEAU_DE_BORD" | "SUIVI_PROJET";
  contenu: "TOUT" | "ACTIVITES" | "INDICATEURS";
  projetId: number | null;
  /** Filtres du tableau de bord enregistrés avec le lien. */
  filtres: Record<string, unknown>;
}

export const PartageContext = createContext<Partage | null>(null);

export function usePartage() {
  return useContext(PartageContext);
}

/** Chemin d'API : la ressource publique du lien en mode partage, sinon le chemin habituel. */
export function cheminApi(partage: Partage | null, chemin: string, ressourcePublique: string) {
  return partage ? `/public/partage/${partage.jeton}/${ressourcePublique}/` : chemin;
}
