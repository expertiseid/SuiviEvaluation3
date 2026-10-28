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
  queryClient.invalidateQueries({ queryKey: ["approbations"] });
  queryClient.invalidateQueries({ queryKey: ["projets"] });
  queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["activite"] });
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
