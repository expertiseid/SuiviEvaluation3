import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  CadreStrategique,
  ElementStrategique,
  ImportStructurationResultat,
  Paginated,
  RecapAxesCadreStrategique,
  RecapCadreStrategique,
  TypeNiveau,
} from "../types";

export function useCadresStrategiques() {
  return useQuery({
    queryKey: ["cadres-strategiques"],
    queryFn: async () =>
      (await apiClient.get<Paginated<CadreStrategique>>("/cadres-strategiques/", { params: { page_size: 200 } }))
        .data.results,
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

export function useElementsStrategiques(params?: Record<string, string | number>) {
  return useQuery({
    queryKey: ["elements-strategiques", params],
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
  link.setAttribute("download", `plan_strategique_${nomCadre.replace(/[^\w-]+/g, "_")}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
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
    },
  });
}
