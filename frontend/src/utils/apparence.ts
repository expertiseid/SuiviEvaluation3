import { createContext, useContext } from "react";

/**
 * Apparence d'un bloc du tableau de bord, réglée par l'Administrateur (ou un rôle ayant ce droit) et
 * commune à tous : titre, mode d'affichage, légende, valeurs, couleurs, axes, taille, format, tri.
 * Les mêmes réglages sont contrôlés côté serveur (apps.dashboard.views.REGLAGES_APPARENCE).
 */
export interface ApparenceBloc {
  titre?: string;
  sous_titre?: string;
  mode?: "graphique" | "tableau" | "les_deux";
  legende?: "auto" | "masquee" | "haut" | "bas" | "droite";
  valeurs?: boolean;
  quadrillage?: boolean;
  palette?: NomPalette;
  /** Couleur imposée par nom de série ou de catégorie. */
  couleurs?: Record<string, string>;
  axe_x?: string;
  axe_y?: string;
  rotation?: 0 | 30 | 45 | 90;
  hauteur?: number;
  taille_texte?: number;
  format?: "auto" | "entier" | "court" | "pourcent";
  tri?: "aucun" | "croissant" | "decroissant";
}

export type NomPalette = "defaut" | "vive" | "douce" | "bleus" | "verts" | "contraste";

/** Palettes proposées : elles remplacent les couleurs d'origine (une couleur imposée l'emporte toujours). */
export const PALETTES: Record<Exclude<NomPalette, "defaut">, string[]> = {
  vive: ["#e03131", "#1c7ed6", "#2f9e44", "#f08c00", "#7048e8", "#0c8599", "#c2255c", "#5c940d"],
  douce: ["#74c0fc", "#8ce99a", "#ffc078", "#b197fc", "#ffa8a8", "#66d9e8", "#ffd43b", "#e599f7"],
  bleus: ["#1864ab", "#1971c2", "#1c7ed6", "#228be6", "#339af0", "#4dabf7", "#74c0fc", "#a5d8ff"],
  verts: ["#2b8a3e", "#2f9e44", "#37b24d", "#40c057", "#51cf66", "#69db7c", "#8ce99a", "#b2f2bb"],
  contraste: ["#000000", "#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00", "#cc79a7"],
};

/** Apparence du bloc en cours d'affichage, lue par les graphiques qu'il contient. */
export const ApparenceContext = createContext<ApparenceBloc>({});

export function useApparence() {
  return useContext(ApparenceContext);
}
