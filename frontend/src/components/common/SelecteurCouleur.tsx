import type { ReactNode } from "react";
import { Group, Tooltip, UnstyledButton } from "@mantine/core";
import { Check, X } from "lucide-react";
import { voc } from "../../utils/vocabulaire";

// Palette restreinte à choisir au clic plutôt qu'un sélecteur de couleur
// libre (code hexa, roue teinte/saturation...) jugé trop compliqué.
const PALETTE_COULEURS = [
  "#d03b3b",
  "#e8590c",
  "#f08c00",
  "#fab219",
  "#82c91e",
  "#0ca30c",
  "#12b886",
  "#15aabf",
  "#1c7ed6",
  "#4263eb",
  "#7048e8",
  "#9c36b5",
  "#e64980",
  "#495057",
];

/**
 * Pastilles de couleur à cliquer. Avec `libelleVide`, une pastille barrée en tête
 * permet de revenir à « aucune couleur imposée » (valeur vide).
 */
export function SelecteurCouleur({ value, onChange, taille = 26, libelleVide }: {
  value: string;
  onChange: (v: string) => void;
  taille?: number;
  libelleVide?: string;
}) {
  const pastille = (couleur: string, selectionnee: boolean, contenu: ReactNode, libelle: string) => (
    <UnstyledButton
      key={couleur || "vide"}
      onClick={() => onChange(couleur)}
      aria-label={libelle}
      style={{
        width: taille,
        height: taille,
        borderRadius: "50%",
        background: couleur || "var(--mantine-color-gray-1)",
        border: couleur ? undefined : "1px dashed var(--mantine-color-gray-5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        outline: selectionnee ? "2px solid var(--mantine-color-dark-6)" : "2px solid transparent",
        outlineOffset: 2,
      }}
    >
      {contenu}
    </UnstyledButton>
  );
  const valeur = value.toLowerCase();
  return (
    <Group gap={6}>
      {libelleVide !== undefined && (
        <Tooltip label={libelleVide}>
          {pastille("", !value, <X size={taille * 0.55} color="var(--mantine-color-gray-6)" />, libelleVide || voc("Aucune"))}
        </Tooltip>
      )}
      {PALETTE_COULEURS.map((couleur) => {
        const selectionnee = couleur === valeur;
        return pastille(couleur, selectionnee, selectionnee && <Check size={taille * 0.55} color="white" strokeWidth={3} />, couleur);
      })}
      {/* Couleur d'origine hors palette (ex : réglage plus ancien) : affichée pour rester visible. */}
      {value && !PALETTE_COULEURS.includes(valeur) && pastille(value, true, <Check size={taille * 0.55} color="white" strokeWidth={3} />, value)}
    </Group>
  );
}
