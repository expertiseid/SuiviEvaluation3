import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  Beneficiaire,
  ImportBeneficiairesResultat,
  Paginated,
  ParticipationProjet,
  SignalementDoublon,
  VariableBeneficiaire,
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

/** Modèle d'import ; ses colonnes de localisation suivent les niveaux administratifs du pays choisi. */
export async function telechargerModeleImportBeneficiaires(pays = "BF", projet?: number) {
  const response = await apiClient.get("/beneficiaires/modele-import/", {
    params: { pays, ...(projet ? { projet } : {}) },
    responseType: "blob",
  });
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

/** Repasse les signalements en attente avec les règles actuelles (retire les faux positifs). */
export function useReverifierDoublons() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      (await apiClient.post<{ retires: number; maintenus: number }>("/signalements-doublons/reverifier/")).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["signalements-doublons"] }),
  });
}

/** QR code (SVG) de la fiche d'un bénéficiaire : il contient le lien vers sa fiche sur cette plateforme. */
export function useQrBeneficiaire(id: number) {
  return useQuery({
    queryKey: ["beneficiaires", id, "qr"],
    queryFn: async () =>
      (
        await apiClient.get<string>(`/beneficiaires/${id}/qr/`, {
          params: { origine: window.location.origin },
          responseType: "text",
        })
      ).data,
  });
}

/** Cartes bénéficiaires à imprimer (PDF) : bénéficiaires choisis, ou tous les inscrits d'un projet. */
export async function telechargerCartesBeneficiaires(choix: { ids?: number[]; projet?: number }, nomFichier: string) {
  const response = await apiClient.get("/beneficiaires/cartes/", {
    params: {
      origine: window.location.origin,
      ...(choix.ids ? { ids: choix.ids.join(",") } : {}),
      ...(choix.projet ? { projet: choix.projet } : {}),
    },
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${nomFichier}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/** Identifiant (lien du QR code) → id du bénéficiaire. */
export async function rechercherBeneficiaireParIdentifiant(identifiant: string) {
  return (await apiClient.get<{ id: number }>(`/beneficiaires/identifiant/${encodeURIComponent(identifiant)}/`)).data.id;
}

export function useVariablesBeneficiaires() {
  return useQuery({
    queryKey: ["variables-beneficiaires"],
    queryFn: async () => (await apiClient.get<VariableBeneficiaire[]>("/variables-beneficiaires/")).data,
  });
}

export function useChoixProjetsVariables(actif: boolean) {
  return useQuery({
    queryKey: ["variables-beneficiaires", "choix-projets"],
    queryFn: async () =>
      (await apiClient.get<{ value: string; label: string }[]>("/variables-beneficiaires/choix-projets/")).data,
    enabled: actif,
  });
}

export function useEnregistrerVariableBeneficiaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<VariableBeneficiaire> & { id?: number }) =>
      id
        ? (await apiClient.patch<VariableBeneficiaire>(`/variables-beneficiaires/${id}/`, payload)).data
        : (await apiClient.post<VariableBeneficiaire>("/variables-beneficiaires/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["variables-beneficiaires"] }),
  });
}

export function useSupprimerVariableBeneficiaire() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/variables-beneficiaires/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["variables-beneficiaires"] });
      queryClient.invalidateQueries({ queryKey: ["beneficiaires"] });
    },
  });
}

export interface CarteBeneficiaires {
  pays: string;
  total: number;
  /** Bénéficiaires avec position GPS. */
  points: { id: number; nom: string; identifiant: string; sexe: string; lat: number; lng: number }[];
  /** Les autres, regroupés au centre de leur localité (ou de la zone parente placée la plus proche). */
  zones: { zone: number; nom: string; lat: number; lng: number; nombre: number; femmes: number; hommes: number }[];
  non_localises: number;
}

export function useCarteBeneficiaires(projet: number | null) {
  return useQuery({
    queryKey: ["beneficiaires", "carte", projet],
    queryFn: async () =>
      (await apiClient.get<CarteBeneficiaires>("/beneficiaires/carte/", { params: projet ? { projet } : {} })).data,
  });
}
