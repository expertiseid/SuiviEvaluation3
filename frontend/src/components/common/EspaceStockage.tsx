import { Progress, Stack, Text } from "@mantine/core";
import type { EspaceStockage } from "../../api/console";
import { volumeLisible } from "../../utils/stockage";
import { voc } from "../../utils/vocabulaire";

/** Jauge de l'espace occupé (console Expertise-ID, page Stockage). */
export function JaugeStockage({ espace, taille = "sm" }: { espace: EspaceStockage; taille?: "sm" | "lg" }) {
  if (espace.utilise == null) return null;
  if (!espace.limite) return <Text size="sm">{volumeLisible(espace.utilise)}</Text>;
  const part = Math.min(100, (espace.utilise / espace.limite) * 100);
  return (
    <Stack gap={4}>
      <Text size={taille === "lg" ? "md" : "sm"}>{voc`${volumeLisible(espace.utilise)} sur ${volumeLisible(espace.limite)}`}</Text>
      <Progress value={Math.max(part, 1)} color={part >= 90 ? "red" : part >= 75 ? "orange" : "teal"} size={taille === "lg" ? "xl" : "sm"} radius="xl" />
    </Stack>
  );
}
