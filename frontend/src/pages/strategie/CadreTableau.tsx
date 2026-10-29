import { useMemo, useState } from "react";
import { ActionIcon, Badge, Group, SegmentedControl, Select, Table, Text, Tooltip } from "@mantine/core";
import { Pencil, Plus } from "lucide-react";
import { useRecapAxesCadreStrategique } from "../../api/strategy";
import type { ElementStrategique, RecapAxesCadreStrategique, TypeNiveau } from "../../types";
import { usePreference } from "../../utils/affichage";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { totaux } from "./calculsAxes";

type Activite = RecapAxesCadreStrategique["activites"][number];
type Ligne =
  | { type: "element"; element: ElementStrategique; rang: number; groupe: boolean; activites: Activite[] }
  | { type: "activite"; activite: Activite };

// Bandeaux par niveau, du plus haut au plus bas, comme le tableau de la planification d'un projet.
const FONDS_NIVEAUX = ["var(--mantine-color-blue-3)", "var(--mantine-color-blue-2)", "var(--mantine-color-blue-1)", "var(--mantine-color-blue-0)"];
const ENTETE = { bg: "var(--mantine-color-green-1)", fz: "xs", style: { verticalAlign: "middle" as const } };
const MILIEU = { style: { verticalAlign: "middle" as const } };
const date = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "");

/** Première date de début et dernière date de fin d'un ensemble d'activités. */
function bornes(activites: Activite[]): [string | null, string | null] {
  const debuts = activites.map((a) => a.date_debut).filter((d): d is string => !!d).sort();
  const fins = activites.map((a) => a.date_fin).filter((d): d is string => !!d).sort();
  return [debuts[0] ?? null, fins[fins.length - 1] ?? null];
}

/** L'élément est-il prévu pendant ce trimestre (dates de début et de fin qui le recoupent) ? */
function prevuAuTrimestre(debut: string | null, fin: string | null, annee: number, trimestre: number) {
  if (!debut && !fin) return false;
  const debutT = `${annee}-${String(trimestre * 3 - 2).padStart(2, "0")}-01`;
  const finT = `${annee}-${String(trimestre * 3).padStart(2, "0")}-${trimestre === 1 || trimestre === 4 ? 31 : 30}`;
  return (debut ?? fin!) <= finT && (fin ?? debut!) >= debutT;
}

function Taux({ taux, titre }: { taux: number | null; titre: boolean }) {
  if (taux === null) return <Text size="sm" c="dimmed">—</Text>;
  const texte = `${taux.toLocaleString(locale())} %`;
  return titre ? (
    <Badge variant="white" color="teal" size="lg" tt="none" fw={500}>{texte}</Badge>
  ) : (
    <Text size="sm" c="teal.7" fw={500}>{texte}</Text>
  );
}

/**
 * Arborescence d'un cadre stratégique présentée comme le tableau de la planification d'un
 * projet : une ligne par élément (bandeau de couleur par niveau), suivie des activités des
 * projets qui y sont rattachées ; dates, budget et taux viennent de ces activités.
 */
