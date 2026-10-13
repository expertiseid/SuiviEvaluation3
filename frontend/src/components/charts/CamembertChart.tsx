import { Group, Stack, Text } from "@mantine/core";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

export interface PartCamembert {
  libelle: string;
  valeur: number;
  couleur: string;
}

/**
 * Graphique en camembert (anneau) avec le total au centre et une légende
 * « libellé — valeur (pourcentage) » à côté — tableau de bord consolidé.
 */
export function CamembertChart({
  parts,
  unite,
  formatValeur = (v) => v.toLocaleString("fr-FR"),
  formatCourt = formatValeur,
}: {
  parts: PartCamembert[];
  unite: string;
  /** Format complet, dans l'infobulle au survol. */
  formatValeur?: (v: number) => string;
  /** Format court (sans unité), au centre et dans la légende — ex : « 11,22 Md ». */
  formatCourt?: (v: number) => string;
}) {
  const visibles = parts.filter((p) => p.valeur > 0);
  const total = visibles.reduce((s, p) => s + p.valeur, 0);
  if (total === 0) return <Text size="sm" c="dimmed" py="xl" ta="center">Aucune donnée.</Text>;

  return (
    <Group wrap="nowrap" align="center" gap="md">
      <div style={{ position: "relative", width: 170, height: 170, flexShrink: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={visibles}
              dataKey="valeur"
              nameKey="libelle"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={visibles.length > 1 ? 2 : 0}
              isAnimationActive={false}
            >
              {visibles.map((p) => (
                <Cell key={p.libelle} fill={p.couleur} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [
                `${formatValeur(Number(value))} (${Math.round((Number(value) / total) * 1000) / 10} %)`,
                name,
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
        <Stack gap={0} align="center" justify="center" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
          <Text fw={700} size={formatCourt(total).length > 7 ? "md" : "xl"} lh={1.1} ta="center" maw={92}>
            {formatCourt(total)}
          </Text>
          <Text size="xs" c="dimmed">{unite}</Text>
        </Stack>
      </div>
      <Stack gap={6} style={{ minWidth: 0 }}>
        {visibles.map((p) => (
          <Group key={p.libelle} gap={8} wrap="nowrap" align="flex-start">
            <div style={{ width: 12, height: 12, borderRadius: 3, background: p.couleur, marginTop: 4, flexShrink: 0 }} />
            <Text size="sm" lh={1.35}>
              {p.libelle}{" "}
              <Text span fw={700}>{formatCourt(p.valeur)}</Text>{" "}
              <Text span c="dimmed">({Math.round((p.valeur / total) * 100)} %)</Text>
            </Text>
          </Group>
        ))}
      </Stack>
    </Group>
  );
}
