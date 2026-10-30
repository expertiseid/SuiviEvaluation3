import { useState } from "react";
import { Alert, Button, FileInput, Group, List, Menu, Modal, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Download, FileInput as IconeCanevas, FileSpreadsheet, FileText, Upload } from "lucide-react";
import { telechargerPlanification, useImporterPlanification } from "../../api/projects";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

/**
 * Menu « Exporter » de la planification d'un projet (modes Arbre et Tableau), comme celui d'un
 * document stratégique : tableau complet ou export simple, en Excel ou en PDF, et le canevas de
 * remplissage réimportable. `annee` absente : le serveur choisit (année en cours).
 */
export function MenuExportPlanification({
  projetId,
  code,
  programmation,
  annee,
}: {
  projetId: number;
  code: string;
  programmation: "trimestres" | "dates";
  annee?: number;
}) {
  const [enCours, setEnCours] = useState(false);

  async function exporter(contenu: "complet" | "simple" | "canevas", fichier: "xlsx" | "pdf" = "xlsx") {
    setEnCours(true);
    try {
      await telechargerPlanification(projetId, code, contenu, fichier, programmation, annee);
    } catch {
      notifications.show({ message: voc("Erreur lors de l'export"), color: "red" });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button size="xs" variant="light" leftSection={<Download size={14} />} loading={enCours}>
          {voc("Exporter")}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{voc("Tableau complet (programmation, budgets, taux)")}</Menu.Label>
        <Menu.Item leftSection={<FileSpreadsheet size={14} />} onClick={() => exporter("complet", "xlsx")}>{voc("Excel (.xlsx)")}</Menu.Item>
        <Menu.Item leftSection={<FileText size={14} />} onClick={() => exporter("complet", "pdf")}>{voc("PDF")}</Menu.Item>
        <Menu.Divider />
        <Menu.Label>{voc("Export simple (structure seule)")}</Menu.Label>
        <Menu.Item leftSection={<FileSpreadsheet size={14} />} onClick={() => exporter("simple", "xlsx")}>{voc("Excel (.xlsx)")}</Menu.Item>
        <Menu.Item leftSection={<FileText size={14} />} onClick={() => exporter("simple", "pdf")}>{voc("PDF")}</Menu.Item>
        <Menu.Divider />
        <Menu.Label>{voc("Réimportable")}</Menu.Label>
        <Menu.Item leftSection={<IconeCanevas size={14} />} onClick={() => exporter("canevas")}>
          <Text size="sm">{voc("Canevas de remplissage (Excel)")}</Text>
          <Text size="xs" c="dimmed">{voc("À compléter puis réimporter avec « Importer depuis Excel »")}</Text>
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

/** Bouton et fenêtre de réimport du canevas de la planification dans le projet. */
export function ImportPlanification({ projetId, code }: { projetId: number; code: string }) {
  const importer = useImporterPlanification(projetId);
  const [ouvert, setOuvert] = useState(false);
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<Awaited<ReturnType<typeof importer.mutateAsync>> | null>(null);

  function fermer() {
    setOuvert(false);
    setFichier(null);
    setResultat(null);
  }

  async function lancer() {
    if (!fichier) return;
    try {
      setResultat(await importer.mutateAsync(fichier));
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'import — vérifie le format du fichier.")), color: "red", autoClose: 10000 });
    }
  }

  return (
    <>
      <Button size="xs" variant="light" leftSection={<Upload size={14} />} onClick={() => setOuvert(true)}>
        {voc("Importer depuis Excel")}
      </Button>
      <Modal opened={ouvert} onClose={fermer} title={voc("Importer la planification depuis Excel")} size="lg">
        <Stack gap="sm">
          <Alert color="blue" variant="light">
            {voc("Téléchargez le canevas (déjà rempli avec la planification actuelle), complétez-le, puis importez-le : les éléments de même libellé et même parent sont mis à jour, les nouvelles lignes ajoutées. Rien n'est supprimé.")}
          </Alert>
          <Button
            variant="light"
            leftSection={<Download size={16} />}
            onClick={() => telechargerPlanification(projetId, code, "canevas", "xlsx", "trimestres")}
          >
            {voc("Télécharger le canevas de la planification")}
          </Button>
          <FileInput label={voc("Fichier Excel (.xlsx)")} accept=".xlsx" value={fichier} onChange={setFichier} clearable />
          <Group justify="flex-end">
            <Button leftSection={<Upload size={16} />} onClick={lancer} loading={importer.isPending} disabled={!fichier}>
              {voc("Importer")}
            </Button>
          </Group>
          {resultat && (
            <Stack gap={6}>
              <Alert color={resultat.erreurs.length ? "orange" : "green"} variant="light">
                {voc`${resultat.elements_crees} élément(s) et ${resultat.sous_activites_creees} sous-activité(s) ajoutés ; les éléments existants sont mis à jour.`}
              </Alert>
              {resultat.erreurs.length > 0 && (
                <>
                  <Text size="sm" fw={600} c="red.7">{voc("Erreurs (lignes ignorées)")}</Text>
                  <List size="sm">{resultat.erreurs.map((e, i) => <List.Item key={i}>{voc`Ligne ${e.ligne}`} : {e.message}</List.Item>)}</List>
                </>
              )}
            </Stack>
          )}
        </Stack>
      </Modal>
    </>
  );
}
