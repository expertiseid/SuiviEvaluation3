import type { StatusTone } from "../components/common/StatusBadge";
import type { StatutActivite, StatutProjet } from "../types";
import { voc } from "./vocabulaire";

export const PROJET_STATUT_TONE: Record<StatutProjet, StatusTone> = {
  EN_PREPARATION: "neutral",
  EN_COURS: "success",
  CLOTURE: "neutral",
};

export const PROJET_STATUT_LABEL: Record<StatutProjet, string> = {
  EN_PREPARATION: voc("En préparation"),
  EN_COURS: voc("En cours"),
  CLOTURE: voc("Clôturé"),
};

export const ACTIVITE_STATUT_TONE: Record<StatutActivite, StatusTone> = {
  NON_REALISEE: "neutral",
  EN_COURS: "warning",
  REALISEE: "success",
};

export const ACTIVITE_STATUT_LABEL: Record<StatutActivite, string> = {
  NON_REALISEE: voc("Non réalisée"),
  EN_COURS: voc("En cours"),
  REALISEE: voc("Réalisée"),
};

export const SOUS_ACTIVITE_STATUT_LABEL: Record<string, string> = {
  PLANIFIEE: voc("Planifiée"),
  EN_COURS: voc("En cours"),
  TERMINEE: voc("Terminée"),
};

export const SUIVI_STATUT_GLOBAL_TONE: Record<string, StatusTone> = {
  ATTEINT: "success",
  EN_COURS: "warning",
  EN_RETARD: "danger",
};

export const SUIVI_STATUT_GLOBAL_LABEL: Record<string, string> = {
  ATTEINT: voc("Atteint"),
  EN_COURS: voc("En cours"),
  EN_RETARD: voc("En retard"),
};
