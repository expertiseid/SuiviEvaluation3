import type { StructureOrganisation } from "../types";

/** Libellé d'une structure de l'organisation, avec son sigle. */
export function libelleStructure(s: StructureOrganisation) {
  return s.sigle ? `${s.sigle} — ${s.nom}` : s.nom;
}

/** Structures dans l'ordre de l'arbre, avec leur profondeur. */
export function structuresEnArbre(structures: StructureOrganisation[]) {
  const resultat: { structure: StructureOrganisation; profondeur: number }[] = [];
  const parcourir = (parent: number | null, profondeur: number) => {
    for (const s of structures.filter((x) => x.parent === parent)) {
      resultat.push({ structure: s, profondeur });
      parcourir(s.id, profondeur + 1);
    }
  };
  parcourir(null, 0);
  return resultat;
}

/** Options de liste de choix (MultiSelect / Select) des structures, indentées selon l'arbre. */
export function optionsStructures(structures: StructureOrganisation[]) {
  return structuresEnArbre(structures).map(({ structure: s, profondeur }) => ({
    value: String(s.id),
    label: `${"\u00a0\u00a0".repeat(profondeur)}${libelleStructure(s)}`,
  }));
}
