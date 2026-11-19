import { apiClient } from "../api/client";
import type { FiltresDashboard } from "../types";
import { exportAutorise, signalerExportDesactive } from "./exportsAutorises";

/** Classe des éléments à ne pas reproduire dans les images (boutons du bloc). */
export const HORS_EXPORT = "hors-export";

/** Un bloc à exporter tel qu'il s'affiche : son élément à l'écran et sa largeur dans la grille (sur 12). */
export interface BlocEcran {
  element: HTMLElement;
  titre: string;
  largeur: number;
}

/** Télécharge un fichier reçu (ou produit) dans le navigateur. */
export function telechargerFichier(contenu: Blob, nom: string) {
  if (!exportAutorise()) {
    signalerExportDesactive();
    return;
  }
  const url = URL.createObjectURL(contenu);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nom;
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Images PNG des blocs, tels qu'ils s'affichent (sans leurs boutons), une à une pour ménager la mémoire ;
 * les polices ne sont lues qu'une fois.
 */
async function capturer(blocs: BlocEcran[]): Promise<(Blob | null)[]> {
  const { getFontEmbedCSS, toBlob } = await import("html-to-image");
  const polices = blocs.length ? await getFontEmbedCSS(blocs[0].element) : undefined;
  const images: (Blob | null)[] = [];
  for (const bloc of blocs) {
    const image = await toBlob(bloc.element, {
      pixelRatio: 2,
      backgroundColor: "#ffffff",
      fontEmbedCSS: polices,
      filter: (n) => !(n instanceof HTMLElement && n.classList.contains(HORS_EXPORT)),
    });
    images.push(image);  // null : bloc vide (rien à dessiner), laissé de côté
  }
  return images;
}

/**
 * PDF, Word ou Excel « comme à l'écran » : les blocs sont capturés puis assemblés par le serveur avec la même
 * disposition (Excel : feuilles de données, puis une dernière feuille avec les images). `titre` : un bloc seul.
 */
export async function exporterCommeEcran(fichier: "pdf" | "docx" | "xlsx", blocs: BlocEcran[], filtres: FiltresDashboard = {}, titre?: string) {
  const captures = await capturer(blocs);
  const gardes = blocs.filter((_, rang) => captures[rang]);
  const images = captures.filter((image): image is Blob => image !== null);
  if (images.length === 0) throw new Error("capture");
  blocs = gardes;
  const envoi = new FormData();
  envoi.append("fichier", fichier);
  envoi.append("blocs", JSON.stringify(blocs.map((b) => ({ titre: b.titre, largeur: b.largeur }))));
  envoi.append("filtres", JSON.stringify({ ...filtres, statuts: filtres.statuts?.length ? filtres.statuts.join(",") : undefined }));
  if (titre) envoi.append("titre", titre);
  images.forEach((image, rang) => envoi.append(`image_${rang}`, image, `bloc_${rang}.png`));
  const reponse = await apiClient.post("/dashboard/consolide/export-ecran/", envoi, {
    responseType: "blob", timeout: 0, headers: { "Content-Type": "multipart/form-data" },
  });
  const nom = /filename="?([^";]+)/.exec(reponse.headers["content-disposition"] ?? "")?.[1] ?? `tableau_de_bord.${fichier}`;
  telechargerFichier(reponse.data, titre ? nom.replace("tableau_de_bord", nomDeFichier(titre)) : nom);
}

export function nomDeFichier(titre: string) {
  return (titre.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\w-]+/g, "_").replace(/^_+|_+$/g, "") || "graphique")
    .slice(0, 80);
}
