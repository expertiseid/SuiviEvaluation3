import { useState } from "react";
import { Button, Group, Select, Stack, TextInput } from "@mantine/core";
import { voc } from "../../utils/vocabulaire";

interface Option {
  value: string;
  label: string;
}

/**
 * Select classique + un champ "ou créer un nouveau X" juste en dessous —
 * évite d'avoir un module d'administration séparé pour des référentiels
 * légers (partenaires, bailleurs) : on les crée directement là où on en a
 * besoin.
 */
export function SelectOrCreate({
  label,
  data,
  value,
  onChange,
  onCreate,
  creating,
  clearable,
}: {
  label: string;
  data: Option[];
  value: string | null;
  onChange: (value: string | null) => void;
  onCreate: (nom: string) => void;
  creating?: boolean;
  clearable?: boolean;
}) {
  const [nouveauNom, setNouveauNom] = useState("");

  return (
    <Stack gap={4}>
      <Select label={label} placeholder={voc("Choisir…")} data={data} value={value} onChange={onChange} searchable clearable={clearable} />
      <Group gap={6} wrap="nowrap">
        <TextInput
          placeholder={voc("Ou créer un nouveau — nom…")}
          size="xs"
          value={nouveauNom}
          onChange={(e) => setNouveauNom(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button
          size="xs"
          variant="light"
          loading={creating}
          onClick={() => {
            if (nouveauNom.trim()) {
              onCreate(nouveauNom.trim());
              setNouveauNom("");
            }
          }}
        >
          {voc("+ Créer")}
        </Button>
      </Group>
    </Stack>
  );
}
