/** Formatage partagé des onglets « Planification par période » et « Suivi par période ». */

export function nombre(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

export function fmt(v: string | number | null | undefined): string {
  const n = nombre(v);
  return n === null ? "—" : n.toLocaleString("fr-FR");
}

/** « 01/02/2026 » */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "?";
  const [a, m, j] = iso.slice(0, 10).split("-");
  return `${j}/${m}/${a}`;
}

/** Durée en jours, bornes comprises (même jour = 1 jour) ; null si une date manque ou fin < début. */
export function dureeJours(debut: string | null | undefined, fin: string | null | undefined): number | null {
  if (!debut || !fin) return null;
  const jours = Math.round((Date.parse(fin.slice(0, 10)) - Date.parse(debut.slice(0, 10))) / 86_400_000) + 1;
  return jours > 0 ? jours : null;
}

/** « 1 jour », « 12 jours » */
export function libelleDuree(debut: string | null | undefined, fin: string | null | undefined): string {
  const jours = dureeJours(debut, fin);
  return jours === null ? "" : `${jours.toLocaleString("fr-FR")} jour${jours > 1 ? "s" : ""}`;
}

/** « 1er janvier 2026 » */
export function fmtDateLongue(iso: string): string {
  const [a, m, j] = iso.slice(0, 10).split("-").map(Number);
  const mois = new Date(a, m - 1, 1).toLocaleString("fr-FR", { month: "long" });
  return `${j === 1 ? "1er" : j} ${mois} ${a}`;
}
