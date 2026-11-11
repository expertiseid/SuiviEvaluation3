import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Badge, Button, Group, Menu, SegmentedControl, Select, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Download, FileInput, FileSpreadsheet, FileText } from "lucide-react";
import { telechargerExportStructuration, telechargerTableauDocument, useRecapAxesCadreStrategique } from "../../api/strategy";
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
  nomDocument,
  niveaux,
  racines,
  enfants,
  editionActive,
  actions,
}: {
  cadreId: number;
  /** Nom du document, pour le nom du fichier exporté. */
  nomDocument: string;
  niveaux: TypeNiveau[];
  racines: ElementStrategique[];
  /** Éléments en dessous (déjà filtrés par la recherche). */
  enfants: (e: ElementStrategique) => ElementStrategique[];
  editionActive: boolean;
  /** Actions d'un élément (mêmes icônes que dans l'arbre : ajouter dessous, modifier, supprimer). */
  actions: (e: ElementStrategique) => ReactNode;
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
        // Activités masquées à cet utilisateur : comptées dans les totaux de l'élément, sans ligne propre.
        lignes: [ligne, ...sous.flatMap((s) => s.lignes), ...propres.filter((a) => !a.masquee).map((a) => ({ type: "activite" as const, activite: a }))],
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
      <Group gap="md" mb="xs" justify="space-between">
        <Group gap="md">
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
        <MenuExport cadreId={cadreId} nomDocument={nomDocument} programmation={programmation} annee={annee} />
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
                      {estElement && actions(l.element)}
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

/**
 * Menu « Exporter » de l'arborescence d'un document (modes Arbre et Tableau) : tableau complet
 * (programmation, budgets, taux) ou export simple (structure seule), en Excel ou en PDF, et le
 * canevas de remplissage réimportable. `annee` absente : le serveur choisit (année en cours).
 */
export function MenuExport({
  cadreId,
  nomDocument,
  programmation,
  annee,
}: {
  cadreId: number;
  nomDocument: string;
  programmation: "trimestres" | "dates";
  annee?: number;
}) {
  const [exportEnCours, setExportEnCours] = useState(false);

  /** Tout le tableau (tous les niveaux, sans le filtre de recherche), avec la programmation affichée. */
  async function exporter(fichier: "xlsx" | "pdf" | "canevas", contenu: "complet" | "simple" = "complet") {
    setExportEnCours(true);
    try {
      if (fichier === "canevas") await telechargerExportStructuration(cadreId, nomDocument);
      else await telechargerTableauDocument(cadreId, nomDocument, fichier, programmation, annee ?? 0, contenu);
    } catch {
      notifications.show({ message: voc("Erreur lors de l'export"), color: "red" });
    } finally {
      setExportEnCours(false);
    }
  }

  return (
  <Menu position="bottom-end" withinPortal>
    <Menu.Target>
      <Button size="xs" variant="light" leftSection={<Download size={14} />} loading={exportEnCours}>
        {voc("Exporter")}
      </Button>
    </Menu.Target>
    <Menu.Dropdown>
      <Menu.Label>{voc("Tableau complet (programmation, budgets, taux)")}</Menu.Label>
      <Menu.Item leftSection={<FileSpreadsheet size={14} />} onClick={() => exporter("xlsx")}>{voc("Excel (.xlsx)")}</Menu.Item>
      <Menu.Item leftSection={<FileText size={14} />} onClick={() => exporter("pdf")}>{voc("PDF")}</Menu.Item>
      <Menu.Divider />
      <Menu.Label>{voc("Export simple (structure seule)")}</Menu.Label>
      <Menu.Item leftSection={<FileSpreadsheet size={14} />} onClick={() => exporter("xlsx", "simple")}>{voc("Excel (.xlsx)")}</Menu.Item>
      <Menu.Item leftSection={<FileText size={14} />} onClick={() => exporter("pdf", "simple")}>{voc("PDF")}</Menu.Item>
      <Menu.Divider />
      <Menu.Label>{voc("Réimportable")}</Menu.Label>
      {/* Même format que le modèle d'import : on complète le fichier et on le réimporte. */}
      <Menu.Item leftSection={<FileInput size={14} />} onClick={() => exporter("canevas")}>
        <Text size="sm">{voc("Canevas de remplissage (Excel)")}</Text>
        <Text size="xs" c="dimmed">{voc("À compléter puis réimporter avec « Importer depuis Excel »")}</Text>
      </Menu.Item>
    </Menu.Dropdown>
  </Menu>
  );
}
