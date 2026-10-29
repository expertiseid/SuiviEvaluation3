/** Carte par zone : classes et couleurs des valeurs (régions, provinces…). */
import type { IndicateurZone, SyntheseZone } from "../api/geo";

// Dégradé du plus faible au plus fort (5 classes), et gris pour « aucune donnée ».
export const DEGRADES: Record<IndicateurZone, string[]> = {
  projets: ["#dbeafe", "#93c5fd", "#3b82f6", "#1d4ed8", "#1e3a8a"],
  beneficiaires: ["#d1fae5", "#6ee7b7", "#10b981", "#047857", "#064e3b"],
  budget: ["#fef3c7", "#fcd34d", "#f59e0b", "#b45309", "#78350f"],
  taux_physique: ["#fee2e2", "#fdba74", "#fde047", "#86efac", "#16a34a"],
  taux_financier: ["#fee2e2", "#fdba74", "#fde047", "#86efac", "#16a34a"],
};
export const SANS_DONNEE = "#f1f3f5";
const pourcentage = (i: IndicateurZone) => i === "taux_physique" || i === "taux_financier";

export const normaliser = (s: string) =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-']/g, " ").replace(/\s+/g, " ").trim();

export function formatValeur(indicateur: IndicateurZone, v: number | null): string {
  if (v === null) return "—";
  if (pourcentage(indicateur)) return `${v.toLocaleString("fr-FR")} %`;
  if (indicateur === "budget") {
    return v >= 1e9 ? `${(v / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} Md` : v >= 1e6 ? `${(v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M` : v.toLocaleString("fr-FR");
  }
  return v.toLocaleString("fr-FR");
}

/** Bornes des classes : seuils fixes pour les taux, sinon classes égales jusqu'au maximum. */
export function classes(indicateur: IndicateurZone, zones: SyntheseZone[]): number[] {
  if (pourcentage(indicateur)) return [20, 40, 60, 80];
  const max = Math.max(0, ...zones.map((z) => (z[indicateur] as number) ?? 0));
  if (max <= 0) return [1, 2, 3, 4];
  const bornes = [1, 2, 3, 4].map((k) => (max * k) / 5);
  // Comptages (projets, bénéficiaires) : bornes entières, croissantes.
  if (indicateur === "projets" || indicateur === "beneficiaires") {
    return bornes.map((b, i) => Math.max(Math.ceil(b), i + 2));
  }
  return bornes;
}

export function couleur(indicateur: IndicateurZone, v: number | null, bornes: number[]) {
  if (v === null || (!pourcentage(indicateur) && v <= 0)) return SANS_DONNEE;
  const i = bornes.findIndex((b) => v < b);
  return DEGRADES[indicateur][i === -1 ? 4 : i];
}

