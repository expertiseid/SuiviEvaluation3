import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Approbations, SaisieAApprouver } from "../types";

export function useApprobations() {
  return useQuery({
    queryKey: ["approbations"],
    queryFn: async () => (await apiClient.get<Approbations>("/approbations/")).data,
  });
}

/** Une décision change les totaux, les taux et la planification : tout ce qui en dépend est rechargé. */
function apresDecision(queryClient: ReturnType<typeof useQueryClient>) {
  // Une modification approuvée peut toucher n'importe quel écran (bénéficiaires, indicateurs…) : tout est rechargé.
  queryClient.invalidateQueries();
}

/** Onglets dont toute création, modification ou suppression doit être approuvée (sauf par l'Administrateur). */
export function useReglagesApprobation() {
  return useQuery({
    queryKey: ["approbations", "reglages"],
    queryFn: async () => (await apiClient.get<{ modules_a_approuver: string[] }>("/approbations/reglages/")).data,
  });
}

export function useEnregistrerReglagesApprobation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (modules: string[]) =>
      (await apiClient.put("/approbations/reglages/", { modules_a_approuver: modules })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approbations", "reglages"] }),
  });
}

export function useTraiterSaisie() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ type, id, approuver, motif }: { type: SaisieAApprouver["type"]; id: number; approuver: boolean; motif?: string }) =>
      (await apiClient.post(`/approbations/saisies/${type}/${id}/`, { approuver, motif })).data,
    onSuccess: () => apresDecision(queryClient),
  });
}

export function useTraiterDemande() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, approuver, motif }: { id: number; approuver: boolean; motif?: string }) =>
      (await apiClient.post(`/approbations/demandes/${id}/`, { approuver, motif })).data,
    onSuccess: () => apresDecision(queryClient),
  });
}
