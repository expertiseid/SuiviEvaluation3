import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LayoutGrid, Pencil, Search, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Button,
  Card,
  Group,
  Modal,
  MultiSelect,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCadresStrategiques,
  useCreateCadreStrategique,
  useDeleteCadreStrategique,
  useUpdateCadreStrategique,
} from "../../api/strategy";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { correspond } from "../../utils/recherche";
import type { CadreStrategique } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";
import { usePartiesPrenantes, useStructures } from "../../api/organisation";
import { optionsStructures } from "../../utils/organisation";

function CadreModal({
  opened,
  onClose,
  cadreExistant,
}: {
  opened: boolean;
  onClose: () => void;
  cadreExistant?: CadreStrategique | null;
}) {
  const createCadre = useCreateCadreStrategique();
  const updateCadre = useUpdateCadreStrategique();
  const [nom, setNom] = useState(cadreExistant?.nom ?? "");
  const [description, setDescription] = useState(cadreExistant?.description ?? "");
  const [structuresIds, setStructuresIds] = useState<string[]>((cadreExistant?.structures ?? []).map(String));
  const [partiesIds, setPartiesIds] = useState<string[]>((cadreExistant?.parties_prenantes ?? []).map(String));
  const { data: structures } = useStructures();
  const { data: partiesPrenantes } = usePartiesPrenantes();

  function reinitialiser() {
    setNom(cadreExistant?.nom ?? "");
    setDescription(cadreExistant?.description ?? "");
    setStructuresIds((cadreExistant?.structures ?? []).map(String));
    setPartiesIds((cadreExistant?.parties_prenantes ?? []).map(String));
  }
  const liens = { structures: structuresIds.map(Number), parties_prenantes: partiesIds.map(Number) };

  async function handleSave() {
    if (!nom.trim()) {
      notifications.show({ message: "Le nom est requis.", color: "orange" });
      return;
    }
    try {
      if (cadreExistant) {
        await updateCadre.mutateAsync({ id: cadreExistant.id, payload: { nom: nom.trim(), description, ...liens } });
        notifications.show({ message: voc("Cadre stratégique modifié"), color: "green" });
      } else {
        await createCadre.mutateAsync({ nom: nom.trim(), description, ...liens });
        notifications.show({ message: voc("Cadre stratégique créé"), color: "green" });
      }
      onClose();
    } catch {
      notifications.show({ message: "Erreur lors de l'enregistrement", color: "red" });
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={reinitialiser}
      title={cadreExistant ? voc("Modifier le cadre stratégique") : voc("Nouveau cadre stratégique")}
    >
      <Stack gap="sm">
        <TextInput
          label="Nom"
          description={voc("Ex : « Cadre stratégique 2022-2026 »")}
          value={nom}
          onChange={(e) => setNom(e.currentTarget.value)}
          required
        />
        <Textarea label="Description" minRows={2} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
        <MultiSelect
          label={voc("Services chargés")}
          placeholder="Aucun"
          data={optionsStructures(structures ?? [])}
          value={structuresIds}
          onChange={setStructuresIds}
          searchable
          clearable
        />
        <MultiSelect
          label="Parties prenantes"
          placeholder="Aucune"
          data={(partiesPrenantes ?? []).map((p) => ({ value: String(p.id), label: p.nom }))}
          value={partiesIds}
          onChange={setPartiesIds}
          searchable
          clearable
        />
        <Group justify="flex-end">
          <Button onClick={handleSave} loading={createCadre.isPending || updateCadre.isPending}>
            {cadreExistant ? "Enregistrer" : "Créer"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function CadresStrategiquesListPage() {
  const { data: cadres, isLoading } = useCadresStrategiques();
  const deleteCadre = useDeleteCadreStrategique();
  const [modalOuvert, setModalOuvert] = useState(false);
  const [cadreEnEdition, setCadreEnEdition] = useState<CadreStrategique | null>(null);
  const [recherche, setRecherche] = useState("");
  const [editionActive, setEditionActive] = useState(false);

  const cadresFiltres = useMemo(
    () => (cadres ?? []).filter((c) => correspond(c.nom, recherche) || correspond(c.description, recherche)),
    [cadres, recherche],
  );

  function handleSupprimer(cadre: CadreStrategique) {
    confirmerSuppression({
      message: voc`Supprimer le cadre stratégique « ${cadre.nom} » ainsi que tous ses niveaux et éléments ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteCadre.mutateAsync(cadre.id);
          notifications.show({ message: voc("Cadre stratégique supprimé"), color: "green" });
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression du cadre stratégique"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <TitreRubrique route="/strategie" defaut="Cadres stratégiques" />
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          <Button onClick={() => setModalOuvert(true)}>{voc("Nouveau cadre stratégique")}</Button>
        </Group>
      </Group>

      <TextInput
        placeholder={voc("Rechercher un cadre stratégique…")}
        leftSection={<Search size={15} />}
        value={recherche}
        onChange={(e) => setRecherche(e.currentTarget.value)}
        maw={400}
      />

      {isLoading ? (
        <Text c="dimmed">Chargement…</Text>
      ) : !cadres || cadres.length === 0 ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState
            icon={<LayoutGrid size={32} strokeWidth={1.5} />}
            message={voc("Aucun cadre stratégique pour le moment — crée le premier pour définir sa structuration.")}
          />
        </Card>
      ) : cadresFiltres.length === 0 ? (
        <Card withBorder padding="md" radius="md">
          <EmptyState icon={<LayoutGrid size={32} strokeWidth={1.5} />} message="Aucun cadre ne correspond à la recherche." />
        </Card>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {cadresFiltres.map((cadre) => (
            <Card key={cadre.id} withBorder padding="md" radius="md">
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Text component={Link} to={`/strategie/${cadre.id}`} fw={700} size="md" c="teal.8" style={{ flex: 1 }}>
                  {cadre.nom}
                </Text>
                {editionActive && (
                <Group gap={4} wrap="nowrap">
                  <Tooltip label="Modifier">
                    <ActionIcon variant="subtle" onClick={() => setCadreEnEdition(cadre)}>
                      <Pencil size={15} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Supprimer">
                    <ActionIcon variant="subtle" color="red" loading={deleteCadre.isPending} onClick={() => handleSupprimer(cadre)}>
                      <Trash2 size={15} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
                )}
              </Group>
              {cadre.description && (
                <Text size="sm" c="dimmed" mt={4}>
                  {cadre.description}
                </Text>
              )}
              {(cadre.structures_noms?.length ?? 0) > 0 && (
                <Text size="xs" c="dimmed" mt={4}>{voc("Services")} : {cadre.structures_noms?.join(", ")}</Text>
              )}
              <Button component={Link} to={`/strategie/${cadre.id}`} variant="light" size="xs" mt="sm" fullWidth>
                Ouvrir
              </Button>
            </Card>
          ))}
        </SimpleGrid>
      )}

      <CadreModal opened={modalOuvert} onClose={() => setModalOuvert(false)} />
      <CadreModal
        key={cadreEnEdition?.id ?? "aucun"}
        opened={!!cadreEnEdition}
        onClose={() => setCadreEnEdition(null)}
        cadreExistant={cadreEnEdition}
      />
    </Stack>
  );
}
