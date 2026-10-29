/**
 * Vocabulaire de l'organisation, choisi par l'Administrateur (« Personnaliser le menu ») :
 * chaque terme (« projet », « cadre stratégique »...) peut être remplacé par celui de
 * l'organisation (« action », « programme »...), avec son pluriel et son genre.
 *
 * `voc` adapte un texte de l'INTERFACE — jamais les données saisies : on l'applique aux
 * textes écrits dans le code, et, en gabarit (voc`… ${x} …`), seulement aux parties fixes.
 * Il garde les majuscules et accorde les petits mots qui précèdent le terme (un/une,
 * le/la/l', ce/cette, du/de la/de l'...). Les adjectifs placés après ne sont pas accordés.
 *
 * Doit rester identique à backend/apps/core/vocabulaire.py.
 *
 * Dans une autre langue que le français, `voc` (alias `t`) traduit le texte (utils/i18n).
 */
import { langue, traduire } from "./i18n";

export interface ChoixTerme {
  singulier: string;
  pluriel: string;
  feminin: boolean;
}
export type Vocabulaire = Record<string, ChoixTerme>;

/** [clé, singulier par défaut, pluriel par défaut, féminin par défaut] */
export const TERMES: [string, string, string, boolean][] = [
  ["tableau_de_bord", "tableau de bord", "tableaux de bord", false],
  ["planification", "planification", "planifications", true],
  ["cadre_strategique", "cadre stratégique", "cadres stratégiques", false],
  ["projet", "projet", "projets", false],
  ["indicateur", "indicateur", "indicateurs", false],
  ["suivi", "suivi", "suivis", false],
  ["beneficiaire", "bénéficiaire", "bénéficiaires", false],
  ["doublon", "doublon", "doublons", false],
  ["zone_administrative", "zone administrative", "zones administratives", true],
  ["document", "document", "documents", false],
  ["utilisateur", "utilisateur", "utilisateurs", false],
  ["alerte", "alerte", "alertes", true],
];

const VOYELLE = /^[aeiouyhàâäéèêëîïôöùûüœ]/i;

// Petit mot qui précède le terme → [forme masculine, forme féminine, forme devant voyelle]
const DETERMINANTS: Record<string, [string, string, string | null]> = {
  un: ["un", "une", null],
  une: ["un", "une", null],
  le: ["le", "la", "l'"],
  la: ["le", "la", "l'"],
  "l'": ["le", "la", "l'"],
  ce: ["ce", "cette", "cet"],
  cet: ["ce", "cette", "cet"],
  cette: ["ce", "cette", "cet"],
  du: ["du", "de la", "de l'"],
  "de la": ["du", "de la", "de l'"],
  "de l'": ["du", "de la", "de l'"],
  au: ["au", "à la", "à l'"],
  "à la": ["au", "à la", "à l'"],
  "à l'": ["au", "à la", "à l'"],
  nouveau: ["nouveau", "nouvelle", "nouvel"],
  nouvel: ["nouveau", "nouvelle", "nouvel"],
  nouvelle: ["nouveau", "nouvelle", "nouvelle"],
  aucun: ["aucun", "aucune", null],
  aucune: ["aucun", "aucune", null],
  chaque: ["chaque", "chaque", null],
  de: ["de", "de", "d'"],
  "d'": ["de", "de", "d'"],
};
// Apostrophe typographique acceptée comme l'apostrophe droite.
for (const cle of Object.keys(DETERMINANTS).filter((c) => c.includes("'"))) {
  DETERMINANTS[cle.replace("'", "’")] = DETERMINANTS[cle];
}
const echapper = (t: string) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const MOTIF_DETERMINANT = Object.keys(DETERMINANTS)
  .sort((a, b) => b.length - a.length)
  .map(echapper)
  .join("|");

function estMajuscules(t: string) {
  return t.length > 1 && t === t.toUpperCase() && t !== t.toLowerCase();
}

function casse(modele: string, texte: string) {
  if (estMajuscules(modele)) return texte.toUpperCase();
  if (modele[0] && modele[0] !== modele[0].toLowerCase()) return texte[0].toUpperCase() + texte.slice(1);
  // Terme en minuscules dans la phrase : on garde la saisie si elle est tout en majuscules.
  return estMajuscules(texte) ? texte : texte[0].toLowerCase() + texte.slice(1);
}

