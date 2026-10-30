// Code d'un rôle : les rôles système (ADMIN, COORDO_GENERAL, CHARGE_SE,
// CHEF_PROJET, CHEF_SERVICE, ANIMATEUR_TERRAIN) plus ceux ajoutés par
// l'Administrateur (référentiel RoleUtilisateur).
export type Role = string;

export interface RoleUtilisateur {
  id: number;
  code: string;
  libelle: string;
  visibilite_globale: boolean;
  /** Peut choisir les blocs et graphiques du tableau de bord pour tous les utilisateurs. */
  peut_personnaliser_tableau_de_bord: boolean;
  /** Approuve les saisies et changements des projets qui l'exigent. */
  peut_approuver: boolean;
  systeme: boolean;
  nb_utilisateurs: number;
}

export type NiveauAcces = "LECTURE_SEULE" | "LECTURE_ECRITURE";

export type TypeStructureUtilisateur = "INTERNE" | "CONSORTIUM" | "MISE_EN_OEUVRE" | "PARTIE_PRENANTE" | "BAILLEUR";

/** Droit sur un module : masqué, consultation, ou création et modification. */
export type NiveauModule = "MASQUE" | "LECTURE" | "ECRITURE";

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  role_libelle: string;
  /** Calculé côté serveur (Administrateur, ou rôle ayant ce droit) — lecture seule. */
  peut_personnaliser_tableau_de_bord?: boolean;
  /** Calculé côté serveur (Administrateur, ou rôle ayant ce droit) — lecture seule. */
  peut_approuver?: boolean;
  /** Droits par module ({clé: niveau}) ; un module absent suit niveau_acces (voir utils/modules.ts). */
  acces_modules?: Record<string, NiveauModule>;
  /** Structure de l'utilisateur ; seul le lien correspondant au type est renseigné. */
  type_structure?: TypeStructureUtilisateur | "";
  structure_interne?: number | null;
  partenaire?: number | null;
  partie_prenante?: number | null;
  /** En clair, ex : « Partenaire de consortium — ONG X » (lecture seule). */
  structure_libelle?: string;
  niveau_acces: NiveauAcces;
  /** Langue de l'interface choisie (vide : celle de l'organisation). */
  langue: string;
  telephone: string;
  zones_affectees: number[];
  is_active: boolean;
}

export interface NiveauAdministratif {
  id: number;
  pays: string;
  nom_niveau: string;
  ordre: number;
  niveau_parent: number | null;
  niveau_parent_nom: string | null;
  saut_niveau_autorise: boolean;
  aide_code: string;
}

export interface Zone {
  id: number;
  nom: string;
  code: string;
  niveau_administratif: number;
  niveau_administratif_nom: string;
  pays: string;
  parent: number | null;
  parent_nom: string | null;
  /** Centre de la zone (carte des bénéficiaires) : calculé depuis les limites administratives, ou saisi. */
  latitude?: string | null;
  longitude?: string | null;
}

export interface Partenaire {
  id: number;
  nom: string;
  type: "BAILLEUR" | "MISE_EN_OEUVRE" | "CONSORTIUM";
  contact: string;
  email: string;
  telephone: string;
  /** Codes des projets où il est partenaire de mise en œuvre / du consortium (lecture seule). */
  projets_mise_en_oeuvre_codes?: string[];
  projets_consortium_codes?: string[];
  projets_bailleur_codes?: string[];
}

/** Direction, service, secteur… de l'organisation (arbre de profondeur libre). */
export interface StructureOrganisation {
  id: number;
  nom: string;
  sigle: string;
  type: string;
  parent: number | null;
  responsable: string;
  nb_projets: number;
  nb_utilisateurs: number;
  projets_resume: { id: number; code: string; nom: string; statut: string }[];
  utilisateurs_resume: { id: number; nom: string; role: string }[];
}

export interface CategoriePartiePrenante {
  id: number;
  nom: string;
}

export interface PartiePrenante {
  id: number;
  nom: string;
  categorie: number | null;
  categorie_nom: string | null;
  contact: string;
  email: string;
  telephone: string;
  description: string;
  nb_projets: number;
}

/** Rôle d'un partenaire dans un projet et éléments de la planification qu'il réalise. */
export interface PartenaireProjet {
  id: number;
  projet: number;
  partenaire: number;
  partenaire_nom: string;
  nature: "MISE_EN_OEUVRE" | "CONSORTIUM";
  chef_de_file: boolean;
  role: string;
  elements: number[];
  elements_libelles: string[];
}

export interface Bailleur {
  id: number;
  nom: string;
  type: "INSTITUTIONNEL" | "FONDATION" | "COOPERATION_BILATERALE" | "AUTRE";
  contact: string;
}

export interface Financement {
  id: number;
  projet: number;
  bailleur: number;
  bailleur_nom: string;
  montant_finance: string;
  montant_rallonges: string;
  montant_total: string;
  rallonges: RallongeFinancement[];
}

export interface RallongeFinancement {
  id: number;
  financement: number;
  montant: string;
  date: string;
  motif: string;
  saisi_par_nom: string;
  created_at: string;
}

