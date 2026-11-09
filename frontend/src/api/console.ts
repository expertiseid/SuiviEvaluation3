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
  /** Espace fixé par Expertise-ID (Go) ; null : celui de l'offre. */
  stockage_go: number | null;
  stockage: EspaceStockage;
}

/** Espace de stockage d'une organisation : occupé et limite en octets (limite null : sans limite). */
export interface EspaceStockage {
  utilise: number | null;
  limite: number | null;
  limite_go: number | null;
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

export function useStockageOrganisation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, stockage_go }: { id: number; stockage_go: number | null }) =>
      (await apiClient.post<OrganisationPlateforme>(`/console/organisations/${id}/stockage/`, { stockage_go })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["console"] }),
  });
}

/** Page Stockage : espace de l'organisation, tarifs du stockage supplémentaire, achats déjà payés. */
export interface PageStockage extends EspaceStockage {
  offre?: string;
  /** Espace inclus dans l'offre (Go). */
  offre_go?: number | null;
  /** Administrateur de l'organisation : peut acheter du stockage. */
  peut_acheter?: boolean;
  tarifs?: { paiement: boolean; devise: string; tranche: number; tranche_usd: number; durees: number[]; tranches_max: number };
  achats?: { date: string; tranches: number; mois: number; montant: number; devise: string }[];
}

export function usePageStockage() {
  return useQuery({
    queryKey: ["stockage"],
    queryFn: async () => (await apiClient.get<PageStockage>("/stockage/")).data,
  });
}

/** Stockage supplémentaire : mobile money (lien vers la page de paiement) ou carte (demande à Expertise-ID). */
export async function acheterStockage(achat: { tranches: number; mois: number; moyen: "mobile" | "carte"; langue: string }) {
  return (await apiClient.post<{ lien?: string; paiement?: string; carte?: boolean }>("/stockage/achat/", achat)).data;
}

/** Retour de CinetPay : statut du paiement (redemandé à CinetPay tant qu'il est en attente). */
export function useEtatPaiementStockage(reference: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["stockage", "paiement", reference],
    enabled: !!reference,
    queryFn: async () => {
      const etat = (await apiClient.get<{ statut: "EN_ATTENTE" | "PAYE" | "ECHOUE"; tranches: number }>(`/stockage/paiement/${reference}/`)).data;
      if (etat.statut === "PAYE") await queryClient.invalidateQueries({ queryKey: ["stockage"], exact: true });
      return etat;
    },
    refetchInterval: (requete) => (requete.state.data?.statut === "EN_ATTENTE" ? 4000 : false),
  });
}

interface Disque { total: number; utilise: number; libre: number }

/** Vue d'ensemble de la console (supervision.py) : mesures prises à chaque ouverture. */
export interface VueEnsemble {
  organisations: { actives: number; suspendues: number; demonstration: number };
  demandes_a_traiter: number;
  paiements_30_jours: { devise: string; total: number }[];
  paiements: {
    date: string; organisation: string; nature: "ABONNEMENT" | "STOCKAGE"; nature_libelle: string; offre: string;
    mois: number; tranches: number; montant: number; devise: string; statut: "EN_ATTENTE" | "PAYE" | "ECHOUE"; statut_libelle: string;
  }[];
  stockage: {
    vendu_go: number;
    utilise: number;
    espaces: (EspaceStockage & { id: number; nom: string; statut: string; mode_demo: boolean })[];
  };
  /** Disque commun des fichiers (Volume du serveur de données), agrandi tout seul à `seuil` %. */
  disque: (Disque & { plafond_go: number | null; seuil: number }) | null;
  serveurs: {
    plateforme: { processeurs: number | null; charge: number | null; memoire: { total: number | null; libre: number | null }; disque: Disque | null; allume_depuis: number | null };
    donnees: { adresse: string; joignable: boolean; reponse_ms?: number; taille_bases?: number; bases?: number };
  };
}

export function useVueEnsemble(actif = true) {
  return useQuery({
    queryKey: ["console", "vue-ensemble"],
    enabled: actif,
    queryFn: async () => (await apiClient.get<VueEnsemble>("/console/vue-ensemble/")).data,
    refetchInterval: 60_000,
  });
}
