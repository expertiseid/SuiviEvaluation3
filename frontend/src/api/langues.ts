import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Langue } from "../utils/i18n";

/** Traduction d'un texte de l'interface corrigée par l'Administrateur (remplace celle livrée). */
export interface TraductionCorrigee {
  id: number;
  langue: Langue;
  source: string;
  traduction: string;
  updated_at: string;
  modifie_par_nom: string | null;
}

/** Une ligne du journal des traductions : correction ou retrait d'une correction. */
export interface EntreeJournalTraduction {
  date: string;
  utilisateur: string | null;
  type: "correction" | "retrait";
  source: string;
  traduction: string;
}

export function useTraductionsCorrigees(langue: Langue) {
  return useQuery({
    queryKey: ["traductions-corrigees", langue],
    queryFn: async () =>
      (await apiClient.get<TraductionCorrigee[]>("/traductions-corrigees/", { params: { langue } })).data,
  });
}

/** Enregistre une correction (une nouvelle saisie remplace la précédente pour ce texte). */
export function useCorrigerTraduction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { langue: Langue; source: string; traduction: string }) =>
      (await apiClient.post<TraductionCorrigee>("/traductions-corrigees/", payload)).data,
    onSuccess: (_d, { langue }) => {
      queryClient.invalidateQueries({ queryKey: ["traductions-corrigees", langue] });
      queryClient.invalidateQueries({ queryKey: ["journal-traductions", langue] });
    },
  });
}

/** Retire une correction : la traduction livrée avec l'application revient. */
export function useRetirerCorrection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (correction: TraductionCorrigee) => {
      await apiClient.delete(`/traductions-corrigees/${correction.id}/`);
      return correction;
    },
    onSuccess: (correction) => {
      queryClient.invalidateQueries({ queryKey: ["traductions-corrigees", correction.langue] });
      queryClient.invalidateQueries({ queryKey: ["journal-traductions", correction.langue] });
    },
  });
}

/**
 * Import d'un fichier de traductions : une traduction nulle retire la correction. Tout ou rien :
 * le serveur refuse l'ensemble si une ligne est invalide.
 */
export function useImporterTraductions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { langue: Langue; lignes: { source: string; traduction: string | null }[] }) =>
      (await apiClient.post<{ corrigees: number; retirees: number }>("/traductions-corrigees/importer/", payload)).data,
    onSuccess: (_d, { langue }) => {
      queryClient.invalidateQueries({ queryKey: ["traductions-corrigees", langue] });
      queryClient.invalidateQueries({ queryKey: ["journal-traductions", langue] });
    },
  });
}

/** Les dernières modifications des traductions d'une langue : qui, quand, quoi. */
export function useJournalTraductions(langue: Langue, actif: boolean) {
  return useQuery({
    queryKey: ["journal-traductions", langue],
    queryFn: async () =>
      (await apiClient.get<EntreeJournalTraduction[]>("/traductions-corrigees/journal/", { params: { langue } })).data,
    enabled: actif,
  });
}

/** Langue proposée par défaut aux utilisateurs qui n'en ont pas choisi (réglage de l'organisation). */
export function useDefinirLangueParDefaut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (langue: Langue) => (await apiClient.put("/interface/menu/", { langue_defaut: langue })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["configuration-menu"] }),
  });
}