/** Maillon de la chaîne des documents stratégiques (Cadre stratégique, Programme, Pilier…) : une rubrique du menu. */
export interface TypeDocument {
  id: number;
  nom: string;
  nom_pluriel: string;
  /** 1 = maillon le plus haut. */
  ordre: number;
  icone: string;
  nombre_documents: number;
}

export interface CadreStrategique {
  id: number;
  nom: string;
  description: string;
  created_at: string;
  structures?: number[];
  structures_noms?: string[];
  parties_prenantes?: number[];
  parties_prenantes_noms?: string[];
  /** Maillon de la chaîne (vide = premier maillon). */
  type_document?: number | null;
  type_document_nom?: string | null;
  /** Rattachement à un document d'un maillon au-dessus, et éventuellement à l'un de ses éléments. */
  document_parent?: number | null;
  document_parent_nom?: string | null;
  document_parent_type?: string | null;
  element_parent?: number | null;
  element_parent_nom?: string | null;
  /** Autres éléments du document parent, pour information (seul element_parent compte). */
  elements_parents_secondaires?: number[];
  elements_parents_secondaires_noms?: string[];
  documents_rattaches?: {
    id: number;
    nom: string;
    type_document_nom: string | null;
    element_parent_nom: string | null;
    elements_secondaires_noms?: string[];
  }[];
  /** Sauts de maillons, rattachement manquant… */
  alertes_chaine?: string[];
  /** Fiche du document, comme celle d'un projet (tout facultatif). */
  code?: string;
  budget_total?: string;
  fonds_propres?: string;
  date_debut?: string | null;
  date_fin?: string | null;
  statut?: StatutProjet | "";
  type_mise_en_oeuvre?: "DIRECT" | "CONSORTIUM";
  responsable_nom?: string;
  utilisateurs_affectes?: number[];
  utilisateurs_affectes_noms?: string[];
  partenaire_mise_en_oeuvre?: number | null;
  partenaire_mise_en_oeuvre_nom?: string | null;
  partenaires_consortium?: number[];
  partenaires_consortium_noms?: string[];
  pays?: string[];
  tout_le_pays?: boolean;
  zones?: number[];
  zones_noms?: string[];
  cible_totale?: number | null;
  cible_hommes?: number | null;
  cible_femmes?: number | null;
  cible_jeunes?: number | null;
  cible_pdi?: number | null;
  elements_capitalisation?: string;
  /** Bailleurs du document (lecture). */
  financements?: { id: number; bailleur: number; bailleur_nom: string; montant: string }[];
  /** Bailleurs à enregistrer (écriture) : remplace toute la liste ; un nom inconnu crée le bailleur. */
  bailleurs?: { nom: string; montant: number }[];
}

export interface ImportChaineResultat {
  maillons_crees: number;
  documents_crees: number;
  documents_mis_a_jour: number;
  elements_crees: number;
  elements_mis_a_jour: number;
  erreurs: { ligne: number; message: string }[];
  avertissements: { ligne: number; message: string }[];
}

export interface RecapCadreStrategique {
  budget_total: number;
  nombre_activites_total: number;
  nombre_indicateurs_total: number;
  taux_execution_physique_moyen: number | null;
  taux_execution_financiere_moyen: number | null;
  projets: {
    id: number;
    code: string;
    nom: string;
    statut: StatutProjet;
    date_debut: string;
    date_fin: string;
    chef_de_projet_nom: string;
    /** Élément du document auquel le projet arrive, et document par lequel il arrive (chaîne). */
    element_strategique?: number | null;
    element_strategique_nom?: string | null;
    via_document?: string | null;
    bailleur_nom: string | null;
    budget_total: string;
    budget_activites_alloue_total: string;
    budget_activites_realise_total: string;
    financement_bailleurs_total: string;
    taux_execution_physique: number | null;
    taux_execution_financiere: number | null;
    nombre_activites: number;
    nombre_indicateurs: number;
    activites: {
      id: number;
      code: string;
      libelle: string;
      statut: string;
      taux_realisation: number | null;
      quantite_realisee: string | null;
      quantite_prevue: string | null;
      unite_quantite: string;
      budget_alloue: string | null;
      budget_realise: string | null;
    }[];
    indicateurs: { id: number; libelle: string; valeur_realisee: string; valeur_cible: string; unite: string }[];
  }[];
}

/** Données de l'onglet « Axes & budgets » d'un cadre stratégique. */
export interface RecapAxesCadreStrategique {
  elements: {
    id: number;
    code: string;
    nom: string;
    type_niveau: number;
    ordre_niveau: number;
    element_parent: number | null;
  }[];
  activites: {
    id: number;
    code: string;
    libelle: string;
    projet_id: number;
    projet_code: string;
    /** Élément stratégique rattaché (null : activité non rattachée). */
    axe: number | null;
    budget_alloue: string | null;
    budget_realise: string | null;
    /** Part comptée dans les totaux (0 quand le détail est saisi en dessous). */
    budget_alloue_compte: string | number | null;
    budget_realise_compte: string | number | null;
    /** Éléments au-dessus de cette activité dans la planification de son projet. */
    ancetres: number[];
    taux_physique: number | null;
    taux_financier: number | null;
    date_debut: string | null;
    date_fin: string | null;
  }[];
}

