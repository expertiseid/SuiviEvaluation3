import { ActionIcon, Menu, Table, Text, Tooltip as InfoBulle } from "@mantine/core";
import {
  AreaChart as IconeAires,
  BarChart3,
  BarChartHorizontal,
  Check,
  Columns3,
  LineChart as IconeCourbe,
  PieChart as IconeCamembert,
  Table as IconeTableau,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";
import { CamembertChart } from "./CamembertChart";
import type { TypeGraphique } from "../../utils/typesGraphiques";


import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
export interface SerieGraphique {
  cle: string;
  nom: string;
  couleur: string;
  valeurs: (number | null)[];
}

const LIBELLES: Record<TypeGraphique, { libelle: string; icone: ReactNode }> = {
  camembert: { libelle: voc("Camembert"), icone: <IconeCamembert size={15} /> },
  colonnes: { libelle: voc("Colonnes"), icone: <BarChart3 size={15} /> },
  "colonnes-empilees": { libelle: voc("Colonnes empilées"), icone: <Columns3 size={15} /> },
  barres: { libelle: voc("Barres horizontales"), icone: <BarChartHorizontal size={15} /> },
  courbes: { libelle: voc("Courbes"), icone: <IconeCourbe size={15} /> },
  aires: { libelle: voc("Aires"), icone: <IconeAires size={15} /> },
  tableau: { libelle: voc("Tableau"), icone: <IconeTableau size={15} /> },
};


/** Menu de choix du type de graphique, placé dans l'en-tête d'un bloc. */
export function ChoixTypeGraphique({
  valeur,
  types,
  onChange,
}: {
  valeur: TypeGraphique;
  types: TypeGraphique[];
  onChange: (t: TypeGraphique) => void;
}) {
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <InfoBulle label={voc`Type de graphique : ${LIBELLES[valeur].libelle}`}>
          <ActionIcon variant="light" color="gray" size="md">
            {LIBELLES[valeur].icone}
          </ActionIcon>
        </InfoBulle>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{voc("Type de graphique")}</Menu.Label>
        {types.map((t) => (
          <Menu.Item
            key={t}
            leftSection={LIBELLES[t].icone}
            rightSection={t === valeur ? <Check size={14} /> : null}
            onClick={() => onChange(t)}
          >
            {LIBELLES[t].libelle}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

const AXE = { fontSize: 13, fill: "var(--mantine-color-dimmed)" };
const GRILLE = "var(--mantine-color-gray-2)";

/**
 * Graphique dont le type est choisi par l'utilisateur, à partir de données
 * « catégories × séries » (ex : projets × statuts d'activité). Avec une seule
 * série, `couleursCategories` colore chaque catégorie (camembert, colonnes…).
 */
export function GraphiqueAdaptable({
  type,
  categories,
  series,
  couleursCategories,
  formatValeur = (v) => v.toLocaleString(locale()),
  formatAxe,
  formatCategorie = (c) => c,
  unite = "",
  hauteur = 280,
  etiquettes = true,
}: {
  type: TypeGraphique;
  categories: string[];
  series: SerieGraphique[];
  couleursCategories?: string[];
  formatValeur?: (v: number) => string;
  /** Format court des graduations (ex : « 1,2 M »), sinon formatValeur. */
  formatAxe?: (v: number) => string;
  formatCategorie?: (c: string) => string;
  unite?: string;
  hauteur?: number;
  etiquettes?: boolean;
}) {
  if (categories.length === 0 || series.length === 0) {
    return <Text size="sm" c="dimmed" py="xl" ta="center">{voc("Aucune donnée.")}</Text>;
  }
  const axe = formatAxe ?? formatValeur;
  const lignes = categories.map((c, i) => ({
    categorie: c,
    ...Object.fromEntries(series.map((s) => [s.cle, s.valeurs[i]])),
  }));
  const uneSerie = series.length === 1;
  const couleurCategorie = (i: number) => couleursCategories?.[i] ?? series[0].couleur;
  const tooltip = (
    <Tooltip
      cursor={{ fill: "var(--mantine-color-gray-1)" }}
      labelFormatter={(c) => formatCategorie(String(c))}
      formatter={(v, nom) => [v === null || v === undefined ? "—" : formatValeur(Number(v)), nom]}
    />
  );
  const legende = !uneSerie && <Legend wrapperStyle={{ fontSize: 13 }} />;
  const etiquette = (cle: string, position: "top" | "right") =>
    etiquettes && (uneSerie || type === "colonnes" || type === "barres") ? (
      <LabelList
        dataKey={cle}
        position={position}
        formatter={(v: unknown) => (v === null || v === undefined ? "" : axe(Number(v)))}
        style={{ fontSize: 12, fontWeight: 600 }}
      />
    ) : null;

  if (type === "camembert" && uneSerie) {
    return (
      <CamembertChart
        unite={unite}
        formatValeur={formatValeur}
        formatCourt={formatAxe}
        parts={categories.map((c, i) => ({
          libelle: formatCategorie(c),
          valeur: series[0].valeurs[i] ?? 0,
          couleur: couleurCategorie(i),
        }))}
      />
    );
  }

  if (type === "tableau") {
    // Le tableau prend le sens qui donne le moins de colonnes (ex : 20 projets
    // × 6 mois → projets en lignes, mois en colonnes), défile dans le bloc,
    // avec première colonne et en-tête figés ; montants au format court.
    const transpose = series.length > categories.length;
    const entetes = transpose ? categories.map(formatCategorie) : series.map((s) => s.nom);
    const lignesTableau = transpose
      ? series.map((s) => ({ libelle: s.nom, couleur: s.couleur, valeurs: s.valeurs }))
      : categories.map((c, i) => ({
          libelle: formatCategorie(c),
          couleur: uneSerie ? couleurCategorie(i) : undefined,
          valeurs: series.map((s) => s.valeurs[i]),
        }));
    const fixe = { position: "sticky", left: 0, zIndex: 1, background: "var(--mantine-color-body)" } as const;
    return (
      <Table.ScrollContainer minWidth={Math.min(1200, 160 + entetes.length * 110)} maw="100%" mah={hauteur + 120}>
        <Table striped withTableBorder withColumnBorders stickyHeader verticalSpacing={6} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={fixe} />
              {entetes.map((e) => <Table.Th key={e} ta="right" style={{ whiteSpace: "nowrap" }}>{e}</Table.Th>)}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {lignesTableau.map((l) => (
              <Table.Tr key={l.libelle}>
                <Table.Td style={{ ...fixe, whiteSpace: "nowrap", fontWeight: 600 }}>
                  {l.couleur && (
                    <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: l.couleur, marginRight: 6 }} />
                  )}
                  {l.libelle}
                </Table.Td>
                {l.valeurs.map((v, i) => (
                  <Table.Td key={i} ta="right" style={{ whiteSpace: "nowrap" }}>
                    {v === null || v === undefined ? "—" : axe(v)}
                  </Table.Td>
                ))}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    );
  }

  if (type === "barres") {
    return (
      <ResponsiveContainer width="100%" height={Math.max(hauteur, categories.length * (uneSerie ? 40 : 26 * series.length + 14))}>
        <BarChart data={lignes} layout="vertical" margin={{ top: 4, right: 64, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={GRILLE} />
          <XAxis type="number" tickFormatter={(v) => axe(Number(v))} tick={AXE} />
          <YAxis type="category" dataKey="categorie" width={150} tickFormatter={formatCategorie} tick={AXE} />
          {tooltip}
          {legende}
          {series.map((s) => (
            <Bar key={s.cle} dataKey={s.cle} name={s.nom} fill={s.couleur} radius={[0, 4, 4, 0]} maxBarSize={26}>
              {uneSerie && categories.map((c, i) => <Cell key={c} fill={couleurCategorie(i)} />)}
              {etiquette(s.cle, "right")}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  const axes = (
    <>
      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRILLE} />
      <XAxis dataKey="categorie" tickFormatter={formatCategorie} tick={AXE} />
      <YAxis tickFormatter={(v) => axe(Number(v))} tick={AXE} width={64} />
      {tooltip}
      {legende}
    </>
  );

  if (type === "courbes") {
    return (
      <ResponsiveContainer width="100%" height={hauteur}>
        <LineChart data={lignes} margin={{ top: 20, right: 24, bottom: 4, left: 0 }}>
          {axes}
          {series.map((s) => (
            <Line key={s.cle} dataKey={s.cle} name={s.nom} stroke={s.couleur} strokeWidth={2.5} dot={{ r: 4 }}
              type="monotone" connectNulls isAnimationActive={false}>
              {uneSerie && etiquette(s.cle, "top")}
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === "aires") {
    return (
      <ResponsiveContainer width="100%" height={hauteur}>
        <AreaChart data={lignes} margin={{ top: 20, right: 24, bottom: 4, left: 0 }}>
          {axes}
          {series.map((s) => (
            <Area key={s.cle} dataKey={s.cle} name={s.nom} stroke={s.couleur} fill={s.couleur} fillOpacity={0.2}
              strokeWidth={2} type="monotone" connectNulls isAnimationActive={false} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  // Colonnes (groupées ou empilées).
  const empile = type === "colonnes-empilees";
  return (
    <ResponsiveContainer width="100%" height={hauteur}>
      <BarChart data={lignes} margin={{ top: 20, right: 8, bottom: 4, left: 0 }}>
        {axes}
        {series.map((s, n) => (
          <Bar
            key={s.cle}
            dataKey={s.cle}
            name={s.nom}
            fill={s.couleur}
            stackId={empile ? "pile" : undefined}
            radius={!empile || n === series.length - 1 ? [4, 4, 0, 0] : undefined}
            maxBarSize={empile || uneSerie ? 60 : 36}
          >
            {uneSerie && categories.map((c, i) => <Cell key={c} fill={couleurCategorie(i)} />)}
            {!empile && etiquette(s.cle, "top")}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
