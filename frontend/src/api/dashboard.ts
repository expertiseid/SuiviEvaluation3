import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  ConfigurationTableauDeBord,
  DashboardConsolide,
  DashboardProjet,
  Echeance,
  FiltresDashboard,
} from "../types";

export function useDashboardConsolide(filtres: FiltresDashboard = {}) {
  const params = {
    ...filtres,
    statuts: filtres.statuts?.length ? filtres.statuts.join(",") : undefined,
  };
  return useQuery({
    queryKey: ["dashboard", "consolide", params],
    queryFn: async () => (await apiClient.get<DashboardConsolide>("/dashboard/consolide/", { params })).data,
    // Garde l'affichage précédent pendant le rechargement après un changement de filtre.
    placeholderData: keepPreviousData,
  });
}

export function useEcheances() {
  return useQuery({
    queryKey: ["dashboard", "echeances"],
    queryFn: async () => (await apiClient.get<Echeance[]>("/dashboard/echeances/")).data,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useDashboardProjet(projetId: number | undefined) {
  return useQuery({
    queryKey: ["dashboard", "projet", projetId],
    queryFn: async () => (await apiClient.get<DashboardProjet>(`/dashboard/projet/${projetId}/`)).data,
    enabled: !!projetId,
  });
}

/** Blocs masqués et types de graphiques, communs à tous les utilisateurs. */
export function useConfigurationTableauDeBord() {
  return useQuery({
    queryKey: ["dashboard", "configuration"],
    queryFn: async () => (await apiClient.get<ConfigurationTableauDeBord>("/dashboard/configuration/")).data,
  });
}

export function useEnregistrerConfigurationTableauDeBord() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Pick<ConfigurationTableauDeBord, "blocs_masques" | "types_graphiques">>) =>
      (await apiClient.put<ConfigurationTableauDeBord>("/dashboard/configuration/", payload)).data,
    // Mise à jour immédiate de l'écran, sans attendre un rechargement.
    onSuccess: (configuration) => queryClient.setQueryData(["dashboard", "configuration"], configuration),
  });
}
