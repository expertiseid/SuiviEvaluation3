/** État des filtres du tableau de bord consolidé et traduction en paramètres de l'API. */
import type { FiltresDashboard, StatutProjet } from "../types";

export type ModeDates = "toutes" | "annee" | "plage";

export interface EtatFiltres {
  mode: ModeDates;
  annee: string | null;
  dateDebut: string | null;
  dateFin: string | null;
  periode: NonNullable<FiltresDashboard["periode"]>;
  statuts: StatutProjet[];
}

export const FILTRES_PAR_DEFAUT: EtatFiltres = {
  mode: "toutes",
  annee: String(new Date().getFullYear()),
  dateDebut: null,
  dateFin: null,
  periode: "actifs",
  statuts: [],
};


/** Traduit l'état de l'écran en paramètres de l'API. */
export function versParametres(f: EtatFiltres): FiltresDashboard {
  const params: FiltresDashboard = { statuts: f.statuts };
  if (f.mode === "annee" && f.annee) {
    params.annee = Number(f.annee);
  } else if (f.mode === "plage" && (f.dateDebut || f.dateFin)) {
    params.date_debut = f.dateDebut ?? undefined;
    params.date_fin = f.dateFin ?? undefined;
  } else {
    return params;
  }
  params.periode = f.periode;
  return params;
}

/** Paramètres de requête des filtres (statuts séparés par des virgules), pour les autres écrans (carte). */
export function parametresRequete(f: FiltresDashboard) {
  return { ...f, statuts: f.statuts?.length ? f.statuts.join(",") : undefined };
}