export interface TypeNiveau {
  id: number;
  cadre_strategique: number;
  nom_niveau: string;
  ordre: number;
  niveau_parent: number | null;
  niveau_parent_nom: string | null;
  saut_niveau_autorise: boolean;
  aide_code: string;
}

export interface ElementStrategique {
  id: number;
  type_niveau: number;
  type_niveau_nom: string;
  element_parent: number | null;
  element_parent_nom: string | null;
  code: string;
  nom: string;
  description: string;
  /** Autres éléments du niveau supérieur auxquels celui-ci contribue aussi (informatif, non compté). */
  parents_secondaires?: number[];
  parents_secondaires_noms?: string[];
  structures?: number[];
  structures_noms?: string[];
  parties_prenantes?: number[];
  parties_prenantes_noms?: string[];
  /** Document auquel appartient l'élément. */
  cadre_strategique?: number;
  /** Élément d'un document d'un maillon au-dessus auquel celui-ci (et ce qui est en dessous) contribue. */
  contribue_a?: number | null;
  contribue_a_nom?: string | null;
  alertes_chaine?: string[];
}

export interface Intervenant {
  id: number;
  nom: string;
  prenom: string;
  fonction: string;
  contact: string;
  utilisateur: number | null;
  utilisateur_nom: string | null;
  projets_associes: number[];
  activites_associees: number[];
}

export type StatutProjet = "EN_PREPARATION" | "EN_COURS" | "CLOTURE";
export type TypeMiseEnOeuvre = "DIRECT" | "CONSORTIUM";
export type StatutActivite = "NON_REALISEE" | "EN_COURS" | "REALISEE";

export interface SousActivite {
  id: number;
  activite: number;
  libelle: string;
  axe_strategique: number | null;
  axe_strategique_libelle: string | null;
  quantite_prevue: string | null;
  quantite_realisee: string | null;
  unite_quantite: string;
  date_debut: string | null;
  date_fin: string | null;
  statut: "PLANIFIEE" | "EN_COURS" | "TERMINEE";
  /** Méthode « tâches pondérées » : poids de la tâche et niveau d'achèvement saisi (0 à 100). */
  poids: string | null;
  avancement: string | null;
  /** Attributs libres de l'organisation (« Responsable », « Lieu »…). */
  attributs: Record<string, string>;
}

export type MethodeCalcul = "QUANTITE" | "TACHES" | "JALONS" | "LIVRABLES" | "BINAIRE" | "MANUELLE";
export type MethodeAgregation = "MOYENNE" | "PONDEREE_BUDGET" | "PONDEREE_POIDS";

export interface JalonLivrable {
  id: number;
  activite: number;
  type: "JALON" | "LIVRABLE";
  libelle: string;
  poids: string | null;
  date_prevue: string | null;
  achevement: string;
  valide: boolean;
  valide_par: number | null;
  valide_par_nom: string | null;
  date_validation: string | null;
}

export interface TauxManuel {
  id: number;
  activite: number;
  taux: string;
  date: string;
  saisi_par: number | null;
  saisi_par_nom: string | null;
  commentaire: string;
}

/** Réglage de l'organisation, hérité par les projets qui ne fixent pas le leur. */
export interface ParametresCalcul {
  methode_calcul: MethodeCalcul;
  methode_agregation: MethodeAgregation;
  plafonner_agregation: boolean;
}

/** Ce qui est fermé hors période de rapportage. */
export type PerimetreFermeture = "REALISATIONS" | "TOUT";

export interface ParametresRapportage {
  controle_actif: boolean;
  perimetre: PerimetreFermeture;
}

/** Période pendant laquelle la saisie est ouverte : tous les projets (projet null) ou un seul. */
export interface FenetreRapportage {
  id: number;
  projet: number | null;
  projet_code: string | null;
  libelle: string;
  date_debut: string;
  date_fin: string;
}

export type SaisieProjet = "HERITE" | "OUVERTE" | "FERMEE";

export interface Equipe {
  id: number;
  nom: string;
  membres: number[];
  membres_noms: string[];
  date_debut_contrat: string | null;
  date_fin_contrat: string | null;
}

/**
 * Élément de la planification d'un projet, à n'importe quel niveau : les niveaux
 * sont libres (« Objectif général », « Résultat », « Pilier », « Activité »...) et
 * nommés par projet (NiveauActivite) ; `enfants` porte le niveau suivant.
 */
