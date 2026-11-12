import { Alert, Button, Group, Loader, Text } from "@mantine/core";
import { useInstallerPays, usePaysZones } from "../../api/geo";
import { nomPays } from "../../utils/pays";
import { voc } from "../../utils/vocabulaire";

/**
 * État des zones administratives des pays donnés : installation automatique en cours, terminée, ou échouée
 * (avec « Réessayer »). Rien n'est affiché quand tout est prêt.
 */
export function EtatInstallationZones({ pays }: { pays: string[] }) {
  const { data: etats = [] } = usePaysZones();
  const installer = useInstallerPays();
  const concernes = etats.filter((e) => pays.includes(e.pays));
  const enCours = concernes.filter((e) => e.statut === "EN_COURS");
  const echecs = concernes.filter((e) => e.statut === "ECHEC");
  if (!enCours.length && !echecs.length) return null;
  return (
    <>
      {enCours.length > 0 && (
        <Group gap="xs">
          <Loader size="xs" />
          <Text size="xs" c="dimmed">
            {voc`Zones administratives en cours d'installation : ${enCours.map((e) => nomPays(e.pays)).join(", ")}. Elles apparaîtront d'elles-mêmes dans un instant.`}
          </Text>
        </Group>
      )}
      {echecs.length > 0 && (
        <Alert color="orange" p="xs">
          <Group justify="space-between" gap="xs">
            <Text size="xs">
              {voc`Les zones de ${echecs.map((e) => nomPays(e.pays)).join(", ")} n'ont pas pu être installées automatiquement (source indisponible pour ce pays). Vous pouvez réessayer, ou les saisir sur la page Zones administratives.`}
            </Text>
            <Button size="compact-xs" variant="light" loading={installer.isPending} onClick={() => installer.mutate(echecs.map((e) => e.pays))}>
              {voc("Réessayer")}
            </Button>
          </Group>
        </Alert>
      )}
    </>
  );
}
