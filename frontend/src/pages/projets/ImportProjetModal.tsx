import { useState } from "react";
import { Download, Upload } from "lucide-react";
import { Alert, Button, FileInput, Group, List, Modal, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useImporterProjet, telechargerModeleImportProjet } from "../../api/projects";
import type { ImportProjetResultat } from "../../types";
import { voc } from "../../utils/vocabulaire";

export function ImportProjetModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const importer = useImporterProjet();
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ImportProjetResultat | null>(null);

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
      if (res.projet_id) {
        notifications.show({ message: voc`Projet « ${res.projet_code} » créé`, color: "green" });
      }
    } catch {
      notifications.show({ message: voc("Erreur lors de l'import — vérifie le format du fichier."), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={fermer} title={voc("Importer un projet depuis Excel")} size="lg">
      <Stack gap="md">
        <Alert color="blue" variant="light">
          {voc("La feuille « Projet » du modèle porte sa fiche (nom, code, dates, modalités, bailleur…) en une ligne par champ. La feuille « Planification » porte sa planification : une colonne par niveau (en jaune dans le modèle, avec les noms et le nombre que tu veux, ex : Résultat → Pilier → Activité), puis Sous-activité — une seule colonne de niveau remplie par ligne.")}</Alert>

        <Button variant="light" leftSection={<Download size={16} />} onClick={() => telechargerModeleImportProjet()}>
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
            <Alert color={resultat.projet_id ? "green" : "orange"} title={voc("Résultat de l'import")}>
              {resultat.projet_id ? (
                <Text size="sm">
                  {voc("Projet ")}<strong>{resultat.projet_code}</strong> {voc("créé —")} <strong>{resultat.elements_crees}</strong>{" "}
                  {voc("élément(s) de planification")}{resultat.niveaux.length > 0 && <> {voc("(niveaux :")} {resultat.niveaux.join(" › ")})</>},{" "}
                  <strong>{resultat.sous_activites_creees}</strong> {voc("sous-activité(s).")}
                </Text>
              ) : (
                <Text size="sm">{voc("Aucun projet créé — voir les erreurs ci-dessous.")}</Text>
              )}
            </Alert>

            {resultat.erreurs.length > 0 && (
              <Alert color="red" title={voc`${resultat.erreurs.length} erreur(s)`}>
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
