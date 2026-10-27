import { useMemo } from "react";
import { useProjets } from "../../api/projects";
import type { Activite } from "../../types";

/**
 * Options de rattachement d'un indicateur : les projets, puis, pour chaque
 * projet, tous les éléments de sa planification quel que soit leur niveau
 * (les niveaux sont libres : objectif, résultat, pilier, activité...),
 * présentés avec leur chemin dans l'arborescence.
 */
export function useHierarchyOptions() {
  const { data: projets } = useProjets();

  return useMemo(() => {
    const listeProjets: { value: string; label: string }[] = [];
    const elementsParProjet: { projetLabel: string; options: { value: string; label: string }[] }[] = [];

    // Pour retrouver, à partir du rattachement choisi, le cadre stratégique
    // du projet concerné — pour ne proposer que les éléments stratégiques
    // pertinents à ce projet.
    const cadreParProjetId = new Map<number, number | null>();
    const projetIdParActivite = new Map<number, number>();

    for (const projet of projets ?? []) {
      listeProjets.push({ value: String(projet.id), label: `${projet.code} · ${projet.nom}` });
      cadreParProjetId.set(projet.id, projet.cadre_strategique);

      const options: { value: string; label: string }[] = [];
      const parcourir = (elements: Activite[], chemin: string[]) => {
        for (const element of elements) {
          const cheminElement = [...chemin, element.libelle];
          options.push({ value: String(element.id), label: cheminElement.join(" › ") });
          projetIdParActivite.set(element.id, projet.id);
          parcourir(element.enfants, cheminElement);
        }
      };
      parcourir(projet.activites, []);
      if (options.length > 0) elementsParProjet.push({ projetLabel: projet.code, options });
    }
    return { projets: listeProjets, elementsParProjet, cadreParProjetId, projetIdParActivite };
  }, [projets]);
}
