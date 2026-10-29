import { useState } from "react";
import { Trash2, UserPlus, Users } from "lucide-react";
import { ActionIcon, Button, Card, Group, MultiSelect, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useBeneficiaires,
  useCreateParticipation,
  useDeleteParticipation,
  useParticipations,
} from "../../api/beneficiaries";
import { EmptyState } from "../common/EmptyState";
import { confirmerSuppression } from "../common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

export function BeneficiairesTab({
  projetId,
  activiteId,
  sousActiviteId,
}: {
  projetId: number;
  activiteId?: number;
  sousActiviteId?: number;
}) {
  const { data: participations, isLoading } = useParticipations({
    activite: activiteId,
    sous_activite: sousActiviteId,
  });
  const [recherche, setRecherche] = useState("");
  const { data: resultatsRecherche } = useBeneficiaires(recherche || undefined);
  const [selection, setSelection] = useState<string[]>([]);
  const createParticipation = useCreateParticipation();
  const deleteParticipation = useDeleteParticipation();

  const optionsBeneficiaires = (resultatsRecherche?.results ?? [])
    .filter((b) => !participations?.some((p) => p.beneficiaire === b.id))
    .map((b) => ({ value: String(b.id), label: `${b.nom} ${b.prenom}${b.telephone ? " — " + b.telephone : ""}` }));

  async function ajouter() {
    if (selection.length === 0) return;
    const dateInscription = new Date().toISOString().slice(0, 10);
    const resultats = await Promise.allSettled(
      selection.map((id) =>
        createParticipation.mutateAsync({
          beneficiaire: Number(id),
          projet: projetId,
          activite: activiteId,
          sous_activite: sousActiviteId,
          date_inscription: dateInscription,
        }),
      ),
    );
    const echecs = resultats.filter((r) => r.status === "rejected");
    if (echecs.length === 0) {
      notifications.show({
        message: selection.length > 1 ? voc("Bénéficiaires associés") : voc("Bénéficiaire associé"),
        color: "green",
      });
    } else {
      const premierEchec = echecs[0] as PromiseRejectedResult;
      notifications.show({
        message:
          echecs.length === selection.length
            ? messageErreurApi(premierEchec.reason, voc("Erreur lors de l'association des bénéficiaires"))
            : voc`${selection.length - echecs.length} associé(s), ${echecs.length} en échec.`,
        color: echecs.length === selection.length ? "red" : "orange",
      });
    }
    setSelection([]);
    setRecherche("");
  }

  function handleSupprimer(participation: { id: number; beneficiaire_nom: string }) {
    confirmerSuppression({
      message: voc`Retirer "${participation.beneficiaire_nom}" de cette liste ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteParticipation.mutateAsync(participation.id);
          notifications.show({ message: voc("Bénéficiaire retiré"), color: "green" });
        } catch (error) {
          notifications.show({
            message: messageErreurApi(error, voc("Erreur lors du retrait du bénéficiaire")),
            color: "red",
          });
        }
      },
    });
  }

  return (
    <Card withBorder padding="md" radius="md">
      <Group align="flex-end" mb="md">
        <TextInput
          label={voc("Rechercher un bénéficiaire")}
          placeholder={voc("Nom, prénom, téléphone…")}
          value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <MultiSelect
          placeholder={voc("Choisir un ou plusieurs bénéficiaires…")}
          data={optionsBeneficiaires}
          value={selection}
          onChange={setSelection}
          searchable
          hidePickedOptions
          style={{ flex: 1 }}
        />
        <Button
          leftSection={<UserPlus size={16} />}
          onClick={ajouter}
          loading={createParticipation.isPending}
          disabled={selection.length === 0}
        >
          {voc("Associer")}{selection.length > 0 ? ` (${selection.length})` : ""}
        </Button>
      </Group>

      {isLoading ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : !participations || participations.length === 0 ? (
        <EmptyState icon={<Users size={32} strokeWidth={1.5} />} message={voc("Aucun bénéficiaire associé pour le moment.")} />
      ) : (
        <Table.ScrollContainer minWidth={400}>
          <Table verticalSpacing="sm" striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Nom")}</Table.Th>
                <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Date d'inscription")}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {participations.map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{p.beneficiaire_nom}</Text>
                  </Table.Td>
                  <Table.Td>{p.date_inscription}</Table.Td>
                  <Table.Td>
                    <Tooltip label={voc("Retirer")}>
                      <ActionIcon variant="subtle" color="red" onClick={() => handleSupprimer(p)}>
                        <Trash2 size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Card>
  );
}
