import { Button, Group, SegmentedControl, Stack, Table, Text } from "@mantine/core";
import { DEPENDANCES, modulesReglables, niveauParDefaut } from "../../utils/modules";
import type { NiveauModule } from "../../types";
import { voc } from "../../utils/vocabulaire";

const CHOIX_ECRITURE = [
  { value: "MASQUE", label: voc("Masqué") },
  { value: "LECTURE", label: voc("Consultation") },
  { value: "ECRITURE", label: voc("Création et modification") },
];
const CHOIX_VISIBILITE = [
  { value: "MASQUE", label: voc("Masqué") },
  { value: "VISIBLE", label: voc("Visible") },
];
const COULEURS: Record<string, string> = { MASQUE: "red", LECTURE: "blue", ECRITURE: "teal", VISIBLE: "teal" };

/**
 * Droits d'un utilisateur module par module. Seuls les modules réglés autrement que le niveau
 * d'accès par défaut sont enregistrés : les autres suivent ce niveau.
 */
export function DroitsModules({
  value,
  onChange,
  niveauAcces,
}: {
  value: Record<string, NiveauModule>;
  onChange: (valeur: Record<string, NiveauModule>) => void;
  niveauAcces: string | null;
}) {
  const defaut = niveauParDefaut(niveauAcces);
  const libelles = Object.fromEntries(modulesReglables().flatMap((g) => g.items.map((m) => [m.cle, m.label])));
  // Module masqué avec celui dont il dépend (ex. doublons avec bénéficiaires).
  const masquePar = (cle: string) =>
    Object.keys(DEPENDANCES).find((source) => DEPENDANCES[source].includes(cle) && value[source] === "MASQUE");

  function regler(cle: string, choix: string, ecriture: boolean) {
    const suite = { ...value };
    const parDefaut = ecriture ? choix === defaut : choix === "VISIBLE";
    if (parDefaut) delete suite[cle];
    else suite[cle] = (choix === "VISIBLE" ? defaut : choix) as NiveauModule;
    onChange(suite);
  }

  return (
    <Stack gap={4}>
      <Group justify="space-between" align="flex-end">
        <div>
          <Text size="sm" fw={500}>{voc("Droits par module")}</Text>
          <Text size="xs" c="dimmed">
            {voc("Par défaut, chaque module suit le niveau d'accès ci-dessus. Les onglets peuvent seulement être masqués.")}
          </Text>
        </div>
        <Button size="compact-xs" variant="subtle" disabled={Object.keys(value).length === 0} onClick={() => onChange({})}>
          {voc("Tout remettre par défaut")}
        </Button>
      </Group>
      <Table verticalSpacing={4} fz="sm">
        <Table.Tbody>
          {modulesReglables().map((groupe) => [
            <Table.Tr key={groupe.group}>
              <Table.Td colSpan={2} pt="sm">
                <Text size="xs" fw={700} c="dimmed" tt="uppercase">{groupe.group}</Text>
              </Table.Td>
            </Table.Tr>,
            ...groupe.items.map((m) => {
              const regle = value[m.cle];
              const source = masquePar(m.cle);
              const choix = source ? "MASQUE" : m.ecriture ? (regle ?? defaut) : regle === "MASQUE" ? "MASQUE" : "VISIBLE";
              return (
                <Table.Tr key={m.cle}>
                  <Table.Td>
                    {m.label}
                    {source ? (
                      <Text span size="xs" c="dimmed"> {voc("· masqué avec «")} {libelles[source]} »</Text>
                    ) : (
                      regle && <Text span size="xs" c="dimmed"> {voc("· personnalisé")}</Text>
                    )}
                  </Table.Td>
                  <Table.Td align="right">
                    <SegmentedControl
                      size="xs"
                      color={COULEURS[choix]}
                      data={m.ecriture ? CHOIX_ECRITURE : CHOIX_VISIBILITE}
                      value={choix}
                      disabled={!!source}
                      onChange={(v) => regler(m.cle, v, m.ecriture)}
                    />
                  </Table.Td>
                </Table.Tr>
              );
            }),
          ])}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
