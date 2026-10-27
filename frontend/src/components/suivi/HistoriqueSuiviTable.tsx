import { ActionIcon, Group, Table, Text, Tooltip } from "@mantine/core";
import { Pencil, Trash2 } from "lucide-react";

export interface LigneHistoriqueSuivi {
  id: number;
  periode: string;
  /** Absente quand le taux ne vient pas des quantités (méthode de calcul autre). */
  valeur?: string;
  cumule?: string;
  detail?: string;
  attendu?: string;
  statut?: string;
}

export function HistoriqueSuiviTable({
  lignes,
  onEdit,
  onDelete,
  editable,
  libelleStatut = "Statut",
  messageVide = "Aucune saisie pour le moment.",
}: {
  lignes: LigneHistoriqueSuivi[];
  onEdit?: (id: number) => void;
  onDelete?: (id: number) => void;
  editable: boolean;
  /** En-tête de la dernière colonne (ex : « Commentaire » dans le suivi par période). */
  libelleStatut?: string;
  messageVide?: string;
}) {
  if (lignes.length === 0) {
    return (
      <Text size="sm" c="dimmed" mt={6}>
        {messageVide}
      </Text>
    );
  }

  const aValeur = lignes.some((l) => l.valeur);
  const aCumule = lignes.some((l) => l.cumule);
  const aAttendu = lignes.some((l) => l.attendu);
  const aDetail = lignes.some((l) => l.detail);
  const aStatut = lignes.some((l) => l.statut);

  return (
    <Table fz="sm" verticalSpacing={4} withRowBorders={false} mt={6}>
      <Table.Thead>
        <Table.Tr>
          <Table.Th fw={600} c="dimmed" tt="none">Période</Table.Th>
          {aValeur && <Table.Th fw={600} c="dimmed" tt="none">Cette période</Table.Th>}
          {aCumule && <Table.Th fw={600} c="dimmed" tt="none">Cumul</Table.Th>}
          {aDetail && <Table.Th fw={600} c="dimmed" tt="none">Budget</Table.Th>}
          {aAttendu && <Table.Th fw={600} c="dimmed" tt="none">Attendu</Table.Th>}
          {aStatut && <Table.Th fw={600} c="dimmed" tt="none">{libelleStatut}</Table.Th>}
          <Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {lignes.map((ligne) => (
          <Table.Tr key={ligne.id}>
            <Table.Td c="dimmed" style={{ whiteSpace: "nowrap" }}>{ligne.periode}</Table.Td>
            {aValeur && <Table.Td fw={500}>{ligne.valeur}</Table.Td>}
            {aCumule && <Table.Td c="dimmed">{ligne.cumule}</Table.Td>}
            {aDetail && <Table.Td c="dimmed">{ligne.detail}</Table.Td>}
            {aAttendu && <Table.Td c="dimmed">{ligne.attendu}</Table.Td>}
            {aStatut && <Table.Td c="dimmed">{ligne.statut}</Table.Td>}
            <Table.Td style={{ width: 1 }}>
              {editable && (onEdit || onDelete) && (
                <Group gap={2} wrap="nowrap" justify="flex-end">
                  {onEdit && (
                    <Tooltip label="Modifier cette saisie">
                      <ActionIcon size="sm" variant="subtle" onClick={() => onEdit(ligne.id)}>
                        <Pencil size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  {onDelete && (
                    <Tooltip label="Supprimer cette saisie">
                      <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onDelete(ligne.id)}>
                        <Trash2 size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Group>
              )}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
