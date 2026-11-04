import { Group, Stack, Tabs } from "@mantine/core";
import { ChartColumn, FolderOpen, Settings, Wrench } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

const ONGLETS = [
  { route: "/plaintes", libelle: () => voc("Dossiers"), icone: FolderOpen },
  { route: "/plaintes/tableau-de-bord", libelle: () => voc("Tableau de bord"), icone: ChartColumn },
  { route: "/plaintes/actions-correctives", libelle: () => voc("Actions correctives"), icone: Wrench },
  { route: "/plaintes/parametrage", libelle: () => voc("Paramétrage"), icone: Settings },
];

/** En-tête commun des pages du module : titre, actions de la page, onglets des sections. */
export function EnTetePlaintes({ actions }: { actions?: React.ReactNode }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const actif = [...ONGLETS].reverse().find((o) => pathname.startsWith(o.route))?.route ?? "/plaintes";
  return (
    <Stack gap={4}>
      <Group justify="space-between" align="center" gap="sm">
        <TitreRubrique route="/plaintes" defaut={voc("Plaintes et retours")} />
        {actions && <Group gap="xs">{actions}</Group>}
      </Group>
      <Tabs value={actif} onChange={(v) => v && navigate(v)}>
        <Tabs.List>
          {ONGLETS.map(({ route, libelle, icone: Icone }) => (
            <Tabs.Tab key={route} value={route} leftSection={<Icone size={15} />}>{libelle()}</Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
    </Stack>
  );
}
