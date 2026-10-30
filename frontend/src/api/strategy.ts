import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  CadreStrategique,
  ElementStrategique,
  ImportChaineResultat,
  ImportStructurationResultat,
  Paginated,
  RecapAxesCadreStrategique,
  RecapCadreStrategique,
  TypeDocument,
  TypeNiveau,
} from "../types";

/** Documents stratégiques : tous, ou ceux d'un maillon de la chaîne (`typeDocument`). */
export function useCadresStrategiques(typeDocument?: number) {
  return useQuery({
    queryKey: ["cadres-strategiques", "liste", typeDocument ?? "tous"],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<CadreStrategique>>("/cadres-strategiques/", {
          params: { page_size: 1000, type_document: typeDocument },
        })
      ).data.results,
  });
}

// ------------------------------------------------------------ Chaîne des documents (maillons)

export function useTypesDocuments() {
  return useQuery({
    queryKey: ["types-documents"],
    queryFn: async () => (await apiClient.get<TypeDocument[]>("/types-documents/")).data,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEnregistrerTypeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<TypeDocument>) =>
      id
        ? (await apiClient.patch<TypeDocument>(`/types-documents/${id}/`, payload)).data
        : (await apiClient.post<TypeDocument>("/types-documents/", payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["types-documents"] });
      queryClient.invalidateQueries({ queryKey: ["cadres-strategiques"] });
    },
  });
}

export function useSupprimerTypeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/types-documents/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["types-documents"] }),
  });
}

/** Modèle (`modele`) ou export de la chaîne actuelle (`export`) en Excel. */
export async function telechargerChaine(quoi: "modele" | "export") {
  const response = await apiClient.get(`/cadres-strategiques/chaine/${quoi}/`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", quoi === "modele" ? "modele_chaine_documents.xlsx" : "chaine_documents.xlsx");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
}

export function useImporterChaine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<ImportChaineResultat>("/cadres-strategiques/chaine/importer/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => {
      for (const cle of ["types-documents", "cadres-strategiques", "types-niveaux", "elements-strategiques"]) {
        queryClient.invalidateQueries({ queryKey: [cle] });
      }
    },
  });
}

export function useCadreStrategique(id: number | undefined) {
  return useQuery({
    queryKey: ["cadres-strategiques", id],
    queryFn: async () => (await apiClient.get<CadreStrategique>(`/cadres-strategiques/${id}/`)).data,
    enabled: !!id,
  });
}

export function useCreateCadreStrategique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<CadreStrategique>) =>
      (await apiClient.post<CadreStrategique>("/cadres-strategiques/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cadres-strategiques"] }),
  });
}

export function useUpdateCadreStrategique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<CadreStrategique> }) =>
      (await apiClient.patch<CadreStrategique>(`/cadres-strategiques/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cadres-strategiques"] }),
  });
}

export function useDeleteCadreStrategique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/cadres-strategiques/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cadres-strategiques"] }),
  });
}

export function useTypesNiveaux(cadreStrategiqueId: number | null | undefined) {
  return useQuery({
    queryKey: ["types-niveaux", cadreStrategiqueId],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<TypeNiveau>>("/types-niveaux/", {
          params: { page_size: 500, cadre_strategique: cadreStrategiqueId },
        })
      ).data.results,
    enabled: !!cadreStrategiqueId,
  });
}

export function useCreateTypeNiveau() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<TypeNiveau>) =>
      (await apiClient.post<TypeNiveau>("/types-niveaux/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["types-niveaux"] }),
  });
}

/**
 * Supprime un niveau s'il n'a aucun élément : niveau « Sous-… » créé par « Ajouter dessous »
 * puis abandonné (formulaire fermé sans enregistrer).
 */
export function useSupprimerNiveauSiVide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const elements = (await apiClient.get<Paginated<ElementStrategique>>("/elements-strategiques/", { params: { type_niveau: id } })).data;
      if (elements.count === 0) await apiClient.delete(`/types-niveaux/${id}/`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["types-niveaux"] }),
  });
}

export function useUpdateTypeNiveau() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<TypeNiveau> }) =>
      (await apiClient.patch<TypeNiveau>(`/types-niveaux/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["types-niveaux"] }),
  });
}

export function useDeleteTypeNiveau() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/types-niveaux/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["types-niveaux"] }),
  });
}

export function useElementsStrategiques(params?: Record<string, string | number>, actif = true) {
  return useQuery({
    queryKey: ["elements-strategiques", params],
    enabled: actif,
    queryFn: async () =>
      (
        await apiClient.get<Paginated<ElementStrategique>>("/elements-strategiques/", {
          params: { page_size: 1000, ...params },
        })
      ).data.results,
  });
}

export function useCreateElementStrategique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<ElementStrategique>) =>
      (await apiClient.post<ElementStrategique>("/elements-strategiques/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["elements-strategiques"] }),
  });
}

export function useUpdateElementStrategique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<ElementStrategique> }) =>
      (await apiClient.patch<ElementStrategique>(`/elements-strategiques/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["elements-strategiques"] }),
  });
}

export function useDeleteElementStrategique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/elements-strategiques/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["elements-strategiques"] }),
  });
}

export function useRecapCadreStrategique(id: number | undefined) {
  return useQuery({
    queryKey: ["cadres-strategiques", id, "recap"],
    queryFn: async () => (await apiClient.get<RecapCadreStrategique>(`/cadres-strategiques/${id}/recap/`)).data,
    enabled: !!id,
  });
}

export function useRecapAxesCadreStrategique(id: number | undefined) {
  return useQuery({
    queryKey: ["cadres-strategiques", id, "recap-axes"],
    queryFn: async () =>
      (await apiClient.get<RecapAxesCadreStrategique>(`/cadres-strategiques/${id}/recap-axes/`)).data,
    enabled: !!id,
  });
}

export async function telechargerExportStructuration(cadreStrategiqueId: number, nomCadre: string) {
  const response = await apiClient.get(`/cadres-strategiques/${cadreStrategiqueId}/export/`, {
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `canevas_${nomCadre.replace(/[^\w-]+/g, "_")}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/**
 * Arborescence d'un document exportée en Excel ou en PDF : « complet » = le mode Tableau
 * (programmation et année choisies, budgets, taux, activités) ; « simple » = la structure seule.
 */
export async function telechargerTableauDocument(
  cadreStrategiqueId: number,
  nomFichier: string,
  fichier: "xlsx" | "pdf",
  programmation: "trimestres" | "dates",
  annee: number,
  contenu: "complet" | "simple" = "complet",
) {
  const response = await apiClient.get(`/cadres-strategiques/${cadreStrategiqueId}/tableau/`, {
    responseType: "blob",
    params: { fichier, programmation, annee, contenu },
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${contenu === "simple" ? "structure" : "tableau"}_${nomFichier.replace(/[^\w-]+/g, "_")}.${fichier}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function telechargerModeleImportStructuration(cadreStrategiqueId: number) {
  const response = await apiClient.get("/elements-strategiques/modele-import/", {
    responseType: "blob",
    params: { cadre_strategique: cadreStrategiqueId },
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "modele_import_structuration.xlsx");
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function useImporterStructuration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<ImportStructurationResultat>("/elements-strategiques/importer/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["types-niveaux"] });
      queryClient.invalidateQueries({ queryKey: ["elements-strategiques"] });
      // Feuille « Fiche » d'un programme, d'un pilier… : la fiche et les bailleurs changent aussi.
      queryClient.invalidateQueries({ queryKey: ["cadres-strategiques"] });
    },
  });
}
