import type { RecapAxesCadreStrategique } from "../../types";

type Activite = RecapAxesCadreStrategique["activites"][number];

export function nombre(v: string | number | null): number {
  return v === null ? 0 : Number(v);
}

function moyenne(valeurs: (number | null)[]): number | null {
  const definies = valeurs.filter((v): v is number => v !== null);
  return definies.length ? Math.round((definies.reduce((s, v) => s + v, 0) / definies.length) * 10) / 10 : null;
}

/**
 * Ligne de totaux d'un groupe d'activités : nombre, budgets additionnés sans double compte
 * (budget d'un niveau ignoré quand le détail est saisi en dessous), taux = moyenne des
 * éléments les plus bas du groupe (un niveau dont un élément en dessous est aussi dans le
 * groupe est déjà compté à travers lui).
 */
export function totaux(activites: Activite[]) {
  const auDessus = new Set(activites.flatMap((a) => a.ancetres));
  const derniers = activites.filter((a) => !auDessus.has(a.id));
  return {
    nombre: activites.length,
    alloue: activites.reduce((s, a) => s + nombre(a.budget_alloue_compte), 0),
    depense: activites.reduce((s, a) => s + nombre(a.budget_realise_compte), 0),
    tauxPhysique: moyenne(derniers.map((a) => a.taux_physique)),
    tauxFinancier: moyenne(derniers.map((a) => a.taux_financier)),
  };
}
