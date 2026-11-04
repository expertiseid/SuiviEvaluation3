/** Console Expertise-ID : demandes d'inscription, activation des espaces, organisations. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { DemandeInscription } from "./identite";

export interface OrganisationPlateforme {
  id: number;
  nom: string;
  sous_domaine: string;
  base: string;
  statut: "EN_ATTENTE" | "ACTIVE" | "SUSPENDUE";
  statut_libelle: string;
  offre: string;
  mode_demo: boolean;
  courriel_contact: string;
  cree_le: string;
  active_le: string | null;
  /** Comptes qui peuvent se connecter (adresse courriel réelle). */
  comptes: number;
}

export function useDemandesConsole() {
  return useQuery({
    queryKey: ["console", "demandes"],
    queryFn: async () => (await apiClient.get<DemandeInscription[]>("/console/demandes/")).data,
    // Une activation en cours se termine en arrière-plan : la liste se rafraîchit d'elle-même.
    refetchInterval: (requete) => (requete.state.data?.some((d) => d.statut === "EN_ACTIVATION") ? 3000 : false),
  });
}

export function useOrganisationsConsole() {
  return useQuery({
    queryKey: ["console", "organisations"],
    queryFn: async () => (await apiClient.get<OrganisationPlateforme[]>("/console/organisations/")).data,
  });
}

export function useActiverDemande() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, sous_domaine, zones }: { id: number; sous_domaine: string; zones: boolean }) =>
      (await apiClient.post<DemandeInscription>(`/console/demandes/${id}/activer/`, { sous_domaine, zones })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["console"] }),
  });
}

export function useStatutOrganisation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, statut }: { id: number; statut: "ACTIVE" | "SUSPENDUE" }) =>
      (await apiClient.post<OrganisationPlateforme>(`/console/organisations/${id}/statut/`, { statut })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["console"] }),
  });
}