export interface Activite {
  id: number;
  projet: number;
  activite_parent: number | null;
  code_activite: string;
  libelle: string;
  /** Attributs libres de l'organisation (« Responsable », « Lieu »…). */
  attributs: Record<string, string>;
  description: string;
  statut: StatutActivite;
  commentaire: string;
  axe_strategique: number | null;
  axe_strategique_libelle: string | null;
  /** Autres éléments stratégiques auxquels cet élément contribue aussi (informatif, non compté). */
  axes_strategiques_secondaires?: number[];
  axes_strategiques_secondaires_noms?: string[];
  /** Services de l'organisation chargés de cette partie du projet. */
  structures?: number[];
  structures_noms?: string[];
  /** Partenaires chargés de cet élément (onglet Partenaires du projet). */
  partenaires_charges_noms?: string[];
  budget_alloue: string | null;
  budget_realise: string | null;
  valeur_reference: string | null;
  quantite_prevue: string | null;
  quantite_realisee: string | null;
  unite_quantite: string;
  date_debut: string | null;
  date_fin: string | null;
  date_debut_reelle: string | null;
  date_fin_reelle: string | null;
  nb_jours_planifies: number | null;
  date_rappel: string | null;
  responsables: number[];
  responsables_noms: string[];
  responsable: number | null;
  responsable_compte_nom: string | null;
  equipe_responsable: number | null;
  equipe_responsable_nom: string | null;
  sous_activites: SousActivite[];
  enfants: Activite[];
  taux_realisation: number | null;
  /** Vides = hérités de l'élément parent, du projet, puis de l'organisation. */
  methode_calcul: MethodeCalcul | "";
  methode_agregation: MethodeAgregation | "";
  poids: string | null;
  /** Méthode réellement appliquée, ou « AGREGATION » pour un élément qui a des éléments en dessous. */
  methode_calcul_effective: MethodeCalcul | "AGREGATION";
  taux_avertissements: string[];
  /** Contrôle d'un budget dont le détail est saisi en dessous (règle sans double compte). */
  budget_avertissements: string[];
  jalons_livrables: JalonLivrable[];
  taux_execution_financiere: number | null;
  alerte_retard: boolean;
}

export interface NiveauActivite {
  id: number;
  projet: number;
  profondeur: number;
  nom_niveau: string;
}

export interface Projet {
  id: number;
  nom: string;
  code: string;
  pays: string[];
  partenaire_bailleur: number | null;
  partenaire_bailleur_nom: string | null;
  partenaire_mise_en_oeuvre: number | null;
  partenaire_mise_en_oeuvre_nom: string | null;
  partenaires_consortium: number[];
  partenaires_consortium_noms: string[];
  budget_total: string;
  fonds_propres: string;
  financement_bailleurs_total: string;
  date_debut: string;
  date_fin: string;
  date_rappel: string | null;
  statut: StatutProjet;
  type_mise_en_oeuvre: TypeMiseEnOeuvre;
  zones: number[];
  /** Intervention sur tout le territoire du ou des pays : pas de zones détaillées. */
  tout_le_pays: boolean;
  /** Ouverture de la saisie (périodes de rapportage), réglée par l'administrateur. */
  saisie: SaisieProjet;
  perimetre_fermeture: PerimetreFermeture | "";
  /** Circuit d'approbation du projet (réglé par l'administrateur). */
  approbation_realisations: boolean;
  approbation_planification: boolean;
  /** Saisie ouverte ou fermée aujourd'hui, avec l'explication à afficher. */
  etat_saisie: { ouverte: boolean; perimetre: PerimetreFermeture; message: string };
  cadre_strategique: number | null;
  cadre_strategique_nom: string | null;
  /** Élément du cadre dont relève le projet (programme, axe, pilier...), à n'importe quel niveau. */
  element_strategique: number | null;
  element_strategique_libelle: string | null;
  /** Autres éléments stratégiques auxquels le projet contribue aussi (informatif, non compté). */
  elements_strategiques_secondaires: number[];
  elements_strategiques_secondaires_noms: string[];
  structures: number[];
  structures_noms: string[];
  parties_prenantes: number[];
  parties_prenantes_noms: string[];
  /** Services qui travaillent sur le projet (en entier ou sur une partie) et leurs membres. */
  services_detail?: {
    id: number;
    nom: string;
    type: string;
    tout_le_projet: boolean;
    parties: string[];
    membres: string[];
  }[];
  chef_de_projet_nom: string;
  utilisateurs_affectes: number[];
  cible_totale: number | null;
  cible_hommes: number | null;
  cible_femmes: number | null;
  cible_jeunes: number | null;
  cible_pdi: number | null;
  elements_capitalisation: string;
  methode_calcul: MethodeCalcul | "";
  methode_agregation: MethodeAgregation | "";
  /** Ordre des attributs libres de la planification (colonnes du fichier importé, puis ajoutés). */
  ordre_attributs: string[];
  /** Éléments de premier niveau de la planification, chacun avec ses `enfants`. */
  activites: Activite[];
}

/** Projet tel que renvoyé par la liste : sans planification ni services (voir useProjets). */
export type ProjetResume = Omit<Projet, "activites" | "services_detail">;

export type ProjetInput = Omit<
  Projet,
  | "id"
  | "partenaire_bailleur_nom"
  | "partenaire_mise_en_oeuvre_nom"
  | "partenaires_consortium_noms"
  | "activites"
  | "financement_bailleurs_total"
  | "cadre_strategique_nom"
  | "element_strategique_libelle"
  | "etat_saisie"
  | "elements_strategiques_secondaires_noms"
  | "structures_noms"
  | "parties_prenantes_noms"
  | "services_detail"
