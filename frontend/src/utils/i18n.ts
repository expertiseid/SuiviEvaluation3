/**
 * Langue de l'interface. Les textes sont écrits en français dans le code et servent de clés :
 * `traduire("Nouveau projet")` renvoie leur traduction dans la langue courante (catalogue
 * livré avec l'application, i18n/<langue>.json, corrigé par l'Administrateur), sinon le texte
 * français. La langue est fixée au démarrage, avant l'affichage ; en changer recharge la page.
 *
 * Choix de la langue : celui de l'utilisateur (son compte, ou ce navigateur avant connexion),
 * sinon la langue par défaut de l'organisation, sinon le français.
 */
import axios from "axios";

export type Langue = "fr" | "en" | "ar" | "es" | "de";
export const LANGUES: { code: Langue; nom: string }[] = [
  { code: "fr", nom: "Français" },
  { code: "en", nom: "English" },
  { code: "ar", nom: "العربية" },
  { code: "es", nom: "Español" },
  { code: "de", nom: "Deutsch" },
];
const CLE_STOCKAGE = "langue";
// Nombres et dates ; en arabe, chiffres latins (usage courant dans les rapports de projet).
const LOCALES: Record<Langue, string> = { fr: "fr-FR", en: "en-GB", ar: "ar-u-nu-latn", es: "es-ES", de: "de-DE" };

let langueCourante: Langue = "fr";
let langueDefaut: Langue = "fr";
let catalogue: Record<string, string> = {};

const estLangue = (l: unknown): l is Langue => LANGUES.some((x) => x.code === l);

function lireChoix(): Langue | null {
  // ?lang=en dans l'adresse (ex : « Essayer la démo » depuis le site vitrine en anglais) : retenu comme choix.
  const dansAdresse = new URLSearchParams(window.location.search).get("lang");
  if (estLangue(dansAdresse)) {
    try { localStorage.setItem(CLE_STOCKAGE, dansAdresse); } catch { /* navigation privée */ }
    return dansAdresse;
  }
  try {
    const l = localStorage.getItem(CLE_STOCKAGE);
    return estLangue(l) ? l : null;
  } catch {
    return null;
  }
}

/** À appeler avant d'afficher l'application (main.tsx). */
export async function demarrerLangue(): Promise<void> {
  // Même adresse que api/client (sans l'importer : il dépend lui-même des traductions).
  const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
  const choisie = lireChoix();
  let corrections: Record<string, string> = {};
  try {
    const { data } = await axios.get(`${base}/traductions/`, { params: { langue: choisie ?? undefined }, timeout: 8000 });
    if (estLangue(data.langue_defaut)) langueDefaut = data.langue_defaut;
    corrections = data.corrections ?? {};
    langueCourante = choisie ?? langueDefaut;
    if (!choisie && langueCourante !== "fr") {
      corrections = (await axios.get(`${base}/traductions/`, { params: { langue: langueCourante }, timeout: 8000 })).data.corrections ?? {};
    }
  } catch {
    langueCourante = choisie ?? "fr"; // serveur injoignable : on affiche quand même
  }
  if (langueCourante !== "fr") {
    try {
      const module = await import(`../i18n/${langueCourante}.json`);
      catalogue = { ...(module.default as Record<string, string>), ...corrections };
    } catch {
      catalogue = { ...corrections };
    }
  }
  document.documentElement.lang = langueCourante;
  document.documentElement.dir = langueCourante === "ar" ? "rtl" : "ltr";
}

export const langue = () => langueCourante;
export const langueParDefaut = () => langueDefaut;
export const estRtl = () => langueCourante === "ar";
/** Locale des nombres et des dates (toLocaleString, Intl). */
export const locale = () => LOCALES[langueCourante];

