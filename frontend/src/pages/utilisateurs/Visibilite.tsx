import { MultiSelect, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { EyeOff } from "lucide-react";
import { apiClient } from "../../api/client";
import { voc } from "../../utils/vocabulaire";

interface LigneActivite { id: number; projet: number; projet__nom: string; activite_parent: number | null; libelle: string; code_activite: string }
interface LigneElement {
  id: number; code: string; nom: string; element_parent: number | null;
  type_niveau__cadre_strategique: number; type_niveau__cadre_strategique__nom: string;
}

/** Libellé avec le chemin depuis la racine (« Résultat 1 › Activité 1.1 ») pour s'y retrouver dans la liste. */
function chemins<T extends { id: number }>(lignes: T[], parent: (l: T) => number | null, nom: (l: T) => string) {
  const parId = new Map(lignes.map((l) => [l.id, l]));
  const chemin = (l: T): string => {
    const p = parent(l);
    const haut = p !== null ? parId.get(p) : undefined;
    return haut ? `${chemin(haut)} › ${nom(l)}` : nom(l);
  };
  return new Map(lignes.map((l) => [l.id, chemin(l)]));
}

function grouper<T extends { id: number }>(lignes: T[], groupe: (l: T) => string, libelles: Map<number, string>) {
  const groupes = new Map<string, { value: string; label: string }[]>();
  for (const l of lignes) {
    const g = groupe(l);
    groupes.set(g, [...(groupes.get(g) ?? []), { value: String(l.id), label: libelles.get(l.id) ?? "" }]);
  }
  return [...groupes.entries()].map(([group, items]) => ({ group, items: items.sort((a, b) => a.label.localeCompare(b.label)) }));
}

/**
 * Fiche d'un utilisateur : activités et éléments stratégiques qu'il ne voit pas (apps.core.masquage). Masquer un
 * élément masque tout ce qui est en dessous ; les totaux des projets ne changent pas.
 */
export function VisibiliteUtilisateur({ activites, elements, onActivites, onElements }: {
  activites: number[]; elements: number[]; onActivites: (v: number[]) => void; onElements: (v: number[]) => void;
}) {
  const { data: lignesActivites = [] } = useQuery({
    queryKey: ["activites", "arborescence"],
    queryFn: async () => (await apiClient.get<LigneActivite[]>("/activites/arborescence/")).data,
  });
  const { data: lignesElements = [] } = useQuery({
    queryKey: ["elements-strategiques", "arborescence"],
    queryFn: async () => (await apiClient.get<LigneElement[]>("/elements-strategiques/arborescence/")).data,
  });
  const libellesActivites = chemins(lignesActivites, (l) => l.activite_parent, (l) => [l.code_activite, l.libelle].filter(Boolean).join(" "));
  const libellesElements = chemins(lignesElements, (l) => l.element_parent, (l) => [l.code, l.nom].filter(Boolean).join(" "));
  return (
    <Stack gap="xs">
      <Text fw={600} size="sm">{voc("Éléments masqués à cet utilisateur")}</Text>
      <Text size="xs" c="dimmed">
        {voc("Il ne les voit nulle part (planification, suivi, indicateurs, documents, exports). Masquer un élément masque tout ce qui est en dessous. Les totaux des projets ne changent pas.")}
      </Text>
      <MultiSelect label={voc("Activités masquées")} placeholder={voc("Rechercher une activité…")} searchable clearable
        leftSection={<EyeOff size={15} />} maxDropdownHeight={320} nothingFoundMessage={voc("Aucun résultat.")}
        data={grouper(lignesActivites, (l) => l.projet__nom, libellesActivites)}
        value={activites.map(String)} onChange={(v) => onActivites(v.map(Number))} />
      <MultiSelect label={voc("Éléments stratégiques masqués")} placeholder={voc("Rechercher un élément…")} searchable clearable
        leftSection={<EyeOff size={15} />} maxDropdownHeight={320} nothingFoundMessage={voc("Aucun résultat.")}
        data={grouper(lignesElements, (l) => l.type_niveau__cadre_strategique__nom, libellesElements)}
        value={elements.map(String)} onChange={(v) => onElements(v.map(Number))} />
    </Stack>
  );
}
