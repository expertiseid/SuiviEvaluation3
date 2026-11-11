/** Informations publiques de la plateforme, identité de l'organisation, inscription et démonstration. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, organisationConnectee, organisationPublique } from "./client";
import type { JetonsConnexion } from "./doubleAuth";

export interface IdentiteOrganisation {
  nom: string;
  /** Adresse du logo de l'organisation, ou null. */
  logo: string | null;
  /** Visiteur de la démonstration (lecture seule). */
  mode_demo: boolean;
  /** Une démonstration est proposée (« Essayer la démo »). */
  demo_disponible: boolean;
  /** Installation séparée : adresse de l'installation de démonstration (ou vide). */
  url_demo: string;
  inscriptions: boolean;
  /** Adresse de contact d'Expertise-ID (abonnements). */
  contact: string;
  /** Adresse du site vitrine (pages des conditions d'utilisation, de la confidentialité et des cookies). */
  url_site: string;
  /** Plateforme multi-organisations : une adresse unique, une base par organisation. */
  multi_organisations: boolean;
  /** Organisation du compte connecté (ou de la page publique), sinon null. */
  espace: { sous_domaine: string; nom: string } | null;
  /** Déconnexion après ce nombre de minutes sans activité (réglage de l'Administrateur) ; 0 : jamais. */
  session_inactivite_min: number;
}

export function useIdentiteOrganisation() {
  return useQuery({
    // L'identité dépend de l'organisation : celle du compte connecté, ou celle d'une page publique.
    queryKey: ["identite", organisationConnectee() || organisationPublique()],
    queryFn: async () => (await apiClient.get<IdentiteOrganisation>("/identite/")).data,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEnregistrerIdentite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ nom, logo, supprimerLogo, sessionInactiviteMin }: {
      nom?: string; logo?: File | null; supprimerLogo?: boolean; sessionInactiviteMin?: number;
    }) => {
      const envoi = new FormData();
      if (nom !== undefined) envoi.append("nom", nom);
      if (sessionInactiviteMin !== undefined) envoi.append("session_inactivite_min", String(sessionInactiviteMin));
      if (logo) envoi.append("logo", logo);
      if (supprimerLogo) envoi.append("supprimer_logo", "true");
      return (await apiClient.patch<IdentiteOrganisation>("/identite/", envoi)).data;
    },
    onSuccess: (donnees) => queryClient.setQueryData(["identite", organisationConnectee()], donnees),
  });
}

export interface ProfilOrganisation {
  organisation: string;
  type_organisation: string;
  pays: string;
  secteur: string;
  taille: string;
  contact_nom: string;
  contact_fonction: string;
  courriel: string;
  telephone: string;
  mot_de_passe: string;
  message: string;
  conditions: boolean;
}

/** Suite d'une inscription : référence pour la page d'abonnement. */
export interface DemandeAbonnement {
  reference: string;
  organisation: string;
  statut: "ABONNEMENT_REQUIS" | "OFFRE_CHOISIE" | "EN_ACTIVATION" | "ACTIVEE" | "REFUSEE";
  offre: "" | "STANDARD_25" | "STANDARD_50" | "STANDARD" | "STOCKAGE_PLUS" | "PARTENARIAT";
  contact: string;
  /** Organisation activée (plateforme multi-organisations) : page de connexion. */
  espace: string;
  /** Paiement en ligne (CinetPay) : prix d'un mois de l'offre Standard et d'une tranche de 10 Go. */
  tarifs?: { paiement: boolean; devise: string; mois: number; tranche: number; durees: number[]; tranches_max: number;
    /** Prix affichés et payés par carte bancaire (finalisée avec Expertise-ID). */
    usd?: { mois: number; tranche: number };
    /** Prix d'un mois de chaque offre payante (FCFA et dollars). */
    offres?: Record<string, { mois: number; usd: number }>;
    /** Formation gratuite à partir de ce nombre de mois de licence, par offre. */
    formation?: Record<string, number> };
}

export const creerProfil = async (profil: ProfilOrganisation & { site_web: string }) =>
  (await apiClient.post<DemandeAbonnement>("/public/inscription/", profil)).data;
export const choisirOffre = async (reference: string, offre: string, message: string,
  carte?: { mois: number; tranches: number }) =>
  (await apiClient.post<DemandeAbonnement>("/public/inscription/offre/",
    { reference, offre, message, ...(carte ? { moyen: "carte", ...carte } : {}) })).data;
/** Offre payée en ligne : renvoie le lien vers la page de paiement de CinetPay (l'espace est créé une fois payé). */
export const payerOffre = async (demande: { reference: string; offre: string; mois: number; tranches: number; message: string; langue: string }) =>
  (await apiClient.post<{ lien: string; paiement: string; montant: number; devise: string }>("/public/inscription/paiement/", demande)).data;

export const connexionDemo = async () => (await apiClient.post<JetonsConnexion>("/public/demo/")).data;

export interface DemandeInscription {
  id: number;
  organisation: string;
  type_organisation: string;
  pays: string;
  secteur: string;
  taille: string;
  contact_nom: string;
  contact_fonction: string;
  courriel: string;
  telephone: string;
  identifiant: string;
  sous_domaine: string;
  erreur_activation: string;
  offre: string;
  offre_libelle: string;
  message: string;
  statut: DemandeAbonnement["statut"];
  statut_libelle: string;
  cree_le: string;
}

export function useDemandesInscription() {
  return useQuery({
    queryKey: ["demandes-inscription"],
    queryFn: async () => (await apiClient.get<DemandeInscription[]>("/demandes-inscription/")).data,
  });
}

export function useStatutDemandeInscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, statut }: { id: number; statut: string }) =>
      (await apiClient.post<DemandeInscription>(`/demandes-inscription/${id}/statut/`, { statut })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["demandes-inscription"] }),
  });
}
