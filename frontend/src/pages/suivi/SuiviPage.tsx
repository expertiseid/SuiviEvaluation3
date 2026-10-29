import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, RefreshCw, Search } from "lucide-react";
import { ActionIcon, Card, Group, Stack, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { useProjets } from "../../api/projects";
import { StatusBadge } from "../../components/common/StatusBadge";
import { EmptyState } from "../../components/common/EmptyState";
import { PROJET_STATUT_LABEL, PROJET_STATUT_TONE } from "../../utils/statusTones";
import { correspond } from "../../utils/recherche";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

export function SuiviPage() {
  const { data: projets, isLoading, isFetching, refetch } = useProjets();
  const [recherche, setRecherche] = useState("");

  const projetsFiltres = useMemo(
    () => (projets ?? []).filter((p) => correspond(p.nom, recherche) || correspond(p.code, recherche)),
    [projets, recherche],
  );

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <div>
          <TitreRubrique route="/suivi" defaut={voc("Suivi")} />
          <Text c="dimmed" size="sm">
            {voc("Choisis un projet pour saisir le réel et suivre son évolution dans le temps.")}</Text>
        </div>
        <Tooltip label={voc("Actualiser")}>
          <ActionIcon variant="light" size="lg" onClick={() => refetch()} loading={isFetching}>
            <RefreshCw size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <TextInput
        placeholder={voc("Rechercher un projet (nom ou code)…")}
        leftSection={<Search size={15} />}
        value={recherche}
        onChange={(e) => setRecherche(e.currentTarget.value)}
        maw={400}
      />

      <Card withBorder padding="md" radius="md">
        {isLoading ? (
          <Text c="dimmed">{voc("Chargement…")}</Text>
        ) : !projets || projets.length === 0 ? (
          <EmptyState icon={<Activity size={32} strokeWidth={1.5} />} message={voc("Aucun projet pour le moment.")} />
        ) : projetsFiltres.length === 0 ? (
          <EmptyState icon={<Activity size={32} strokeWidth={1.5} />} message={voc("Aucun projet ne correspond à la recherche.")} />
        ) : (
          <Table.ScrollContainer minWidth={560}>
            <Table striped highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Code")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Nom")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Statut")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Période")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {projetsFiltres.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Text size="sm" c="dimmed" fw={500}>{p.code}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text component={Link} to={`/suivi/${p.id}`} size="sm" fw={500} c="teal.8">
                        {p.nom}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <StatusBadge tone={PROJET_STATUT_TONE[p.statut]}>{PROJET_STATUT_LABEL[p.statut]}</StatusBadge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">{p.date_debut} → {p.date_fin}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>
    </Stack>
  );
}
