import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface PointReel {
  date: string;
  valeur: number;
}

function versTimestamp(dateIso: string) {
  return new Date(dateIso).getTime();
}

function formatTick(ts: number) {
  return new Date(ts).toISOString().slice(0, 10);
}

/** Courbe du cumul réalisé dans le temps, avec la cible en repère horizontal. */
export function EvolutionChart({
  data,
  cible,
  unite,
  height = 160,
}: {
  data: PointReel[];
  cible?: number | null;
  unite?: string;
  height?: number;
}) {
  const realise = data.map((p) => ({ ts: versTimestamp(p.date), valeur: p.valeur }));
  if (realise.length === 0) {
    return null;
  }

  const tousLesTs = realise.map((p) => p.ts);
  const domaine: [number, number] = [Math.min(...tousLesTs), Math.max(...tousLesTs)];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--mantine-color-gray-2)" />
        <XAxis
          dataKey="ts"
          type="number"
          domain={domaine}
          tickFormatter={formatTick}
          tick={{ fontSize: 13, fill: "var(--mantine-color-dimmed)" }}
          allowDuplicatedCategory={false}
        />
        <YAxis tick={{ fontSize: 13, fill: "var(--mantine-color-dimmed)" }} width={56} />
        <Tooltip
          labelFormatter={(ts) => formatTick(Number(ts))}
          formatter={(value) => [`${value}${unite ? " " + unite : ""}`, "Cumul réalisé"]}
        />
        {cible != null && (
          <ReferenceLine
            y={cible}
            stroke="var(--mantine-color-teal-6)"
            strokeDasharray="4 4"
            label={{ value: "Cible", position: "insideTopRight", fontSize: 12, fill: "var(--mantine-color-teal-7)" }}
          />
        )}
        <Line
          data={realise}
          dataKey="valeur"
          type="monotone"
          stroke="var(--mantine-color-teal-7)"
          strokeWidth={2}
          dot={{ r: 3 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
