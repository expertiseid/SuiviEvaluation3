import { Link } from "react-router-dom";
import { MessagesSquare } from "lucide-react";
import { Alert, Anchor, Group, Loader, Stack, Text } from "@mantine/core";
import { useRetoursProjet } from "../../api/plaintes";
import { voc } from "../../utils/vocabulaire";
import { ElementsTableau } from "./ElementsTableau";

/** Encart « Retours des communautés » de la fiche projet : agrégé, sans détail confidentiel. */
export function RetoursProjet({ projetId }: { projetId: number }) {
  const { data, isLoading, isError } = useRetoursProjet(projetId);
  if (isLoading) return <Loader size="sm" />;
  if (isError || !data) return <Alert color="gray">{voc("Les retours des communautés ne sont pas accessibles avec votre compte.")}</Alert>;
  return (
    <Stack>
      <Group justify="space-between">
        <Group gap="xs"><MessagesSquare size={18} /><Text fw={600}>{voc("Retours des communautés")}</Text></Group>
        <Anchor component={Link} to={`/plaintes?projet=${projetId}`} size="sm">{voc("Voir les dossiers du projet")}</Anchor>
      </Group>
      <Text size="sm" c="dimmed">
        {voc("Plaintes, suggestions et autres retours reçus sur les 12 derniers mois pour ce projet. Les dossiers confidentiels n'apparaissent que dans des totaux.")}
      </Text>
      <ElementsTableau elements={data.elements} />
    </Stack>
  );
}
