/** Site vitrine : actualités et partenaires, gérés dans la console Expertise-ID (apps.organisations.site). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";

export const LANGUES_SITE = ["en", "ar", "es", "de"] as const;
export type LangueSite = (typeof LANGUES_SITE)[number];

export interface ActualiteSite {
  id: number;
  titre: string;
  resume: string;
  contenu: string;
  image: string | null;
  lien: string;
  date_publication: string;
  publiee: boolean;
  traductions: Partial<Record<LangueSite, { titre?: string; resume?: string; contenu?: string }>>;
  modifie_le: string;
}

export interface PartenaireSite {
  id: number;
  nom: string;
  categorie: "FINANCIER" | "TECHNIQUE" | "INSTITUTION" | "CLIENT";
  categorie_libelle: string;
  description: string;
  logo: string | null;
  site_web: string;
  ordre: number;
  visible: boolean;
  traductions: Partial<Record<LangueSite, { description?: string }>>;
  modifie_le: string;
}

type Ressource = "actualites" | "partenaires";

function useListe<T>(ressource: Ressource) {
  return useQuery({
    queryKey: ["console", "site", ressource],
    queryFn: async () => (await apiClient.get<T[]>(`/console/site/${ressource}/`)).data,
  });
}
export const useActualitesSite = () => useListe<ActualiteSite>("actualites");
export const usePartenairesSite = () => useListe<PartenaireSite>("partenaires");

/** Enregistrement en multipart (image ou logo), les traductions en JSON. */
export function useEnregistrerSite(ressource: Ressource) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, champs, fichier }: { id?: number; champs: Record<string, unknown>; fichier?: { nom: string; valeur: File } }) => {
      const envoi = new FormData();
      Object.entries(champs).forEach(([cle, valeur]) => {
        if (valeur === undefined || valeur === null) return;
        envoi.append(cle, typeof valeur === "object" ? JSON.stringify(valeur) : String(valeur));
      });
      if (fichier) envoi.append(fichier.nom, fichier.valeur);
      const url = id ? `/console/site/${ressource}/${id}/` : `/console/site/${ressource}/`;
      return (await (id ? apiClient.patch(url, envoi) : apiClient.post(url, envoi))).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["console", "site", ressource] }),
  });
}

export function useSupprimerSite(ressource: Ressource) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/console/site/${ressource}/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["console", "site", ressource] }),
  });
}
