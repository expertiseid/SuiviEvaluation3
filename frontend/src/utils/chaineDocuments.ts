/**
 * Chaîne des documents stratégiques (maillons : Cadre stratégique → Programme → Pilier…) :
 * adresses des rubriques et des documents, choix de rattachement et maillons sautés.
 */
import type { CadreStrategique, TypeDocument } from "../types";

/** Rubrique d'un maillon (le premier maillon garde « /strategie »). */
export const routeMaillon = (typeId: number) => `/strategie/type/${typeId}`;

/** Rang (0 = premier maillon) du maillon d'un document ; sans maillon = premier. */
export function rangMaillon(typeId: number | null | undefined, maillons: TypeDocument[]) {
  const rang = maillons.findIndex((m) => m.id === typeId);
  return rang === -1 ? 0 : rang;
}

/** Adresse de la fiche d'un document, dans la rubrique de son maillon. */
export function lienDocument(document: Pick<CadreStrategique, "id" | "type_document">, maillons: TypeDocument[]) {
  const rang = rangMaillon(document.type_document, maillons);
  return rang === 0 ? `/strategie/${document.id}` : `${routeMaillon(maillons[rang].id)}/${document.id}`;
}

/** Documents d'un maillon au-dessus de `rang`, groupés par maillon (du plus proche au plus haut). */
export function optionsDocumentsAuDessus(rang: number, documents: CadreStrategique[], maillons: TypeDocument[], exclure?: number) {
  return maillons
    .slice(0, rang)
    .map((m, i) => ({
      group: m.nom_pluriel,
      items: documents
        .filter((d) => d.id !== exclure && rangMaillon(d.type_document, maillons) === i)
        .map((d) => ({ value: String(d.id), label: d.nom })),
    }))
    .filter((g) => g.items.length > 0)
    .reverse();
}

/** Noms des maillons sautés entre un document parent (rang) et un document (rang). */
export function maillonsSautes(rangParent: number, rang: number, maillons: TypeDocument[]) {
  return maillons.slice(rangParent + 1, rang).map((m) => m.nom);
}