>;

export interface ParametresAlerte {
  seuil_echeance_jours: number;
}

export interface PalierAlerte {
  id: number;
  projet: number | null;
  indicateur: number | null;
  activite: number | null;
  borne_min: number;
  libelle: string;
  couleur: string;
}

export interface PorteeAlerte {
  projetId?: number | null;
  indicateurId?: number | null;
  activiteId?: number | null;
}

export interface PalierAlerteInput {
  borne_min: number;
  libelle: string;
  couleur: string;
}

export interface PaliersAlerteResolus {
  personnalise: boolean;
  paliers: PalierAlerte[];
}

export interface ValeurIndicateur {
  id: number;
  indicateur: number;
  periode_debut: string;
  periode_fin: string;
  valeur_realisee: string;
  date_saisie: string;
  saisi_par: number;
  saisi_par_nom: string;
  commentaire: string;
  taux_realisation: number;
}

export interface TranchePlanifiee {
  id: number;
  /** Période de planification (onglet « Planification par période »), ou null pour une tranche libre. */
  periode: number | null;
  activite: number | null;
  activite_libelle: string | null;
  sous_activite: number | null;
  sous_activite_libelle: string | null;
  indicateur: number | null;
  indicateur_libelle: string | null;
  libelle: string;
  periode_debut: string;
  periode_fin: string;
  cible: string | null;
  budget: string | null;
  date_debut_prevue: string | null;
  date_fin_prevue: string | null;
  commentaire: string;
  realise: string | null;
  taux: number | null;
  budget_realise: string | null;
  taux_financier: number | null;
  statut: "ATTEINTE" | "EN_RETARD" | "EN_COURS";
}

/** Objectifs d'un élément sur une période : définis par l'utilisateur (« saisi ») ou pas encore (« a_definir »). */
export type SourceValeurPeriode = "saisi" | "a_definir";

/** Valeurs d'un élément sur une période, telles que calculées par /periodes-planification/{id}/valeurs/. */
export interface ValeurElementPeriode {
  type: "activite" | "sous_activite" | "indicateur";
  id: number;
  source: SourceValeurPeriode;
  tranche_id: number | null;
  /** Les dates globales de l'élément recoupent-elles la période ? (null : élément sans dates) */
  dans_dates_globales: boolean | null;
  prevu_quantite: number | null;
  prevu_budget: number | null;
  debut_prevu: string | null;
  fin_prevue: string | null;
  /** Quantité réalisée sur la période ; en mode « avancement » : avancement atteint en fin de période (%). */
  realise_quantite: number | null;
  taux: number | null;
  budget_realise: number | null;
  taux_financier: number | null;
  statut: string;
  commentaire: string;
  /** Saisies comptées dans le réalisé de la période (ordre chronologique). */
  saisies: SaisiePeriode[];
}

export interface SaisiePeriode {
  id: number;
  periode_debut: string;
  periode_fin: string;
  quantite: string | null;
  budget: string | null;
  statut: string;
  commentaire: string;
}

/** Ligne de l'arborescence (activité/sous-activité) avec ses valeurs sur la période. */
export interface LignePeriode extends ValeurElementPeriode {
  parent_id: number | null;
  /** Méthode appliquée ; « avancement » : objectif et réalisé en % d'avancement en fin de période. */
  methode: MethodeCalcul | "AGREGATION";
  mode: "quantite" | "avancement";
  niveau: string;
  profondeur: number;
  code: string;
  libelle: string;
  unite: string;
  global_quantite: string | null;
  global_budget: string | null;
}

export interface IndicateurPeriode extends ValeurElementPeriode {
  libelle: string;
  unite: string;
  valeur_cible: string;
}

export interface ValeursPeriode {
  lignes: LignePeriode[];
  indicateurs: IndicateurPeriode[];
  totaux: {
    budget_prevu: number;
    budget_realise: number;
    nb_definis: number;
    nb_elements: number;
    /** Moyenne des taux des activités dont l'objectif de la période est défini. */
    taux_physique: number | null;
    taux_financier: number | null;
  };
}

export interface PeriodePlanification {
  id: number;
  projet: number;
  libelle: string;
  date_debut: string;
  date_fin: string;
}

export interface Indicateur {
  id: number;
  libelle: string;
  unite: string;
  valeur_reference: string | null;
  valeur_reference_date: string | null;
  valeur_cible: string;
  frequence_collecte: "MENSUELLE" | "TRIMESTRIELLE" | "SEMESTRIELLE" | "ANNUELLE";
  projet: number | null;
  projet_nom: string | null;
  projet_rattache_nom: string | null;
  activite: number | null;
  activite_libelle: string | null;
  elements_strategiques: number[];
  elements_strategiques_libelles: string[];
  valeurs: ValeurIndicateur[];
  taux_realisation_actuel: number;
  palier_actuel: { id: number; libelle: string; couleur: string; borne_min: number } | null;
}