function accorder(determinant: string, feminin: boolean, terme: string) {
  const [masculin, formeFeminine, devantVoyelle] = DETERMINANTS[determinant.toLowerCase()];
  let forme = feminin ? formeFeminine : masculin;
  // Élision (l', d', de l', à l') quel que soit le genre ; « cet » / « nouvel » seulement au masculin.
  if (devantVoyelle && VOYELLE.test(terme) && (devantVoyelle.endsWith("'") || !feminin)) forme = devantVoyelle;
  return casse(determinant, forme);
}

export function adapterTexte(texte: string, vocabulaire: Vocabulaire | null | undefined): string {
  if (!texte || !vocabulaire) return texte;
  for (const [cle, singulier, pluriel, femininDefaut] of TERMES) {
    const choix = vocabulaire[cle];
    let nouveauSingulier = (choix?.singulier ?? "").trim();
    let nouveauPluriel = (choix?.pluriel ?? "").trim();
    if (!nouveauSingulier && !nouveauPluriel) continue;
    nouveauSingulier ||= singulier;
    nouveauPluriel ||= nouveauSingulier;
    const feminin = choix?.feminin ?? femininDefaut;
    for (const [ancien, nouveau, estPluriel] of [
      [pluriel, nouveauPluriel, true],
      [singulier, nouveauSingulier, false],
    ] as [string, string, boolean][]) {
      const motif = new RegExp(
        `(?:(?<!\\p{L})(${MOTIF_DETERMINANT})(\\s*))?(?<!\\p{L})(${echapper(ancien)})(?!\\p{L})`,
        "giu",
      );
      texte = texte.replace(motif, (_m, determinant: string | undefined, espace: string | undefined, terme: string) => {
        const remplacement = casse(terme, nouveau);
        if (determinant && !estPluriel) {
          let forme = accorder(determinant, feminin, remplacement);
          const separateur = forme.endsWith("'") ? "" : espace || " ";
          if (determinant.includes("’")) forme = forme.replace("'", "’");
          return `${forme}${separateur}${remplacement}`;
        }
        return `${determinant ?? ""}${espace ?? ""}${remplacement}`;
      });
    }
  }
  return texte;
}

// Vocabulaire courant, chargé une fois au démarrage (AppLayout attend son chargement
// avant d'afficher les pages) ; un changement recharge la page.
let vocabulaireCourant: Vocabulaire = {};

export function definirVocabulaire(vocabulaire: Vocabulaire | undefined) {
  vocabulaireCourant = vocabulaire ?? {};
}

/**
 * Adapte un texte de l'interface au vocabulaire de l'organisation.
 * - voc("Nouveau projet") : tout le texte ;
 * - voc`Projet ${nom} créé` : seulement les parties fixes (jamais les données insérées).
 */
export function voc(texte: string): string;
export function voc(morceaux: TemplateStringsArray, ...valeurs: unknown[]): string;
export function voc(texteOuMorceaux: string | TemplateStringsArray, ...valeurs: unknown[]): string {
  // Autre langue que le français : traduction (le vocabulaire, propre au français, ne s'applique pas).
  if (langue() !== "fr") {
    if (typeof texteOuMorceaux === "string") return traduire(texteOuMorceaux);
    // Gabarit : clé « Projet {0} créé », traduite puis complétée avec les valeurs.
    const cle = texteOuMorceaux.reduce((r, m, i) => r + m + (i < valeurs.length ? `{${i}}` : ""), "");
    return traduire(cle).replace(/\{(\d+)\}/g, (_m, i: string) => String(valeurs[Number(i)] ?? ""));
  }
  if (typeof texteOuMorceaux === "string") return adapterTexte(texteOuMorceaux, vocabulaireCourant);
  return texteOuMorceaux.reduce(
    (resultat, morceau, i) =>
      resultat + adapterTexte(morceau, vocabulaireCourant) + (i < valeurs.length ? String(valeurs[i]) : ""),
    "",
  );
}

/** Texte de l'interface : traduit, et adapté au vocabulaire de l'organisation en français. */
export const t = voc;
