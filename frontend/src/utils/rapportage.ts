/** Libellés des périodes de rapportage (voir apps/projects/rapportage.py). */
import type { PerimetreFermeture, Projet } from "../types";
import { voc } from "./vocabulaire";

export const LIBELLES_PERIMETRE: Record<PerimetreFermeture, string> = {
  REALISATIONS: voc("Les réalisations seulement"),
  TOUT: voc("Tout le projet"),
};

export const AIDES_PERIMETRE: Record<PerimetreFermeture, string> = {
  REALISATIONS:
    voc("Hors période : suivis, valeurs d'indicateurs, taux manuels, avancement des tâches et validation des livrables sont fermés ; la planification reste modifiable."),
  TOUT: voc("Hors période : tout le projet est en lecture seule (planification, suivi, indicateurs, bénéficiaires, documents)."),
};

/** La saisie des réalisations (et, si fermé en entier, de tout le projet) est-elle bloquée pour cet utilisateur ? */
export function saisieBloquee(projet: Projet | undefined, role: string | undefined) {
  if (!projet || projet.etat_saisie.ouverte || role === "ADMIN") return { realisations: false, tout: false };
  return { realisations: true, tout: projet.etat_saisie.perimetre === "TOUT" };
}
