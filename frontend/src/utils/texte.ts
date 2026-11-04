const REGEX_DIACRITIQUES = new RegExp(`[${String.fromCharCode(0x0300)}-${String.fromCharCode(0x036f)}]`, "g");

/**
 * Dérive un code référentiel (ex : "MARAICHAGE") à partir d'un libellé
 * tapé librement (ex : "Maraîchage") — majuscules, sans accent, espaces et
 * ponctuation remplacés par des underscores.
 */
export function codeDepuisLibelle(libelle: string): string {
  return libelle
    .normalize("NFD")
    .replace(REGEX_DIACRITIQUES, "")
    .toUpperCase()
    .trim()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** Initiales d'un nom (deux lettres au plus), pour les avatars. */
export const initiales = (nom: string) => nom.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]).join("").toUpperCase();
