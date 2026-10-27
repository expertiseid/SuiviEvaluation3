import { useState } from "react";
import { Download, Upload } from "lucide-react";
import { Alert, Button, FileInput, Group, List, Modal, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useImporterBeneficiaires, telechargerModeleImportBeneficiaires } from "../../api/beneficiaries";
import type { ImportBeneficiairesResultat } from "../../types";
import { voc } from "../../utils/vocabulaire";

export function ImportBeneficiairesModal({
  opened,
  onClose,
  projet,
}: {
  opened: boolean;
  onClose: () => void;
  // Import depuis la fiche projet : chaque bénéficiaire importé est inscrit à ce projet.
  projet?: { id: number; nom: string };
}) {
  const importer = useImporterBeneficiaires();
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultat, setResultat] = useState<ImportBeneficiairesResultat | null>(null);

  function fermer() {
    setFichier(null);
    setResultat(null);
    onClose();
  }

  async function handleImporter() {
    if (!fichier) {
      notifications.show({ message: "Choisis d'abord un fichier Excel.", color: "orange" });
      return;
    }
    const formData = new FormData();
    formData.append("fichier", fichier);
    if (projet) formData.append("projet", String(projet.id));
    try {
      const res = await importer.mutateAsync(formData);
      setResultat(res);
      if (res.crees > 0) {
        notifications.show({ message: voc`${res.crees} bénéficiaire(s) importé(s)`, color: "green" });
      }
    } catch {
      notifications.show({ message: "Erreur lors de l'import — vérifie le format du fichier.", color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={fermer} title={voc("Importer des bénéficiaires depuis Excel")} size="lg">
      <Stack gap="md">
        <Alert color="blue" variant="light">
          Utilise le modèle ci-dessous pour être sûr que les colonnes sont dans le bon format, puis
          remplis-le et importe-le. Les régions/provinces doivent correspondre à des zones existantes ;
          les communes/villages sont créés automatiquement s'ils n'existent pas encore.
          {projet && (
            <>
              {" "}{voc("Chaque bénéficiaire importé sera automatiquement associé au projet ")}<strong>{projet.nom}</strong>
              {" "}{voc("(sauf si sa ligne indique un autre Code projet).")}</>
          )}
        </Alert>

        <Button
          variant="light"
          leftSection={<Download size={16} />}
          onClick={() => telechargerModeleImportBeneficiaires()}
        >
          Télécharger le modèle Excel
        </Button>

        <Group align="flex-end">
          <FileInput
            label="Fichier à importer"
            placeholder="Choisir un fichier .xlsx"
            accept=".xlsx"
            value={fichier}
            onChange={setFichier}
            style={{ flex: 1 }}
          />
          <Button leftSection={<Upload size={16} />} onClick={handleImporter} loading={importer.isPending}>
            Importer
          </Button>
        </Group>

        {resultat && (
          <Stack gap="xs">
            <Alert color={resultat.crees > 0 ? "green" : "orange"} title="Résultat de l'import">
              <Text size="sm">
                <strong>{resultat.crees}</strong> {voc(" bénéficiaire(s) créé(s)")}{resultat.doublons_detectes > 0 && (
                  <>, dont <strong>{resultat.doublons_detectes}</strong> {voc(" doublon(s) potentiel(s) détecté(s) — à traiter dans « Doublons d'enregistrement »")}</>
                )}
                .
              </Text>
            </Alert>

            {resultat.erreurs.length > 0 && (
              <Alert color="red" title={`${resultat.erreurs.length} ligne(s) ignorée(s)`}>
                <List size="sm">
                  {resultat.erreurs.map((e, i) => (
                    <List.Item key={i}>Ligne {e.ligne} : {e.message}</List.Item>
                  ))}
                </List>
              </Alert>
            )}

            {resultat.avertissements.length > 0 && (
              <Alert color="yellow" title={`${resultat.avertissements.length} avertissement(s)`}>
                <List size="sm">
                  {resultat.avertissements.map((a, i) => (
                    <List.Item key={i}>Ligne {a.ligne} : {a.message}</List.Item>
                  ))}
                </List>
              </Alert>
            )}
          </Stack>
        )}

        <Group justify="flex-end">
          <Button variant="subtle" onClick={fermer}>Fermer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
