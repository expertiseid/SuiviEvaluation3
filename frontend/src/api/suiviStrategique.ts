import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";

export type EtatAppreciation = "BON" | "MOYEN" | "INSUFFISANT";

export interface PieceJointe {
  id: number;
  nom: string;
  /** Chemin d'API (authentifié) du fichier. */
  telechargement: string;
  ajoute_par: string;
}

export interface LigneSuiviCadre {
  id: number;
  code: string;
  nom: string;
  element_parent: number | null;
  niveau: string;
  ordre_niveau: number;
  taux_physique: number | null;
  taux_financier: number | null;
  nombre_projets: number;
  nombre_indicateurs: number;
  derniere_appreciation: { etat: EtatAppreciation; libelle_periode: string; periode_fin: string } | null;
}

export interface AppreciationStrategique {
  id: number;
  element: number;
  libelle_periode: string;
  periode_debut: string;
  periode_fin: string;
  etat: EtatAppreciation;
  commentaire: string;
  difficultes: string;
  recommandations: string;
  saisi_par_nom: string;
  pieces: PieceJointe[];
}

export interface IndicateurStrategique {
  id: number;
  libelle: string;
  unite: string;
  valeur_reference: number | null;
  valeur_cible: number;
  frequence_collecte: string;
  realise: number;
  taux: number | null;
  origine: string;
  saisie_directe: boolean;
  valeurs: {
    id: number;
    periode_debut: string;
    periode_fin: string;
    valeur_realisee: number;
    commentaire: string;
    etat_approbation: string;
    pieces: PieceJointe[];
  }[];
}

export interface SuiviElement {
  element: { id: number; code: string; nom: string; niveau: string };
  calcule: {
    projets: { id: number; code: string; nom: string; nombre_activites: number; taux_physique: number | null }[];
    nombre_activites: number;
    taux_physique: number | null;
    budget_alloue: number;
    budget_realise: number;
    taux_financier: number | null;
  };
  indicateurs: IndicateurStrategique[];
  appreciations: AppreciationStrategique[];
}

export function useSuiviCadre(cadreId: number) {
  return useQuery({
    queryKey: ["suivi-strategique", "cadre", cadreId],
    queryFn: async () => (await apiClient.get<{ elements: LigneSuiviCadre[] }>(`/cadres-strategiques/${cadreId}/suivi/`)).data.elements,
  });
}

export function useSuiviElement(elementId: number | null) {
  return useQuery({
    queryKey: ["suivi-strategique", "element", elementId],
    queryFn: async () => (await apiClient.get<SuiviElement>(`/elements-strategiques/${elementId}/suivi/`)).data,
    enabled: !!elementId,
  });
}

function useInvalider() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["suivi-strategique"] });
    queryClient.invalidateQueries({ queryKey: ["indicateurs"] });
  };
}

/** Pièces jointes envoyées après l'enregistrement de ce qu'elles justifient. */
async function joindre(fichiers: File[], lien: { appreciation_strategique?: number; valeur_indicateur?: number }) {
  for (const fichier of fichiers) {
    const donnees = new FormData();
    donnees.append("fichier", fichier);
    donnees.append("nom", fichier.name.slice(0, 200));
    Object.entries(lien).forEach(([cle, valeur]) => donnees.append(cle, String(valeur)));
    await apiClient.post("/pieces-justificatives/", donnees);
  }
}

export function useEnregistrerAppreciation() {
  const invalider = useInvalider();
  return useMutation({
    mutationFn: async ({ id, fichiers, ...payload }: Partial<AppreciationStrategique> & { fichiers: File[] }) => {
      const a = (
        id
          ? await apiClient.patch<AppreciationStrategique>(`/appreciations-strategiques/${id}/`, payload)
          : await apiClient.post<AppreciationStrategique>("/appreciations-strategiques/", payload)
      ).data;
      await joindre(fichiers, { appreciation_strategique: a.id });
      return a;
    },
    onSuccess: invalider,
  });
}

export function useSupprimerAppreciation() {
  const invalider = useInvalider();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/appreciations-strategiques/${id}/`),
    onSuccess: invalider,
  });
}

export function useSupprimerPiece() {
  const invalider = useInvalider();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/pieces-justificatives/${id}/`),
    onSuccess: invalider,
  });
}

/** Indicateur propre à l'élément (sans projet) : ses valeurs se saisissent directement. */
export function useCreerIndicateurStrategique() {
  const invalider = useInvalider();
  return useMutation({
    mutationFn: async (payload: {
      libelle: string;
      unite: string;
      valeur_reference: number | null;
      valeur_cible: number;
      frequence_collecte: string;
      elements_strategiques: number[];
    }) => (await apiClient.post("/indicateurs/", payload)).data,
    onSuccess: invalider,
  });
}

export function useSaisirValeurStrategique() {
  const invalider = useInvalider();
  return useMutation({
    mutationFn: async ({ fichiers, ...payload }: { indicateur: number; periode_debut: string; periode_fin: string; valeur_realisee: number; commentaire: string; fichiers: File[] }) => {
      const valeur = (await apiClient.post<{ id: number }>("/valeurs-indicateurs/", payload)).data;
      await joindre(fichiers, { valeur_indicateur: valeur.id });
      return valeur;
    },
    onSuccess: invalider,
  });
}

export function useSupprimerValeurStrategique() {
  const invalider = useInvalider();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/valeurs-indicateurs/${id}/`),
    onSuccess: invalider,
  });
}
