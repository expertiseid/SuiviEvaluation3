import { type ReactNode, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Layers } from "lucide-react";
import { ActionIcon, Badge, Card, Group, Progress, SegmentedControl, Select, Stack, Table, Text, Tooltip } from "@mantine/core";
import { useRecapAxesCadreStrategique } from "../../api/strategy";
import { EmptyState } from "../../components/common/EmptyState";
import { STATUS_HEX } from "../../components/common/statusPalette";
import { toneDeTaux } from "../../components/suivi/BarreProgression";
import type { RecapAxesCadreStrategique, TypeNiveau } from "../../types";
import { voc } from "../../utils/vocabulaire";
import { nombre, totaux } from "./calculsAxes";

import { locale } from "../../utils/i18n";
type Activite = RecapAxesCadreStrategique["activites"][number];

const CLE_NON_RATTACHEES = -1;

function fcfa(v: number): string {
  return v.toLocaleString(locale());
}

function Taux({ taux }: { taux: number | null }) {
  if (taux === null) return <Text size="sm" c="dimmed" ta="right">—</Text>;
  return (
    <Group gap={6} wrap="nowrap" justify="flex-end">
      <Text size="sm" fw={600}>{taux}%</Text>
      <Progress value={Math.min(100, taux)} color={STATUS_HEX[toneDeTaux(taux)]} size={6} w={54} radius="xl" />
    </Group>
  );
}

type Element = RecapAxesCadreStrategique["elements"][number];
type Arbre = {
  enfants: Map<number, Element[]>;
  directes: Map<number, Activite[]>;
  cumul: Map<number, Activite[]>;
};

function parCode(a: Element, b: Element) {
  return (a.code || a.nom).localeCompare(b.code || b.nom, "fr", { numeric: true });
}

const RETRAIT = 24;