export function CadreTableau({
  cadreId,
  niveaux,
  racines,
  enfants,
  editionActive,
  onModifier,
  onAjouter,
}: {
  cadreId: number;
  niveaux: TypeNiveau[];
  racines: ElementStrategique[];
  /** Éléments en dessous (déjà filtrés par la recherche). */
  enfants: (e: ElementStrategique) => ElementStrategique[];
  editionActive: boolean;
  onModifier: (e: ElementStrategique) => void;
  onAjouter: (typeNiveau: TypeNiveau, parent: ElementStrategique) => void;
}) {
  const { data } = useRecapAxesCadreStrategique(cadreId);
  const [programmation, setProgrammation] = usePreference("programmation-planification", ["trimestres", "dates"] as const);
  const parTrimestre = programmation === "trimestres";

  const lignes = useMemo(() => {
    const directes = new Map<number, Activite[]>();
    for (const a of data?.activites ?? []) {
      if (a.axe !== null) directes.set(a.axe, [...(directes.get(a.axe) ?? []), a]);
    }
    const rang = new Map([...niveaux].sort((a, b) => a.ordre - b.ordre).map((n, i) => [n.id, i]));
    // Chaque élément, puis ses éléments en dessous, puis les activités qui y sont rattachées.
    function aplatir(e: ElementStrategique): { lignes: Ligne[]; activites: Activite[] } {
      const sous = enfants(e).map(aplatir);
      const propres = directes.get(e.id) ?? [];
      const activites = [...propres, ...sous.flatMap((s) => s.activites)];
      const ligne: Ligne = { type: "element", element: e, rang: rang.get(e.type_niveau) ?? 0, groupe: sous.length + propres.length > 0, activites };
      return {
        lignes: [ligne, ...sous.flatMap((s) => s.lignes), ...propres.map((a) => ({ type: "activite" as const, activite: a }))],
        activites,
      };
    }
    return racines.flatMap((r) => aplatir(r).lignes);
  }, [data, niveaux, racines, enfants]);

  const anneesPossibles = useMemo(() => {
    const ans = (data?.activites ?? []).flatMap((a) => [a.date_debut, a.date_fin]).filter((d): d is string => !!d).map((d) => Number(d.slice(0, 4)));
    if (ans.length === 0) return [new Date().getFullYear()];
    const premiere = Math.min(...ans);
    return Array.from({ length: Math.max(...ans) - premiere + 1 }, (_, i) => premiere + i);
  }, [data]);
  const anneeCourante = new Date().getFullYear();
  const [annee, setAnnee] = useState(anneesPossibles.includes(anneeCourante) ? anneeCourante : anneesPossibles[0]);
  const nomsNiveaux = new Map(niveaux.map((n) => [n.id, n.nom_niveau]));

  return (
    <>
      <Group gap="md" mb="xs">
        <SegmentedControl
          size="xs"
          value={programmation}
          onChange={(v) => setProgrammation(v as typeof programmation)}
          data={[
            { value: "trimestres", label: voc("Trimestres") },
            { value: "dates", label: voc("Dates") },
          ]}
        />
        {parTrimestre && anneesPossibles.length > 1 && (
          <Group gap="xs">
            <Text size="sm">{voc("Programmation de l'année")}</Text>
            <Select size="xs" w={100} value={String(annee)} onChange={(v) => v && setAnnee(Number(v))} data={anneesPossibles.map(String)} allowDeselect={false} />
          </Group>
        )}
      </Group>
      <Table.ScrollContainer minWidth={900}>
        <Table withTableBorder withColumnBorders verticalSpacing={6} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th rowSpan={2} w={90} {...ENTETE}>{voc("Code")}</Table.Th>
              <Table.Th rowSpan={2} miw={260} {...ENTETE}>{voc("Logique d'intervention")}</Table.Th>
              {parTrimestre ? (
                <Table.Th colSpan={4} ta="center" {...ENTETE}>{voc`Programmation ${annee}`}</Table.Th>
              ) : (
                <>
                  <Table.Th rowSpan={2} w={100} {...ENTETE}>{voc("Date début")}</Table.Th>
                  <Table.Th rowSpan={2} w={100} {...ENTETE}>{voc("Date fin")}</Table.Th>
                </>
              )}
              <Table.Th rowSpan={2} w={140} ta="right" {...ENTETE}>{voc("Budget alloué (FCFA)")}</Table.Th>
              <Table.Th rowSpan={2} w={90} ta="center" {...ENTETE}>{voc("Taux")}</Table.Th>
              {editionActive && <Table.Th rowSpan={2} w={70} {...ENTETE} />}
            </Table.Tr>
            <Table.Tr>
              {parTrimestre && [1, 2, 3, 4].map((t) => <Table.Th key={t} w={34} ta="center" {...ENTETE}>{`T${t}`}</Table.Th>)}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {lignes.map((l) => {
              const estElement = l.type === "element";
              const titre = estElement && l.groupe;
              const fond = titre ? FONDS_NIVEAUX[Math.min(l.rang, FONDS_NIVEAUX.length - 1)] : undefined;
              const [debut, fin] = estElement ? bornes(l.activites) : [l.activite.date_debut, l.activite.date_fin];
              // Élément : budgets additionnés sans double compte et taux moyen de ses activités.
              const t = estElement && l.activites.length ? totaux(l.activites) : null;
              const brut = estElement ? null : l.activite.budget_alloue;
              const budget = t ? t.alloue : brut !== null ? Number(brut) : null;
              const taux = estElement ? (t?.tauxPhysique ?? null) : l.activite.taux_physique;
              const niveauEnfant = estElement ? niveaux.find((n) => n.niveau_parent === l.element.type_niveau) : undefined;
              return (
                <Table.Tr key={estElement ? `e${l.element.id}` : `a${l.activite.id}`} bg={fond}>
                  <Table.Td ta="center" fw={titre ? 700 : undefined} {...MILIEU}>{estElement ? l.element.code : l.activite.code}</Table.Td>
                  <Table.Td fw={titre ? 700 : undefined} pl={estElement ? undefined : "lg"}>
                    {estElement ? (
                      <>{nomsNiveaux.get(l.element.type_niveau)} : {l.element.nom}</>
                    ) : (
                      <>
                        {l.activite.libelle}{" "}
                        <Text span size="xs" c="dimmed">({l.activite.projet_code})</Text>
                      </>
                    )}
                  </Table.Td>
                  {parTrimestre ? (
                    [1, 2, 3, 4].map((tr) => (
                      <Table.Td key={tr} ta="center" fw={700} {...MILIEU}>{prevuAuTrimestre(debut, fin, annee, tr) ? "X" : ""}</Table.Td>
                    ))
                  ) : (
                    <>
                      <Table.Td style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{date(debut)}</Table.Td>
                      <Table.Td style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{date(fin)}</Table.Td>
                    </>
                  )}
                  <Table.Td ta="right" fw={titre ? 700 : undefined} style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                    {budget !== null ? budget.toLocaleString(locale()) : ""}
                  </Table.Td>
                  <Table.Td ta="center" {...MILIEU}><Taux taux={taux} titre={!!titre} /></Table.Td>
                  {editionActive && (
                    <Table.Td {...MILIEU}>
                      {estElement && (
                        <Group gap={2} wrap="nowrap">
                          <Tooltip label={voc("Modifier")}>
                            <ActionIcon size="sm" variant="subtle" onClick={() => onModifier(l.element)}><Pencil size={12} /></ActionIcon>
                          </Tooltip>
                          {niveauEnfant && (
                            <Tooltip label={voc`Ajouter ${niveauEnfant.nom_niveau}`}>
                              <ActionIcon size="sm" variant="subtle" onClick={() => onAjouter(niveauEnfant, l.element)}><Plus size={13} /></ActionIcon>
                            </Tooltip>
                          )}
                        </Group>
                      )}
                    </Table.Td>
                  )}
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </>
  );
}
