/** Types de graphiques proposés sur le tableau de bord (composant GraphiqueAdaptable). */
export type TypeGraphique = "camembert" | "colonnes" | "colonnes-empilees" | "barres" | "courbes" | "aires" | "tableau";

/** Types proposés selon la forme des données (le camembert n'a de sens qu'avec une seule série). */
export function typesPossibles(nbSeries: number): TypeGraphique[] {
  return nbSeries === 1
    ? ["camembert", "colonnes", "barres", "courbes", "aires", "tableau"]
    : ["colonnes", "colonnes-empilees", "barres", "courbes", "aires", "tableau"];
}