export interface StatutParticulier {
  id: number;
  code: string;
  libelle: string;
}

export interface TypeActiviteBeneficiaire {
  id: number;
  code: string;
  libelle: string;
}

export interface ParticipationProjet {
  id: number;
  beneficiaire: number;
  beneficiaire_nom: string;
  projet: number;
  projet_nom: string;
  activite: number | null;
  activite_nom: string | null;
  sous_activite: number | null;
  sous_activite_nom: string | null;
  date_inscription: string;
  role_dans_projet: string;
}

export interface Beneficiaire {
  id: number;
  /** Identifiant unique attribué automatiquement (BEN-000123), repris dans le QR code. */
  identifiant: string;
  nom: string;
  prenom: string;
  sexe: "F" | "M";
  date_naissance: string | null;
  age: number | null;
  tranche_age: string | null;
  telephone: string;
  numero_piece_identite: string;
  type_piece: string;
  pays: string;
  zone: number | null;
  zone_nom: string | null;
  latitude: string | null;
  longitude: string | null;
  /** Réponses aux variables personnalisées : {id de la variable: valeur}. */
  reponses: Record<string, string | number | boolean | string[]>;
  statuts_particuliers: number[];
  types_activite: number[];
  participations: ParticipationProjet[];
}

export type TypeVariableBeneficiaire = "TEXTE" | "NOMBRE" | "DATE" | "OUI_NON" | "CHOIX" | "CHOIX_MULTIPLE";

/** Information à collecter sur les bénéficiaires, pour tous les projets ou certains (sinon « NA »). */
export interface VariableBeneficiaire {
  id: number;
  libelle: string;
  type: TypeVariableBeneficiaire;
  choix: string[];
  unite: string;
  aide: string;
  tous_les_projets: boolean;
  projets: number[];
  projets_codes: string[];
  ordre: number;
  nb_reponses: number;
}

export interface ImportBeneficiairesResultat {
  crees: number;
  erreurs: { ligne: number; message: string }[];
  avertissements: { ligne: number; message: string }[];
  doublons_detectes: number;
}

export interface ImportStructurationResultat {
  niveaux_crees: number;
  elements_crees: number;
  elements_mis_a_jour: number;
  erreurs: { ligne: number; message: string }[];
  /** Ex : niveau inséré au-dessus d'un niveau existant (anciens éléments gardant leur rattachement). */
  avertissements: { ligne: number; message: string }[];
  /** Le fichier avait une feuille « Fiche » (programme, pilier…) : fiche et bailleurs mis à jour. */
  fiche_mise_a_jour?: boolean;
}

export interface ImportProjetResultat {
  projet_id: number | null;
  projet_code: string | null;
  /** Éléments de planification créés, tous niveaux confondus. */
  elements_crees: number;
  /** Noms des niveaux lus dans le fichier, du plus haut au plus bas. */
  niveaux: string[];
  sous_activites_creees: number;
  erreurs: { ligne: number; message: string }[];
  avertissements: { ligne: number; message: string }[];
}

export interface ImportIndicateursResultat {
  crees: number;
  erreurs: { ligne: number; message: string }[];
  avertissements: { ligne: number; message: string }[];
}

export interface ImportPlanificationCompleteResultat {
  cadre_strategique_id: number | null;
  cadre_strategique_nom: string | null;
  elements_strategiques_crees: number;
  projet_id: number | null;
  projet_code: string | null;
  elements_crees: number;
  niveaux: string[];
  sous_activites_creees: number;
  indicateurs_crees: number;
  beneficiaires_crees: number;
  doublons_detectes: number;
  erreurs: { ligne: number; message: string }[];
  avertissements: { ligne: number; message: string }[];
}

export interface SignalementDoublon {
  id: number;
  beneficiaire_1: number;
  beneficiaire_1_nom: string;
  beneficiaire_2: number;
  beneficiaire_2_nom: string;
  score: number | null;
  methode: "PIECE_IDENTITE" | "SIMILARITE";
  /** Pourquoi la paire est signalée (« Même téléphone »…). */
  motifs?: string[];
  statut: "SIGNALE" | "ECARTE" | "FUSIONNE";
  traite_par: number | null;
  date_traitement: string | null;
}

export interface PieceJustificative {
  id: number;
  fichier: string;
  nom: string;
  type_document: string;
  uploaded_by: number;
  uploaded_by_nom: string;
  valeur_indicateur: number | null;
  created_at: string;
}

export type TypeNotification =
  | "INDICATEUR_ALERTE"
  | "RAPPORT_SOUMIS"
  | "RAPPORT_VALIDE"
  | "DOUBLON_SIGNALE"
  | "ECHEANCE_ACTIVITE"
  | "ACTIVITE_MODIFIEE";

export interface AppNotification {
  id: number;
  type: TypeNotification;
  titre: string;
  message: string;
  lien: string;
  lu: boolean;
  date_lecture: string | null;
  created_at: string;
}

export interface Dossier {
  id: number;
  nom: string;
  projet: number | null;
  parent: number | null;
  cree_par: number;
  cree_par_nom: string;
}

