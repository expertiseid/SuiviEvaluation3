import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Bailleur, Financement, Paginated, Partenaire, RallongeFinancement, StatutParticulier, TypeActiviteBeneficiaire } from "../types";

export function usePartenaires() {
  return useQuery({
    queryKey: ["partenaires"],
    queryFn: async () => (await apiClient.get<Paginated<Partenaire>>("/partenaires/")).data.results,
  });
}

export function useStatutsParticuliers() {
  return useQuery({
    queryKey: ["statuts-particuliers"],
    queryFn: async () =>
      (await apiClient.get<Paginated<StatutParticulier>>("/statuts-particuliers/")).data.results,
  });
}

export function useCreateStatutParticulier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { code: string; libelle: string }) =>
      (await apiClient.post<StatutParticulier>("/statuts-particuliers/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["statuts-particuliers"] }),
  });
}

export function useTypesActiviteBeneficiaire() {
  return useQuery({
    queryKey: ["types-activite-beneficiaire"],
    queryFn: async () =>
      (await apiClient.get<Paginated<TypeActiviteBeneficiaire>>("/types-activite-beneficiaire/")).data.results,
  });
}

export function useCreateTypeActiviteBeneficiaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { code: string; libelle: string }) =>
      (await apiClient.post<TypeActiviteBeneficiaire>("/types-activite-beneficiaire/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["types-activite-beneficiaire"] }),
  });
}

export function useCreatePartenaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Partenaire>) =>
      (await apiClient.post<Partenaire>("/partenaires/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["partenaires"] }),
  });
}

export function useBailleurs() {
  return useQuery({
    queryKey: ["bailleurs"],
    queryFn: async () => (await apiClient.get<Paginated<Bailleur>>("/bailleurs/")).data.results,
  });
}

export function useCreateBailleur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Bailleur>) => (await apiClient.post<Bailleur>("/bailleurs/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bailleurs"] }),
  });
}

export function useFinancements(projetId?: number) {
  return useQuery({
    queryKey: ["financements", projetId],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<Financement>>("/financements/", {
          params: projetId ? { projet: projetId } : undefined,
        })
      ).data.results,
    enabled: !!projetId,
  });
}

/** Rallonge de fonds d'un bailleur (motif obligatoire) ; le coût total du projet est recalculé. */
export function useEnregistrerRallonge(projetId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { financement: number; montant: number; date: string; motif: string }) =>
      (await apiClient.post<RallongeFinancement>("/rallonges-financement/", payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["financements"] });
      queryClient.invalidateQueries({ queryKey: ["projets", projetId] });
    },
  });
}

export function useSupprimerRallonge(projetId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/rallonges-financement/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["financements"] });
      queryClient.invalidateQueries({ queryKey: ["projets", projetId] });
    },
  });
}

export function useCreateFinancement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { projet: number; bailleur: number; montant_finance: number }) =>
      (await apiClient.post<Financement>("/financements/", payload)).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["financements"] });
      // Le coût total du projet (budget_total) est recalculé côté backend à
      // chaque financement ajouté — il faut aussi invalidate le projet
      // lui-même, sinon la carte "Coût total" reste figée sur sa valeur
      // mise en cache tant qu'on ne quitte pas/revient pas sur la page.
      queryClient.invalidateQueries({ queryKey: ["projets", variables.projet] });
    },
  });
}

/** Une ligne « bailleur + montant » saisie dans la fiche projet. */
export interface LigneFinancement {
  nom: string;
  montant: number;
}

/**
 * Aligne les financements d'un projet sur les lignes saisies : bailleur retrouvé par son nom
 * (créé s'il n'existe pas), montant mis à jour, financement ajouté ou retiré. Le serveur recalcule
 * le coût total du projet à chaque changement.
 */
export function useEnregistrerFinancements() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ projetId, lignes, existants }: { projetId: number; lignes: LigneFinancement[]; existants: Financement[] }) => {
      const voulus = new Map<number, number>();
      for (const ligne of lignes) {
        const nom = ligne.nom.trim();
        const trouves = (await apiClient.get<Paginated<Bailleur>>("/bailleurs/", { params: { search: nom } })).data.results;
        const bailleur =
          trouves.find((b) => b.nom.localeCompare(nom, "fr", { sensitivity: "base" }) === 0) ??
          (await apiClient.post<Bailleur>("/bailleurs/", { nom, type: "AUTRE" })).data;
        voulus.set(bailleur.id, ligne.montant);
      }
      for (const f of existants) {
        const montant = voulus.get(f.bailleur);
        if (montant === undefined) await apiClient.delete(`/financements/${f.id}/`);
        else if (Number(f.montant_finance) !== montant) await apiClient.patch(`/financements/${f.id}/`, { montant_finance: montant });
        voulus.delete(f.bailleur);
      }
      for (const [bailleur, montant] of voulus) {
        await apiClient.post("/financements/", { projet: projetId, bailleur, montant_finance: montant });
      }
    },
    onSuccess: (_d, { projetId }) => {
      queryClient.invalidateQueries({ queryKey: ["financements"] });
      queryClient.invalidateQueries({ queryKey: ["bailleurs"] });
      queryClient.invalidateQueries({ queryKey: ["projets", projetId] });
    },
  });
}
