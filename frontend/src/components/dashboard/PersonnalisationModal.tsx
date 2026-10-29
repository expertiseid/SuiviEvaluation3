import { Button, Checkbox, Group, Modal, SimpleGrid, Stack, Text } from "@mantine/core";
import { voc } from "../../utils/vocabulaire";

export interface DefinitionBloc {
  cle: string;
  titre: string;
  groupe: string;
}

/** Choix des blocs affichés sur le tableau de bord, regroupés par thème. */
export function PersonnalisationModal({
  opened,
  onClose,
  blocs,
  masques,
  onChange,
  onReinitialiserTypes,
}: {
  opened: boolean;
  onClose: () => void;
  blocs: DefinitionBloc[];
  masques: string[];
  onChange: (masques: string[]) => void;
  /** Remet chaque graphique sur son type par défaut. */
  onReinitialiserTypes: () => void;
}) {
  const groupes = [...new Set(blocs.map((b) => b.groupe))];

  function basculer(cle: string) {
    onChange(masques.includes(cle) ? masques.filter((c) => c !== cle) : [...masques, cle]);
  }

  return (
    <Modal opened={opened} onClose={onClose} title={voc("Personnaliser le tableau de bord")} size="xl">
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {voc("Coche les blocs à afficher. Le type de chaque graphique se change avec le petit bouton en haut à droite du bloc. Ces choix s'appliquent au tableau de bord de tous les utilisateurs.")}</Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
          {groupes.map((groupe) => (
            <div key={groupe}>
              <Text fw={700} size="sm" mb={6}>{groupe}</Text>
              <Stack gap={6}>
                {blocs
                  .filter((b) => b.groupe === groupe)
                  .map((b) => (
                    <Checkbox
                      key={b.cle}
                      label={b.titre}
                      checked={!masques.includes(b.cle)}
                      onChange={() => basculer(b.cle)}
                    />
                  ))}
              </Stack>
            </div>
          ))}
        </SimpleGrid>
        <Group justify="space-between" mt="sm">
          <Group gap="xs">
            <Button variant="subtle" onClick={() => onChange([])}>{voc("Tout afficher")}</Button>
            <Button variant="subtle" color="gray" onClick={() => onChange(blocs.map((b) => b.cle))}>
              {voc("Tout masquer")}
            </Button>
            <Button variant="subtle" color="gray" onClick={onReinitialiserTypes}>
              {voc("Types de graphiques par défaut")}
            </Button>
          </Group>
          <Button onClick={onClose}>{voc("Fermer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
