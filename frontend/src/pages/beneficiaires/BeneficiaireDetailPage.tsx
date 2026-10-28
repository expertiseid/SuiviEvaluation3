import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { FolderKanban, IdCard, MapPin, Pencil, Trash2 } from "lucide-react";
import { ActionIcon, Badge, Button, Card, Flex, Group, Modal, SimpleGrid, Stack, Table, Text, Title, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  telechargerCartesBeneficiaires,
  useBeneficiaire,
  useDeleteBeneficiaire,
  useQrBeneficiaire,
  useVariablesBeneficiaires,
} from "../../api/beneficiaries";
import { concerne, reponseLisible } from "../../utils/variablesBeneficiaires";
import type { Beneficiaire } from "../../types";
import { useStatutsParticuliers, useTypesActiviteBeneficiaire } from "../../api/referentiels";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { PAYS_MONDE } from "../../utils/pays";
import { BeneficiaireForm } from "./BeneficiaireForm";
import { voc } from "../../utils/vocabulaire";

/** Réponses aux variables qui concernent les projets du bénéficiaire. */
function InformationsComplementaires({ beneficiaire }: { beneficiaire: Beneficiaire }) {
  const { data: variables = [] } = useVariablesBeneficiaires();
  const projetIds = beneficiaire.participations.map((p) => p.projet);
  const affichees = variables.filter((v) => concerne(v, projetIds) || beneficiaire.reponses?.[String(v.id)] !== undefined);
  if (affichees.length === 0) return null;
  return (
    <Card withBorder padding="md" radius="md">
      <Text size="xs" c="dimmed" fw={600} tt="uppercase" mb="sm" style={{ letterSpacing: 0.4 }}>
        {voc("Informations complémentaires")}
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="xs">
        {affichees.map((v) => (
          <div key={v.id}>
            <Text size="xs" c="dimmed">{v.libelle}</Text>
            <Text size="sm" fw={500}>
              {concerne(v, projetIds) ? reponseLisible(v, beneficiaire.reponses?.[String(v.id)]) : "NA"}
            </Text>
          </div>
        ))}
      </SimpleGrid>
    </Card>
  );
}

/** QR code de la fiche et impression de la carte bénéficiaire. */
function CarteQr({ id, identifiant }: { id: number; identifiant: string }) {
  const { data: svg } = useQrBeneficiaire(id);
  const [impression, setImpression] = useState(false);
  return (
    <Stack gap={4} align="center" miw={150}>
      {svg ? (
        <div style={{ width: 132, height: 132 }} dangerouslySetInnerHTML={{ __html: svg.replace("<svg ", '<svg width="132" height="132" ') }} />
      ) : (
        <div style={{ width: 132, height: 132 }} />
      )}
      <Text size="xs" c="dimmed" ta="center">{voc("Scanner pour ouvrir cette fiche")}</Text>
      <Button
        size="xs"
        variant="light"
        leftSection={<IdCard size={14} />}
        loading={impression}
        onClick={async () => {
          setImpression(true);
          try {
            await telechargerCartesBeneficiaires({ ids: [id] }, `carte_${identifiant}`);
          } finally {
            setImpression(false);
          }
        }}
      >
        {voc("Imprimer la carte")}
      </Button>
    </Stack>
  );
}

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
          <Group gap="xs">
            <Title order={2}>{beneficiaire.nom} {beneficiaire.prenom}</Title>
            <Badge size="lg" variant="outline" color="teal" ff="monospace">{beneficiaire.identifiant}</Badge>
          </Group>
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
        {/* Sur téléphone, le QR passe sous les informations. */}
        <Flex direction={{ base: "column", xs: "row" }} justify="space-between" align={{ base: "stretch", xs: "flex-start" }} gap="md">
        <div style={{ minWidth: 0 }}>
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
          {beneficiaire.latitude && beneficiaire.longitude && (
            <Text size="sm">
              <MapPin size={13} style={{ verticalAlign: -2 }} /> <strong>Position GPS :</strong> {beneficiaire.latitude}, {beneficiaire.longitude}
            </Text>
          )}
        </Stack>
        </div>
        <CarteQr id={beneficiaire.id} identifiant={beneficiaire.identifiant} />
        </Flex>
      </Card>

      <InformationsComplementaires beneficiaire={beneficiaire} />

      <Card withBorder padding="md" radius="md">
        <Group gap="xs" mb="sm">
          <FolderKanban size={16} />
          <Text fw={600}>{voc("Projets qui l'ont aidé(e)")}</Text>
        </Group>
        {beneficiaire.participations.length === 0 ? (
          <EmptyState icon={<FolderKanban size={32} strokeWidth={1.5} />} message={voc("Aucun projet pour le moment.")} />
        ) : (
          <>
          {/* Téléphone : une ligne par projet plutôt qu'un tableau coupé. */}
          <Stack gap="xs" hiddenFrom="sm">
            {beneficiaire.participations.map((p) => (
              <div key={p.id} style={{ borderTop: "1px solid var(--mantine-color-gray-2)", paddingTop: 8 }}>
                <Text component={Link} to={`/projets/${p.projet}`} size="sm" fw={500} c="teal.8">
                  {p.projet_nom}
                </Text>
                <Text size="xs" c="dimmed">
                  Inscrit(e) le {p.date_inscription}
                  {p.role_dans_projet && ` · ${p.role_dans_projet}`}
                </Text>
              </div>
            ))}
          </Stack>
          <Table.ScrollContainer minWidth={500} visibleFrom="sm">
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
          </>
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
