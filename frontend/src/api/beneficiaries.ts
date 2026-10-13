import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  Beneficiaire,
  ImportBeneficiairesResultat,
  Paginated,
  ParticipationProjet,
  SignalementDoublon,
} from "../types";

const TAILLE_PAGE_BENEFICIAIRES = 25;

// `filtres` : restreint la liste à un projet, ou aux bénéficiaires sans aucun
// projet (affichage groupé projet par projet de l'écran Bénéficiaires).
export function useBeneficiaires(
  search?: string,
  page = 1,
  filtres?: { projet?: number; sans_projet?: boolean },
) {
  return useQuery({
    queryKey: ["beneficiaires", search, page, filtres],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<Beneficiaire>>("/beneficiaires/", {
          params: {
            search,
            page,
            page_size: TAILLE_PAGE_BENEFICIAIRES,
            projet: filtres?.projet,
            sans_projet: filtres?.sans_projet ? 1 : undefined,
          },
        })
      ).data,
  });
}

export function useBeneficiaire(id: number | undefined) {
  return useQuery({
    queryKey: ["beneficiaires", id],
    queryFn: async () => (await apiClient.get<Beneficiaire>(`/beneficiaires/${id}/`)).data,
    enabled: !!id,
  });
}

export function useCreateBeneficiaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Beneficiaire>) =>
      (await apiClient.post<Beneficiaire>("/beneficiaires/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["beneficiaires"] }),
  });
}

export function useUpdateBeneficiaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<Beneficiaire> }) =>
      (await apiClient.patch<Beneficiaire>(`/beneficiaires/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["beneficiaires"] }),
  });
}

export function useDeleteBeneficiaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/beneficiaires/${id}/`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["beneficiaires"] }),
  });
}

export function useParticipations(params: { projet?: number; activite?: number; sous_activite?: number }) {
  return useQuery({
    queryKey: ["participations-projet", params],
    queryFn: async () =>
      (await apiClient.get<Paginated<ParticipationProjet>>("/participations-projet/", { params })).data
        .results,
    enabled: !!(params.projet || params.activite || params.sous_activite),
  });
}

export function useCreateParticipation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      beneficiaire: number;
      projet: number;
      activite?: number;
      sous_activite?: number;
      date_inscription: string;
      role_dans_projet?: string;
    }) => (await apiClient.post<ParticipationProjet>("/participations-projet/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["participations-projet"] }),
  });
}

export function useDeleteParticipation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/participations-projet/${id}/`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["participations-projet"] }),
  });
}

export async function telechargerModeleImportBeneficiaires() {
  const response = await apiClient.get("/beneficiaires/modele-import/", { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "modele_import_beneficiaires.xlsx");
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/**
 * Export des bénéficiaires en Excel ou PDF : des projets choisis (codes
 * passés pour nommer le fichier), ou de tous si la liste est vide.
 */
export async function telechargerExportBeneficiaires(
  projets: { id: number; code: string }[],
  fichier: "excel" | "pdf",
) {
  const response = await apiClient.get("/beneficiaires/exporter/", {
    params: { fichier, ...(projets.length > 0 ? { projets: projets.map((p) => p.id).join(",") } : {}) },
    responseType: "blob",
  });
  const nom = projets.length > 0 ? `beneficiaires_${projets.map((p) => p.code).join("_")}` : "beneficiaires_tous_projets";
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${nom}.${fichier === "pdf" ? "pdf" : "xlsx"}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function useImporterBeneficiaires() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<ImportBeneficiairesResultat>("/beneficiaires/importer/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["beneficiaires"] });
      queryClient.invalidateQueries({ queryKey: ["participations-projet"] });
    },
  });
}

export function useVerifierDoublons() {
  return useMutation({
    mutationFn: async (beneficiaireId: number) =>
      (await apiClient.post<SignalementDoublon[]>(`/beneficiaires/${beneficiaireId}/verifier-doublons/`))
        .data,
  });
}

export function useSignalementsDoublons(statut?: string) {
  return useQuery({
    queryKey: ["signalements-doublons", statut],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<SignalementDoublon>>("/signalements-doublons/", {
          params: statut ? { statut } : undefined,
        })
      ).data.results,
  });
}

export function useTraiterSignalement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, statut }: { id: number; statut: "ECARTE" | "FUSIONNE" }) =>
      (await apiClient.patch<SignalementDoublon>(`/signalements-doublons/${id}/`, { statut })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["signalements-doublons"] }),
  });
}
