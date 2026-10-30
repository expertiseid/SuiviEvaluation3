import { useState } from "react";
import { Download, Upload } from "lucide-react";
import { Alert, Button, FileInput, Group, List, Modal, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useImporterStructuration, telechargerModeleImportStructuration } from "../../api/strategy";
import type { ImportStructurationResultat } from "../../types";
import { voc } from "../../utils/vocabulaire";

/**
 * Import Excel d'un document. Cadre stratégique : la structuration seule. Programme, Pilier…
 * (`avecFiche`) : modèle comme celui d'un projet — feuilles Fiche, Financements et Structuration.
 */
export function ImportStructurationModal({
  opened,
  onClose,
  cadreStrategiqueId,
  avecFiche = false,
}: {
  opened: boolean;
  onClose: () => void;
  cadreStrategiqueId: number;
  avecFiche?: boolean;
}) {
  const importer = useImporterStructuration();
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ImportStructurationResultat | null>(null);

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
    formData.append("cadre_strategique", String(cadreStrategiqueId));
    try {
      const res = await importer.mutateAsync(formData);
      setResultat(res);
      if (res.elements_crees > 0 || res.elements_mis_a_jour > 0 || res.fiche_mise_a_jour) {
        notifications.show({
          message: voc`${res.elements_crees} élément(s) créé(s), ${res.elements_mis_a_jour} mis à jour`,
          color: "green",
        });
      }
    } catch {
      notifications.show({ message: voc("Erreur lors de l'import — vérifie le format du fichier."), color: "red" });
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={fermer}
      title={avecFiche ? voc("Importer la fiche et la structuration depuis Excel") : voc("Importer la structuration depuis Excel")}
      size="lg"
    >
      <Stack gap="md">
        {avecFiche && (
          <Alert color="teal" variant="light">
            {voc("Même modèle que pour un projet : feuille « Fiche » (un champ par ligne, préremplie avec les valeurs actuelles), « Financements » (un bailleur par ligne) et « Structuration » (une colonne par niveau, puis « Contribue à (code) »). Une cellule vide ne change rien.")}
          </Alert>
        )}
        <Alert color="blue" variant="light">
          {voc("Utilise le modèle ci-dessous : une colonne = un niveau. Écris chaque élément dans la colonne de son niveau, une seule colonne par ligne — son rattachement au niveau supérieur se déduit automatiquement du dernier élément écrit juste à gauche, au-dessus. Les niveaux manquants sont créés automatiquement. Réimporter le même fichier met à jour les éléments déjà importés au lieu de les dupliquer.")}
        </Alert>

        <Button
          variant="light"
          leftSection={<Download size={16} />}
          onClick={() => telechargerModeleImportStructuration(cadreStrategiqueId)}
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
            <Alert
              color={resultat.elements_crees > 0 || resultat.elements_mis_a_jour > 0 ? "green" : "orange"}
              title={voc("Résultat de l'import")}
            >
              {resultat.fiche_mise_a_jour && <Text size="sm">{voc("Fiche et bailleurs mis à jour.")}</Text>}
              <Text size="sm">
                <strong>{resultat.niveaux_crees}</strong> {voc("niveau(x) créé(s),")} <strong>{resultat.elements_crees}</strong> {voc("élément(s) créé(s),")} <strong>{resultat.elements_mis_a_jour}</strong> {voc("mis à jour.")}
              </Text>
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

            {(resultat.avertissements ?? []).length > 0 && (
              <Alert color="yellow" title={voc("À vérifier")}>
                <List size="sm">
                  {resultat.avertissements.map((e, i) => (
                    <List.Item key={i}>{e.message}</List.Item>
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
