import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  Paginated,
  PeriodePlanification,
  PointSuivi,
  SuiviDashboard,
  TranchePlanifiee,
  ValeursPeriode,
} from "../types";

export function useSuiviDashboard(projetId: number | undefined) {
  return useQuery({
    queryKey: ["suivi-dashboard", projetId],
    queryFn: async () => (await apiClient.get<SuiviDashboard>(`/suivi/projets/${projetId}/dashboard/`)).data,
    enabled: !!projetId,
  });
}

async function telecharger(url: string, nomFichier: string) {
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

export async function telechargerExportPeriode(periode: PeriodePlanification, codeProjet: string, format: "excel" | "pdf") {
  const libelle = periode.libelle.replace(/[^\p{L}\p{N}]+/gu, "_");
  await telecharger(
    `/periodes-planification/${periode.id}/exporter/${format}/`,
    `planification_${codeProjet}_${libelle}.${format === "excel" ? "xlsx" : "pdf"}`,
  );
}

/** Export du suivi par période (module Suivi), même présentation que l'export du suivi global. */
export async function telechargerExportSuiviPeriode(
  periode: PeriodePlanification,
  codeProjet: string,
  format: "excel" | "pdf",
) {
  const libelle = periode.libelle.replace(/[^\p{L}\p{N}]+/gu, "_");
  await telecharger(
    `/periodes-planification/${periode.id}/exporter-suivi/${format}/`,
    `suivi_${codeProjet}_${libelle}.${format === "excel" ? "xlsx" : "pdf"}`,
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
