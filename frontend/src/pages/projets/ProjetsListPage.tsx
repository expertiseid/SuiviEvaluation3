import { useState } from "react";
import { FileSpreadsheet, Pencil, Trash2 } from "lucide-react";
import { ActionIcon, Button, Group, Modal, Stack, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useDeleteProjet, useProjets } from "../../api/projects";
import { ProjetForm } from "./ProjetForm";
import { ImportProjetModal } from "./ImportProjetModal";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { ListeProjets } from "../../components/projets/ListeProjets";
import type { ProjetResume } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

export function ProjetsListPage() {
  const { data: projets, isLoading } = useProjets();
  const deleteProjet = useDeleteProjet();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImportOuvert, setModalImportOuvert] = useState(false);
  const [projetEnEdition, setProjetEnEdition] = useState<ProjetResume | null>(null);
  const [editionActive, setEditionActive] = useState(false);

  function handleSupprimer(id: number, nom: string) {
    confirmerSuppression({
      message: voc`Supprimer le projet "${nom}" ainsi que toute sa planification et ses indicateurs ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteProjet.mutateAsync(id);
          notifications.show({ message: voc("Projet supprimé"), color: "green" });
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression du projet"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <TitreRubrique route="/projets" defaut={voc("Projets")} />
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          <Button variant="light" leftSection={<FileSpreadsheet size={16} />} onClick={() => setModalImportOuvert(true)}>
            {voc("Importer depuis Excel")}
          </Button>
          <Button onClick={() => setModalOpen(true)}>{voc("Nouveau projet")}</Button>
        </Group>
      </Group>

      <ListeProjets projets={projets} isLoading={isLoading} lien={(p) => `/projets/${p.id}`}
        actions={editionActive ? (p) => (
          <Group gap={4} wrap="nowrap">
            <Tooltip label={voc("Modifier le projet")}>
              <ActionIcon variant="subtle" onClick={() => setProjetEnEdition(p)}>
                <Pencil size={15} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={voc("Supprimer le projet")}>
              <ActionIcon variant="subtle" color="red" loading={deleteProjet.isPending} onClick={() => handleSupprimer(p.id, p.nom)}>
                <Trash2 size={15} />
              </ActionIcon>
            </Tooltip>
          </Group>
        ) : undefined} />

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title={voc("Nouveau projet")} size="lg">
        <ProjetForm onDone={() => setModalOpen(false)} />
      </Modal>

      <Modal opened={!!projetEnEdition} onClose={() => setProjetEnEdition(null)} title={voc("Modifier le projet")} size="lg">
        {projetEnEdition && (
          <ProjetForm projet={projetEnEdition} onDone={() => setProjetEnEdition(null)} />
        )}
      </Modal>

      <ImportProjetModal opened={modalImportOuvert} onClose={() => setModalImportOuvert(false)} />
    </Stack>
  );
}
