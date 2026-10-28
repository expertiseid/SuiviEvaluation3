import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import { cheminApi, usePartage } from "../utils/partage";
import type {
  Paginated,
  PeriodePlanification,
  PointSuivi,
  SuiviDashboard,
  TranchePlanifiee,
  ValeursPeriode,
} from "../types";

export function useSuiviDashboard(projetId: number | undefined) {
  const partage = usePartage();
  return useQuery({
    queryKey: ["suivi-dashboard", projetId, partage?.jeton],
    queryFn: async () =>
      (await apiClient.get<SuiviDashboard>(cheminApi(partage, `/suivi/projets/${projetId}/dashboard/`, "suivi"))).data,
    enabled: !!projetId,
  });
}

export async function telecharger(url: string, nomFichier: string) {
  const response = await apiClient.get(url, { responseType: "blob" });
  const objetUrl = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = objetUrl;
  link.setAttribute("download", nomFichier);
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export async function telechargerExportSuiviExcel(projetId: number, codeProjet: string) {
  await telecharger(`/suivi/projets/${projetId}/exporter/excel/`, `suivi_${codeProjet}.xlsx`);
}

export async function telechargerExportSuiviPdf(projetId: number, codeProjet: string) {
  await telecharger(`/suivi/projets/${projetId}/exporter/pdf/`, `suivi_${codeProjet}.pdf`);
}

/** Fiche de suivi au format Word (même contenu que le PDF). */
export async function telechargerExportSuiviWord(projetId: number, codeProjet: string) {
  await telecharger(`/suivi/projets/${projetId}/exporter/word/`, `suivi_${codeProjet}.docx`);
}

export type FormatExport = "excel" | "pdf" | "word";
const EXTENSION: Record<FormatExport, string> = { excel: "xlsx", pdf: "pdf", word: "docx" };

export type SectionRapportFinancier = "sources" | "rallonges" | "execution" | "detail" | "trimestres";

/** Rapport financier seul, sections et période au choix. */
export async function telechargerRapportFinancier(
  projetId: number,
  codeProjet: string,
  options: { fichier: "pdf" | "docx" | "xlsx"; sections: SectionRapportFinancier[]; debut?: string | null; fin?: string | null },
) {
  const params = new URLSearchParams({ fichier: options.fichier, sections: options.sections.join(",") });
  if (options.debut) params.set("debut", options.debut);
  if (options.fin) params.set("fin", options.fin);
  await telecharger(`/rapports/financier/${projetId}/?${params}`, `rapport_financier_${codeProjet}.${options.fichier}`);
}

export function useCreatePointSuivi() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<PointSuivi>) =>
      (await apiClient.post<PointSuivi>("/points-suivi/", payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export function useUpdatePointSuivi() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<PointSuivi> }) =>
      (await apiClient.patch<PointSuivi>(`/points-suivi/${id}/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export function useDeletePointSuivi() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/points-suivi/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export function useTranchesPlanifiees(params: { activite?: number; sous_activite?: number; indicateur?: number }) {
  return useQuery({
    queryKey: ["tranches-planifiees", params],
    queryFn: async () =>
      (await apiClient.get<Paginated<TranchePlanifiee>>("/tranches-planifiees/", { params })).data.results,
    enabled: !!(params.activite || params.sous_activite || params.indicateur),
  });
}

export function useCreateTranchePlanifiee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Omit<TranchePlanifiee, "cible" | "budget">> & {
      cible?: number | null;
      budget?: number | null;
    }) => (await apiClient.post<TranchePlanifiee>("/tranches-planifiees/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] }),
  });
}

export function useDeleteTranchePlanifiee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/tranches-planifiees/${id}/`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] }),
  });
}

