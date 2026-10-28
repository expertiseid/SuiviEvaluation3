import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { NiveauAdministratif, Paginated, Zone } from "../types";

/** Pays dont le découpage administratif est configuré (codes ISO). */
export function usePaysAvecNiveaux() {
  return useQuery({
    queryKey: ["niveaux-administratifs", "pays"],
    queryFn: async () => {
      const niveaux = (
        await apiClient.get<Paginated<NiveauAdministratif>>("/niveaux-administratifs/", { params: { page_size: 1000 } })
      ).data.results;
      return [...new Set(niveaux.map((n) => n.pays))].sort();
    },
  });
}

export function useNiveauxAdministratifs(pays: string | null | undefined) {
  return useQuery({
    queryKey: ["niveaux-administratifs", pays],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<NiveauAdministratif>>("/niveaux-administratifs/", {
          params: { page_size: 200, pays },
        })
      ).data.results,
    enabled: !!pays,
  });
}

export function useCreateNiveauAdministratif() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<NiveauAdministratif>) =>
      (await apiClient.post<NiveauAdministratif>("/niveaux-administratifs/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["niveaux-administratifs"] }),
  });
}

export function useUpdateNiveauAdministratif() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<NiveauAdministratif> }) =>
      (await apiClient.patch<NiveauAdministratif>(`/niveaux-administratifs/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["niveaux-administratifs"] }),
  });
}

export function useDeleteNiveauAdministratif() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/niveaux-administratifs/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["niveaux-administratifs"] }),
  });
}

export function useZones(params?: { pays?: string | null; niveau_administratif?: number }) {
  return useQuery({
    queryKey: ["zones", params],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<Zone>>("/zones/", {
          params: { page_size: 2000, ...params },
        })
      ).data.results,
    enabled: params?.pays === undefined || !!params.pays,
  });
}

export function useCreateZone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Zone>) => (await apiClient.post<Zone>("/zones/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["zones"] }),
  });
}

export function useUpdateZone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<Zone> }) =>
      (await apiClient.patch<Zone>(`/zones/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["zones"] }),
  });
}

export function useDeleteZone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/zones/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["zones"] }),
  });
}

/** Contours d'un niveau administratif (GeoJSON, source geoBoundaries) pour la carte. */
export function useLimitesAdministratives(pays: string | undefined, niveau: number) {
  return useQuery({
    queryKey: ["limites-administratives", pays, niveau],
    queryFn: async () =>
      (
        await apiClient.get<{ pays: string; niveau: number; nom_niveau: string; annee: string; geojson: GeoJSON.FeatureCollection }>(
          "/limites-administratives/",
          { params: { pays, niveau } },
        )
      ).data,
    enabled: !!pays,
    staleTime: Infinity,
    retry: false,
  });
}
