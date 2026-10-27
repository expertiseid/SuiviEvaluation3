import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  Activite,
  Equipe,
  ImportProjetResultat,
  JalonLivrable,
  NiveauActivite,
  Paginated,
  ParametresCalcul,
  Projet,
  ProjetInput,
  TauxManuel,
} from "../types";

export async function telechargerModeleImportProjet() {
  const response = await apiClient.get("/projets/modele-import/", { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "modele_import_projet.xlsx");
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function useImporterProjet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<ImportProjetResultat>("/projets/importer/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export function useProjets() {
  return useQuery({
    queryKey: ["projets"],
    queryFn: async () => (await apiClient.get<Paginated<Projet>>("/projets/")).data.results,
  });
}

export function useActivitesPourProjet(projetId: number | null) {
  return useQuery({
    queryKey: ["activites", "pour-projet", projetId],
    queryFn: async () =>
      (await apiClient.get<{ id: number; libelle: string }[]>("/activites/pour-projet/", { params: { projet: projetId } }))
        .data,
    enabled: !!projetId,
  });
}

export function useProjet(id: number | undefined) {
  return useQuery({
    queryKey: ["projets", id],
    queryFn: async () => (await apiClient.get<Projet>(`/projets/${id}/`)).data,
    enabled: !!id,
  });
}

export function useCreateProjet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<ProjetInput>) =>
      (await apiClient.post<Projet>("/projets/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export function useUpdateProjet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<ProjetInput> }) =>
      (await apiClient.patch<Projet>(`/projets/${id}/`, payload)).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["projets", variables.id] });
    },
  });
}

export function useDeleteProjet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/projets/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export function useEquipes() {
  return useQuery({
    queryKey: ["equipes"],
    queryFn: async () => (await apiClient.get<Paginated<Equipe>>("/equipes/", { params: { page_size: 200 } })).data.results,
  });
}

export function useCreateEquipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      nom: string;
      membres?: number[];
      date_debut_contrat?: string | null;
      date_fin_contrat?: string | null;
    }) => (await apiClient.post<Equipe>("/equipes/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["equipes"] }),
  });
}

export function useUpdateEquipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: number;
      payload: { nom?: string; membres?: number[]; date_debut_contrat?: string | null; date_fin_contrat?: string | null };
    }) => (await apiClient.patch<Equipe>(`/equipes/${id}/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipes"] });
      queryClient.invalidateQueries({ queryKey: ["intervenants"] });
    },
  });
}

export function useDeleteEquipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/equipes/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipes"] });
      queryClient.invalidateQueries({ queryKey: ["projets"] });
    },
  });
}

export function useCreateActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      /** Projet de l'élément ; facultatif quand `activite_parent` est donné (repris du parent). */
      projet?: number;
      activite_parent?: number | null;
      libelle: string;
      description?: string;
      budget_alloue?: number;
      date_debut?: string;
      date_fin?: string;
      responsable?: number;
    }) => (await apiClient.post("/activites/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export function useNiveauxActivite(projetId?: number) {
  return useQuery({
    queryKey: ["niveaux-activite", projetId],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<NiveauActivite>>("/niveaux-activite/", {
          params: { projet: projetId, page_size: 1000 },
        })
      )
        .data.results,
    enabled: !!projetId,
  });
}

export function useCreateNiveauActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { projet: number; profondeur: number; nom_niveau: string }) =>
      (await apiClient.post<NiveauActivite>("/niveaux-activite/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["niveaux-activite"] }),
  });
}

export function useUpdateNiveauActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: { nom_niveau: string } }) =>
      (await apiClient.patch<NiveauActivite>(`/niveaux-activite/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["niveaux-activite"] }),
  });
}

export function useDeleteNiveauActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/niveaux-activite/${id}/`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["niveaux-activite"] }),
  });
}

export function useUpdateActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      (await apiClient.patch(`/activites/${id}/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projets"] });
      queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["activite"] });
    },
  });
}