export function useUpdateTranchePlanifiee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: number;
      payload: Partial<Omit<TranchePlanifiee, "cible" | "budget">> & { cible?: number | null; budget?: number | null };
    }) => (await apiClient.patch<TranchePlanifiee>(`/tranches-planifiees/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] }),
  });
}

/** Toutes les valeurs (activités et sous-activités) d'une période de planification. */
export function useTranchesPeriode(periodeId: number | null) {
  return useQuery({
    queryKey: ["tranches-planifiees", { periode: periodeId }],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<TranchePlanifiee>>("/tranches-planifiees/", {
          params: { periode: periodeId, page_size: 1000 },
        })
      ).data.results,
    enabled: !!periodeId,
  });
}

export function usePeriodesPlanification(projetId: number) {
  return useQuery({
    queryKey: ["periodes-planification", projetId],
    queryFn: async () =>
      (await apiClient.get<PeriodePlanification[]>("/periodes-planification/", { params: { projet: projetId } })).data,
  });
}

export function useCreatePeriodePlanification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Omit<PeriodePlanification, "id">) =>
      (await apiClient.post<PeriodePlanification>("/periodes-planification/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["periodes-planification"] }),
  });
}

export function useUpdatePeriodePlanification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<PeriodePlanification> }) =>
      (await apiClient.patch<PeriodePlanification>(`/periodes-planification/${id}/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["periodes-planification"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export function useDeletePeriodePlanification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/periodes-planification/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["periodes-planification"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export async function telechargerExportPeriode(periode: PeriodePlanification, codeProjet: string, format: FormatExport) {
  const libelle = periode.libelle.replace(/[^\p{L}\p{N}]+/gu, "_");
  await telecharger(
    `/periodes-planification/${periode.id}/exporter/${format}/`,
    `planification_${codeProjet}_${libelle}.${EXTENSION[format]}`,
  );
}

/** Export du suivi par période (module Suivi), même présentation que l'export du suivi global. */
export async function telechargerExportSuiviPeriode(
  periode: PeriodePlanification,
  codeProjet: string,
  format: FormatExport,
) {
  const libelle = periode.libelle.replace(/[^\p{L}\p{N}]+/gu, "_");
  await telecharger(
    `/periodes-planification/${periode.id}/exporter-suivi/${format}/`,
    `suivi_${codeProjet}_${libelle}.${EXTENSION[format]}`,
  );
}

/**
 * Valeurs de chaque élément sur la période (saisies, sinon calculées au
 * prorata) et réalisé de la période — clé sous « tranches-planifiees » pour
 * être rafraîchie par toute modification d'une tranche.
 */
export function useValeursPeriode(periodeId: number | null) {
  return useQuery({
    queryKey: ["tranches-planifiees", "valeurs-periode", periodeId],
    queryFn: async () => (await apiClient.get<ValeursPeriode>(`/periodes-planification/${periodeId}/valeurs/`)).data,
    enabled: !!periodeId,
  });
}

// --- Canevas de suivi : Excel prérempli à compléter hors ligne puis à réimporter ---------

export interface LigneCanevas {
  feuille: string;
  ligne: number;
  identifiant: string;
  libelle: string;
  statut: "ajout" | "modification" | "ignoree" | "erreur";
  actions: string[];
  erreurs: { colonne: string; message: string }[];
}

export interface ResultatCanevas {
  mode: ModeCanevas;
  totaux: { ajout: number; modification: number; ignoree: number; erreur: number };
  lignes: LigneCanevas[];
  erreurs_generales: string[];
}

/** « ajout » : ne remplace jamais une saisie existante ; « mise_a_jour » : la remplace (avec historique). */
export type ModeCanevas = "ajout" | "mise_a_jour";

export async function telechargerCanevasSuivi(projetId: number, codeProjet: string) {
  await telecharger(`/suivi/projets/${projetId}/canevas/`, `canevas_suivi_${codeProjet}.xlsx`);
}

function formulaireCanevas(fichier: File, mode: ModeCanevas) {
  const formData = new FormData();
  formData.append("fichier", fichier);
  formData.append("mode", mode);
  return formData;
}

export async function analyserCanevasSuivi(projetId: number, fichier: File, mode: ModeCanevas) {
  return (await apiClient.post<ResultatCanevas>(`/suivi/projets/${projetId}/canevas/apercu/`, formulaireCanevas(fichier, mode)))
    .data;
}

export function useImporterCanevasSuivi() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ projetId, fichier, mode }: { projetId: number; fichier: File; mode: ModeCanevas }) =>
      (await apiClient.post<ResultatCanevas>(`/suivi/projets/${projetId}/canevas/importer/`, formulaireCanevas(fichier, mode)))
        .data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["indicateurs"] });
    },
  });
}

export async function telechargerRapportErreursCanevas(projetId: number, fichier: File, mode: ModeCanevas) {
  const response = await apiClient.post(`/suivi/projets/${projetId}/canevas/rapport-erreurs/`, formulaireCanevas(fichier, mode), {
    responseType: "blob",
  });
  const objetUrl = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = objetUrl;
  link.setAttribute("download", "rapport_erreurs_canevas_suivi.xlsx");
  document.body.appendChild(link);
  link.click();
  link.remove();
}
