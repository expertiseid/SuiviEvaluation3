import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { FiltresDashboard, NiveauAdministratif, Paginated, Zone } from "../types";
import { parametresRequete } from "../utils/filtresTableauDeBord";

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
        await apiClient.get<{ pays: string; niveau: number; nom_niveau: string; annee: string; source: string; geojson: GeoJSON.FeatureCollection }>(
          "/limites-administratives/",
          { params: { pays, niveau } },
        )
      ).data,
    enabled: !!pays,
    staleTime: Infinity,
    retry: false,
  });
}

/** Couche d'habillage importée (ex. routes) ; absente tant qu'elle n'a pas été importée. */
export function useCoucheCarte(pays: string | undefined, cle: string, active: boolean) {
  return useQuery({
    queryKey: ["couches-carte", pays, cle],
    queryFn: async () =>
      (await apiClient.get<{ cle: string; libelle: string; source: string; geojson: GeoJSON.FeatureCollection }>("/couches-carte/", { params: { pays, cle } })).data,
    enabled: !!pays && active,
    staleTime: Infinity,
    retry: false,
  });
}

export interface LocaliteCarte {
  nom: string;
  statut: "VILLE" | "VILLAGE_ADMIN" | "VILLAGE";
  commune: string;
  lat: number;
  lng: number;
}

/** Villes et villages de la partie visible de la carte (bbox : sud,ouest,nord,est). */
export function useLocalites(pays: string | undefined, bbox: string | null) {
  return useQuery({
    queryKey: ["localites", pays, bbox],
    queryFn: async () => (await apiClient.get<{ total: number; localites: LocaliteCarte[] }>("/localites/", { params: { pays, bbox } })).data,
    enabled: !!pays && !!bbox,
    staleTime: Infinity,
    placeholderData: (precedent) => precedent,
    retry: false,
  });
}

export interface CoucheImportee {
  id: number;
  nom: string;
  couleur: string;
  geometrie: "POINT" | "LIGNE" | "POLYGONE";
  fichier_source: string;
  projection_source: string;
  colonnes: string[];
  champ_etiquette: string;
  nombre_objets: number;
  emprise: [number, number, number, number];
  cree_par_nom: string;
  created_at: string;
}

export function useCouchesImportees() {
  return useQuery({
    queryKey: ["couches-importees"],
    queryFn: async () => (await apiClient.get<Paginated<CoucheImportee>>("/couches-importees/", { params: { page_size: 200 } })).data.results,
  });
}

export function useGeojsonCouche(id: number, active: boolean) {
  return useQuery({
    queryKey: ["couches-importees", id, "geojson"],
    queryFn: async () => (await apiClient.get<GeoJSON.FeatureCollection>(`/couches-importees/${id}/geojson/`)).data,
    enabled: active,
    staleTime: Infinity,
  });
}

/** Import d'un fichier SIG (.zip de shapefile, .gpkg, .geojson, .kml). */
export function useImporterCouche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ fichier, nom, couleur }: { fichier: File; nom: string; couleur: string }) => {
      const donnees = new FormData();
      donnees.append("fichier", fichier);
      donnees.append("nom", nom);
      donnees.append("couleur", couleur);
      return (await apiClient.post<CoucheImportee>("/couches-importees/", donnees, { timeout: 300000 })).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["couches-importees"] }),
  });
}

export function useModifierCouche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<CoucheImportee> & { id: number }) =>
      (await apiClient.patch<CoucheImportee>(`/couches-importees/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["couches-importees"] }),
  });
}

export function useSupprimerCouche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/couches-importees/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["couches-importees"] }),
  });
}

/** Code d'un indicateur par zone (catalogue : utils/carteParZone.ts). */
export type IndicateurZone = string;

export interface SyntheseZone {
  zone: number;
  nom: string;
  nom_contour: string | null;
  lat: number | null;
  lng: number | null;
  projets: number;
  beneficiaires: number;
  femmes: number;
  hommes: number;
  budget: number;
  taux_physique: number | null;
  taux_financier: number | null;
  /** Tous les indicateurs du catalogue pour cette zone. */
  valeurs: Record<string, number | null>;
  liste_projets: {
    id: number;
    code: string;
    nom: string;
    statut: string;
    budget: number;
    taux_physique: number | null;
    taux_financier: number | null;
    beneficiaires: number;
  }[];
}

/** Synthèse par zone (régions, provinces…) : projets présents, bénéficiaires, budget, taux. */
export function useSyntheseCarte(pays: string | undefined, niveau: number, projets: number[], zones: number[], filtres: FiltresDashboard, active: boolean) {
  return useQuery({
    queryKey: ["carte-synthese", pays, niveau, projets, zones, filtres],
    queryFn: async () =>
      (
        await apiClient.get<{ niveau: { ordre: number; nom: string } | null; zones: SyntheseZone[]; indicateurs: Record<IndicateurZone, string> }>(
          "/carte/synthese/",
          { params: { pays, niveau, projet: projets.join(",") || undefined, zone: zones.join(",") || undefined, ...parametresRequete(filtres) } },
        )
      ).data,
    enabled: !!pays && active,
    placeholderData: (precedent) => precedent,
  });
}

/** Zones administratives d'un pays installées automatiquement (apps/geo/services/installation.py). */
export interface PaysZones {
  pays: string;
  zones: number;
  statut: "EN_COURS" | "TERMINE" | "ECHEC";
  message: string;
}

/** Pays de l'organisation et état de leurs zones ; se rafraîchit tant qu'une installation est en cours. */
export function usePaysZones() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["pays-zones"],
    queryFn: async () => {
      const donnees = (await apiClient.get<PaysZones[]>("/pays-zones/")).data;
      // Installation terminée depuis la dernière lecture : zones et niveaux à recharger.
      const avant = queryClient.getQueryData<PaysZones[]>(["pays-zones"]) ?? [];
      if (donnees.some((p) => p.statut !== "EN_COURS" && avant.find((a) => a.pays === p.pays)?.statut === "EN_COURS")) {
        void queryClient.invalidateQueries({ queryKey: ["zones"] });
        void queryClient.invalidateQueries({ queryKey: ["niveaux-administratifs"] });
      }
      return donnees;
    },
    refetchInterval: (requete) => (requete.state.data?.some((p) => p.statut === "EN_COURS") ? 3000 : false),
  });
}

/** Installe (en arrière-plan) les zones des pays qui n'en ont pas encore. */
export function useInstallerPays() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (pays: string[]) => (await apiClient.post<PaysZones[]>("/pays-zones/", { pays })).data,
    onSuccess: (donnees) => queryClient.setQueryData(["pays-zones"], donnees),
  });
}
