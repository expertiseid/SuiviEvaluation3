/** Outils communs au formulaire public et à la saisie par un agent. */
import { isAxiosError } from "axios";
import type { SaisieRetour } from "../../api/plaintes";
import { voc } from "../../utils/vocabulaire";

export const RETOUR_VIDE: SaisieRetour = {
  type_retour: null,
  categorie: null,
  projet: null,
  lieu: "",
  description: "",
  concerne_personnel: null,
  anonyme: false,
  nom: "",
  telephone: "",
  courriel: "",
  mode_reponse: "AUCUN",
  consentement: false,
  langue: "",
};

/** Erreurs du serveur champ par champ ({champ: message}), pour les afficher sous chaque champ. */
export function erreursParChamp(error: unknown): Record<string, string> {
  if (!isAxiosError(error) || !error.response?.data || typeof error.response.data !== "object") return {};
  return Object.fromEntries(
    Object.entries(error.response.data as Record<string, unknown>).map(([champ, valeur]) => [
      champ,
      voc(String(Array.isArray(valeur) ? valeur[0] : valeur)),
    ]),
  );
}

/** Catégories pour une liste : principales, puis « Principale › Sous-catégorie ». */
export function optionsCategories(categories: { id: number; nom: string; parent: number | null }[]) {
  const noms = new Map(categories.map((c) => [c.id, c.nom]));
  return categories
    .filter((c) => c.parent === null)
    .flatMap((p) => [
      { value: String(p.id), label: p.nom },
      ...categories.filter((s) => s.parent === p.id).map((s) => ({ value: String(s.id), label: `${noms.get(p.id)} › ${s.nom}` })),
    ]);
}
