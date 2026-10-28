import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { EvaluationRisque, Paginated, Risque } from "../types";

export function useRisques(projetId: number) {
  return useQuery({
    queryKey: ["risques", projetId],
    queryFn: async () =>
      (await apiClient.get<Paginated<Risque>>("/risques/", { params: { projet: projetId, page_size: 500 } })).data.results,
  });
}

export function useEnregistrerRisque() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<Risque>) =>
      (id ? await apiClient.patch<Risque>(`/risques/${id}/`, payload) : await apiClient.post<Risque>("/risques/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risques"] }),
  });
}

export function useSupprimerRisque() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/risques/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risques"] }),
  });
}

/** Réévaluation : devient la cotation et le statut courants du risque. */
export function useEnregistrerEvaluationRisque() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<EvaluationRisque>) =>
      (await apiClient.post<EvaluationRisque>("/evaluations-risques/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risques"] }),
  });
}

export function useSupprimerEvaluationRisque() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/evaluations-risques/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risques"] }),
  });
}
