import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet, Pencil, Search, Trash2 } from "lucide-react";
import { ActionIcon, Button, Card, Group, Modal, Stack, Table, Text, TextInput, Title, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useDeleteIndicateur, useIndicateurs } from "../../api/indicators";
import { AlerteBadge } from "../../components/indicators/AlerteBadge";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { correspond } from "../../utils/recherche";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { IndicateurForm } from "./IndicateurForm";
import { ImportIndicateursModal } from "./ImportIndicateursModal";
import type { Indicateur } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

const SANS_PROJET = voc("Indicateurs stratégiques (sans projet rattaché)");

function grouperParProjet(indicateurs: Indicateur[]): [string, Indicateur[]][] {
  const groupes = new Map<string, Indicateur[]>();
  for (const indicateur of indicateurs) {
    const cle = indicateur.projet_rattache_nom ?? SANS_PROJET;
    if (!groupes.has(cle)) groupes.set(cle, []);
    groupes.get(cle)!.push(indicateur);
  }
  for (const liste of groupes.values()) {
    liste.sort((a, b) => a.libelle.localeCompare(b.libelle, "fr"));
  }
  return [...groupes.entries()].sort(([a], [b]) => {
    if (a === SANS_PROJET) return 1;
    if (b === SANS_PROJET) return -1;
    return a.localeCompare(b, "fr");
  });
}

export function IndicateursListPage() {
  const { data: indicateurs, isLoading } = useIndicateurs();
  const deleteIndicateur = useDeleteIndicateur();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImportOuvert, setModalImportOuvert] = useState(false);
  const [indicateurEnEdition, setIndicateurEnEdition] = useState<Indicateur | null>(null);
  const [recherche, setRecherche] = useState("");
  const [editionActive, setEditionActive] = useState(false);

  const indicateursFiltres = useMemo(
    () => (indicateurs ?? []).filter((i) => correspond(i.libelle, recherche) || correspond(i.projet_rattache_nom ?? "", recherche)),
    [indicateurs, recherche],
  );
  const groupes = useMemo(() => grouperParProjet(indicateursFiltres), [indicateursFiltres]);

  function handleSupprimer(id: number, libelle: string) {
    confirmerSuppression({
      message: voc`Supprimer l'indicateur "${libelle}" ainsi que toutes ses valeurs saisies ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteIndicateur.mutateAsync(id);
          notifications.show({ message: voc("Indicateur supprimé"), color: "green" });
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression de l'indicateur"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <TitreRubrique route="/indicateurs" defaut="Indicateurs" />
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          <Button variant="light" leftSection={<FileSpreadsheet size={16} />} onClick={() => setModalImportOuvert(true)}>
            Importer depuis Excel
          </Button>
          <Button onClick={() => setModalOpen(true)}>{voc("Nouvel indicateur")}</Button>
        </Group>
      </Group>

      <TextInput
        placeholder={voc("Rechercher un indicateur ou un projet…")}
        leftSection={<Search size={15} />}
        value={recherche}
        onChange={(e) => setRecherche(e.currentTarget.value)}
        maw={400}
      />

      {isLoading ? (
        <div>Chargement…</div>
      ) : groupes.length === 0 ? (
        <Text c="dimmed" size="sm">
          {recherche ? voc("Aucun indicateur ne correspond à la recherche.") : voc("Aucun indicateur pour le moment.")}
        </Text>
      ) : (
        <Stack gap="lg">
          {groupes.map(([nomProjet, liste]) => (
            <Card key={nomProjet} withBorder padding="md" radius="md">
              <Title order={4} mb="xs">
                {nomProjet}
              </Title>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Libellé</Table.Th>
                    <Table.Th>Unité</Table.Th>
                    <Table.Th>Valeur de base</Table.Th>
                    <Table.Th>Cible</Table.Th>
                    <Table.Th>Statut</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {liste.map((i) => (
                    <Table.Tr key={i.id}>
                      <Table.Td>
                        <Link to={`/indicateurs/${i.id}`}>{i.libelle}</Link>
                      </Table.Td>
                      <Table.Td>{i.unite}</Table.Td>
                      <Table.Td>{i.valeur_reference ?? "—"}</Table.Td>
                      <Table.Td>{i.valeur_cible}</Table.Td>
                      <Table.Td>
                        <AlerteBadge palier={i.palier_actuel} taux={i.taux_realisation_actuel} />
                      </Table.Td>
                      <Table.Td>
                        {editionActive && (
                        <Group gap={4} wrap="nowrap">
                          <Tooltip label={voc("Modifier l'indicateur")}>
                            <ActionIcon variant="subtle" onClick={() => setIndicateurEnEdition(i)}>
                              <Pencil size={15} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label={voc("Supprimer l'indicateur")}>
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              loading={deleteIndicateur.isPending}
                              onClick={() => handleSupprimer(i.id, i.libelle)}
                            >
                              <Trash2 size={15} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Card>
          ))}
        </Stack>
      )}

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title={voc("Nouvel indicateur")} size="lg">
        <IndicateurForm onDone={() => setModalOpen(false)} />
      </Modal>

      <Modal opened={!!indicateurEnEdition} onClose={() => setIndicateurEnEdition(null)} title={voc("Modifier l'indicateur")} size="lg">
        {indicateurEnEdition && (
          <IndicateurForm indicateur={indicateurEnEdition} onDone={() => setIndicateurEnEdition(null)} />
        )}
      </Modal>

      <ImportIndicateursModal opened={modalImportOuvert} onClose={() => setModalImportOuvert(false)} />
    </Stack>
  );
}
