import { useState } from "react";
import { ActionIcon, Autocomplete, Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { Plus, Trash2 } from "lucide-react";
import type { Attributs } from "../../utils/attributs";
import { voc } from "../../utils/vocabulaire";

/**
 * Attributs libres d'un élément de la planification ou d'une sous-activité (« Responsable »,
 * « Lieu »…) : une ligne nom + valeur chacun. Les noms déjà utilisés dans le projet sont proposés,
 * pour garder les mêmes colonnes dans les exports. Une ligne sans nom ou sans valeur est ignorée.
 */
export function AttributsLibres({
  value,
  onChange,
  suggestions = [],
}: {
  value: Attributs;
  onChange: (value: Attributs) => void;
  suggestions?: string[];
}) {
  const [lignes, setLignes] = useState(() => Object.entries(value).map(([nom, valeur]) => ({ nom, valeur })));

  function modifier(nouvelles: { nom: string; valeur: string }[]) {
    setLignes(nouvelles);
    onChange(Object.fromEntries(nouvelles.filter((l) => l.nom.trim() && l.valeur.trim()).map((l) => [l.nom.trim(), l.valeur.trim()])));
  }

  const utilises = new Set(lignes.map((l) => l.nom.trim()));

  return (
    <Stack gap={6}>
      <div>
        <Text size="sm" fw={500}>{voc("Attributs")}</Text>
        <Text size="xs" c="dimmed">
          {voc("Informations libres sur cet élément (ex : Responsable, Lieu), reprises dans les exports. À l'import, ce sont les colonnes « Attribut : … ».")}
        </Text>
      </div>
      {lignes.map((ligne, i) => (
        <Group key={i} gap="xs" wrap="nowrap" align="flex-start">
          <Autocomplete
            placeholder={voc("Nom (ex : Responsable)")}
            data={suggestions.filter((n) => !utilises.has(n) || n === ligne.nom)}
            value={ligne.nom}
            onChange={(nom) => modifier(lignes.map((l, j) => (j === i ? { ...l, nom } : l)))}
            style={{ flex: 1 }}
          />
          <TextInput
            placeholder={voc("Valeur")}
            value={ligne.valeur}
            onChange={(e) => {
              const valeur = e.currentTarget.value;
              modifier(lignes.map((l, j) => (j === i ? { ...l, valeur } : l)));
            }}
            style={{ flex: 2 }}
          />
          <ActionIcon variant="subtle" color="red" mt={4} aria-label={voc("Retirer l'attribut")} onClick={() => modifier(lignes.filter((_, j) => j !== i))}>
            <Trash2 size={14} />
          </ActionIcon>
        </Group>
      ))}
      <Group>
        <Button size="compact-xs" variant="light" leftSection={<Plus size={12} />} onClick={() => setLignes([...lignes, { nom: "", valeur: "" }])}>
          {voc("Ajouter un attribut")}
        </Button>
      </Group>
    </Stack>
  );
}

/** Affichage compact des attributs (« Responsable : … · Lieu : … »). */
export function ResumeAttributs({ attributs }: { attributs?: Attributs }) {
  const entrees = Object.entries(attributs ?? {});
  if (entrees.length === 0) return null;
  return (
    <Text size="xs" c="dimmed" mt={2}>
      {entrees.map(([nom, valeur], i) => (
        <span key={nom}>
          {i > 0 && " · "}
          {nom} : <Text span size="xs" c="dark" fw={500}>{valeur}</Text>
        </span>
      ))}
    </Text>
  );
}
