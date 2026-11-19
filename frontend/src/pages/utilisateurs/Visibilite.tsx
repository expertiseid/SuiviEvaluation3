import { useState } from "react";
import { ActionIcon, Button, Checkbox, Group, MultiSelect, Radio, Select, Stack, Switch, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { EyeOff, Plus, Trash2 } from "lucide-react";
import { useUtilisateurs } from "../../api/accounts";
import { apiClient } from "../../api/client";
import { useProjets } from "../../api/projects";
import { useCadresStrategiques } from "../../api/strategy";
import type { DroitObjet } from "../../types";
import { modulesApprouvables } from "../../utils/modules";
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

type Genre = "projet" | "document" | "element";

const genreDe = (d: DroitObjet): Genre => (d.projet ? "projet" : d.document ? "document" : "element");

/**
 * Fiche d'un utilisateur : droits précis sur des projets, des documents stratégiques (stratégie, programme,
 * plan…) ou des éléments (pilier, axe…) — lecture seule ou lecture et écriture, et droit d'approuver. Ils
 * remplacent ses droits globaux pour ces objets ; un droit sur un document ou un élément vaut pour ce qui
 * est en dessous (apps.projects.droits).
 */
export function DroitsPrecisUtilisateur({ droits, onDroits, hors, onHors }: {
  droits: DroitObjet[]; onDroits: (v: DroitObjet[]) => void; hors: "GLOBAL" | "LECTURE"; onHors: (v: "GLOBAL" | "LECTURE") => void;
}) {
  const { data: projets = [] } = useProjets();
  const { data: documents = [] } = useCadresStrategiques();
  const { data: lignesElements = [] } = useQuery({
    queryKey: ["elements-strategiques", "arborescence"],
    queryFn: async () => (await apiClient.get<LigneElement[]>("/elements-strategiques/arborescence/")).data,
  });
  const libellesElements = chemins(lignesElements, (l) => l.element_parent, (l) => [l.code, l.nom].filter(Boolean).join(" "));
  const [genre, setGenre] = useState<Genre>("projet");
  const [cible, setCible] = useState<string | null>(null);
  const genres: Record<Genre, string> = { projet: voc("Projet"), document: voc("Stratégie, programme ou plan"), element: voc("Élément stratégique") };
  const libelle = (d: DroitObjet) => {
    if (d.projet) {
      const p = projets.find((x) => x.id === d.projet);
      return p ? `${p.code} — ${p.nom}` : d.libelle ?? "";
    }
    if (d.document) return documents.find((x) => x.id === d.document)?.nom ?? d.libelle ?? "";
    return (d.element && libellesElements.get(d.element)) || d.libelle || "";
  };
  const dejaPris = new Set(droits.map((d) => `${genreDe(d)}-${d.projet ?? d.document ?? d.element}`));
  const options = (genre === "projet"
    ? projets.map((p) => ({ value: String(p.id), label: `${p.code} — ${p.nom}` }))
    : genre === "document"
      ? documents.map((x) => ({ value: String(x.id), label: x.nom }))
      : grouper(lignesElements, (l) => l.type_niveau__cadre_strategique__nom, libellesElements).flatMap((g) => g.items.map((i) => ({ ...i, label: `${g.group} › ${i.label}` }))))
    .filter((o) => !dejaPris.has(`${genre}-${o.value}`));
  const modifier = (rang: number, champs: Partial<DroitObjet>) => onDroits(droits.map((d, i) => (i === rang ? { ...d, ...champs } : d)));
  const ajouter = () => {
    if (!cible) return;
    onDroits([...droits, { [genre]: Number(cible), acces: "LECTURE", approuver: false }]);
    setCible(null);
  };
  return (
    <Stack gap="xs">
      <Text fw={600} size="sm">{voc("Droits précis par projet et par stratégie")}</Text>
      <Text size="xs" c="dimmed">
        {voc("Pour les projets, stratégies et éléments listés ici, ces droits remplacent son niveau d'accès et son rôle. Un droit sur une stratégie vaut pour ses éléments (piliers, axes…) et les programmes qui lui sont rattachés, sauf droit plus précis. Un droit sur un projet le rend visible.")}
      </Text>
      {droits.length > 0 && (
        <Table withTableBorder verticalSpacing={4} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{voc("Objet")}</Table.Th>
              <Table.Th w={190}>{voc("Accès")}</Table.Th>
              <Table.Th w={110}>{voc("Peut approuver")}</Table.Th>
              <Table.Th w={40} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {droits.map((d, rang) => (
              <Table.Tr key={`${genreDe(d)}-${d.projet ?? d.document ?? d.element}`}>
                <Table.Td>
                  <Text size="sm">{libelle(d)}</Text>
                  <Text size="xs" c="dimmed">{genres[genreDe(d)]}</Text>
                </Table.Td>
                <Table.Td>
                  <Select size="xs" allowDeselect={false} value={d.acces} aria-label={voc("Accès")}
                    data={[{ value: "LECTURE", label: voc("Lecture seule") }, { value: "ECRITURE", label: voc("Lecture et écriture") }]}
                    onChange={(v) => v && modifier(rang, { acces: v as DroitObjet["acces"] })} />
                </Table.Td>
                <Table.Td>
                  <Checkbox checked={d.approuver} aria-label={voc("Peut approuver")} onChange={(e) => modifier(rang, { approuver: e.currentTarget.checked })} />
                </Table.Td>
                <Table.Td>
                  <ActionIcon size="sm" variant="subtle" color="red" aria-label={voc("Retirer ce droit")}
                    onClick={() => onDroits(droits.filter((_, i) => i !== rang))}>
                    <Trash2 size={13} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      <Group gap="xs" align="flex-end" wrap="nowrap">
        <Select size="xs" w={220} label={voc("Ajouter un droit sur")} allowDeselect={false} value={genre}
          data={Object.entries(genres).map(([value, label]) => ({ value, label }))} onChange={(v) => { if (v) { setGenre(v as Genre); setCible(null); } }} />
        <Select size="xs" style={{ flex: 1 }} label={genres[genre]} placeholder={voc("Rechercher…")} searchable clearable
          data={options} value={cible} onChange={setCible} maxDropdownHeight={300} nothingFoundMessage={voc("Aucun résultat.")} />
        <Button size="xs" leftSection={<Plus size={13} />} disabled={!cible} onClick={ajouter}>{voc("Ajouter")}</Button>
      </Group>
      <Radio.Group label={voc("Pour tout le reste")} value={hors} onChange={(v) => onHors(v as "GLOBAL" | "LECTURE")}>
        <Stack gap={4} mt={4}>
          <Radio value="GLOBAL" label={voc("Ses droits habituels (niveau d'accès et rôle)")} />
          <Radio value="LECTURE" label={voc("Lecture seule, sans droit d'approuver")} />
        </Stack>
      </Radio.Group>
    </Stack>
  );
}

/**
 * Fiche d'un utilisateur : tout ce qu'il renseigne (réalisations, planification, stratégies) doit être approuvé,
 * par les personnes désignées (avec l'Administrateur), ou à défaut par toute personne ayant le droit d'approuver.
 */
export function ApprobationSaisies({ utilisateurId, actif, onActif, approbateurs, onApprobateurs, modules, onModules }: {
  utilisateurId: number; actif: boolean; onActif: (v: boolean) => void; approbateurs: number[]; onApprobateurs: (v: number[]) => void;
  modules: string[]; onModules: (v: string[]) => void;
}) {
  const { data: utilisateurs = [] } = useUtilisateurs();
  const options = utilisateurs
    .filter((u) => u.id !== utilisateurId && u.is_active)
    .map((u) => ({ value: String(u.id), label: [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username }));
  return (
    <Stack gap="xs">
      <Text fw={600} size="sm">{voc("Approbation de ses saisies")}</Text>
      <Switch checked={actif} onChange={(e) => onActif(e.currentTarget.checked)}
        label={voc("Tout ce qu'il renseigne doit être approuvé")}
        description={voc("Toute création, modification ou suppression (bénéficiaires, indicateurs, suivis, planification, stratégies, documents…) : rien ne compte ni ne s'applique avant approbation. Il ne peut pas approuver ses propres saisies.")} />
      {actif && (
        <MultiSelect label={voc("Seulement dans ces onglets")} searchable clearable data={modulesApprouvables()} value={modules}
          onChange={onModules} placeholder={modules.length ? undefined : voc("Tous les onglets")}
          description={voc("Laisser vide : tout ce qu'il renseigne, dans tous les onglets.")} />
      )}
      {actif && (
        <MultiSelect label={voc("Approuvé par")} searchable clearable data={options} value={approbateurs.map(String)}
          onChange={(v) => onApprobateurs(v.map(Number))} nothingFoundMessage={voc("Aucun résultat.")}
          placeholder={approbateurs.length ? undefined : voc("L'administrateur ou toute personne ayant le droit d'approuver")}
          description={voc("Les personnes choisies approuvent ses saisies, en plus de l'administrateur. Laisser vide : l'administrateur ou toute personne ayant le droit d'approuver le projet ou la stratégie.")} />
      )}
    </Stack>
  );
}

export interface DroitsExport {
  peut_exporter: boolean;
  captures: "ORGANISATION" | "BLOQUEES" | "PERMISES";
  export_global: boolean;
  import_global: boolean;
}

/** Exports de l'utilisateur : tous les téléchargements de données, et l'export / import global (sur autorisation). */
export function ExportsUtilisateur({ droits, onDroits }: { droits: DroitsExport; onDroits: (v: DroitsExport) => void }) {
  return (
    <Stack gap="xs">
      <Text fw={600} size="sm">{voc("Exports et captures d'écran")}</Text>
      <Switch checked={droits.peut_exporter} onChange={(e) => onDroits({ ...droits, peut_exporter: e.currentTarget.checked })}
        label={voc("Peut exporter les données")}
        description={voc("Tous les exports de la plateforme : Excel, PDF, Word, CSV, images, documents téléchargés… Désactivé : il consulte, mais ne télécharge rien.")} />
      <Select label={voc("Captures d'écran")} value={droits.captures} allowDeselect={false} maw={360}
        onChange={(v) => onDroits({ ...droits, captures: (v ?? "ORGANISATION") as DroitsExport["captures"] })}
        data={[
          { value: "ORGANISATION", label: voc("Réglage de l'organisation") },
          { value: "BLOQUEES", label: voc("Bloquées pour lui") },
          { value: "PERMISES", label: voc("Permises pour lui") },
        ]}
        description={voc("Bloquées : filigrane à son nom, écran masqué pendant une capture, impression et copie bloquées. Le réglage de l'organisation se trouve dans Organisation › Identité et logo.")} />
      <Switch checked={droits.export_global} onChange={(e) => onDroits({ ...droits, export_global: e.currentTarget.checked })}
        label={voc("Peut faire l'export global")}
        description={voc("Sauvegarde de tout l'espace ou d'une partie (onglet Export et import global). Par défaut : l'administrateur seulement.")} />
      <Switch checked={droits.import_global} onChange={(e) => onDroits({ ...droits, import_global: e.currentTarget.checked })}
        label={voc("Peut faire l'import global")}
        description={voc("Ajout d'une sauvegarde à l'espace. Remplacer tout l'espace reste réservé à l'administrateur.")} />
    </Stack>
  );
}