/** Montant abrégé : « 9,66 Md », « 1,8 M » en français ; notation courte de la langue sinon (9.66B…). */
export function nombreCourt(v: number): string {
  if (Math.abs(v) < 1e6) return v.toLocaleString(locale());
  if (langueCourante === "fr") {
    return Math.abs(v) >= 1e9
      ? `${(v / 1e9).toLocaleString(locale(), { maximumFractionDigits: 2 })} Md`
      : `${(v / 1e6).toLocaleString(locale(), { maximumFractionDigits: 1 })} M`;
  }
  return v.toLocaleString(locale(), { notation: "compact", maximumFractionDigits: Math.abs(v) >= 1e9 ? 2 : 1 });
}

export function traduire(texte: string): string {
  if (langueCourante === "fr" || !texte) return texte;
  return catalogue[texte] ?? catalogue[texte.trim()] ?? traduireSelonModele(texte) ?? texte;
}

// Messages du serveur construits avec des valeurs (« Saisie (01/10 → 15/10) en dehors… ») :
// on retrouve le modèle du catalogue (« Saisie ({0} → {1}) en dehors… »), on le traduit,
// puis on y remet les valeurs. Les modèles sont compilés une fois, au premier besoin.
let modeles: { motif: RegExp; ordre: number[]; cle: string }[] | null = null;

function traduireSelonModele(texte: string): string | null {
  modeles ??= Object.keys(catalogue)
    // Il faut assez de texte fixe (deux mots au moins) pour ne pas capturer n'importe quelle
    // donnée : « Objectif{0} » ne doit pas transformer « Objectif général ».
    .filter((cle) => /\{\d+\}/.test(cle) && /\S+\s+\S+/.test(cle.replace(/\{\d+\}/g, "").trim()) && cle.replace(/\{\d+\}/g, "").length >= 10)
    .map((cle) => {
      const ordre: number[] = [];
      const source = cle
        .split(/(\{\d+\})/)
        .map((morceau) => {
          const repere = /^\{(\d+)\}$/.exec(morceau);
          if (!repere) return morceau.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
          ordre.push(Number(repere[1]));
          return "([\\s\\S]+?)";
        })
        .join("");
      return { motif: new RegExp(`^${source}$`), ordre, cle };
    })
    // Les modèles les plus longs (donc les plus précis) d'abord.
    .sort((a, b) => b.cle.length - a.cle.length);
  for (const { motif, ordre, cle } of modeles) {
    const m = motif.exec(texte);
    if (!m) continue;
    const valeurs: string[] = [];
    ordre.forEach((n, i) => (valeurs[n] = m[i + 1]));
    return catalogue[cle].replace(/\{(\d+)\}/g, (_x, n: string) => valeurs[Number(n)] ?? "");
  }
  return null;
}

/**
 * Donnée saisie par l'organisation (nom d'un niveau administratif…) : traduite seulement
 * si elle figure telle quelle au catalogue (« Région », « Province »…), sinon laissée telle
 * quelle. Gère aussi la forme « BF — Région ».
 */
export function traduireDonnee(texte: string | null | undefined): string {
  if (!texte) return texte ?? "";
  const morceaux = texte.split(" — ");
  if (morceaux.length === 2) return `${morceaux[0]} — ${traduire(morceaux[1])}`;
  return traduire(texte);
}

/**
 * Choix explicite (sélecteur) : mémorisé dans ce navigateur ; la page est rechargée, ou
 * chargée à `destination` si elle est donnée.
 */
export function changerLangue(nouvelle: Langue, destination?: string) {
  try {
    localStorage.setItem(CLE_STOCKAGE, nouvelle);
  } catch {
    /* navigation privée : la langue ne sera pas mémorisée */
  }
  if (destination) window.location.replace(destination);
  else window.location.reload();
}

/**
 * Langue du compte connu : elle l'emporte ; la page est rechargée si elle diffère. Juste après
 * la connexion, on passe `destination` : recharger la page de connexion y ramènerait l'utilisateur.
 */
export function appliquerLangueDuCompte(langueCompte: string | null | undefined, destination?: string) {
  const voulue = estLangue(langueCompte) ? langueCompte : lireChoix() ?? langueDefaut;
  if (voulue !== langueCourante) changerLangue(voulue, destination);
}
