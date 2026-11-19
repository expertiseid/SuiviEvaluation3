import { Stack, Text } from "@mantine/core";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { SauvegardeTransfert } from "../organisation/SauvegardeTransfert";
import { voc } from "../../utils/vocabulaire";

/** Export et import global de l'espace : visible de tous, utilisable par l'Administrateur ou sur son autorisation. */
export function ExportGlobalPage() {
  return (
    <Stack gap="md">
      <div>
        <TitreRubrique route="/export-global" defaut={voc("Export et import global")} />
        <Text c="dimmed" size="sm">
          {voc("Sauvegarde de tout l'espace (ou d'une partie) dans un fichier, et reprise d'une sauvegarde. Réservé à l'administrateur, sauf autorisation de sa part.")}
        </Text>
      </div>
      <SauvegardeTransfert />
    </Stack>
  );
}
