import { useState, type RefObject } from "react";
import { ActionIcon, Loader, Menu, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Download, FileImage, FileSpreadsheet, FileText, Image as IconeImage, PenTool } from "lucide-react";
import { apiClient } from "../../api/client";
import { messageErreurApi } from "../../utils/erreurs";
import { langue } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { exportAutorise } from "../../utils/exportsAutorises";
import { exporterCommeEcran, HORS_EXPORT, nomDeFichier, telechargerFichier as telecharger } from "../../utils/exportEcran";
import type { FiltresDashboard } from "../../types";

/** Données d'un bloc, pour le CSV et l'Excel : première colonne = catégories, suivantes = séries. */
export interface DonneesExport {
  entetes: string[];
  lignes: (string | number | null)[][];
  /** Type du graphique Excel natif (colonnes, barres, camembert, courbes…). */
  type?: string;
  /** Colonnes de valeurs tracées dans le graphique Excel (les premières) ; par défaut toutes. */
  series?: number;
  /** Légende ajoutée à l'image SVG (les légendes de l'écran ne font pas partie du dessin). */
  legende?: { nom: string; couleur: string }[];
}

export { HORS_EXPORT };

/** CSV lisible par le tableur de la langue : « ; » et virgule décimale là où la virgule est décimale. */
function csv(donnees: DonneesExport) {
  const virgule = ["fr", "es", "de", "it"].includes(langue());
  const separateur = virgule ? ";" : ",";
  const cellule = (v: string | number | null) => {
    if (v === null || v === undefined) return "";
    const texte = typeof v === "number" && virgule ? String(v).replace(".", ",") : String(v);
    return /[";,\n]/.test(texte) ? `"${texte.replace(/"/g, '""')}"` : texte;
  };
  const lignes = [donnees.entetes, ...donnees.lignes].map((l) => l.map(cellule).join(separateur));
  return new Blob(["﻿" + lignes.join("\r\n")], { type: "text/csv;charset=utf-8" });
}

/**
 * Graphique vectoriel : le dessin SVG du graphique, avec ses couleurs, un fond blanc (ou transparent), le
 * titre et la légende ajoutés (à l'écran, ce sont des éléments à part).
 */
function svgVectoriel(zone: HTMLElement, titre: string, legende: DonneesExport["legende"], transparent: boolean) {
  // Le plus grand graphique du bloc (un bloc peut en avoir deux, ex. camembert et colonnes).
  const source = Array.from(zone.querySelectorAll<SVGSVGElement>("svg.recharts-surface"))
    .sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
  if (!source) return null;
  const { width: largeurGraphique, height } = source.getBoundingClientRect();
  // Largeur assez grande pour le titre (~9 px par lettre) ; légende disposée ligne par ligne selon la longueur des noms.
  const width = Math.max(largeurGraphique, titre.length * 9 + 20, 360);
  const placements: { x: number; y: number }[] = [];
  let x0 = 8, rang = 0;
  for (const element of legende ?? []) {
    const largeur = 16 + element.nom.length * 7 + 18;
    if (x0 + largeur > width && x0 > 8) { x0 = 8; rang += 1; }
    placements.push({ x: x0, y: rang });
    x0 += largeur;
  }
  const copie = source.cloneNode(true) as SVGSVGElement;
  // Styles calculés recopiés sur le texte (police, couleur) : le fichier ne dépend pas de la page.
  const textes = source.querySelectorAll("text");
  copie.querySelectorAll("text").forEach((t, i) => {
    const style = getComputedStyle(textes[i]);
    t.setAttribute("font-family", style.fontFamily);
    t.setAttribute("font-size", style.fontSize);
    if (!t.getAttribute("fill")) t.setAttribute("fill", style.fill || style.color);
  });
  const ns = "http://www.w3.org/2000/svg";
  const haut = 34;
  const lignesLegende = placements.length ? rang + 1 : 0;
  const totalH = haut + height + lignesLegende * 20 + (lignesLegende ? 10 : 0);
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("xmlns", ns);
  svg.setAttribute("width", String(Math.ceil(width)));
  svg.setAttribute("height", String(Math.ceil(totalH)));
  svg.setAttribute("viewBox", `0 0 ${Math.ceil(width)} ${Math.ceil(totalH)}`);
  if (!transparent) {
    const fond = document.createElementNS(ns, "rect");
    fond.setAttribute("width", "100%");
    fond.setAttribute("height", "100%");
    fond.setAttribute("fill", "#ffffff");
    svg.appendChild(fond);
  }
  const texteTitre = document.createElementNS(ns, "text");
  texteTitre.setAttribute("x", "4");
  texteTitre.setAttribute("y", "22");
  texteTitre.setAttribute("font-family", "Inter, Arial, sans-serif");
  texteTitre.setAttribute("font-size", "16");
  texteTitre.setAttribute("font-weight", "700");
  texteTitre.setAttribute("fill", "#212529");
  texteTitre.textContent = titre;
  svg.appendChild(texteTitre);
  const groupe = document.createElementNS(ns, "g");
  groupe.setAttribute("transform", `translate(0 ${haut})`);
  Array.from(copie.childNodes).forEach((n) => groupe.appendChild(n));
  svg.appendChild(groupe);
  legende?.forEach((element, i) => {
    const x = placements[i].x;
    const y = haut + height + 12 + placements[i].y * 20;
    const carre = document.createElementNS(ns, "rect");
    carre.setAttribute("x", String(x));
    carre.setAttribute("y", String(y));
    carre.setAttribute("width", "11");
    carre.setAttribute("height", "11");
    carre.setAttribute("rx", "2");
    carre.setAttribute("fill", element.couleur);
    const nom = document.createElementNS(ns, "text");
    nom.setAttribute("x", String(x + 16));
    nom.setAttribute("y", String(y + 10));
    nom.setAttribute("font-family", "Inter, Arial, sans-serif");
    nom.setAttribute("font-size", "12");
    nom.setAttribute("fill", "#343a40");
    nom.textContent = element.nom;
    svg.append(carre, nom);
  });
  return new Blob([new XMLSerializer().serializeToString(svg)], { type: "image/svg+xml;charset=utf-8" });
}

/**
 * Télécharger un bloc du tableau de bord seul : image PNG (haute résolution, fond blanc ou transparent),
 * image vectorielle SVG (graphiques), PDF et Word comme à l'écran, données CSV et Excel avec graphique natif relié aux données.
 */
export function ExportBloc({ titre, zone, donnees, filtres }: {
  titre: string;
  zone: RefObject<HTMLDivElement | null>;
  donnees?: () => DonneesExport | null;
  /** Filtres du tableau de bord, rappelés dans le PDF et le Word. */
  filtres?: FiltresDashboard;
}) {
  const [encours, setEncours] = useState(false);
  const nom = nomDeFichier(titre);

  async function lancer(action: () => Promise<void>) {
    setEncours(true);
    try {
      await action();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Le téléchargement a échoué.")), color: "red" });
    } finally {
      setEncours(false);
    }
  }

  const png = (transparent: boolean) => lancer(async () => {
    if (!zone.current) return;
    const { toBlob } = await import("html-to-image");
    const image = await toBlob(zone.current, {
      pixelRatio: 3,
      backgroundColor: transparent ? undefined : "#ffffff",
      // Fond transparent : sans le fond ni la bordure du bloc.
      style: transparent ? { background: "transparent", border: "none", boxShadow: "none" } : undefined,
      filter: (n) => !(n instanceof HTMLElement && n.classList.contains(HORS_EXPORT)),
    });
    if (image) telecharger(image, `${nom}.png`);
  });

  const svg = () => lancer(async () => {
    if (!zone.current) return;
    const fichier = svgVectoriel(zone.current, titre, donnees?.()?.legende, false);
    if (!fichier) {
      notifications.show({ message: voc("Ce bloc n'a pas de graphique à exporter en SVG : choisissez PNG ou Excel."), color: "orange" });
      return;
    }
    telecharger(fichier, `${nom}.svg`);
  });

  // PDF et Word : le bloc tel qu'il s'affiche, avec son titre et les filtres.
  const document_ = (fichier: "pdf" | "docx") => lancer(async () => {
    if (!zone.current) return;
    await exporterCommeEcran(fichier, [{ element: zone.current, titre, largeur: 12 }], filtres, titre);
  });

  const tableau = (format: "csv" | "xlsx") => lancer(async () => {
    const d = donnees?.();
    if (!d) return;
    if (format === "csv") {
      telecharger(csv(d), `${nom}.csv`);
      return;
    }
    const reponse = await apiClient.post("/dashboard/graphique/excel/", { titre, entetes: d.entetes, lignes: d.lignes, type: d.type, series: d.series },
      { responseType: "blob" });
    telecharger(reponse.data, `${nom}.xlsx`);
  });

  // Exports désactivés pour ce compte : pas de bouton de téléchargement.
  if (!exportAutorise()) return null;
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Tooltip label={voc("Télécharger ce bloc")} withArrow>
          <ActionIcon variant="default" size="md" className={HORS_EXPORT} aria-label={voc("Télécharger ce bloc")}>
            {encours ? <Loader size={14} /> : <Download size={15} />}
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{voc("Image")}</Menu.Label>
        <Menu.Item leftSection={<IconeImage size={15} />} onClick={() => png(false)}>{voc("PNG (haute résolution)")}</Menu.Item>
        <Menu.Item leftSection={<FileImage size={15} />} onClick={() => png(true)}>{voc("PNG, fond transparent")}</Menu.Item>
        <Menu.Item leftSection={<PenTool size={15} />} onClick={svg}>{voc("SVG (vectoriel)")}</Menu.Item>
        <Menu.Label>{voc("Document, comme à l'écran")}</Menu.Label>
        <Menu.Item leftSection={<FileText size={15} color="var(--mantine-color-red-7)" />} onClick={() => document_("pdf")}>PDF</Menu.Item>
        <Menu.Item leftSection={<FileText size={15} color="var(--mantine-color-blue-7)" />} onClick={() => document_("docx")}>Word</Menu.Item>
        {donnees && (
          <>
            <Menu.Label>{voc("Données")}</Menu.Label>
            <Menu.Item leftSection={<FileText size={15} />} onClick={() => tableau("csv")}>CSV</Menu.Item>
            <Menu.Item leftSection={<FileSpreadsheet size={15} />} onClick={() => tableau("xlsx")}>{voc("Excel avec graphique")}</Menu.Item>
          </>
        )}
      </Menu.Dropdown>
    </Menu>
  );
}
