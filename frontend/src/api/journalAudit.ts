/** Journal d'audit de la plateforme (Administrateur) : consultation filtrée et export Excel. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Paginated } from "../types";
import { voc } from "../utils/vocabulaire";

export type ActionAudit =
  | "CONNEXION" | "CONNEXION_ECHOUEE" | "CONSULTATION_SENSIBLE" | "DOSSIER" | "TELECHARGEMENT" | "EXPORT"
  | "CONFIGURATION" | "PERMISSION" | "HABILITATION" | "DROITS_PERSONNES" | "DOUBLE_AUTHENTIFICATION"
  | "PARTAGE" | "MOT_DE_PASSE" | "SUPPRESSION";

export const ACTIONS_AUDIT: ActionAudit[] = [
  "CONNEXION", "CONNEXION_ECHOUEE", "CONSULTATION_SENSIBLE", "DOSSIER", "TELECHARGEMENT", "EXPORT",
  "CONFIGURATION", "PERMISSION", "HABILITATION", "DROITS_PERSONNES", "DOUBLE_AUTHENTIFICATION",
  "PARTAGE", "MOT_DE_PASSE", "SUPPRESSION",
];

export const libelleActionAudit = (a: ActionAudit): string =>
  ({
    CONNEXION: voc("Connexion"),
    CONNEXION_ECHOUEE: voc("Connexion refusée"),
    CONSULTATION_SENSIBLE: voc("Consultation d'un dossier confidentiel"),
    DOSSIER: voc("Action sur un dossier"),
    TELECHARGEMENT: voc("Téléchargement d'une pièce jointe"),
    EXPORT: voc("Export"),
    CONFIGURATION: voc("Modification de la configuration"),
    PERMISSION: voc("Modification des droits d'un compte"),
    HABILITATION: voc("Habilitation confidentielle"),
    DROITS_PERSONNES: voc("Demande d'une personne sur ses données"),
    DOUBLE_AUTHENTIFICATION: voc("Double authentification"),
    PARTAGE: voc("Partage d'un document par lien"),
    MOT_DE_PASSE: voc("Mot de passe oublié"),
    SUPPRESSION: voc("Suppression"),
  })[a];

export interface EvenementAudit {
  id: number;
  date: string;
  utilisateur_id: number | null;
  utilisateur: string;
  action: ActionAudit;
  module: string;
  objet: string;
  details: Record<string, unknown>;
}

export interface FiltresAudit {
  page: number;
  action?: string | null;
  utilisateur?: string;
  objet?: string;
  du?: string | null;
  au?: string | null;
}

const parametres = (f: Partial<FiltresAudit>) => Object.fromEntries(Object.entries(f).filter(([, x]) => x !== "" && x != null));

export function useJournalAudit(filtres: FiltresAudit) {
  return useQuery({
    queryKey: ["journal-audit", filtres],
    queryFn: async () => (await apiClient.get<Paginated<EvenementAudit>>("/journal-audit/", { params: parametres(filtres) })).data,
    placeholderData: keepPreviousData,
  });
}

export async function exporterJournalAudit(filtres: Omit<FiltresAudit, "page">) {
  const r = await apiClient.get("/journal-audit/exporter/", { params: parametres(filtres), responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([r.data]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", "journal_audit.xlsx");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}
