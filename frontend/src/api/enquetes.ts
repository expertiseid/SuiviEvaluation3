import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { CalculEnquete, Enquete, Paginated, ResultatEnquete } from "../types";

export function useEnquetes() {
  return useQuery({
    queryKey: ["enquetes"],
    queryFn: async () => (await apiClient.get<Paginated<Enquete>>("/enquetes/", { params: { page_size: 200 } })).data.results,
  });
}

export function useImporterEnquete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ fichier, titre, projet }: { fichier: File; titre: string; projet: number | null }) => {
      const donnees = new FormData();
      donnees.append("fichier", fichier);
      donnees.append("titre", titre);
      if (projet) donnees.append("projet", String(projet));
      return (await apiClient.post<Enquete>("/enquetes/", donnees, { timeout: 300000 })).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["enquetes"] }),
  });
}

/** Titre, projet, dates et plan de sondage (poids, strate, grappe). */
export function useModifierEnquete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<Enquete> & { id: number }) => (await apiClient.patch<Enquete>(`/enquetes/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["enquetes"] }),
  });
}

export function useSupprimerEnquete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/enquetes/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["enquetes"] }),
  });
}

/** Réponses d'une colonne texte et leur nombre. */
export function useModalitesEnquete(enquete: number | null | undefined, colonne: string | null | undefined) {
  return useQuery({
    queryKey: ["enquetes", enquete, "modalites", colonne],
    queryFn: async () =>
      (await apiClient.get<{ valeur: string; nombre: number }[]>(`/enquetes/${enquete}/modalites/`, { params: { colonne } })).data,
    enabled: !!enquete && !!colonne,
  });
}

/** Estimation pondérée avec intervalle de confiance à 95 %. */
export function useCalculEnquete(enquete: number | null, params: { calcul: CalculEnquete; colonne: string | null; valeurs: string[]; par: string | null }) {
  const pret = !!enquete && !!params.colonne && (params.calcul !== "proportion" || params.valeurs.length > 0);
  return useQuery({
    queryKey: ["enquetes", enquete, "calcul", params],
    queryFn: async () =>
      (await apiClient.get<ResultatEnquete>(`/enquetes/${enquete}/calcul/`, {
        params: { ...params, par: params.par ?? undefined },
        paramsSerializer: { indexes: null },
      })).data,
    enabled: pret,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
