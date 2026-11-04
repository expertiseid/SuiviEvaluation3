import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, avecOrganisation } from "./client";
import type { Paginated } from "../types";

export interface LienPartage {
  id: number;
  jeton: string;
  type: "TABLEAU_DE_BORD" | "SUIVI_PROJET";
  contenu: "TOUT" | "ACTIVITES" | "INDICATEURS";
  projet: number | null;
  projet_code: string;
  filtres: Record<string, unknown>;
  libelle: string;
  cree_par_nom: string;
  expire_le: string | null;
  actif: boolean;
  valide: boolean;
  nombre_consultations: number;
  derniere_consultation: string | null;
  created_at: string;
}

export function useLiensPartage(type: LienPartage["type"], projetId: number | null) {
  return useQuery({
    queryKey: ["liens-partage", type, projetId],
    queryFn: async () =>
      (await apiClient.get<Paginated<LienPartage>>("/liens-partage/", { params: { type, projet: projetId ?? undefined, page_size: 200 } })).data.results,
  });
}

export function useEnregistrerLienPartage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<LienPartage>) =>
      (id ? await apiClient.patch<LienPartage>(`/liens-partage/${id}/`, payload) : await apiClient.post<LienPartage>("/liens-partage/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["liens-partage"] }),
  });
}

export function useSupprimerLienPartage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/liens-partage/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["liens-partage"] }),
  });
}

/** Adresse publique d'un lien (à copier et envoyer). */
export const adresseLien = (jeton: string) => avecOrganisation(`${window.location.origin}/partage/${jeton}`);
