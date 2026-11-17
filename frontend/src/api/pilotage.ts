import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Apprentissage, Paginated, RapportProjet, Recommandation } from "../types";

/** Liste, enregistrement et suppression des éléments de pilotage d'un projet (une même forme d'API). */
function ressource<T extends { id: number }>(adresse: string) {
  return {
    useListe: (projetId: number) =>
      useQuery({
        queryKey: [adresse, projetId],
        queryFn: async () => (await apiClient.get<Paginated<T>>(`/${adresse}/`, { params: { projet: projetId, page_size: 500 } })).data.results,
      }),
    useEnregistrer: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: async ({ id, ...payload }: Partial<T>) =>
          (id ? await apiClient.patch<T>(`/${adresse}/${id}/`, payload) : await apiClient.post<T>(`/${adresse}/`, payload)).data,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: [adresse] }),
      });
    },
    useSupprimer: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: async (id: number) => apiClient.delete(`/${adresse}/${id}/`),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: [adresse] }),
      });
    },
  };
}

export const rapportsApi = ressource<RapportProjet>("rapports-attendus");
export const recommandationsApi = ressource<Recommandation>("recommandations");
export const apprentissagesApi = ressource<Apprentissage>("apprentissages");
