import { useState } from "react";
import { Download, Upload } from "lucide-react";
import { Alert, Button, FileInput, Group, List, Modal, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useImporterIndicateurs, telechargerModeleImportIndicateurs } from "../../api/indicators";
import type { ImportIndicateursResultat } from "../../types";
import { voc } from "../../utils/vocabulaire";

export function ImportIndicateursModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const importer = useImporterIndicateurs();
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ImportIndicateursResultat | null>(null);

  function fermer() {
    setFichier(null);
    setResultat(null);
    onClose();
  }

  async function handleImporter() {
    if (!fichier) {
      notifications.show({ message: voc("Choisis d'abord un fichier Excel."), color: "orange" });
      return;
    }
    const formData = new FormData();
    formData.append("fichier", fichier);
    try {
      const res = await importer.mutateAsync(formData);
      setResultat(res);
      if (res.crees > 0) {
        notifications.show({ message: voc`${res.crees} indicateur(s) importé(s)`, color: "green" });
      }
    } catch {
      notifications.show({ message: voc("Erreur lors de l'import — vérifie le format du fichier."), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={fermer} title={voc("Importer des indicateurs depuis Excel")} size="lg">
      <Stack gap="md">
        <Alert color="blue" variant="light">
          {voc("Une ligne = un indicateur. Le rattachement (Projet, ou nom d'un niveau de la planification : Objectif, Résultat, Pilier, Activité…) se fait par le code exact du projet et le libellé exact de l'élément — laisse « Aucun » pour un indicateur stratégique sans projet.")}</Alert>

        <Button
          variant="light"
          leftSection={<Download size={16} />}
          onClick={() => telechargerModeleImportIndicateurs()}
        >
          {voc("Télécharger le modèle Excel")}
        </Button>

        <Group align="flex-end">
          <FileInput
            label={voc("Fichier à importer")}
            placeholder={voc("Choisir un fichier .xlsx")}
            accept=".xlsx"
            value={fichier}
            onChange={setFichier}
            style={{ flex: 1 }}
          />
          <Button leftSection={<Upload size={16} />} onClick={handleImporter} loading={importer.isPending}>
            {voc("Importer")}
          </Button>
        </Group>

        {resultat && (
          <Stack gap="xs">
            <Alert color={resultat.crees > 0 ? "green" : "orange"} title={voc("Résultat de l'import")}>
              <Text size="sm"><strong>{resultat.crees}</strong> {voc(" indicateur(s) créé(s).")}</Text>
            </Alert>

            {resultat.erreurs.length > 0 && (
              <Alert color="red" title={voc`${resultat.erreurs.length} ligne(s) ignorée(s)`}>
                <List size="sm">
                  {resultat.erreurs.map((e, i) => (
                    <List.Item key={i}>{voc("Ligne")} {e.ligne} : {e.message}</List.Item>
                  ))}
                </List>
              </Alert>
            )}

            {resultat.avertissements.length > 0 && (
              <Alert color="yellow" title={voc`${resultat.avertissements.length} avertissement(s)`}>
                <List size="sm">
                  {resultat.avertissements.map((a, i) => (
                    <List.Item key={i}>{voc("Ligne")} {a.ligne} : {a.message}</List.Item>
                  ))}
                </List>
              </Alert>
            )}
          </Stack>
        )}

        <Group justify="flex-end">
          <Button variant="subtle" onClick={fermer}>{voc("Fermer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
