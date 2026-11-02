import { AlarmClock, CircleCheck, Clock } from "lucide-react";
import { Badge, Group, Text, Tooltip } from "@mantine/core";
import { type DossierPlainte, dateLisible, etatDelai, useMecanisme } from "../../api/plaintes";
import { voc } from "../../utils/vocabulaire";

/** Échéance d'un dossier : date et état (en retard, proche, dans les temps). */
export function BadgeDelai({ dossier, compact = false }: { dossier: DossierPlainte; compact?: boolean }) {
  const { data: mecanisme } = useMecanisme();
  const { etat, jours } = etatDelai(dossier, mecanisme?.rappel_jours_avant ?? 2);
  if (etat === "clos" || jours === null) return <Text size="sm" c="dimmed">—</Text>;
  const etapeDepassee = etat === "retard" && jours >= 0;
  const libelle =
    etat === "retard"
      ? etapeDepassee ? voc("Étape en retard") : voc`En retard de ${-jours} j`
      : jours === 0 ? voc("Aujourd'hui") : voc`Dans ${jours} j`;
  const badge = (
    <Badge
      color={etat === "retard" ? "red" : etat === "proche" ? "orange" : "teal"}
      variant={etat === "ok" ? "light" : "filled"}
      tt="none"
      style={{ flexShrink: 0, maxWidth: "none" }}
      leftSection={etat === "retard" ? <AlarmClock size={11} /> : etat === "proche" ? <Clock size={11} /> : <CircleCheck size={11} />}
    >
      {libelle}
    </Badge>
  );
  if (compact) {
    return (
      <Tooltip label={voc`Échéance : ${dateLisible(dossier.echeance!)}`}>
        <span>{badge}</span>
      </Tooltip>
    );
  }
  return (
    <Group gap={6} wrap="nowrap">
      <Text size="sm">{dateLisible(dossier.echeance!)}</Text>
      {badge}
    </Group>
  );
}
