import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import { cheminApi, usePartage } from "../utils/partage";
import type {
  ImportIndicateursResultat,
  Indicateur,
  Paginated,
  PaliersAlerteResolus,
  PalierAlerteInput,
  ParametresAlerte,
  PorteeAlerte,
  ValeurIndicateur,
} from "../types";

function paramsPortee(portee: PorteeAlerte): Record<string, number> {
  if (portee.indicateurId) return { indicateur: portee.indicateurId };
  if (portee.activiteId) return { activite: portee.activiteId };
  if (portee.projetId) return { projet: portee.projetId };
  return {};
}

export function useParametresAlerte() {
  const partage = usePartage();
  return useQuery({
    queryKey: ["parametres-alerte", partage?.jeton],
    queryFn: async () =>
      (await apiClient.get<ParametresAlerte>(cheminApi(partage, "/parametres-alerte/", "parametres-alerte"))).data,
    staleTime: 5 * 60 * 1000,
  });
}

export function useUpdateParametresAlerte() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<ParametresAlerte>) =>
      (await apiClient.patch<ParametresAlerte>("/parametres-alerte/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parametres-alerte"] }),
  });
}

export function usePaliersAlerte(portee: PorteeAlerte) {
  return useQuery({
    queryKey: ["paliers-alerte", portee.projetId ?? null, portee.indicateurId ?? null, portee.activiteId ?? null],
    queryFn: async () =>
      (await apiClient.get<PaliersAlerteResolus>("/paliers-alerte/", { params: paramsPortee(portee) })).data,
    staleTime: 60 * 1000,
  });
}

export function useEnregistrerPaliersAlerte() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ portee, paliers }: { portee: PorteeAlerte; paliers: PalierAlerteInput[] }) =>
      (await apiClient.put<PaliersAlerteResolus>("/paliers-alerte/", { ...paramsPortee(portee), paliers })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["paliers-alerte"] }),
  });
}

export async function telechargerModeleImportIndicateurs() {
  const response = await apiClient.get("/indicateurs/modele-import/", { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "modele_import_indicateurs.xlsx");
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function useImporterIndicateurs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<ImportIndicateursResultat>("/indicateurs/importer/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["indicateurs"] }),
  });
}

export function useIndicateursPourProjet(projetId: number | null) {
  return useQuery({
    queryKey: ["indicateurs", "pour-projet", projetId],
    queryFn: async () =>
      (await apiClient.get<{ id: number; libelle: string }[]>("/indicateurs/pour-projet/", { params: { projet: projetId } }))
        .data,
    enabled: !!projetId,
  });
}

export function useIndicateurs(params?: Record<string, string | number>) {
  return useQuery({
    queryKey: ["indicateurs", params],
    queryFn: async () =>
      (await apiClient.get<Paginated<Indicateur>>("/indicateurs/", { params })).data.results,
  });
}

export function useIndicateur(id: number | undefined) {
  return useQuery({
    queryKey: ["indicateurs", id],
    queryFn: async () => (await apiClient.get<Indicateur>(`/indicateurs/${id}/`)).data,
    enabled: !!id,
  });
}

export function useCreateIndicateur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Indicateur>) =>
      (await apiClient.post<Indicateur>("/indicateurs/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["indicateurs"] }),
  });
}

export function useUpdateIndicateur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<Indicateur> }) =>
      (await apiClient.patch<Indicateur>(`/indicateurs/${id}/`, payload)).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["indicateurs"] });
      queryClient.invalidateQueries({ queryKey: ["indicateurs", variables.id] });
    },
  });
}

export function useDeleteIndicateur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/indicateurs/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["indicateurs"] }),
  });
}

export function useCreateValeurIndicateur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<ValeurIndicateur>) =>
      (await apiClient.post<ValeurIndicateur>("/valeurs-indicateurs/", payload)).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["indicateurs"] });
      queryClient.invalidateQueries({ queryKey: ["indicateurs", variables.indicateur] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export function useUpdateValeurIndicateur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<ValeurIndicateur> }) =>
      (await apiClient.patch<ValeurIndicateur>(`/valeurs-indicateurs/${id}/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["indicateurs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}

export function useDeleteValeurIndicateur() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/valeurs-indicateurs/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["indicateurs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tranches-planifiees"] });
    },
  });
}
