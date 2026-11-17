import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accesPartage, apiClient, avecOrganisation } from "./client";
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
  /** Protégé par un mot de passe (le mot de passe lui-même n'est jamais renvoyé). */
  protege: boolean;
  /** Envoi seulement : nouveau mot de passe, ou « » pour le retirer. */
  mot_de_passe?: string;
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

/** Lien protégé : vérifie le mot de passe et garde l'accès accordé pour les demandes suivantes. */
export async function ouvrirLienProtege(jeton: string, motDePasse: string) {
  const { data } = await apiClient.post<{ acces: string }>(`/public/partage/${jeton}/acces/`, { mot_de_passe: motDePasse });
  accesPartage.ecrire(jeton, data.acces);
}
