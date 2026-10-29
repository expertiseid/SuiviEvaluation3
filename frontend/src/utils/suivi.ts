import { voc } from "./vocabulaire";
export interface FenetreAttendue {
  debut: string;
  fin: string;
  depart: number;
  arrivee: number;
}

/** Valeur "attendue" à une date donnée si la progression était parfaitement
 * linéaire entre le début et la fin planifiés (avant le début : valeur de
 * départ ; après la fin : valeur cible). */
export function valeurAttendueA(dateIso: string, fenetre: FenetreAttendue): number {
  const debut = new Date(fenetre.debut).getTime();
  const fin = new Date(fenetre.fin).getTime();
  const date = new Date(dateIso).getTime();
  if (fin <= debut) return fenetre.arrivee;
  const t = Math.min(1, Math.max(0, (date - debut) / (fin - debut)));
  return fenetre.depart + (fenetre.arrivee - fenetre.depart) * t;
}

export function tauxDe(valeur: number | null, cible: number | null): number | null {
  if (valeur === null || !cible) return null;
  return Math.round((valeur / cible) * 1000) / 10;
}

/**
 * Écart exprimé dans l'unité du projet (personnes, hectares…), pas en
 * pourcentage — "75 producteurs de plus que prévu" se comprend directement,
 * contrairement à un écart en points de pourcentage.
 */
export function ecartTexte(valeurReelle: number | null, valeurAttendue: number | null, unite?: string): string | null {
  if (valeurReelle === null || valeurAttendue === null) return null;
  const ecart = Math.round((valeurReelle - valeurAttendue) * 10) / 10;
  const suffixe = unite ? ` ${unite}` : "";
  if (ecart > 0) return voc`${ecart}${suffixe} de plus que prévu à cette date`;
  if (ecart < 0) return voc`${Math.abs(ecart)}${suffixe} de moins que prévu à cette date`;
  return voc("exactement comme prévu à cette date");
}
