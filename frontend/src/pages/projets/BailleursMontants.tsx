import { ActionIcon, Autocomplete, Button, Group, NumberInput, Stack, Text, Tooltip } from "@mantine/core";
import { Plus, Trash2 } from "lucide-react";
import { useBailleurs } from "../../api/referentiels";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { type LigneBailleur, nouvelleLigneBailleur, totalBailleurs } from "./lignesBailleurs";

/**
 * Bailleurs du projet (ou d'un document de la chaîne) et montant apporté par chacun : autant de
 * lignes que de bailleurs. Un nom inconnu crée le bailleur à l'enregistrement.
 */
export function BailleursMontants({ lignes, onChange, messageVide }: {
  lignes: LigneBailleur[];
  onChange: (lignes: LigneBailleur[]) => void;
  /** Texte quand aucun bailleur n'est saisi (par défaut, celui d'un projet). */
  messageVide?: string;
}) {
  const { data: bailleurs } = useBailleurs();
  const noms = [...new Set((bailleurs ?? []).map((b) => b.nom))];
  const modifier = (cle: number, champs: Partial<LigneBailleur>) =>
    onChange(lignes.map((l) => (l.cle === cle ? { ...l, ...champs } : l)));

  return (
    <Stack gap={6}>
      <Text size="sm" fw={500}>{voc("Bailleurs et montants")}</Text>
      {lignes.length === 0 && <Text size="xs" c="dimmed">{messageVide ?? voc("Aucun bailleur : le projet est financé sur fonds propres.")}</Text>}
      {lignes.map((l) => (
        <Group key={l.cle} gap="xs" wrap="nowrap" align="flex-start">
          <Autocomplete
            placeholder={voc("Nom du bailleur")}
            data={noms}
            value={l.nom}
            onChange={(nom) => modifier(l.cle, { nom })}
            style={{ flex: 2 }}
          />
          <NumberInput
            placeholder={voc("Montant (FCFA)")}
            value={l.montant ?? ""}
            onChange={(v) => modifier(l.cle, { montant: v === "" ? null : Number(v) })}
            min={0}
            thousandSeparator=" "
            style={{ flex: 1 }}
            description={l.rallonges ? voc`+ ${l.rallonges.toLocaleString(locale())} de rallonges` : undefined}
            inputWrapperOrder={["label", "input", "description", "error"]}
          />
          <Tooltip label={l.rallonges ? voc("Ce financement a des rallonges : à gérer dans l'onglet Financement") : voc("Retirer ce bailleur")}>
            <ActionIcon
              variant="subtle"
              color="red"
              mt={6}
              disabled={l.rallonges > 0}
              aria-label={voc("Retirer ce bailleur")}
              onClick={() => onChange(lignes.filter((x) => x.cle !== l.cle))}
            >
              <Trash2 size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>
      ))}
      <Group justify="space-between">
        <Button size="xs" variant="light" leftSection={<Plus size={14} />} onClick={() => onChange([...lignes, nouvelleLigneBailleur()])}>
          {voc("Ajouter un bailleur")}
        </Button>
        {lignes.length > 1 && (
          <Text size="sm" c="dimmed">
            {voc("Total bailleurs :")} {totalBailleurs(lignes).toLocaleString(locale())} FCFA
          </Text>
        )}
      </Group>
    </Stack>
  );
}
