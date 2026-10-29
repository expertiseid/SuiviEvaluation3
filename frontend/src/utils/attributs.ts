/** Attributs libres d'un élément de la planification ou d'une sous-activité : {nom: texte}. */
export type Attributs = Record<string, string>;

/**
 * Noms des attributs utilisés dans une planification (éléments et sous-activités), dans l'ordre du
 * projet (`ordre` : colonnes du fichier importé, puis ceux ajoutés par la fiche).
 */
export function nomsAttributs(
  elements: { attributs?: Attributs; enfants?: unknown[]; sous_activites?: { attributs?: Attributs }[] }[],
  ordre: string[] = [],
): string[] {
  const noms = new Set<string>();
  const parcourir = (liste: typeof elements) => {
    for (const e of liste) {
      Object.keys(e.attributs ?? {}).forEach((n) => noms.add(n));
      (e.sous_activites ?? []).forEach((sa) => Object.keys(sa.attributs ?? {}).forEach((n) => noms.add(n)));
      parcourir((e.enfants ?? []) as typeof elements);
    }
  };
  parcourir(elements);
  const rang = (nom: string) => (ordre.includes(nom) ? ordre.indexOf(nom) : ordre.length);
  return [...noms].sort((a, b) => rang(a) - rang(b) || a.localeCompare(b));
}
