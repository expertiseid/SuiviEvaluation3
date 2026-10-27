import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { FolderKanban, Pencil, Trash2 } from "lucide-react";
import { ActionIcon, Badge, Button, Card, Group, Modal, Stack, Table, Text, Title, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useBeneficiaire, useDeleteBeneficiaire } from "../../api/beneficiaries";
import { useStatutsParticuliers, useTypesActiviteBeneficiaire } from "../../api/referentiels";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { PAYS_MONDE } from "../../utils/pays";
import { BeneficiaireForm } from "./BeneficiaireForm";
import { voc } from "../../utils/vocabulaire";

export function BeneficiaireDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const beneficiaireId = Number(id);
  const { data: beneficiaire, isLoading } = useBeneficiaire(beneficiaireId);
  const { data: statuts } = useStatutsParticuliers();
  const { data: typesActivite } = useTypesActiviteBeneficiaire();
  const deleteBeneficiaire = useDeleteBeneficiaire();
  const [modalEditionOuvert, setModalEditionOuvert] = useState(false);

  if (isLoading || !beneficiaire) return <Text>Chargement…</Text>;

  const libellesStatuts = beneficiaire.statuts_particuliers
    .map((sid) => statuts?.find((s) => s.id === sid)?.libelle)
    .filter(Boolean);
  const libellesTypesActivite = beneficiaire.types_activite
    .map((tid) => typesActivite?.find((t) => t.id === tid)?.libelle)
    .filter(Boolean);

  function handleSupprimer() {
    confirmerSuppression({
      message: voc`Supprimer "${beneficiaire!.nom} ${beneficiaire!.prenom}" ? Ses participations aux projets et signalements de doublon associés seront aussi supprimés. Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteBeneficiaire.mutateAsync(beneficiaireId);
          notifications.show({ message: voc("Bénéficiaire supprimé"), color: "green" });
          navigate("/beneficiaires");
        } catch (error) {
          notifications.show({
            message: messageErreurApi(error, voc("Erreur lors de la suppression du bénéficiaire")),
            color: "red",
          });
        }
      },
    });
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>{beneficiaire.nom} {beneficiaire.prenom}</Title>
          <Text c="dimmed">
            {beneficiaire.sexe === "F" ? "Féminin" : "Masculin"}
            {beneficiaire.date_naissance && ` · Né(e) le ${beneficiaire.date_naissance}`}
            {beneficiaire.tranche_age && ` · ${beneficiaire.tranche_age}`}
            {beneficiaire.telephone && ` · ${beneficiaire.telephone}`}
          </Text>
        </div>
        <Group gap="xs">
          <Button variant="light" leftSection={<Pencil size={15} />} onClick={() => setModalEditionOuvert(true)}>
            Modifier
          </Button>
          <Tooltip label={voc("Supprimer le bénéficiaire")}>
            <ActionIcon variant="light" color="red" size="lg" loading={deleteBeneficiaire.isPending} onClick={handleSupprimer}>
              <Trash2 size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <Card withBorder padding="md" radius="md">
        <Text size="xs" c="dimmed" fw={600} tt="uppercase" mb="sm" style={{ letterSpacing: 0.4 }}>
          Informations
        </Text>
        <Stack gap={4}>
          <Text size="sm"><strong>N° pièce d'identité :</strong> {beneficiaire.numero_piece_identite || "—"} {beneficiaire.type_piece && `(${beneficiaire.type_piece})`}</Text>
          <Text size="sm">
            <strong>Localisation :</strong>{" "}
            {PAYS_MONDE.find((p) => p.code === beneficiaire.pays)?.nom ?? (beneficiaire.pays || "—")}
            {beneficiaire.zone_nom && ` · ${beneficiaire.zone_nom}`}
          </Text>
          {libellesStatuts.length > 0 && (
            <Group gap={6} mt={4}>
              {libellesStatuts.map((l) => (
                <Badge key={l} variant="light" color="grape">{l}</Badge>
              ))}
            </Group>
          )}
          {libellesTypesActivite.length > 0 && (
            <Group gap={6} mt={4}>
              {libellesTypesActivite.map((l) => (
                <Badge key={l} variant="light" color="teal">{l}</Badge>
              ))}
            </Group>
          )}
        </Stack>
      </Card>

      <Card withBorder padding="md" radius="md">
        <Group gap="xs" mb="sm">
          <FolderKanban size={16} />
          <Text fw={600}>{voc("Projets qui l'ont aidé(e)")}</Text>
        </Group>
        {beneficiaire.participations.length === 0 ? (
          <EmptyState icon={<FolderKanban size={32} strokeWidth={1.5} />} message={voc("Aucun projet pour le moment.")} />
        ) : (
          <Table.ScrollContainer minWidth={500}>
            <Table striped highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Projet")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">Date d'inscription</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">Rôle</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {beneficiaire.participations.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Text component={Link} to={`/projets/${p.projet}`} size="sm" fw={500} c="teal.8">
                        {p.projet_nom}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">{p.date_inscription}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">{p.role_dans_projet || "—"}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>

      <Modal
        opened={modalEditionOuvert}
        onClose={() => setModalEditionOuvert(false)}
        title={`Modifier — ${beneficiaire.nom} ${beneficiaire.prenom}`}
        size="lg"
      >
        <BeneficiaireForm beneficiaire={beneficiaire} onDone={() => setModalEditionOuvert(false)} />
      </Modal>
    </Stack>
  );
}
