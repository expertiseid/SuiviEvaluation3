import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { voc } from "../../utils/vocabulaire";

interface Entree {
  id: number;
  libelle: string;
  taux_realisation: number;
  palier_actuel: { libelle: string; couleur: string } | null;
}

function tronquer(texte: string, max = 28) {
  return texte.length > max ? `${texte.slice(0, max - 1)}…` : texte;
}

export function TauxParIndicateurChart({ indicateurs }: { indicateurs: Entree[] }) {
  if (indicateurs.length === 0) return null;

  const data = indicateurs.map((i) => ({ ...i, label: tronquer(i.libelle) }));
  const hauteur = Math.max(120, data.length * 34);

  return (
    <ResponsiveContainer width="100%" height={hauteur}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 32, bottom: 4, left: 4 }}>
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          type="category"
          dataKey="label"
          width={150}
          tickLine={false}
          axisLine={false}
          tick={{ fill: "var(--mantine-color-dimmed)", fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "var(--mantine-color-gray-1)" }}
          formatter={(value) => [`${value}%`, voc("Taux de réalisation")]}
          labelFormatter={(_label, payload) => payload?.[0]?.payload?.libelle ?? ""}
        />
        <Bar dataKey="taux_realisation" radius={[0, 4, 4, 0]} maxBarSize={18}>
          {data.map((entry) => (
            <Cell key={entry.id} fill={entry.palier_actuel?.couleur ?? "#999999"} />
          ))}
          <LabelList
            dataKey="taux_realisation"
            position="right"
            formatter={(v) => (v === undefined || v === null ? "" : `${v}%`)}
            style={{ fill: "var(--mantine-color-dark-6)", fontSize: 12, fontWeight: 600 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
