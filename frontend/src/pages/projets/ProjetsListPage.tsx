import { useState } from "react";
import { Download, FileSpreadsheet, FileText, Pencil, Sheet, Trash2 } from "lucide-react";
import { ActionIcon, Button, Group, Menu, Modal, Stack, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { exporterListeProjets, useDeleteProjet, useProjets } from "../../api/projects";
import { messageErreurApi } from "../../utils/erreurs";
import { exportAutorise } from "../../utils/exportsAutorises";
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
  // Projets affichés (null : tous) : l'export suit le filtre de la liste.
  const [affiches, setAffiches] = useState<number[] | null>(null);
  const [exportEnCours, setExportEnCours] = useState(false);

  async function exporter(fichier: "xlsx" | "docx" | "pdf") {
    setExportEnCours(true);
    try {
      await exporterListeProjets(fichier, affiches);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Le téléchargement a échoué.")), color: "red" });
    } finally {
      setExportEnCours(false);
    }
  }

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
          {exportAutorise() && (
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <Button variant="light" leftSection={<Download size={16} />} loading={exportEnCours}>{voc("Exporter")}</Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>{affiches ? voc`${affiches.length} projet(s) affiché(s)` : voc("Tous les projets")}</Menu.Label>
                <Menu.Item leftSection={<Sheet size={15} color="var(--mantine-color-green-7)" />} onClick={() => exporter("xlsx")}>Excel</Menu.Item>
                <Menu.Item leftSection={<FileText size={15} color="var(--mantine-color-blue-7)" />} onClick={() => exporter("docx")}>Word</Menu.Item>
                <Menu.Item leftSection={<FileText size={15} color="var(--mantine-color-red-7)" />} onClick={() => exporter("pdf")}>PDF</Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
          <Button variant="light" leftSection={<FileSpreadsheet size={16} />} onClick={() => setModalImportOuvert(true)}>
            {voc("Importer depuis Excel")}
          </Button>
          <Button onClick={() => setModalOpen(true)}>{voc("Nouveau projet")}</Button>
        </Group>
      </Group>

      <ListeProjets projets={projets} isLoading={isLoading} lien={(p) => `/projets/${p.id}`} surFiltre={setAffiches}
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
