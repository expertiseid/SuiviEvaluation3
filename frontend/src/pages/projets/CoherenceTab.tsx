import { Link } from "react-router-dom";
import { CircleCheck } from "lucide-react";
import { Badge, Group, Loader, Stack, Table, Text } from "@mantine/core";
import { useCoherenceProjet } from "../../api/projects";
import { voc } from "../../utils/vocabulaire";

/**
 * Onglet « Contrôle de cohérence » de la fiche projet : incohérences repérées dans la
 * planification, les suivis, les indicateurs et les budgets (apps/projects/coherence.py), des
 * plus graves aux moins graves. Rien n'est bloqué : c'est une liste de points à vérifier.
 */
export function CoherenceTab({ projetId }: { projetId: number }) {
  const { data, isLoading } = useCoherenceProjet(projetId);
  if (isLoading || !data) return <Loader size="sm" />;
  if (data.length === 0) {
    return (
      <Group gap={8} c="teal">
        <CircleCheck size={18} />
        <Text>{voc("Aucune incohérence repérée dans ce projet.")}</Text>
      </Group>
    );
  }
  const erreurs = data.filter((i) => i.gravite === "erreur").length;
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("Points à vérifier dans les données de ce projet : « Erreur » = donnée certainement fausse (fin avant début, période future, % au-delà de 100…) ; « À vérifier » = possible mais inhabituel (dépassement de cible, dates hors du projet, saisies qui se chevauchent…).")}
      </Text>
      <Group gap="xs">
        {erreurs > 0 && <Badge color="red" variant="light">{erreurs} erreur{erreurs > 1 ? "s" : ""}</Badge>}
        {data.length - erreurs > 0 && (
          <Badge color="orange" variant="light">{data.length - erreurs} à vérifier</Badge>
        )}
      </Group>
      <Table fz="sm" verticalSpacing={6} striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={110}>Gravité</Table.Th>
            <Table.Th w={120}>Domaine</Table.Th>
            <Table.Th>Élément</Table.Th>
            <Table.Th>Problème</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.map((i, n) => (
            <Table.Tr key={n}>
              <Table.Td>
                <Badge color={i.gravite === "erreur" ? "red" : "orange"} variant="light">
                  {i.gravite === "erreur" ? "Erreur" : "À vérifier"}
                </Badge>
              </Table.Td>
              <Table.Td>{i.categorie}</Table.Td>
              <Table.Td>{i.lien ? <Link to={i.lien}>{i.element}</Link> : i.element}</Table.Td>
              <Table.Td>{i.message}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