export interface DocumentVersion {
  id: number;
  document: number;
  fichier: string;
  version: number;
  uploaded_by: number;
  uploaded_by_nom: string;
  commentaire: string;
  created_at: string;
}

export interface GedDocument {
  id: number;
  nom: string;
  dossier: number | null;
  projet: number | null;
  activite: number | null;
  activite_nom: string | null;
  sous_activite: number | null;
  sous_activite_nom: string | null;
  type_document: string;
  description: string;
  cree_par: number;
  cree_par_nom: string;
  derniere_version: DocumentVersion | null;
  nombre_versions: number;
  created_at: string;
}

export interface RepartitionPalier {
  libelle: string;
  couleur: string;
  count: number;
}

export interface DashboardConsolide {
  nombre_projets: number;
  budget_total: number;
  nombre_beneficiaires: number;
  indicateurs_par_statut: RepartitionPalier[];
  zones_couvertes: { niveau: string; count: number }[];
  projets_par_statut: Partial<Record<StatutProjet, number>>;
  activites_par_statut: Partial<Record<StatutActivite, number>>;
  beneficiaires_par_sexe: Partial<Record<"F" | "M", number>>;
  /** Clé : code du projet. */
  beneficiaires_par_projet: Record<string, number>;
  execution_par_projet: { code: string; physique: number | null; financier: number | null }[];
  activites_par_projet: ({ code: string } & Partial<Record<StatutActivite, number>>)[];
  beneficiaires_par_projet_sexe: { code: string; F?: number; M?: number }[];
  /** Dépenses cumulées par mois ; une clé par code de projet. */
  depenses_par_mois: ({ mois: string } & Record<string, number | string>)[];
  /** Nouveaux bénéficiaires inscrits par mois (non cumulé) ; une clé par code de projet. */
  inscriptions_par_mois: ({ mois: string } & Record<string, number | string>)[];
  projets: { id: number; code: string; nom: string; statut: StatutProjet; budget_total: string }[];
  projets_par_pays: LigneRepartitionProjets[];
  projets_par_zone: { niveau: string; zones: LigneRepartitionProjets[] }[];
  budget_detail: {
    total: number;
    fonds_propres: number;
    financements_bailleurs: number;
    alloue_activites: number;
    depense_activites: number;
    par_projet: { code: string; nom: string; total: number; fonds_propres: number; financements_bailleurs: number }[];
  };
  projets_par_bailleur: LigneRepartitionProjets[];
  projets_par_consortium: LigneRepartitionProjets[];
  projets_par_mise_en_oeuvre: LigneRepartitionProjets[];
  cibles: {
    totale: number;
    femmes: number;
    hommes: number;
    jeunes: number;
    pdi: number;
    par_projet: { code: string; totale: number; femmes: number; hommes: number; jeunes: number; pdi: number }[];
  };
}

/** Configuration du tableau de bord commune à tous les utilisateurs. */
export interface ConfigurationTableauDeBord {
  blocs_masques: string[];
  types_graphiques: Record<string, string>;
  peut_modifier: boolean;
}

/** Une ligne de répartition du tableau de bord : nombre de projets et montant (FCFA). */
export interface LigneRepartitionProjets {
  libelle: string;
  nombre: number;
  montant: number;
  projets: string[];
}

/** Filtres du tableau de bord consolidé (voir backend apps/dashboard/filtres.py). */
export interface FiltresDashboard {
  annee?: number;
  date_debut?: string;
  date_fin?: string;
  periode?: "actifs" | "demarres" | "demarres_fin_prevue" | "demarres_termines";
  statuts?: StatutProjet[];
}

export interface DashboardProjet {
  projet: { id: number; code: string; nom: string; statut: StatutProjet };
  nombre_elements_planification: number;
  nombre_beneficiaires: number;
  indicateurs: {
    id: number;
    libelle: string;
    taux_realisation: number;
    palier_actuel: { libelle: string; couleur: string } | null;
  }[];
  indicateurs_par_statut: RepartitionPalier[];
  zones_couvertes: { niveau: string; count: number }[];
}

export interface Echeance {
  type: "ACTIVITE" | "SOUS_ACTIVITE" | "PROJET";
  id: number;
  libelle: string;
  projet_id: number;
  projet_nom: string;
  date_fin: string;
  en_retard: boolean;
  est_rappel: boolean;
  lien: string;
}

export interface PointSuivi {
  id: number;
  activite: number | null;
  activite_libelle: string | null;
  sous_activite: number | null;
  sous_activite_libelle: string | null;
  periode_debut: string;
  periode_fin: string;
  quantite_realisee: string | null;
  budget_realise: string | null;
  statut: string;
  commentaire: string;
  saisi_par: number;
  saisi_par_nom: string;
  date_saisie: string;
}

export interface SuiviHistoriquePoint {
  id: number;
  periode_debut: string;
  periode_fin: string;
  quantite_realisee: string | null;
  quantite_cumulee: string | null;
  budget_realise?: string | null;
  budget_cumule?: string | null;
  statut: string;
  commentaire: string;
  /** Projets avec approbation : une saisie non approuvée est listée mais ne compte pas. */
  etat_approbation?: "APPROUVEE" | "EN_ATTENTE" | "REJETEE";
  motif_rejet?: string;
}

