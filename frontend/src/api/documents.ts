import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, avecOrganisation } from "./client";
import type { Dossier, DocumentVersion, GedDocument, Paginated, PieceJustificative } from "../types";

export function usePiecesJustificatives(params: { valeur_indicateur?: number }) {
  return useQuery({
    queryKey: ["pieces-justificatives", params],
    queryFn: async () =>
      (await apiClient.get<Paginated<PieceJustificative>>("/pieces-justificatives/", { params })).data
        .results,
    enabled: !!params.valeur_indicateur,
  });
}

export function useUploadPieceJustificative() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<PieceJustificative>("/pieces-justificatives/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pieces-justificatives"] }),
  });
}

export function useDossiers(projetId?: number) {
  return useQuery({
    queryKey: ["dossiers", projetId ?? "global"],
    // Tous les dossiers du projet, ou de la bibliothèque libre (sans projet), sans pagination.
    queryFn: async () =>
      (await apiClient.get<Dossier[]>("/dossiers/", { params: projetId ? { projet: projetId } : { libres: true } })).data,
  });
}

export function useCreateDossier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { nom: string; projet?: number | null; parent?: number | null }) =>
      (await apiClient.post<Dossier>("/dossiers/", payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dossiers"] }),
  });
}

export function useModifierDossier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: { id: number; nom?: string; parent?: number | null }) =>
      (await apiClient.patch<Dossier>(`/dossiers/${id}/`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dossiers"] }),
  });
}

/** Renommer un document ou le déplacer dans un autre dossier. */
export function useModifierDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: { id: number; nom?: string; dossier?: number | null }) =>
      (await apiClient.patch<GedDocument>(`/documents/${id}/`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ged-documents"] });
      queryClient.invalidateQueries({ queryKey: ["dossiers"] });
    },
  });
}

export function useDeleteDossier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/dossiers/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dossiers"] });
      queryClient.invalidateQueries({ queryKey: ["ged-documents"] });
      queryClient.invalidateQueries({ queryKey: ["corbeille-documents"] });
    },
  });
}

export function useDocuments(params: {
  dossier?: number;
  projet?: number;
  activite?: number;
  sous_activite?: number;
  search?: string;
  /** Explorateur : documents hors de tout dossier. */
  sans_dossier?: boolean;
  /** Bibliothèque libre : documents sans projet, activité ni sous-activité. */
  libres?: boolean;
}, actif = true) {
  return useQuery({
    queryKey: ["ged-documents", params],
    queryFn: async () =>
      // Jusqu'à 1000 documents d'un coup : un dossier s'affiche en entier dans l'explorateur.
      (await apiClient.get<Paginated<GedDocument>>("/documents/", { params: { page_size: 1000, ...params } })).data.results,
    enabled: actif,
  });
}

export function useCreateDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (formData: FormData) =>
      (
        await apiClient.post<GedDocument>("/documents/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ged-documents"] });
      queryClient.invalidateQueries({ queryKey: ["dossiers"] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/documents/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ged-documents"] });
      queryClient.invalidateQueries({ queryKey: ["dossiers"] });
      queryClient.invalidateQueries({ queryKey: ["corbeille-documents"] });
    },
  });
}

export function useNouvelleVersion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ documentId, formData }: { documentId: number; formData: FormData }) =>
      (
        await apiClient.post<DocumentVersion>(`/documents/${documentId}/nouvelle-version/`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ged-documents"] }),
  });
}

export function useDocumentVersions(documentId: number | undefined) {
  return useQuery({
    queryKey: ["ged-document-versions", documentId],
    queryFn: async () => (await apiClient.get<DocumentVersion[]>(`/documents/${documentId}/versions/`)).data,
    enabled: !!documentId,
  });
}

/** Sélection de l'explorateur : dossiers (avec leur contenu) et documents. */
export interface SelectionDocuments {
  dossiers: number[];
  documents: number[];
}

function useRafraichirDocuments() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["ged-documents"] });
    queryClient.invalidateQueries({ queryKey: ["dossiers"] });
    queryClient.invalidateQueries({ queryKey: ["corbeille-documents"] });
  };
}

/** Met la sélection à la corbeille. */
export function useSupprimerSelection() {
  const rafraichir = useRafraichirDocuments();
  return useMutation({
    mutationFn: async (selection: SelectionDocuments) =>
      (await apiClient.post<{ nombre: number }>("/documents/supprimer-selection/", selection)).data,
    onSuccess: rafraichir,
  });
}

