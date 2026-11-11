/** Site vitrine : actualités et partenaires, gérés dans la console Expertise-ID (apps.organisations.site). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";

export const LANGUES_SITE = ["en", "ar", "es", "de", "it"] as const;
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

// --- Newsletter (apps.organisations.newsletter) ------------------------------------------------------

export interface AbonneNewsletter {
  id: number;
  courriel: string;
  langue: string;
  statut: "ACTIF" | "EN_ATTENTE" | "DESINSCRIT";
  cree_le: string;
  confirme_le: string | null;
  desinscrit_le: string | null;
}

export interface EnvoiNewsletter {
  id: number;
  sujet: string;
  contenu: string;
  traductions: Partial<Record<LangueSite, { sujet?: string; contenu?: string }>>;
  statut: "BROUILLON" | "EN_COURS" | "ENVOYE";
  destinataires: number;
  envoyes: number;
  echecs: number;
  envoye_par: string;
  envoye_le: string | null;
  cree_le: string;
}

const NEWSLETTER = "/console/site/newsletter/";

export function useAbonnesNewsletter() {
  return useQuery({
    queryKey: ["console", "newsletter", "abonnes"],
    queryFn: async () => (await apiClient.get<AbonneNewsletter[]>(`${NEWSLETTER}abonnes/`)).data,
  });
}

export function useResumeNewsletter() {
  return useQuery({
    queryKey: ["console", "newsletter", "resume"],
    queryFn: async () => (await apiClient.get<{ actifs: number; en_attente: number; desinscrits: number }>(`${NEWSLETTER}envois/resume/`)).data,
  });
}

/** Envois : la liste se met à jour toute seule tant qu'un envoi est en cours. */
export function useEnvoisNewsletter() {
  return useQuery({
    queryKey: ["console", "newsletter", "envois"],
    queryFn: async () => (await apiClient.get<EnvoiNewsletter[]>(`${NEWSLETTER}envois/`)).data,
    refetchInterval: (requete) => (requete.state.data?.some((e) => e.statut === "EN_COURS") ? 3000 : false),
  });
}

export function useNewsletter() {
  const queryClient = useQueryClient();
  const rafraichir = () => queryClient.invalidateQueries({ queryKey: ["console", "newsletter"] });
  return {
    enregistrer: async (id: number | undefined, champs: Pick<EnvoiNewsletter, "sujet" | "contenu" | "traductions">) => {
      const reponse = id ? await apiClient.patch(`${NEWSLETTER}envois/${id}/`, champs) : await apiClient.post(`${NEWSLETTER}envois/`, champs);
      await rafraichir();
      return reponse.data as EnvoiNewsletter;
    },
    essai: async (id: number, langue: string) => (await apiClient.post<{ detail: string }>(`${NEWSLETTER}envois/${id}/essai/`, { langue })).data,
    envoyer: async (id: number) => { await apiClient.post(`${NEWSLETTER}envois/${id}/envoyer/`); await rafraichir(); },
    supprimerEnvoi: async (id: number) => { await apiClient.delete(`${NEWSLETTER}envois/${id}/`); await rafraichir(); },
    supprimerAbonne: async (id: number) => { await apiClient.delete(`${NEWSLETTER}abonnes/${id}/`); await rafraichir(); },
  };
}

export async function exporterAbonnesNewsletter() {
  const reponse = await apiClient.get(`${NEWSLETTER}abonnes/exporter/`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", "abonnes-newsletter.xlsx");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
}
