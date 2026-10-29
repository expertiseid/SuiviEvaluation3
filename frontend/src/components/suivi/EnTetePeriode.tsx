import { Card, Group, Text } from "@mantine/core";
import { CalendarRange } from "lucide-react";
import { fmtDateLongue } from "../../utils/periode";
import type { PeriodePlanification } from "../../types";
import { voc } from "../../utils/vocabulaire";

/** Bandeau des dates d'une période de planification, affiché en grand en tête des onglets « par période ». */
export function EnTetePeriode({ periode }: { periode: PeriodePlanification }) {
  return (
    <Card withBorder padding="lg" radius="md" style={{ borderLeft: "4px solid var(--mantine-color-teal-6)" }}>
      <Group gap="md" wrap="nowrap">
        <CalendarRange size={34} color="var(--mantine-color-teal-6)" />
        <div>
          {periode.libelle && <Text size="sm" c="dimmed" fw={600} tt="uppercase">{periode.libelle}</Text>}
          <Text fz={26} fw={700} lh={1.2}>
            {voc("Du")} {fmtDateLongue(periode.date_debut)} {voc("au")} {fmtDateLongue(periode.date_fin)}
          </Text>
        </div>
      </Group>
    </Card>
  );
}
