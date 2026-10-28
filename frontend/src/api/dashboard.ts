import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import { cheminApi, usePartage } from "../utils/partage";
import type { Vocabulaire } from "../utils/vocabulaire";
import type {
  ConfigurationTableauDeBord,
  DashboardConsolide,
  DashboardProjet,
  Echeance,
  FiltresDashboard,
} from "../types";

export function useDashboardConsolide(filtres: FiltresDashboard = {}) {
  const partage = usePartage();
  const params = {
    ...filtres,
    statuts: filtres.statuts?.length ? filtres.statuts.join(",") : undefined,
  };
  return useQuery({
    queryKey: ["dashboard", "consolide", params, partage?.jeton],
    queryFn: async () =>
      (await apiClient.get<DashboardConsolide>(cheminApi(partage, "/dashboard/consolide/", "dashboard"), { params })).data,
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
  const partage = usePartage();
  return useQuery({
    queryKey: ["dashboard", "configuration", partage?.jeton],
    queryFn: async () =>
      (await apiClient.get<ConfigurationTableauDeBord>(cheminApi(partage, "/dashboard/configuration/", "configuration"))).data,
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

/** Noms et icônes des rubriques du menu latéral choisis par l'Administrateur, par route. */
export interface ConfigurationMenu {
  libelles: Record<string, string>;
  /** Nom d'une icône de ICONES_MENU (utils/iconesMenu). */
  icones: Record<string, string>;
  vocabulaire: Vocabulaire;
  peut_modifier: boolean;
}

export function useConfigurationMenu() {
  const partage = usePartage();
  return useQuery({
    queryKey: ["configuration-menu", partage?.jeton],
    queryFn: async () => (await apiClient.get<ConfigurationMenu>(cheminApi(partage, "/interface/menu/", "menu"))).data,
    staleTime: 5 * 60 * 1000,
  });
}

export function useUpdateConfigurationMenu() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      libelles: Record<string, string>;
      icones: Record<string, string>;
      vocabulaire: Vocabulaire;
    }) =>
      (await apiClient.put<ConfigurationMenu>("/interface/menu/", payload)).data,
    onSuccess: (data) => queryClient.setQueryData(["configuration-menu"], data),
  });
}
