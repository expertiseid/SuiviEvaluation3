/**
 * Mécanisme de gestion des plaintes et retours — lot 1 : paramétrage (mécanisme, types,
 * priorités, catégories, circuits et étapes, modèles, canevas Excel) ; lot 2 : réception
 * (dossiers, saisie par un agent, formulaire public et suivi par code) ; lot 3 : traitement
 * (actions sur un dossier, journal, vues prêtes et enregistrées, dossiers liés) ; lot 4 : délais
 * (échéances, prolongation, jours fériés, réglages des rappels) ; lot 5 : circuit confidentiel
 * (marquage, levée, personnes mises en cause, assistance, export, conservation). API : /api/v1/plaintes/
 * et, sans compte, /api/v1/public/plaintes/.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Paginated } from "../types";
import { locale } from "../utils/i18n";
import { voc } from "../utils/vocabulaire";

export interface MecanismePlaintes {
  id: number;
  nom: string;
  actif: boolean;
  modele: string;
  anonymat_autorise: boolean;
  langues: string[];
  texte_information: string;
  prefixe_numero: string;
  jours_ouvres: boolean;
  conservation_ordinaire_mois: number | null;
  conservation_sensible_mois: number | null;
  projets: number[];
  /** Ce qui manque pour activer le mécanisme (vide = activable). */
  controles: string[];
  delai_defaut_jours: number;
  rappel_jours_avant: number;
  escalade_active: boolean;
  notifications_courriel: boolean;
  circuit_alternatif: number | null;
}

export interface TypeRetour {
  id: number;
  nom: string;
  description: string;
  ordre: number;
  actif: boolean;
}

export interface PrioritePlainte {
  id: number;
  nom: string;
  ordre: number;
  urgente: boolean;
  delai_jours: number | null;
  actif: boolean;
}

export interface EtapeCircuit {
  id: number;
  circuit: number;
  nom: string;
  ordre: number;
  delai_jours: number | null;
  role: number | null;
  role_libelle: string | null;
  responsable: number | null;
  responsable_nom: string | null;
  est_cloture: boolean;
}

export interface CircuitPlainte {
  id: number;
  nom: string;
  description: string;
  sensible: boolean;
  par_defaut: boolean;
  actif: boolean;
  etapes: EtapeCircuit[];
  /** Ce qui empêche d'utiliser le circuit (vide = valide). */
  erreurs: string[];
  nb_categories: number;
}

export interface CategoriePlainte {
  id: number;
  nom: string;
  description: string;
  parent: number | null;
  parent_nom: string | null;
  sensible: boolean;
  sensible_effective: boolean;
  /** Protège les personnes : reste sensible et active, ne se supprime pas. */
  verrouillee: boolean;
  circuit: number | null;
  circuit_nom: string | null;
  delai_jours: number | null;
  ordre: number;
  actif: boolean;
}

export interface ModeleMecanisme {
  code: string;
  libelle: string;
  description: string;
}

export interface RapportImportParametrage {
  crees: number;
  mis_a_jour: number;
  erreurs: { ligne: number; message: string }[];
}

const CLE = "plaintes";

/** Tout changement du paramétrage peut changer les contrôles d'activation : on recharge tout. */
function useRafraichir() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: [CLE] });
}

export function useMecanisme() {
  return useQuery({
    queryKey: [CLE, "mecanisme"],
    queryFn: async () => (await apiClient.get<MecanismePlaintes>("/plaintes/mecanisme/")).data,
  });
}

export function useEnregistrerMecanisme() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (payload: Partial<MecanismePlaintes>) =>
      (await apiClient.patch<MecanismePlaintes>("/plaintes/mecanisme/", payload)).data,
    onSuccess: rafraichir,
  });
}

export function useActivationMecanisme() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (activer: boolean) =>
      (await apiClient.post<MecanismePlaintes>(`/plaintes/mecanisme/${activer ? "activer" : "desactiver"}/`)).data,
    onSuccess: rafraichir,
  });
}

export function useModelesMecanisme() {
  return useQuery({
    queryKey: [CLE, "modeles"],
    queryFn: async () => (await apiClient.get<ModeleMecanisme[]>("/plaintes/modeles/")).data,
  });
}

