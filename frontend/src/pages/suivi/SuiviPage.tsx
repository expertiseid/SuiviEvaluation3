import { RefreshCw } from "lucide-react";
import { ActionIcon, Group, Stack, Text, Tooltip } from "@mantine/core";
import { useProjets } from "../../api/projects";
import { ListeProjets } from "../../components/projets/ListeProjets";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

export function SuiviPage() {
  const { data: projets, isLoading, isFetching, refetch } = useProjets();

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <div>
          <TitreRubrique route="/suivi" defaut={voc("Suivi")} />
          <Text c="dimmed" size="sm">
            {voc("Choisissez un projet pour saisir le réalisé et suivre son évolution dans le temps.")}</Text>
        </div>
        <Tooltip label={voc("Actualiser")}>
          <ActionIcon variant="light" size="lg" onClick={() => refetch()} loading={isFetching}>
            <RefreshCw size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <ListeProjets projets={projets} isLoading={isLoading} lien={(p) => `/suivi/${p.id}`} />
    </Stack>
  );
}
