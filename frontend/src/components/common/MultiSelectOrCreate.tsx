import { useState } from "react";
import { Button, Group, MultiSelect, Stack, TextInput } from "@mantine/core";
import { voc } from "../../utils/vocabulaire";

interface Option {
  value: string;
  label: string;
}

/**
 * MultiSelect classique + un champ "ou ajouter un nouvel élément" juste en
 * dessous — même logique que SelectOrCreate mais pour les référentiels à
 * choix multiples (statuts particuliers, types d'activité...) : on les
 * enrichit directement depuis le formulaire où on en a besoin, sans écran
 * d'administration séparé.
 */
export function MultiSelectOrCreate({
  label,
  description,
  data,
  value,
  onChange,
  onCreate,
  creating,
}: {
  label: string;
  description?: string;
  data: Option[];
  value: string[];
  onChange: (value: string[]) => void;
  onCreate: (libelle: string) => Promise<string | null>;
  creating?: boolean;
}) {
  const [nouveauLibelle, setNouveauLibelle] = useState("");

  async function handleCreer() {
    const libelle = nouveauLibelle.trim();
    if (!libelle) return;
    const nouvelId = await onCreate(libelle);
    if (nouvelId) {
      onChange([...value, nouvelId]);
      setNouveauLibelle("");
    }
  }

  return (
    <Stack gap={4}>
      <MultiSelect
        label={label}
        description={description}
        placeholder={voc("Choisir…")}
        data={data}
        value={value}
        onChange={onChange}
        searchable
      />
      <Group gap={6} wrap="nowrap">
        <TextInput
          placeholder={voc("Absent de la liste ? Tape-le ici pour l'ajouter…")}
          size="xs"
          value={nouveauLibelle}
          onChange={(e) => setNouveauLibelle(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleCreer();
            }
          }}
          style={{ flex: 1 }}
        />
        <Button size="xs" variant="light" loading={creating} onClick={handleCreer}>
          {voc("+ Ajouter")}
        </Button>
      </Group>
    </Stack>
  );
}