export function useDeleteActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/activites/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

/** Copie un élément avec tout ce qui est en dessous, sans les réalisations. */
export function useDupliquerActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await apiClient.post<Activite>(`/activites/${id}/dupliquer/`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export async function telechargerExportProjet(id: number, format: "xlsform") {
  const response = await apiClient.get(`/projets/${id}/export/${format}/`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${format}_projet_${id}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function useCreateSousActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      activite: number;
      libelle: string;
      date_debut?: string;
      date_fin?: string;
      statut?: string;
    }) => (await apiClient.post("/sous-activites/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export function useDeleteSousActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/sous-activites/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projets"] }),
  });
}

/**
 * Donne un nom au niveau `profondeur` de la planification d'un projet : le
 * crée s'il n'existe pas encore, le renomme sinon.
 */
export function useNommerNiveau(projetId: number) {
  const { data: niveaux } = useNiveauxActivite(projetId);
  const creer = useCreateNiveauActivite();
  const renommer = useUpdateNiveauActivite();
  return async (profondeur: number, nom: string) => {
    const existant = niveaux?.find((n) => n.profondeur === profondeur);
    if (existant) await renommer.mutateAsync({ id: existant.id, payload: { nom_niveau: nom } });
    else await creer.mutateAsync({ projet: projetId, profondeur, nom_niveau: nom });
  };
}

/** Après une saisie qui change un taux : projets, page Suivi et fiche d'activité à recharger. */
function invaliderTaux(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["projets"] });
  queryClient.invalidateQueries({ queryKey: ["suivi-dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["activite"] });
}

/** Un élément de la planification, avec son taux, sa méthode, ses tâches, jalons et livrables. */
export function useActivite(id: number | null) {
  return useQuery({
    queryKey: ["activite", id],
    queryFn: async () => (await apiClient.get<Activite>(`/activites/${id}/`)).data,
    enabled: !!id,
  });
}

export function useUpdateSousActivite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      (await apiClient.patch(`/sous-activites/${id}/`, payload)).data,
    onSuccess: () => invaliderTaux(queryClient),
  });
}

export function useCreateJalonLivrable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<JalonLivrable> & { activite: number; type: string; libelle: string }) =>
      (await apiClient.post<JalonLivrable>("/jalons-livrables/", payload)).data,
    onSuccess: () => invaliderTaux(queryClient),
  });
}

export function useUpdateJalonLivrable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<JalonLivrable> }) =>
      (await apiClient.patch<JalonLivrable>(`/jalons-livrables/${id}/`, payload)).data,
    onSuccess: () => invaliderTaux(queryClient),
  });
}

export function useDeleteJalonLivrable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/jalons-livrables/${id}/`),
    onSuccess: () => invaliderTaux(queryClient),
  });
}

export function useTauxManuels(activiteId: number | null) {
  return useQuery({
    queryKey: ["taux-manuels", activiteId],
    queryFn: async () =>
      (
        await apiClient.get<Paginated<TauxManuel>>("/taux-manuels/", {
          params: { activite: activiteId, page_size: 1000 },
        })
      ).data.results,
    enabled: !!activiteId,
  });
}

export function useCreateTauxManuel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { activite: number; taux: number; date: string; commentaire?: string }) =>
      (await apiClient.post<TauxManuel>("/taux-manuels/", payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["taux-manuels"] });
      invaliderTaux(queryClient);
    },
  });
}

export function useParametresCalcul() {
  return useQuery({
    queryKey: ["parametres-calcul"],
    queryFn: async () => (await apiClient.get<ParametresCalcul>("/parametres-calcul/")).data,
  });
}

export function useUpdateParametresCalcul() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<ParametresCalcul>) =>
      (await apiClient.patch<ParametresCalcul>("/parametres-calcul/", payload)).data,
    onSuccess: (data) => {
      queryClient.setQueryData(["parametres-calcul"], data);
      invaliderTaux(queryClient);
    },
  });
}
