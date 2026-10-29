import type { ReactNode } from "react";
import { Badge, Table } from "@mantine/core";

type Case<T> = { element: T; lignes: number } | { element: null; lignes: number; colonnes: number } | "couverte";

/**
 * Arborescence présentée en tableau, comme un cadre stratégique imprimé : une colonne par niveau,
 * chaque élément dans la colonne de son niveau, sa cellule fusionnée sur la hauteur de tout ce
 * qui est en dessous. Un niveau sauté (autorisé par le cadre) laisse une cellule vide ; une
 * ligne qui s'arrête avant le dernier niveau est complétée par une cellule vide.
 */
export function TableauHierarchique<T>({
  niveaux,
  racines,
  enfants,
  colonne,
  cle,
  cellule,
}: {
  /** Colonnes, de gauche à droite : nom du niveau et couleur Mantine. */
  niveaux: { nom: string; couleur: string }[];
  racines: T[];
  enfants: (element: T) => T[];
  /** Colonne (rang du niveau) d'un élément. */
  colonne: (element: T) => number;
  cle: (element: T) => string | number;
  cellule: (element: T) => ReactNode;
}) {
  const nbColonnes = niveaux.length;
  const hauteurs = new Map<T, number>();
  const hauteur = (element: T): number => {
    if (!hauteurs.has(element)) {
      const sous = enfants(element);
      hauteurs.set(element, sous.length ? sous.reduce((somme, e) => somme + hauteur(e), 0) : 1);
    }
    return hauteurs.get(element)!;
  };

  const grille: Case<T>[][] = [];
  const poser = (ligne: number, col: number, contenu: Case<T>, lignes: number, colonnes = 1) => {
    for (let l = ligne; l < ligne + lignes; l++) {
      grille[l] ??= [];
      for (let c = col; c < col + colonnes; c++) grille[l][c] = l === ligne && c === col ? contenu : "couverte";
    }
  };
  // Cellules vides entre deux niveaux (niveau sauté), sur la hauteur de l'élément qui suit.
  const combler = (ligne: number, de: number, a: number, lignes: number) => {
    for (let c = de; c < a; c++) poser(ligne, c, { element: null, lignes, colonnes: 1 }, lignes);
  };
  const placer = (element: T, ligne: number, colonneParent: number) => {
    // Toujours à droite de son parent, même si les données ne suivent pas l'ordre des niveaux.
    const col = Math.min(Math.max(colonne(element), colonneParent + 1), nbColonnes - 1);
    const lignes = hauteur(element);
    combler(ligne, colonneParent + 1, col, lignes);
    poser(ligne, col, { element, lignes }, lignes);
    const sous = enfants(element);
    if (sous.length === 0 && col < nbColonnes - 1) {
      poser(ligne, col + 1, { element: null, lignes: 1, colonnes: nbColonnes - col - 1 }, 1, nbColonnes - col - 1);
    }
    let suivante = ligne;
    for (const enfant of sous) {
      placer(enfant, suivante, col);
      suivante += hauteur(enfant);
    }
  };
  let ligne = 0;
  for (const racine of racines) {
    placer(racine, ligne, -1);
    ligne += hauteur(racine);
  }

  return (
    <Table.ScrollContainer minWidth={Math.max(600, nbColonnes * 220)}>
      <Table withTableBorder withColumnBorders verticalSpacing={6} style={{ tableLayout: "fixed" }}>
        <Table.Thead>
          <Table.Tr>
            {niveaux.map((n, i) => (
              <Table.Th key={i} bg={`var(--mantine-color-${n.couleur}-0)`}>
                <Badge color={n.couleur} variant="light" size="sm">{n.nom}</Badge>
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {grille.map((cases, i) => (
            <Table.Tr key={i}>
              {cases.map((c, j) => {
                if (c === "couverte" || c === undefined) return null;
                if (c.element === null) {
                  return <Table.Td key={j} rowSpan={c.lignes} colSpan={c.colonnes} bg="gray.0" />;
                }
                return (
                  <Table.Td
                    key={cle(c.element)}
                    rowSpan={c.lignes}
                    style={{ verticalAlign: "top", borderLeft: `3px solid var(--mantine-color-${niveaux[j]?.couleur ?? "gray"}-5)` }}
                  >
                    {cellule(c.element)}
                  </Table.Td>
                );
              })}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
