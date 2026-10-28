import { Badge, Button, Group, Stack, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { useReverifierDoublons, useSignalementsDoublons, useTraiterSignalement } from "../../api/beneficiaries";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

export function DoublonsPage() {
  const { data: signalements, isLoading } = useSignalementsDoublons("SIGNALE");
  const traiter = useTraiterSignalement();
  const reverifier = useReverifierDoublons();

  async function handleReverifier() {
    try {
      const r = await reverifier.mutateAsync();
      notifications.show({
        message: `${r.retires} signalement(s) retiré(s) (ne sont plus considérés comme des doublons), ${r.maintenus} maintenu(s).`,
        color: "green",
      });
    } catch {
      notifications.show({ message: "Erreur lors de la vérification", color: "red" });
    }
  }

  async function handleTraiter(id: number, statut: "ECARTE" | "FUSIONNE") {
    try {
      await traiter.mutateAsync({ id, statut });
      notifications.show({ message: "Signalement mis à jour", color: "green" });
    } catch {
      notifications.show({ message: "Erreur lors de la mise à jour", color: "red" });
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <TitreRubrique route="/doublons" defaut="Doublons d'enregistrement" />
        <Button variant="light" leftSection={<RefreshCw size={16} />} loading={reverifier.isPending} onClick={handleReverifier}>
          Revérifier les signalements
        </Button>
      </Group>
      <Text size="sm" c="dimmed">
        {voc(
          "Bénéficiaires enregistrés plusieurs fois sur la plateforme. Une paire n'est signalée que si elle a la même pièce d'identité, ou un nom et un prénom très proches confirmés par le même téléphone, la même date de naissance ou la même localité ; jamais si le sexe, l'année de naissance ou la pièce d'identité diffèrent. À confirmer avant de fusionner ou d'écarter.",
        )}
      </Text>
      {isLoading ? (
        <div>Chargement…</div>
      ) : signalements && signalements.length > 0 ? (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{voc("Bénéficiaire 1")}</Table.Th>
              <Table.Th>{voc("Bénéficiaire 2")}</Table.Th>
              <Table.Th>Pourquoi</Table.Th>
              <Table.Th>Score</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {signalements.map((s) => (
              <Table.Tr key={s.id}>
                <Table.Td><Link to={`/beneficiaires/${s.beneficiaire_1}`}>{s.beneficiaire_1_nom}</Link></Table.Td>
                <Table.Td><Link to={`/beneficiaires/${s.beneficiaire_2}`}>{s.beneficiaire_2_nom}</Link></Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {(s.motifs?.length ? s.motifs : [s.methode === "PIECE_IDENTITE" ? "Même pièce d'identité" : "Nom proche"]).map((m) => (
                      <Badge key={m} variant="light" color={s.methode === "PIECE_IDENTITE" ? "red" : "orange"} tt="none">{m}</Badge>
                    ))}
                  </Group>
                </Table.Td>
                <Table.Td>{s.score ?? "—"}</Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Button size="xs" variant="light" color="green" onClick={() => handleTraiter(s.id, "FUSIONNE")}>
                      {voc("Confirmer doublon")}</Button>
                    <Button size="xs" variant="light" onClick={() => handleTraiter(s.id, "ECARTE")}>
                      Écarter (faux positif)
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      ) : (
        <div>{voc("Aucun doublon en attente de traitement.")}</div>
      )}
    </Stack>
  );
}