/** Archive zip de la sélection (dernière version de chaque document, dossiers avec leur arborescence). */
export async function telechargerSelection(selection: SelectionDocuments) {
  const response = await apiClient.get("/documents/telecharger-selection/", {
    responseType: "blob",
    params: { dossiers: selection.dossiers.join(","), documents: selection.documents.join(",") },
  });
  const url = window.URL.createObjectURL(new Blob([response.data], { type: "application/zip" }));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", "documents.zip");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}

export interface ElementCorbeille {
  type: "dossier" | "document";
  id: number;
  nom: string;
  projet: number | null;
  projet_nom: string;
  supprime_le: string;
  supprime_par_nom: string;
  /** Vidage automatique : 30 jours après la suppression. */
  supprime_definitivement_le: string;
  nombre_elements?: number;
}

export function useCorbeille() {
  return useQuery({
    queryKey: ["corbeille-documents"],
    queryFn: async () =>
      (await apiClient.get<{ duree_conservation_jours: number; dossiers: ElementCorbeille[]; documents: ElementCorbeille[] }>("/documents/corbeille/")).data,
  });
}

export function useRestaurerCorbeille() {
  const rafraichir = useRafraichirDocuments();
  return useMutation({
    mutationFn: async (selection: SelectionDocuments) =>
      (await apiClient.post<{ nombre: number }>("/documents/corbeille/restaurer/", selection)).data,
    onSuccess: rafraichir,
  });
}

/** Suppression définitive : la sélection, ou toute la corbeille (`tout`). */
export function useViderCorbeille() {
  const rafraichir = useRafraichirDocuments();
  return useMutation({
    mutationFn: async (selection: SelectionDocuments | { tout: true }) =>
      (await apiClient.post<{ nombre: number }>("/documents/corbeille/vider/", selection)).data,
    onSuccess: rafraichir,
  });
}

/** Lien de partage d'un document avec une personne sans compte (apps.documents.partage). */
export interface LienDocument {
  id: number;
  jeton: string;
  droit: "CONSULTER" | "TELECHARGER";
  droit_libelle: string;
  libelle: string;
  expire_le: string;
  a_mot_de_passe: boolean;
  ouvertures_max: number | null;
  nombre_ouvertures: number;
  derniere_ouverture: string | null;
  etat: "ACTIF" | "EXPIRE" | "EPUISE" | "REVOQUE";
  version: number | null;
  version_numero: number | null;
  cree_par_nom: string;
  created_at: string;
}

export function useLiensDocument(documentId: number | null) {
  return useQuery({
    queryKey: ["ged-document-liens", documentId],
    queryFn: async () => (await apiClient.get<LienDocument[]>(`/documents/${documentId}/liens/`)).data,
    enabled: !!documentId,
  });
}

export function useCreerLienDocument(documentId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (donnees: { droit: string; expire_le: string; libelle: string; mot_de_passe: string; ouvertures_max: number | null }) =>
      (await apiClient.post<LienDocument>(`/documents/${documentId}/liens/`, donnees)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ged-document-liens", documentId] }),
  });
}

export function useRevoquerLienDocument(documentId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (lienId: number) => (await apiClient.post<LienDocument>(`/documents/${documentId}/liens/${lienId}/revoquer/`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ged-document-liens", documentId] }),
  });
}

/** Adresse publique d'un lien de partage (avec l'organisation, plateforme à adresse unique). */
export const adresseLienDocument = (jeton: string) => avecOrganisation(`${window.location.origin}/document/${jeton}`);

/** Page publique : description du lien, puis ouverture (mot de passe éventuel). */
export interface DocumentPartage {
  etat: LienDocument["etat"];
  droit: LienDocument["droit"];
  document: string;
  expire_le: string;
  mot_de_passe: boolean;
  organisation: string;
  type: string;
  apercu: boolean;
  version: number | null;
  apercu_url?: string | null;
  telechargement_url?: string | null;
  duree_minutes?: number;
}
export const lireDocumentPartage = async (jeton: string) =>
  (await apiClient.get<DocumentPartage>(`/public/document-partage/${jeton}/`)).data;
export const ouvrirDocumentPartage = async (jeton: string, motDePasse: string) =>
  (await apiClient.post<DocumentPartage>(`/public/document-partage/${jeton}/`, { mot_de_passe: motDePasse })).data;
