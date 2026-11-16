import { apiClient } from "./client";

export type ChoixExport = { projets: number[]; cadres: number[]; avecProjets: boolean };

/** Reçu d'un extrait téléchargé : permet d'en retirer ensuite le contenu de l'espace (retirerExtrait). */
export type RecuExtrait = { recu: string; empreinte: string };

/**
 * Sauvegarde de l'espace (un zip), complète ou limitée à `choix` : téléchargée par le navigateur.
 * Pour un extrait, renvoie son reçu et l'empreinte du fichier effectivement reçu.
 */
export async function telechargerSauvegarde(choix?: ChoixExport): Promise<RecuExtrait | null> {
  const params = choix
    ? { projets: choix.projets.join(",") || undefined, cadres: choix.cadres.join(",") || undefined, avec_projets: choix.avecProjets ? 1 : 0 }
    : undefined;
  const reponse = await apiClient.get("/transfert/exporter/", { responseType: "blob", timeout: 0, params });
  const entete = String(reponse.headers["content-disposition"] ?? "");
  const nom = /filename="?([^";]+)"?/.exec(entete)?.[1] ?? "sauvegarde.zip";
  const url = window.URL.createObjectURL(new Blob([reponse.data], { type: "application/zip" }));
  const lien = document.createElement("a");
  lien.href = url;
  lien.setAttribute("download", nom);
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(url);
  const recu = reponse.headers["x-recu-extrait"];
  if (!recu) return null;
  const empreinte = await crypto.subtle.digest("SHA-256", await (reponse.data as Blob).arrayBuffer());
  return { recu: String(recu), empreinte: Array.from(new Uint8Array(empreinte), (o) => o.toString(16).padStart(2, "0")).join("") };
}

/** Extrait : projets et cadres retirés ; sauvegarde complète : données effacées (`vide`). */
export type CompteRenduRetrait = { projets?: number; cadres?: number; noms?: string[]; objets?: number; vide?: boolean };

/** Supprime de l'espace ce que le fichier vient d'emporter (après confirmation de l'administrateur). */
export async function retirerExtrait({ recu, empreinte }: RecuExtrait): Promise<CompteRenduRetrait> {
  return (await apiClient.post("/transfert/retirer/", { recu, empreinte, confirmation: "SUPPRIMER" }, { timeout: 0 })).data;
}

// Morceaux de 40 Mo : sous la taille maximale d'un envoi (100 Mo) du serveur web.
const TAILLE_MORCEAU = 40 * 1024 * 1024;

/** Envoie le fichier de reprise par morceaux ; `progression` reçoit la part envoyée (0 à 1). */
export async function envoyerSauvegarde(fichier: File, progression: (part: number) => void): Promise<string> {
  const identifiant = `reprise-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  const nombre = Math.max(1, Math.ceil(fichier.size / TAILLE_MORCEAU));
  for (let numero = 0; numero < nombre; numero++) {
    const donnees = new FormData();
    donnees.append("identifiant", identifiant);
    donnees.append("numero", String(numero));
    donnees.append("morceau", fichier.slice(numero * TAILLE_MORCEAU, (numero + 1) * TAILLE_MORCEAU), "morceau.bin");
    await apiClient.post("/transfert/morceau/", donnees, { timeout: 0 });
    progression((numero + 1) / nombre);
  }
  return identifiant;
}

export type ManifesteSauvegarde = { organisation: string; date: string; objets: number; selection?: boolean };
export type ModeReprise = "ajouter" | "remplacer";
export type CompteRenduReprise = {
  mode: ModeReprise; objets: number; origine: string; date_sauvegarde: string; compte_garde: boolean;
  crees?: number; reutilises?: number; renommes?: number; comptes_desactives?: number; selection?: boolean;
};

export async function analyserSauvegarde(identifiant: string): Promise<ManifesteSauvegarde> {
  return (await apiClient.post("/transfert/reprendre/", { identifiant }, { timeout: 0 })).data.manifeste;
}

export async function reprendreSauvegarde(identifiant: string, mode: ModeReprise): Promise<CompteRenduReprise> {
  const confirmation = mode === "ajouter" ? "AJOUTER" : "REMPLACER";
  return (await apiClient.post("/transfert/reprendre/", { identifiant, mode, confirmation }, { timeout: 0 })).data;
}
