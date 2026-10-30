/** Carte par zone : catalogue des indicateurs, classes et couleurs des valeurs (régions, provinces…). */
import type { IndicateurZone, SyntheseZone } from "../api/geo";
import { locale, nombreCourt } from "./i18n";
import { voc } from "./vocabulaire";

type Famille = "projets" | "beneficiaires" | "budget" | "taux";
type TypeValeur = "entier" | "montant" | "pourcentage";

/**
 * Indicateurs par zone, regroupés comme les blocs du tableau de bord consolidé — même
 * catalogue que le serveur (apps.geo.services.synthese.CATALOGUE).
 */
export const CATALOGUE_ZONE: { code: IndicateurZone; libelle: string; court: string; famille: Famille; type: TypeValeur; groupe: string }[] = [
  { code: "projets", libelle: voc("Nombre de projets"), court: voc("Projets"), famille: "projets", type: "entier", groupe: voc("Vue d'ensemble") },
  { code: "beneficiaires", libelle: voc("Bénéficiaires inscrits"), court: voc("Bénéficiaires"), famille: "beneficiaires", type: "entier", groupe: voc("Vue d'ensemble") },
  { code: "budget", libelle: voc("Budget des projets présents (FCFA)"), court: voc("Budget"), famille: "budget", type: "montant", groupe: voc("Vue d'ensemble") },
  { code: "fonds_propres", libelle: voc("Fonds propres (FCFA)"), court: voc("Fonds propres"), famille: "budget", type: "montant", groupe: voc("Budget et financements") },
  { code: "financements", libelle: voc("Financements des bailleurs (FCFA)"), court: voc("Financements"), famille: "budget", type: "montant", groupe: voc("Budget et financements") },
  { code: "depenses", libelle: voc("Dépenses réalisées (FCFA)"), court: voc("Dépenses"), famille: "budget", type: "montant", groupe: voc("Budget et financements") },
  { code: "bailleurs", libelle: voc("Nombre de bailleurs"), court: voc("Bailleurs"), famille: "projets", type: "entier", groupe: voc("Budget et financements") },
  { code: "partenaires_consortium", libelle: voc("Nombre de partenaires de consortium"), court: voc("Consortium"), famille: "projets", type: "entier", groupe: voc("Budget et financements") },
  { code: "partenaires_mise_en_oeuvre", libelle: voc("Nombre de partenaires de mise en œuvre"), court: voc("Mise en œuvre"), famille: "projets", type: "entier", groupe: voc("Budget et financements") },
  { code: "projets_en_cours", libelle: voc("Projets en cours"), court: voc("En cours"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "projets_en_preparation", libelle: voc("Projets en préparation"), court: voc("En préparation"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "projets_clotures", libelle: voc("Projets clôturés"), court: voc("Clôturés"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "activites", libelle: voc("Nombre d'activités"), court: voc("Activités"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "activites_realisees", libelle: voc("Activités réalisées"), court: voc("Réalisées"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "activites_en_cours", libelle: voc("Activités en cours"), court: voc("Act. en cours"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "activites_non_realisees", libelle: voc("Activités non réalisées"), court: voc("Non réalisées"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "indicateurs", libelle: voc("Nombre d'indicateurs"), court: voc("Indicateurs"), famille: "projets", type: "entier", groupe: voc("Projets") },
  { code: "taux_physique", libelle: voc("Exécution physique moyenne (%)"), court: voc("Exécution physique"), famille: "taux", type: "pourcentage", groupe: voc("Projets") },
  { code: "taux_financier", libelle: voc("Exécution financière moyenne (%)"), court: voc("Exécution financière"), famille: "taux", type: "pourcentage", groupe: voc("Projets") },
  { code: "cible_totale", libelle: voc("Cible totale des projets"), court: voc("Cible"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "cible_femmes", libelle: voc("Cible femmes"), court: voc("Cible femmes"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "cible_hommes", libelle: voc("Cible hommes"), court: voc("Cible hommes"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "cible_jeunes", libelle: voc("Cible jeunes"), court: voc("Cible jeunes"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "cible_pdi", libelle: voc("Cible personnes déplacées (PDI)"), court: voc("Cible PDI"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "femmes", libelle: voc("Bénéficiaires inscrites (femmes)"), court: voc("Femmes"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "hommes", libelle: voc("Bénéficiaires inscrits (hommes)"), court: voc("Hommes"), famille: "beneficiaires", type: "entier", groupe: voc("Bénéficiaires") },
  { code: "nouveaux_beneficiaires", libelle: voc("Nouveaux bénéficiaires inscrits (12 derniers mois)"), court: voc("Nouveaux bénéf."), famille: "beneficiaires", type: "entier", groupe: voc("Évolution dans le temps") },
  { code: "depenses_12_mois", libelle: voc("Dépenses des 12 derniers mois (FCFA)"), court: voc("Dépenses 12 mois"), famille: "budget", type: "montant", groupe: voc("Évolution dans le temps") },
];
const PAR_CODE = new Map(CATALOGUE_ZONE.map((i) => [i.code, i]));
export const infoIndicateur = (code: IndicateurZone) => PAR_CODE.get(code) ?? CATALOGUE_ZONE[0];

/** Options groupées pour une liste de choix (Select / MultiSelect). */
export function optionsIndicateursZone() {
  const groupes = new Map<string, { value: string; label: string }[]>();
  for (const i of CATALOGUE_ZONE) groupes.set(i.groupe, [...(groupes.get(i.groupe) ?? []), { value: i.code, label: i.libelle }]);
  return [...groupes.entries()].map(([group, items]) => ({ group, items }));
}

// Dégradé du plus faible au plus fort (5 classes) par famille, et gris pour « aucune donnée ».
const DEGRADES_FAMILLE: Record<Famille, string[]> = {
  projets: ["#dbeafe", "#93c5fd", "#3b82f6", "#1d4ed8", "#1e3a8a"],
  beneficiaires: ["#d1fae5", "#6ee7b7", "#10b981", "#047857", "#064e3b"],
  budget: ["#fef3c7", "#fcd34d", "#f59e0b", "#b45309", "#78350f"],
  taux: ["#fee2e2", "#fdba74", "#fde047", "#86efac", "#16a34a"],
};
export const degrade = (indicateur: IndicateurZone) => DEGRADES_FAMILLE[infoIndicateur(indicateur).famille];
export const SANS_DONNEE = "#f1f3f5";
const pourcentage = (i: IndicateurZone) => infoIndicateur(i).type === "pourcentage";
export const entier = (i: IndicateurZone) => infoIndicateur(i).type === "entier";

export const normaliser = (s: string) =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-']/g, " ").replace(/\s+/g, " ").trim();

/** Valeur d'un indicateur pour une zone de la synthèse. */
export const valeurZone = (z: SyntheseZone, indicateur: IndicateurZone): number | null => z.valeurs?.[indicateur] ?? null;

export function formatValeur(indicateur: IndicateurZone, v: number | null): string {
  if (v === null) return "—";
  if (pourcentage(indicateur)) return `${v.toLocaleString(locale())} %`;
  if (infoIndicateur(indicateur).type === "montant") return nombreCourt(v);
  return v.toLocaleString(locale());
}

/** Bornes des classes : seuils fixes pour les taux, sinon classes égales jusqu'au maximum. */
export function classes(indicateur: IndicateurZone, zones: SyntheseZone[]): number[] {
  if (pourcentage(indicateur)) return [20, 40, 60, 80];
  const max = Math.max(0, ...zones.map((z) => valeurZone(z, indicateur) ?? 0));
  if (max <= 0) return [1, 2, 3, 4];
  const bornes = [1, 2, 3, 4].map((k) => (max * k) / 5);
  // Comptages : bornes entières, croissantes.
  if (entier(indicateur)) {
    return bornes.map((b, i) => Math.max(Math.ceil(b), i + 2));
  }
  return bornes;
}

export function couleur(indicateur: IndicateurZone, v: number | null, bornes: number[]) {
  if (v === null || (!pourcentage(indicateur) && v <= 0)) return SANS_DONNEE;
  const i = bornes.findIndex((b) => v < b);
  return degrade(indicateur)[i === -1 ? 4 : i];
}
