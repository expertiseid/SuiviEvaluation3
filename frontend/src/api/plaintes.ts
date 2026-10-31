/**
 * Mécanisme de gestion des plaintes et retours — lot 1 : paramétrage (mécanisme, types,
 * priorités, catégories, circuits et étapes, modèles, canevas Excel). API : /api/v1/plaintes/.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";

export interface MecanismePlaintes {
  id: number;
  nom: string;
  actif: boolean;
  modele: string;
  anonymat_autorise: boolean;
  langues: string[];
  texte_information: string;
  prefixe_numero: string;
  jours_ouvres: boolean;
  conservation_ordinaire_mois: number | null;
  conservation_sensible_mois: number | null;
  projets: number[];
  /** Ce qui manque pour activer le mécanisme (vide = activable). */
  controles: string[];
}

export interface TypeRetour {
  id: number;
  nom: string;
  description: string;
  ordre: number;
  actif: boolean;
}

export interface PrioritePlainte {
  id: number;
  nom: string;
  ordre: number;
  urgente: boolean;
  delai_jours: number | null;
  actif: boolean;
}

export interface EtapeCircuit {
  id: number;
  circuit: number;
  nom: string;
  ordre: number;
  delai_jours: number | null;
  role: number | null;
  role_libelle: string | null;
  responsable: number | null;
  responsable_nom: string | null;
  est_cloture: boolean;
}

export interface CircuitPlainte {
  id: number;
  nom: string;
  description: string;
  sensible: boolean;
  par_defaut: boolean;
  actif: boolean;
  etapes: EtapeCircuit[];
  /** Ce qui empêche d'utiliser le circuit (vide = valide). */
  erreurs: string[];
  nb_categories: number;
}

export interface CategoriePlainte {
  id: number;
  nom: string;
  description: string;
  parent: number | null;
  parent_nom: string | null;
  sensible: boolean;
  sensible_effective: boolean;
  /** Protège les personnes : reste sensible et active, ne se supprime pas. */
  verrouillee: boolean;
  circuit: number | null;
  circuit_nom: string | null;
  delai_jours: number | null;
  ordre: number;
  actif: boolean;
}

export interface ModeleMecanisme {
  code: string;
  libelle: string;
  description: string;
}

export interface RapportImportParametrage {
  crees: number;
  mis_a_jour: number;
  erreurs: { ligne: number; message: string }[];
}

const CLE = "plaintes";

/** Tout changement du paramétrage peut changer les contrôles d'activation : on recharge tout. */
function useRafraichir() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: [CLE] });
}

export function useMecanisme() {
  return useQuery({
    queryKey: [CLE, "mecanisme"],
    queryFn: async () => (await apiClient.get<MecanismePlaintes>("/plaintes/mecanisme/")).data,
  });
}

export function useEnregistrerMecanisme() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (payload: Partial<MecanismePlaintes>) =>
      (await apiClient.patch<MecanismePlaintes>("/plaintes/mecanisme/", payload)).data,
    onSuccess: rafraichir,
  });
}

export function useActivationMecanisme() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (activer: boolean) =>
      (await apiClient.post<MecanismePlaintes>(`/plaintes/mecanisme/${activer ? "activer" : "desactiver"}/`)).data,
    onSuccess: rafraichir,
  });
}

export function useModelesMecanisme() {
  return useQuery({
    queryKey: [CLE, "modeles"],
    queryFn: async () => (await apiClient.get<ModeleMecanisme[]>("/plaintes/modeles/")).data,
  });
}

export function useAppliquerModele() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (modele: string) =>
      (await apiClient.post<{ ajouts: Record<string, number> }>("/plaintes/modeles/", { modele })).data,
    onSuccess: rafraichir,
  });
}

/** Liste et enregistrement d'un élément du paramétrage (types, priorités, catégories, circuits, étapes). */
function useListe<T>(ressource: string) {
  return useQuery({
    queryKey: [CLE, ressource],
    queryFn: async () => (await apiClient.get<T[]>(`/plaintes/${ressource}/`)).data,
  });
}

function useEnregistrer<T extends { id: number }>(ressource: string) {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<T> & { id?: number }) =>
      id
        ? (await apiClient.patch<T>(`/plaintes/${ressource}/${id}/`, payload)).data
        : (await apiClient.post<T>(`/plaintes/${ressource}/`, payload)).data,
    onSuccess: rafraichir,
  });
}

function useSupprimer(ressource: string) {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/plaintes/${ressource}/${id}/`),
    onSuccess: rafraichir,
  });
}

export const useTypesRetour = () => useListe<TypeRetour>("types");
export const useEnregistrerTypeRetour = () => useEnregistrer<TypeRetour>("types");
export const useSupprimerTypeRetour = () => useSupprimer("types");
export const usePrioritesPlainte = () => useListe<PrioritePlainte>("priorites");
export const useEnregistrerPriorite = () => useEnregistrer<PrioritePlainte>("priorites");
export const useSupprimerPriorite = () => useSupprimer("priorites");
export const useCategoriesPlainte = () => useListe<CategoriePlainte>("categories");
export const useEnregistrerCategorie = () => useEnregistrer<CategoriePlainte>("categories");
export const useSupprimerCategorie = () => useSupprimer("categories");
export const useCircuitsPlainte = () => useListe<CircuitPlainte>("circuits");
export const useEnregistrerCircuit = () => useEnregistrer<CircuitPlainte>("circuits");
export const useSupprimerCircuit = () => useSupprimer("circuits");
export const useEnregistrerEtape = () => useEnregistrer<EtapeCircuit>("etapes");
export const useSupprimerEtape = () => useSupprimer("etapes");

export async function telechargerCanevasParametrage() {
  const response = await apiClient.get("/plaintes/canevas/", { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", "parametrage_plaintes.xlsx");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}

export function useImporterCanevasParametrage() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (fichier: File) => {
      const donnees = new FormData();
      donnees.append("fichier", fichier);
      return (
        await apiClient.post<RapportImportParametrage>("/plaintes/canevas/importer/", donnees, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data;
    },
    onSuccess: rafraichir,
  });
}