export function useAppliquerModele() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (modele: string) =>
      (await apiClient.post<{ ajouts: Record<string, number> }>("/plaintes/modeles/", { modele })).data,
    onSuccess: rafraichir,
  });
}

/** Liste et enregistrement d'un élément du paramétrage (types, priorités, catégories, circuits, étapes). */
function useListe<T>(ressource: string) {
  return useQuery({
    queryKey: [CLE, ressource],
    queryFn: async () => (await apiClient.get<T[]>(`/plaintes/${ressource}/`)).data,
  });
}

function useEnregistrer<T extends { id: number }>(ressource: string) {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<T> & { id?: number }) =>
      id
        ? (await apiClient.patch<T>(`/plaintes/${ressource}/${id}/`, payload)).data
        : (await apiClient.post<T>(`/plaintes/${ressource}/`, payload)).data,
    onSuccess: rafraichir,
  });
}

function useSupprimer(ressource: string) {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/plaintes/${ressource}/${id}/`),
    onSuccess: rafraichir,
  });
}

export const useTypesRetour = () => useListe<TypeRetour>("types");
export const useEnregistrerTypeRetour = () => useEnregistrer<TypeRetour>("types");
export const useSupprimerTypeRetour = () => useSupprimer("types");
export const usePrioritesPlainte = () => useListe<PrioritePlainte>("priorites");
export const useEnregistrerPriorite = () => useEnregistrer<PrioritePlainte>("priorites");
export const useSupprimerPriorite = () => useSupprimer("priorites");
export const useCategoriesPlainte = () => useListe<CategoriePlainte>("categories");
export const useEnregistrerCategorie = () => useEnregistrer<CategoriePlainte>("categories");
export const useSupprimerCategorie = () => useSupprimer("categories");
export const useCircuitsPlainte = () => useListe<CircuitPlainte>("circuits");
export const useEnregistrerCircuit = () => useEnregistrer<CircuitPlainte>("circuits");
export const useSupprimerCircuit = () => useSupprimer("circuits");
export const useEnregistrerEtape = () => useEnregistrer<EtapeCircuit>("etapes");
export const useSupprimerEtape = () => useSupprimer("etapes");

export async function telechargerCanevasParametrage() {
  const response = await apiClient.get("/plaintes/canevas/", { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", "parametrage_plaintes.xlsx");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}

export function useImporterCanevasParametrage() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (fichier: File) => {
      const donnees = new FormData();
      donnees.append("fichier", fichier);
      return (
        await apiClient.post<RapportImportParametrage>("/plaintes/canevas/importer/", donnees, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data;
    },
    onSuccess: rafraichir,
  });
}

// --- Lot 2 : réception ----------------------------------------------------------------------

export type CanalPlainte = "FORMULAIRE" | "TELEPHONE" | "EN_PERSONNE" | "REUNION" | "BOITE" | "COURRIER" | "COURRIEL" | "AUTRE";
export type StatutDossier = "RECU" | "EN_COURS" | "REPONDU" | "CLOTURE";
export type ModeReponse = "AUCUN" | "TELEPHONE" | "SMS" | "COURRIEL" | "EN_PERSONNE";

export const libelleCanal = (c: CanalPlainte): string =>
  ({
    FORMULAIRE: voc("Formulaire public"),
    TELEPHONE: voc("Téléphone"),
    EN_PERSONNE: voc("En personne, sur le terrain"),
    REUNION: voc("Réunion communautaire"),
    BOITE: voc("Boîte à suggestions"),
    COURRIER: voc("Courrier"),
    COURRIEL: voc("Courriel"),
    AUTRE: voc("Autre"),
  })[c];

export const libelleStatutDossier = (s: StatutDossier): string =>
  ({ RECU: voc("Reçu"), EN_COURS: voc("En cours de traitement"), REPONDU: voc("Réponse donnée"), CLOTURE: voc("Clôturé") })[s];

/** Couleur du statut d'un dossier (liste, fiche, dossiers liés). */
export const couleurStatutDossier = (s: StatutDossier) => ({ RECU: "blue", EN_COURS: "orange", REPONDU: "teal", CLOTURE: "gray" })[s];

/** Date (AAAA-MM-JJ) dans le format de la langue. */
export const dateLisible = (d: string) => new Date(`${d.slice(0, 10)}T00:00:00`).toLocaleDateString(locale());

export const STATUTS_DOSSIER: StatutDossier[] = ["RECU", "EN_COURS", "REPONDU", "CLOTURE"];

export const libelleModeReponse = (m: ModeReponse): string =>
  ({
    AUCUN: voc("Pas de réponse souhaitée"),
    TELEPHONE: voc("Par téléphone"),
    SMS: voc("Par SMS"),
    COURRIEL: voc("Par courriel"),
    EN_PERSONNE: voc("En personne"),
  })[m];

export const MODES_REPONSE: ModeReponse[] = ["AUCUN", "TELEPHONE", "SMS", "COURRIEL", "EN_PERSONNE"];
export const CANAUX_AGENT: CanalPlainte[] = ["TELEPHONE", "EN_PERSONNE", "REUNION", "BOITE", "COURRIER", "COURRIEL", "AUTRE"];

export interface DossierPlainte {
  id: number;
  numero: string;
  canal: CanalPlainte;
  date_reception: string;
  recueilli_directement: boolean | null;
  type_retour: number;
  type_retour_nom: string;
  categorie: number | null;
  categorie_nom: string | null;
  categorie_parent_nom: string | null;
  priorite: number | null;
  priorite_nom: string | null;
  priorite_urgente: boolean;
  projet: number | null;
  projet_nom: string | null;
  projet_code: string | null;
  lieu: string;
  description: string;
  concerne_personnel: boolean | null;
  sensible: boolean;
  circuit: number | null;
  circuit_nom: string | null;
  etape: number | null;
  etape_nom: string | null;
  statut: StatutDossier;
  anonyme: boolean;
  nom: string;
  telephone: string;
  courriel: string;
  mode_reponse: ModeReponse;
  consentement: boolean;
  langue: string;
  saisi_par_nom: string | null;
  created_at: string;
  responsable: number | null;
  responsable_nom: string | null;
  decision: string;
  date_decision: string | null;
  date_reponse: string | null;
  issue: IssueDossier | "";
  motif_cloture: string;
  retour_donne: boolean | null;
  raison_sans_retour: string;
  oriente_vers: string;
  consentement_reference: boolean;
  date_cloture: string | null;
  en_recours: boolean;
  gestionnaire_initial_nom: string | null;
  echeance: string | null;
  echeance_etape: string | null;
  date_entree_etape: string | null;
  jours_prolongation: number;
  en_retard: boolean;
  mis_en_cause_utilisateurs: number[];
  mis_en_cause_noms: string[];
  mis_en_cause_libre: string;
  suspension_legale: boolean;
  motif_suspension: string;
  anonymise: boolean;
  date_anonymisation: string | null;
}

/** État des délais d'un dossier ouvert : en retard (dossier ou étape), proche, ou dans les temps. */
export function etatDelai(d: DossierPlainte, rappelJours = 2): { etat: "retard" | "proche" | "ok" | "clos"; jours: number | null } {
  if (d.statut === "CLOTURE" || !d.echeance) return { etat: "clos", jours: null };
  const jour = (x: string) => new Date(`${x.slice(0, 10)}T00:00:00`).getTime();
  const aujourdhui = new Date(new Date().toDateString()).getTime();
  const jours = Math.round((jour(d.echeance) - aujourdhui) / 86400000);
  const etapeDepassee = !!d.echeance_etape && jour(d.echeance_etape) < aujourdhui;
  if (jours < 0 || etapeDepassee) return { etat: "retard", jours };
  return { etat: jours <= rappelJours ? "proche" : "ok", jours };
}

export type IssueDossier = "RESOLU" | "NON_FONDE" | "REFERE" | "HORS_PERIMETRE" | "SANS_SUITE";
export const ISSUES: IssueDossier[] = ["RESOLU", "NON_FONDE", "REFERE", "HORS_PERIMETRE", "SANS_SUITE"];
export const libelleIssue = (i: IssueDossier): string =>
  ({
    RESOLU: voc("Réponse apportée"),
    NON_FONDE: voc("Non fondé"),
    REFERE: voc("Référé à un acteur externe"),
    HORS_PERIMETRE: voc("Hors périmètre"),
    SANS_SUITE: voc("Sans suite (plaignant injoignable, abandon…)"),
  })[i];

export type TypeAction =
  | "RECEPTION" | "CLASSIFICATION" | "AFFECTATION" | "RECUSATION" | "ETAPE" | "NOTE" | "ACTION_CORRECTIVE"
  | "COMMUNICATION" | "DECISION" | "CLOTURE" | "REOUVERTURE" | "RECOURS" | "SENSIBILITE" | "LIEN" | "PROLONGATION" | "RETARD"
  | "MISE_EN_CAUSE" | "ASSISTANCE" | "EXPORT" | "SUSPENSION" | "ANONYMISATION";
export const libelleTypeAction = (t: TypeAction): string =>
  ({
    RECEPTION: voc("Réception"),
    CLASSIFICATION: voc("Classification"),
    AFFECTATION: voc("Affectation"),
    RECUSATION: voc("Récusation"),
    ETAPE: voc("Changement d'étape"),
    NOTE: voc("Note interne"),
    ACTION_CORRECTIVE: voc("Action corrective"),
    COMMUNICATION: voc("Communication avec le plaignant"),
    DECISION: voc("Décision"),
    CLOTURE: voc("Clôture"),
    REOUVERTURE: voc("Réouverture"),
    RECOURS: voc("Recours"),
    SENSIBILITE: voc("Sensibilité"),
    LIEN: voc("Dossiers liés"),
    PROLONGATION: voc("Prolongation du délai"),
    RETARD: voc("Retard"),
    MISE_EN_CAUSE: voc("Personnes mises en cause"),
    ASSISTANCE: voc("Assistance et référencement"),
    EXPORT: voc("Export de la fiche"),
    SUSPENSION: voc("Suspension légale"),
    ANONYMISATION: voc("Anonymisation"),
  })[t];

export type ObjetEchange = "ACCUSE_RECEPTION" | "PRISE_EN_CHARGE" | "DEMANDE_COMPLEMENT" | "DECISION" | "CLOTURE" | "SATISFACTION" | "AUTRE";
export const OBJETS_ECHANGE: ObjetEchange[] = ["ACCUSE_RECEPTION", "PRISE_EN_CHARGE", "DEMANDE_COMPLEMENT", "DECISION", "CLOTURE", "SATISFACTION", "AUTRE"];
export const libelleObjetEchange = (o: ObjetEchange): string =>
  ({
    ACCUSE_RECEPTION: voc("Accusé de réception"),
    PRISE_EN_CHARGE: voc("Information de prise en charge"),
    DEMANDE_COMPLEMENT: voc("Demande de complément"),
    DECISION: voc("Communication de la décision"),
    CLOTURE: voc("Confirmation de clôture"),
    SATISFACTION: voc("Enquête de satisfaction"),
    AUTRE: voc("Autre échange"),
  })[o];

export interface ActionDossier {
  id: number;
  type: TypeAction;
  auteur_nom: string | null;
  date: string;
  texte: string;
  details: Record<string, unknown>;
  sens: "SORTANT" | "ENTRANT" | "";
  canal: ModeReponse | "";
  objet: ObjetEchange | "";
}

export interface DossierDetail extends DossierPlainte {
  actions: ActionDossier[];
  dossiers_lies: { id: number; numero: string; statut: StatutDossier }[];
  referencements: { id: number; prestataire: string; type: TypePrestataire; date: string; auteur: string }[];
  /** L'utilisateur peut lever la sensibilité (point focal du circuit ou Administrateur). */
  habilite: boolean;
  fin_conservation: string | null;
}

/** Opérations de traitement (POST /plaintes/dossiers/{id}/{operation}/). */
export type OperationDossier =
  | "classer" | "affecter" | "recuser" | "etape" | "noter" | "communiquer" | "decider" | "cloturer" | "rouvrir" | "recours" | "lier"
  | "prolonger" | "lever-sensibilite" | "mettre-en-cause" | "assistance" | "suspendre" | "anonymiser";

/** Données d'un retour, communes au formulaire public et à la saisie par un agent. */
export interface SaisieRetour {
  type_retour: number | null;
  categorie: number | null;
  projet: number | null;
  lieu: string;
  description: string;
  concerne_personnel: boolean | null;
  anonyme: boolean;
  nom: string;
  telephone: string;
  courriel: string;
  mode_reponse: ModeReponse;
  consentement: boolean;
  langue: string;
}

export interface SaisieAgent extends SaisieRetour {
  canal: CanalPlainte | null;
  date_reception: string | null;
  recueilli_directement: boolean;
  priorite: number | null;
  mis_en_cause_utilisateurs: number[];
  mis_en_cause_libre: string;
}

/** Réponse à un enregistrement : le code de suivi n'est donné qu'une fois. */
export interface RecuDossier {
  numero: string;
  code_suivi: string;
  sensible?: boolean;
  /** Faux pour un dossier sensible : l'agent n'en garde que le numéro. */
  visible?: boolean;
}

export interface FiltresDossiers {
  page: number;
  vue?: string | null;
  search?: string;
  statut?: string | null;
  canal?: string | null;
  projet?: string | null;
  categorie?: string | null;
  priorite?: string | null;
  responsable?: string | null;
  date_du?: string | null;
  date_au?: string | null;
}

export function useDossiersPlainte(filtres: FiltresDossiers) {
  return useQuery({
    queryKey: [CLE, "dossiers", filtres],
    queryFn: async () =>
      (await apiClient.get<Paginated<DossierPlainte>>("/plaintes/dossiers/", {
        // Filtres vides omis.
        params: Object.fromEntries(Object.entries(filtres).filter(([, valeur]) => valeur !== "" && valeur != null)),
      })).data,
    placeholderData: keepPreviousData,
  });
}

export function useEnregistrerDossier() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (saisie: SaisieAgent) => (await apiClient.post<RecuDossier>("/plaintes/dossiers/", saisie)).data,
    onSuccess: rafraichir,
  });
}

/** QR code (PNG) du formulaire public, général ou propre à un projet. */
export async function telechargerQrFormulaire(projet: number | null) {
  const response = await apiClient.get("/plaintes/qr/", {
    responseType: "blob",
    params: { projet: projet ?? undefined, origine: window.location.origin },
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", "qr_formulaire_plaintes.png");
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}

/** Adresse du formulaire public (à afficher, imprimer, partager). */
export const adresseFormulairePublic = (projet: number | null) =>
  `${window.location.origin}/plainte${projet ? `?projet=${projet}` : ""}`;

// Pages publiques (sans compte).

export interface FormulairePublic {
  disponible: boolean;
  nom: string;
  texte_information?: string;
  anonymat_autorise?: boolean;
  langues?: string[];
  projet_fixe?: boolean;
  types?: { id: number; nom: string; description: string }[];
  categories?: { id: number; nom: string; parent: number | null }[];
  projets?: { id: number; code: string; nom: string }[];
}

export function useFormulairePublic(projet: string | null) {
  return useQuery({
    queryKey: ["plaintes-public", "formulaire", projet],
    queryFn: async () =>
      (await apiClient.get<FormulairePublic>("/public/plaintes/formulaire/", { params: { projet: projet || undefined } })).data,
  });
}

export function useDeposerRetour() {
  return useMutation({
    mutationFn: async (saisie: SaisieRetour & { site_web: string }) =>
      (await apiClient.post<RecuDossier>("/public/plaintes/deposer/", saisie)).data,
  });
}

export function useSuiviPublic() {
  return useMutation({
    mutationFn: async (code: string) =>
      (await apiClient.post<{ numero: string; date_reception: string; statut: StatutDossier }>("/public/plaintes/suivi/", { code })).data,
  });
}

// --- Lot 3 : traitement --------------------------------------------------------------------

export function useDossierPlainte(id: number) {
  return useQuery({
    queryKey: [CLE, "dossiers", id],
    queryFn: async () => (await apiClient.get<DossierDetail>(`/plaintes/dossiers/${id}/`)).data,
    retry: false,
  });
}

/** Une opération de traitement ; renvoie le dossier à jour, ou {visible: false} s'il est devenu confidentiel. */
export function useOperationDossier(id: number) {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async ({ operation, donnees }: { operation: OperationDossier; donnees: Record<string, unknown> }) =>
      (await apiClient.post<DossierDetail | { numero: string; visible: false }>(`/plaintes/dossiers/${id}/${operation}/`, donnees)).data,
    onSuccess: rafraichir,
  });
}

export function useResponsablesPossibles(id: number, actif: boolean) {
  return useQuery({
    queryKey: [CLE, "dossiers", id, "responsables"],
    queryFn: async () =>
      (await apiClient.get<{ id: number; nom: string; role: string }[]>(`/plaintes/dossiers/${id}/responsables-possibles/`)).data,
    enabled: actif,
  });
}

export function usePossiblementLies(id: number) {
  return useQuery({
    queryKey: [CLE, "dossiers", id, "possiblement-lies"],
    queryFn: async () =>
      (await apiClient.get<{ id: number; numero: string; date_reception: string; statut: StatutDossier }[]>(
        `/plaintes/dossiers/${id}/possiblement-lies/`,
      )).data,
  });
}

/** Filtres enregistrés par l'utilisateur connecté. */
export interface VueEnregistree {
  id: number;
  nom: string;
  filtres: Partial<FiltresDossiers>;
}

export function useVuesEnregistrees() {
  return useQuery({
    queryKey: [CLE, "vues"],
    queryFn: async () => (await apiClient.get<VueEnregistree[]>("/plaintes-vues/")).data,
  });
}

export function useEnregistrerVue() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (vue: Omit<VueEnregistree, "id">) => (await apiClient.post<VueEnregistree>("/plaintes-vues/", vue)).data,
    onSuccess: rafraichir,
  });
}

export function useSupprimerVue() {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(`/plaintes-vues/${id}/`),
    onSuccess: rafraichir,
  });
}

// --- Lot 4 : calendrier des jours fériés --------------------------------------------------------

export interface JourFerie {
  id: number;
  date: string;
  libelle: string;
}

export const useJoursFeries = () => useListe<JourFerie>("jours-feries");
export const useEnregistrerJourFerie = () => useEnregistrer<JourFerie>("jours-feries");
export const useSupprimerJourFerie = () => useSupprimer("jours-feries");

// --- Lot 5 : circuit confidentiel ----------------------------------------------------------------

export type TypePrestataire = "MEDICAL" | "PSYCHOSOCIAL" | "JURIDIQUE" | "SECURITE" | "AUTRE";
export const TYPES_PRESTATAIRE: TypePrestataire[] = ["MEDICAL", "PSYCHOSOCIAL", "JURIDIQUE", "SECURITE", "AUTRE"];
export const libelleTypePrestataire = (t: TypePrestataire): string =>
  ({
    MEDICAL: voc("Médical"),
    PSYCHOSOCIAL: voc("Psychosocial"),
    JURIDIQUE: voc("Juridique"),
    SECURITE: voc("Sécurité et hébergement"),
    AUTRE: voc("Autre"),
  })[t];

export interface Prestataire {
  id: number;
  nom: string;
  type: TypePrestataire;
  contact: string;
  zone: string;
  actif: boolean;
}

export const usePrestataires = () => useListe<Prestataire>("prestataires");
export const useEnregistrerPrestataire = () => useEnregistrer<Prestataire>("prestataires");
export const useSupprimerPrestataire = () => useSupprimer("prestataires");

/** Signaler un dossier comme sensible (possible même en lecture seule) ; renvoie s'il reste visible. */
export function useSignalerSensible(id: number) {
  const rafraichir = useRafraichir();
  return useMutation({
    mutationFn: async (motif: string) =>
      (await apiClient.post<{ numero: string; visible: boolean }>(`/plaintes-signaler/${id}/`, { motif })).data,
    onSuccess: rafraichir,
  });
}

/** Fiche PDF en filigrane (motif et confirmation exigés pour un dossier confidentiel) ; l'export est tracé. */
export async function exporterFicheDossier(id: number, numero: string, motif: string, confirmation: boolean) {
  const reponse = await apiClient.post(`/plaintes/dossiers/${id}/exporter/`, { motif, confirmation }, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([reponse.data], { type: "application/pdf" }));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", `dossier_${numero}.pdf`);
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
}
