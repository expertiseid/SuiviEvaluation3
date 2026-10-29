/** Ligne de saisie : un bailleur, le montant qu'il apporte, et ses rallonges déjà accordées. */
export interface LigneBailleur {
  cle: number;
  nom: string;
  montant: number | null;
  /** Rallonges accordées en cours de projet (onglet Financement) : la ligne ne peut pas être retirée ici. */
  rallonges: number;
}

let compteur = 0;
export const nouvelleLigneBailleur = (nom = "", montant: number | null = null, rallonges = 0): LigneBailleur => ({
  cle: ++compteur,
  nom,
  montant,
  rallonges,
});

/** Somme des financements saisis (rallonges comprises). */
export const totalBailleurs = (lignes: LigneBailleur[]) =>
  lignes.reduce((s, l) => s + (l.nom.trim() ? (l.montant ?? 0) + l.rallonges : 0), 0);