export interface SuiviHistoriqueValeurIndicateur {
  id: number;
  periode_debut: string;
  periode_fin: string;
  valeur_realisee: string;
  valeur_cumulee: string;
  commentaire: string;
  taux: number;
  etat_approbation?: "APPROUVEE" | "EN_ATTENTE" | "REJETEE";
  motif_rejet?: string;
}

export interface SuiviDashboardIndicateur {
  id: number;
  libelle: string;
  unite: string;
  valeur_reference: string | null;
  valeur_cible: string;
  taux_actuel: number;
  palier_actuel: { id: number; libelle: string; couleur: string; borne_min: number } | null;
  periode_debut_planifiee: string | null;
  periode_fin_planifiee: string | null;
  historique: SuiviHistoriqueValeurIndicateur[];
}

export interface SuiviDashboardSousActivite {
  id: number;
  libelle: string;
  statut: string;
  quantite_prevue: string | null;
  unite_quantite: string;
  date_debut: string | null;
  date_fin: string | null;
  historique: SuiviHistoriquePoint[];
}

export interface SuiviDashboardActivite {
  id: number;
  code_activite: string;
  libelle: string;
  statut: StatutActivite;
  valeur_reference: string | null;
  quantite_prevue: string | null;
  unite_quantite: string;
  budget_alloue: string | null;
  date_debut: string | null;
  date_fin: string | null;
  taux_realisation: number | null;
  /** Méthode réglée sur l'activité (vide = héritée) et méthode réellement appliquée. */
  methode_calcul: MethodeCalcul | "";
  methode_calcul_effective: MethodeCalcul | "AGREGATION";
  taux_avertissements: string[];
  /** Saisies non encore comptées : en attente d'approbation, ou rejetées. */
  saisies_en_attente: number;
  saisies_rejetees: number;
  taux_execution_financiere: number | null;
  palier_actuel: { id: number; libelle: string; couleur: string; borne_min: number } | null;
  sous_activites: SuiviDashboardSousActivite[];
  historique: SuiviHistoriquePoint[];
}

export interface SuiviDashboard {
  projet: { id: number; code: string; nom: string; statut: StatutProjet };
  taux_execution_physique_global: number | null;
  taux_execution_financiere_global: number | null;
  statut_global: "ATTEINT" | "EN_RETARD" | "EN_COURS";
  indicateurs: SuiviDashboardIndicateur[];
  activites: SuiviDashboardActivite[];
}

export interface HistoriqueEntree {
  date: string;
  utilisateur: string | null;
  type: string;
  changements: { champ: string; ancienne_valeur: unknown; nouvelle_valeur: unknown }[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ------------------------------------------------------------------ approbations

export type EtatApprobation = "APPROUVEE" | "EN_ATTENTE" | "REJETEE";

export interface SaisieAApprouver {
  type: "point" | "valeur" | "taux";
  id: number;
  projet_id: number | null;
  projet_code: string;
  element: string;
  periode: string;
  valeur: string;
  budget: string | null;
  statut: string;
  commentaire: string;
  saisi_par_nom: string;
  date: string;
  etat: EtatApprobation;
  motif_rejet: string;
}

export interface DemandeModification {
  id: number;
  projet_id: number;
  projet_code: string;
  cible: string;
  action: "CREATION" | "MODIFICATION" | "SUPPRESSION";
  action_libelle: string;
  libelle: string;
  changements: { champ: string; avant: unknown; apres: unknown }[];
  /** Ajout : valeurs demandées. */
  valeurs: { champ: string; valeur: unknown }[];
  etat: EtatApprobation;
  motif_rejet: string;
  demandeur_nom: string;
  date: string;
}

export interface Approbations {
  peut_approuver: boolean;
  saisies: SaisieAApprouver[];
  demandes: DemandeModification[];
}


export type NiveauRisque = "FAIBLE" | "MOYEN" | "ELEVE" | "CRITIQUE";
export type StatutRisque = "ACTIF" | "SURVENU" | "MAITRISE" | "CLOS";

export interface EvaluationRisque {
  id: number;
  risque: number;
  date: string;
  probabilite: number;
  impact: number;
  niveau: NiveauRisque;
  statut: StatutRisque;
  actions_menees: string;
  commentaire: string;
  saisi_par_nom: string;
  created_at: string;
}

export interface Risque {
  id: number;
  projet: number;
  code: string;
  libelle: string;
  description: string;
  nature: "INTERNE" | "EXTERNE";
  categorie: string;
  element: number | null;
  element_libelle: string;
  probabilite: number;
  impact: number;
  criticite: number;
  niveau: NiveauRisque;
  mesures_attenuation: string;
  plan_contingence: string;
  responsable: number | null;
  responsable_nom: string;
  statut: StatutRisque;
  date_identification: string;
  date_prochaine_revue: string | null;
  evaluations: EvaluationRisque[];
}
