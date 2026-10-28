/**
 * Organisation : structure interne (directions, services…), parties prenantes, partenaires et
 * rôle des partenaires dans chaque projet.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  CategoriePartiePrenante,
  Paginated,
  Partenaire,
  PartenaireProjet,
  PartiePrenante,
  StructureOrganisation,
} from "../types";

/** CRUD générique d'un référentiel non paginé ; `invalider` liste les autres requêtes à rafraîchir. */
function crud<T extends { id: number }>(url: string, cle: string, invalider: string[] = []) {
  return {
    useListe: () =>
      useQuery({ queryKey: [cle], queryFn: async () => (await apiClient.get<T[]>(url)).data }),
    useEnregistrer: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: async ({ id, ...payload }: Partial<T> & { id?: number }) =>
          id
            ? (await apiClient.patch<T>(`${url}${id}/`, payload)).data
            : (await apiClient.post<T>(url, payload)).data,
        onSuccess: () => [cle, ...invalider].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] })),
      });
    },
    useSupprimer: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: async (id: number) => apiClient.delete(`${url}${id}/`),
        onSuccess: () => [cle, ...invalider].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] })),
      });
    },
  };
}

const structures = crud<StructureOrganisation>("/structures-organisation/", "structures-organisation");
export const useStructures = structures.useListe;
export const useEnregistrerStructure = structures.useEnregistrer;
export const useSupprimerStructure = structures.useSupprimer;

const categories = crud<CategoriePartiePrenante>("/categories-parties-prenantes/", "categories-parties-prenantes");
export const useCategoriesPartiesPrenantes = categories.useListe;
export const useEnregistrerCategoriePartiePrenante = categories.useEnregistrer;
export const useSupprimerCategoriePartiePrenante = categories.useSupprimer;

const partiesPrenantes = crud<PartiePrenante>("/parties-prenantes/", "parties-prenantes");
export const usePartiesPrenantes = partiesPrenantes.useListe;
export const useEnregistrerPartiePrenante = partiesPrenantes.useEnregistrer;
export const useSupprimerPartiePrenante = partiesPrenantes.useSupprimer;

/** Tous les partenaires (la liste de l'API est paginée). */
export function useTousPartenaires() {
  return useQuery({
    queryKey: ["partenaires", "tous"],
    queryFn: async () =>
      (await apiClient.get<Paginated<Partenaire>>("/partenaires/", { params: { page_size: 1000 } })).data.results,
  });
}

export function useEnregistrerPartenaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<Partenaire> & { id?: number }) =>
      id
        ? (await apiClient.patch<Partenaire>(`/partenaires/${id}/`, payload)).data
        : (await apiClient.post<Partenaire>("/partenaires/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["partenaires"] }),
  });
}

export function useSupprimerPartenaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/partenaires/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["partenaires"] }),
  });
}

export function usePartenairesProjet(projetId: number) {
  return useQuery({
    queryKey: ["partenaires-projet", projetId],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<PartenaireProjet>>("/partenaires-projet/", {
          params: { projet: projetId, page_size: 1000 },
        })
      ).data.results,
  });
}

export function useEnregistrerPartenaireProjet(projetId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<PartenaireProjet> & { id?: number }) =>
      id
        ? (await apiClient.patch<PartenaireProjet>(`/partenaires-projet/${id}/`, payload)).data
        : (await apiClient.post<PartenaireProjet>("/partenaires-projet/", { ...payload, projet: projetId })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["partenaires-projet", projetId] });
      queryClient.invalidateQueries({ queryKey: ["projets", projetId] });
    },
  });
}

export function useSupprimerPartenaireProjet(projetId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/partenaires-projet/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["partenaires-projet", projetId] });
      queryClient.invalidateQueries({ queryKey: ["projets", projetId] });
    },
  });
}

export interface AffectationsStructure {
  projets: number[];
  utilisateurs: number[];
  choix_projets?: { value: string; label: string }[];
  choix_utilisateurs?: { value: string; label: string }[];
}

/** Projets et utilisateurs d'une structure, avec la liste complète des choix possibles. */
export function useAffectationsStructure(structureId: number | null) {
  return useQuery({
    queryKey: ["structures-organisation", structureId, "affectations"],
    queryFn: async () =>
      (await apiClient.get<AffectationsStructure>(`/structures-organisation/${structureId}/affectations/`)).data,
    enabled: structureId !== null,
  });
}

export function useEnregistrerAffectationsStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: { id: number; projets: number[]; utilisateurs: number[] }) =>
      (await apiClient.post<AffectationsStructure>(`/structures-organisation/${id}/affectations/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["structures-organisation"] });
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["utilisateurs"] });
    },
  });
}
