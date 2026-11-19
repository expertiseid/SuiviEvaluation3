import { ActionIcon, Menu, Stack, Table, Text, Tooltip as InfoBulle } from "@mantine/core";
import {
  AreaChart as IconeAires,
  BarChart3,
  BarChartHorizontal,
  Check,
  LayoutGrid,
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


import { locale, nombreCourt } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { PALETTES, useApparence, type ApparenceBloc } from "../../utils/apparence";
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
  cartes: { libelle: voc("Cartes de chiffres"), icone: <LayoutGrid size={15} /> },
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

const GRILLE = "var(--mantine-color-gray-2)";

type ProprietesGraphique = {
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
  /** Mode tableau : titre de la colonne des catégories (ex : « Projet »). */
  libelleCategories?: string;
  /** Mode tableau : ligne « Total » (seulement quand additionner a un sens). */
  total?: boolean;
};

/** Réglages de présentation venus de l'apparence du bloc (voir GraphiqueAdaptable). */
type Presentation = {
  legende?: ApparenceBloc["legende"];
  quadrillage?: boolean;
  axeX?: string;
  axeY?: string;
  rotation?: number;
  tailleTexte?: number;
};

/**
 * Graphique dont le type est choisi par l'utilisateur, à partir de données
 * « catégories × séries » (ex : projets × statuts d'activité). Avec une seule
 * série, `couleursCategories` colore chaque catégorie (camembert, colonnes…).
 * L'apparence du bloc (ApparenceContext) s'applique : tri, palette et couleurs imposées, format des
 * nombres, valeurs affichées, hauteur, légende, axes, quadrillage, et graphique + tableau.
 */
export function GraphiqueAdaptable(props: ProprietesGraphique) {
  const a = useApparence();
  if (Object.keys(a).length === 0) return <GraphiqueBrut {...props} />;
  let { categories, series, couleursCategories } = props;
  if (a.tri && a.tri !== "aucun" && series.length) {
    const ordre = categories.map((_, i) => i).sort((i, j) =>
      ((series[0].valeurs[i] ?? 0) - (series[0].valeurs[j] ?? 0)) * (a.tri === "croissant" ? 1 : -1));
    categories = ordre.map((i) => categories[i]);
    series = series.map((x) => ({ ...x, valeurs: ordre.map((i) => x.valeurs[i]) }));
    couleursCategories = couleursCategories && ordre.map((i) => couleursCategories![i]);
  }
  if (a.palette && a.palette !== "defaut") {
    const palette = PALETTES[a.palette];
    series = series.map((x, i) => ({ ...x, couleur: palette[i % palette.length] }));
    if (series.length === 1) couleursCategories = categories.map((_, i) => palette[i % palette.length]);
  }
  if (a.couleurs) {
    const imposees = a.couleurs;
    series = series.map((x) => ({ ...x, couleur: imposees[x.nom] ?? x.couleur }));
    if (series.length === 1) couleursCategories = categories.map((c, i) => imposees[c] ?? couleursCategories?.[i] ?? series[0].couleur);
  }
  const formats: Record<string, ((v: number) => string) | undefined> = {
    entier: (v) => Math.round(v).toLocaleString(locale()),
    court: (v) => nombreCourt(v),
    pourcent: (v) => `${v.toLocaleString(locale())} %`,
  };
  const format = a.format && a.format !== "auto" ? formats[a.format] : undefined;
  const commun: ProprietesGraphique = {
    ...props, categories, series, couleursCategories,
    type: a.mode === "tableau" ? "tableau" : props.type,
    formatValeur: format ?? props.formatValeur,
    formatAxe: format ?? props.formatAxe,
    etiquettes: a.valeurs ?? props.etiquettes,
    hauteur: a.hauteur ?? props.hauteur,
  };
  const presentation: Presentation = {
    legende: a.legende, quadrillage: a.quadrillage, axeX: a.axe_x, axeY: a.axe_y, rotation: a.rotation, tailleTexte: a.taille_texte,
  };
  const graphique = <GraphiqueBrut {...commun} {...presentation} />;
  if (a.mode === "les_deux" && commun.type !== "tableau") {
    return (
      <Stack gap="sm">
        {graphique}
        <GraphiqueBrut {...commun} type="tableau" />
      </Stack>
    );
  }
  return graphique;
}

function GraphiqueBrut({
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
  libelleCategories = "",
  total = false,
  legende: positionLegende = "auto",
  quadrillage = true,
  axeX = "",
  axeY = "",
  rotation = 0,
  tailleTexte = 13,
}: ProprietesGraphique & Presentation) {
  const AXE = { fontSize: tailleTexte, fill: "var(--mantine-color-dimmed)" };
  const titreAxe = (texte: string, vertical = false) =>
    texte ? { value: texte, angle: vertical ? -90 : 0, position: vertical ? "insideLeft" : "insideBottom", offset: vertical ? 10 : -4,
      style: { fontSize: tailleTexte, fill: "var(--mantine-color-dark-4)", textAnchor: "middle" } } as const : undefined;
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
  // Légende : automatique (plusieurs séries), masquée, ou placée en haut, en bas ou à droite.
  const avecLegende = positionLegende === "auto" ? !uneSerie : positionLegende !== "masquee";
  const legende = avecLegende && (
    <Legend wrapperStyle={{ fontSize: tailleTexte }}
      {...(positionLegende === "haut" ? { verticalAlign: "top" } : positionLegende === "droite"
        ? { layout: "vertical", align: "right", verticalAlign: "middle" } : {})} />
  );
  // Légende sous ou sur le graphique : la hauteur grandit d'autant, sinon une légende de nombreuses séries
  // (ex. 50 projets) prendrait toute la place et écraserait le graphique.
  const hauteurLegende = avecLegende && positionLegende !== "droite" ? Math.ceil(series.length / 4) * 20 + 8 : 0;
  const etiquette = (cle: string, position: "top" | "right") =>
    etiquettes && (uneSerie || type === "colonnes" || type === "barres") ? (
      <LabelList
        dataKey={cle}
        position={position}
        formatter={(v: unknown) => (v === null || v === undefined ? "" : axe(Number(v)))}
        style={{ fontSize: Math.max(9, tailleTexte - 1), fontWeight: 600 }}
      />
    ) : null;

  if (type === "camembert" && uneSerie) {
    return (
      <CamembertChart
        unite={unite}
        sansLegende={positionLegende === "masquee"}
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
    // avec première colonne et en-tête figés ; montants en entier (l'unité dans l'en-tête).
    const transpose = series.length > categories.length;
    const montant = unite === "FCFA";
    const cellule = (v: number) => (montant ? Number(v).toLocaleString(locale()) : formatValeur(v));
    const entetes = transpose
      ? categories.map(formatCategorie)
      : series.map((s) => (montant ? `${s.nom} (${unite})` : s.nom));
    const sommes = entetes.map((_, i) =>
      transpose
        ? series.reduce((somme, s) => somme + (Number(s.valeurs[i]) || 0), 0)
        : series[i].valeurs.reduce((somme: number, v) => somme + (Number(v) || 0), 0));
    const lignesTableau = transpose
      ? series.map((s) => ({ libelle: s.nom, couleur: s.couleur, valeurs: s.valeurs }))
      : categories.map((c, i) => ({
          libelle: formatCategorie(c),
          couleur: uneSerie ? couleurCategorie(i) : undefined,
          valeurs: series.map((s) => s.valeurs[i]),
        }));
    const fixe = { position: "sticky", left: 0, zIndex: 1, background: "var(--mantine-color-body)" } as const;
    return (
      <Table.ScrollContainer minWidth={Math.min(1200, 160 + entetes.length * 110)} maw="100%" mah={Math.min(hauteur + 120, 560)}>
        <Table striped withTableBorder withColumnBorders stickyHeader verticalSpacing={6} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={fixe}>{transpose ? "" : libelleCategories}</Table.Th>
              {entetes.map((e) => <Table.Th key={e} ta="right" style={{ whiteSpace: "nowrap" }}>{e}</Table.Th>)}
            </Table.Tr>
            {/* Total sous l'en-tête : il reste visible quand le tableau défile. */}
            {total && (
              <Table.Tr style={{ background: "var(--mantine-color-gray-1)" }}>
                <Table.Th style={{ ...fixe, background: "var(--mantine-color-gray-1)" }}>{voc("Total")}</Table.Th>
                {sommes.map((somme, i) => <Table.Th key={i} ta="right" style={{ whiteSpace: "nowrap" }}>{cellule(somme)}</Table.Th>)}
              </Table.Tr>
            )}
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
                    {v === null || v === undefined ? "—" : cellule(v)}
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
          {quadrillage && <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={GRILLE} />}
          <XAxis type="number" tickFormatter={(v) => axe(Number(v))} tick={AXE} label={titreAxe(axeY)} height={axeY ? 48 : 30} />
          <YAxis type="category" dataKey="categorie" width={150} tickFormatter={formatCategorie} tick={AXE} label={titreAxe(axeX, true)} />
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
      {quadrillage && <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRILLE} />}
      <XAxis dataKey="categorie" tickFormatter={formatCategorie} tick={AXE} label={titreAxe(axeX)}
        angle={-rotation} textAnchor={rotation ? "end" : "middle"} height={(rotation ? 30 + rotation : 30) + (axeX ? 18 : 0)}
        interval={rotation ? 0 : "preserveEnd"} />
      <YAxis tickFormatter={(v) => axe(Number(v))} tick={AXE} width={axeY ? 80 : 64} label={titreAxe(axeY, true)} />
      {tooltip}
      {legende}
    </>
  );

  if (type === "courbes") {
    return (
      <ResponsiveContainer width="100%" height={hauteur + hauteurLegende}>
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
      <ResponsiveContainer width="100%" height={hauteur + hauteurLegende}>
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
    <ResponsiveContainer width="100%" height={hauteur + hauteurLegende}>
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