/** Ligne d'un groupe (élément du cadre ou « non rattachées ») avec ses totaux ; dépliable. */
function LigneGroupe({
  cle,
  libelle,
  activites,
  profondeur,
  ouvert,
  basculer,
  children,
}: {
  cle: number;
  libelle: ReactNode;
  activites: Activite[];
  profondeur: number;
  ouvert: boolean;
  basculer: (cle: number) => void;
  children: ReactNode;
}) {
  const t = totaux(activites);
  const depliable = activites.length > 0;
  return (
    <>
      <Table.Tr
        style={{ cursor: depliable ? "pointer" : undefined }}
        bg={profondeur > 0 ? "gray.0" : undefined}
        onClick={() => depliable && basculer(cle)}
      >
        <Table.Td pl={12 + profondeur * RETRAIT}>
          <Group gap={6} wrap="nowrap">
            <ActionIcon size="sm" variant="subtle" color="gray" disabled={!depliable}>
              {ouvert ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </ActionIcon>
            {libelle}
          </Group>
        </Table.Td>
        <Table.Td {...CHIFFRE}>
          <Badge variant="light" color={t.nombre ? "teal" : "gray"}>{t.nombre}</Badge>
        </Table.Td>
        <Table.Td {...CHIFFRE} fw={profondeur === 0 ? 600 : undefined}>{fcfa(t.alloue)}</Table.Td>
        <Table.Td {...CHIFFRE} fw={profondeur === 0 ? 600 : undefined}>{fcfa(t.depense)}</Table.Td>
        <Table.Td><Taux taux={t.tauxPhysique} /></Table.Td>
        <Table.Td><Taux taux={t.tauxFinancier} /></Table.Td>
      </Table.Tr>
      {ouvert && children}
    </>
  );
}

function LigneActivite({ a, profondeur }: { a: Activite; profondeur: number }) {
  return (
    <Table.Tr>
      <Table.Td pl={12 + profondeur * RETRAIT + 32}>
        <Text size="sm">
          <Text span c="dimmed">{a.projet_code}</Text>
          {a.code && <Text span c="dimmed"> · {a.code}</Text>} —{" "}
          <Text span component={Link} to={`/projets/${a.projet_id}`} c="teal.8">{a.libelle}</Text>
        </Text>
      </Table.Td>
      <Table.Td />
      <Table.Td {...CHIFFRE}>
        {a.budget_alloue !== null ? fcfa(nombre(a.budget_alloue)) : "—"}
        {nombre(a.budget_alloue) !== 0 && nombre(a.budget_alloue_compte) === 0 && (
          <Tooltip label={voc("Le détail de ce budget est saisi sur les éléments en dessous : il n'est pas compté une seconde fois dans les totaux.")}>
            <Text size="xs" c="dimmed">{voc("non additionné")}</Text>
          </Tooltip>
        )}
      </Table.Td>
      <Table.Td {...CHIFFRE}>{fcfa(nombre(a.budget_realise))}</Table.Td>
      <Table.Td><Taux taux={a.taux_physique} /></Table.Td>
      <Table.Td><Taux taux={a.taux_financier} /></Table.Td>
    </Table.Tr>
  );
}

/**
 * Un élément du cadre et, une fois déplié, ses sous-éléments (ex : les axes
 * d'une orientation, chacun avec ses totaux et lui-même dépliable) puis les
 * activités rattachées directement à lui.
 */
function LignesElement({
  element,
  profondeur,
  arbre,
  ouverts,
  basculer,
  nomsNiveaux,
}: {
  element: Element;
  profondeur: number;
  arbre: Arbre;
  ouverts: number[];
  basculer: (cle: number) => void;
  nomsNiveaux: Map<number, string>;
}) {
  const sousElements = arbre.enfants.get(element.id) ?? [];
  const directes = arbre.directes.get(element.id) ?? [];
  return (
    <LigneGroupe
      cle={element.id}
      libelle={
        <Group gap={6} wrap="nowrap">
          {profondeur > 0 && (
            <Badge size="sm" variant="light" color="blue">{nomsNiveaux.get(element.type_niveau)}</Badge>
          )}
          {element.code && <Text size="sm" c="dimmed">{element.code}</Text>}
          <Text size="sm" fw={profondeur === 0 ? 700 : 600}>{element.nom}</Text>
        </Group>
      }
      activites={arbre.cumul.get(element.id) ?? []}
      profondeur={profondeur}
      ouvert={ouverts.includes(element.id)}
      basculer={basculer}
    >
      {sousElements.map((e) => (
        <LignesElement
          key={e.id}
          element={e}
          profondeur={profondeur + 1}
          arbre={arbre}
          ouverts={ouverts}
          basculer={basculer}
          nomsNiveaux={nomsNiveaux}
        />
      ))}
      {directes.filter((a) => !a.masquee).map((a) => (
        <LigneActivite key={a.id} a={a} profondeur={profondeur + 1} />
      ))}
    </LigneGroupe>
  );
}

const ENTETE = { tt: "uppercase", fz: "xs", c: "dimmed" } as const;
const CHIFFRE = { ta: "right", style: { whiteSpace: "nowrap" } } as const;

/**
 * Onglet « Axes & budgets » : les activités regroupées par élément du cadre
 * stratégique (au niveau choisi : orientation, axe…), avec pour chaque
 * élément le nombre d'activités, le budget alloué et dépensé (sommes) et les
 * taux physique et financier (moyenne par activité), puis le total.
 */
export function AxesBudgetsTab({ cadreId, niveaux }: { cadreId: number; niveaux: TypeNiveau[] }) {
  const { data, isLoading } = useRecapAxesCadreStrategique(cadreId);
  const niveauxTries = useMemo(() => [...niveaux].sort((a, b) => a.ordre - b.ordre), [niveaux]);
  const [niveauId, setNiveauId] = useState<number | null>(null);
  const [ouverts, setOuverts] = useState<number[]>([]);
  const niveau = niveauxTries.find((n) => n.id === niveauId) ?? niveauxTries[0];

  const arbre = useMemo(() => {
    const enfants = new Map<number, Element[]>();
    const directes = new Map<number, Activite[]>();
    if (!data) return { enfants, directes, cumul: new Map<number, Activite[]>(), racines: [] as Element[], nonRattachees: [] as Activite[] };
    for (const e of data.elements) {
      if (e.element_parent !== null) enfants.set(e.element_parent, [...(enfants.get(e.element_parent) ?? []), e]);
    }
    for (const liste of enfants.values()) liste.sort(parCode);
    const nonRattachees: Activite[] = [];
    for (const act of data.activites) {
      if (act.axe === null) nonRattachees.push(act);
      else directes.set(act.axe, [...(directes.get(act.axe) ?? []), act]);
    }
    // Activités d'un élément = les siennes + celles de tous ses sous-éléments.
    const cumul = new Map<number, Activite[]>();
    function cumuler(e: Element): Activite[] {
      const liste = [...(directes.get(e.id) ?? []), ...(enfants.get(e.id) ?? []).flatMap(cumuler)];
      cumul.set(e.id, liste);
      return liste;
    }
    data.elements.filter((e) => e.element_parent === null).forEach(cumuler);
    const racines = niveau ? data.elements.filter((e) => e.type_niveau === niveau.id).sort(parCode) : [];
    // Au niveau choisi, une activité rattachée plus haut (ex : directement à
    // une orientation quand on regroupe par axe) n'a pas d'élément : non rattachée.
    const auNiveau = new Set(racines.flatMap((e) => cumul.get(e.id) ?? []).map((act) => act.id));
    nonRattachees.push(...data.activites.filter((act) => act.axe !== null && !auNiveau.has(act.id)));
    return { enfants, directes, cumul, racines, nonRattachees };
  }, [data, niveau]);

  if (isLoading || !data) return <Text c="dimmed">{voc("Chargement…")}</Text>;
  if (!niveau) {
    return (
      <EmptyState
        icon={<Layers size={32} strokeWidth={1.5} />}
        message={voc("Aucun niveau défini pour ce cadre stratégique (onglet « Configuration des niveaux »).")}
      />
    );
  }

  const total = totaux(data.activites);
  const nomsNiveaux = new Map(niveaux.map((n) => [n.id, n.nom_niveau]));
  const nbNonRattachees = data.activites.filter((a) => a.axe === null).length;

  function basculer(cle: number) {
    setOuverts((o) => (o.includes(cle) ? o.filter((x) => x !== cle) : [...o, cle]));
  }

  const choixNiveaux = niveauxTries.map((n) => ({ value: String(n.id), label: `${n.ordre}. ${n.nom_niveau}` }));
  function choisirNiveau(v: string) {
    setNiveauId(Number(v));
    setOuverts([]);
  }

  return (
    <Stack gap="md">
      {niveauxTries.length > 1 && (
        <Group gap="sm">
          <Text size="sm" fw={600}>{voc("Regrouper par :")}</Text>
          {/* Au-delà de 4 niveaux, une liste déroulante plutôt qu'une rangée de boutons trop large. */}
          {niveauxTries.length <= 4 ? (
            <SegmentedControl value={String(niveau.id)} onChange={choisirNiveau} data={choixNiveaux} />
          ) : (
            <Select value={String(niveau.id)} onChange={(v) => v && choisirNiveau(v)} data={choixNiveaux} allowDeselect={false} w={320} />
          )}
        </Group>
      )}

      <Card withBorder padding="md" radius="md">
        <Table.ScrollContainer minWidth={860}>
          <Table verticalSpacing={8} fz="sm" withTableBorder withColumnBorders striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th {...ENTETE}>{niveau.nom_niveau}</Table.Th>
                <Table.Th {...ENTETE} ta="right">{voc("Nombre d'activités")}</Table.Th>
                <Table.Th {...ENTETE} ta="right">{voc("Budget alloué (FCFA)")}</Table.Th>
                <Table.Th {...ENTETE} ta="right">{voc("Budget dépensé (FCFA)")}</Table.Th>
                <Table.Th {...ENTETE} ta="right">{voc("Taux physique moyen")}</Table.Th>
                <Table.Th {...ENTETE} ta="right">{voc("Taux financier moyen")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {arbre.racines.map((e) => (
                <LignesElement key={e.id} element={e} profondeur={0} arbre={arbre} ouverts={ouverts} basculer={basculer} nomsNiveaux={nomsNiveaux} />
              ))}
              {arbre.nonRattachees.length > 0 && (
                <LigneGroupe
                  cle={CLE_NON_RATTACHEES}
                  libelle={<Text size="sm" fw={600} c="orange.8" fs="italic">{voc("Activités non rattachées à un(e)")} {niveau.nom_niveau.toLowerCase()}</Text>}
                  activites={arbre.nonRattachees}
                  profondeur={0}
                  ouvert={ouverts.includes(CLE_NON_RATTACHEES)}
                  basculer={basculer}
                >
                  {arbre.nonRattachees.filter((act) => !act.masquee).map((act) => <LigneActivite key={act.id} a={act} profondeur={1} />)}
                </LigneGroupe>
              )}
            </Table.Tbody>
            <Table.Tfoot bg="gray.1">
              <Table.Tr>
                <Table.Th>{voc("Total")}</Table.Th>
                <Table.Th {...CHIFFRE}>{total.nombre}</Table.Th>
                <Table.Th {...CHIFFRE}>{fcfa(total.alloue)}</Table.Th>
                <Table.Th {...CHIFFRE}>{fcfa(total.depense)}</Table.Th>
                <Table.Th><Taux taux={total.tauxPhysique} /></Table.Th>
                <Table.Th><Taux taux={total.tauxFinancier} /></Table.Th>
              </Table.Tr>
            </Table.Tfoot>
          </Table>
        </Table.ScrollContainer>
        <Text size="xs" c="dimmed" mt="xs">
          {voc("Budgets : sommes des activités. Taux : moyenne des taux des activités (chaque activité compte pour une). Cliquer sur une ligne pour la déplier : ses sous-éléments (avec leurs propres totaux) puis ses activités.")}
        </Text>
      </Card>

      {nbNonRattachees > 0 && (
        <Text size="sm" c="orange.8">
          {nbNonRattachees > 1
            ? voc`${nbNonRattachees} activités des projets de ce cadre n'ont pas encore d'élément stratégique : à renseigner dans la fiche de l'activité (champ « Élément stratégique »).`
            : voc`${nbNonRattachees} activité des projets de ce cadre n'a pas encore d'élément stratégique : à renseigner dans la fiche de l'activité (champ « Élément stratégique »).`}
        </Text>
      )}
    </Stack>
  );
}
