import { type ReactNode, useState } from "react";
import { ActionIcon, Button, Group, SegmentedControl, Select, Switch, Table, Text, Tooltip } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { ChevronLeft, ChevronRight, ListPlus, Pencil, Plus, Trash2 } from "lucide-react";
import type { Activite, SousActivite } from "../../types";
import { usePreference } from "../../utils/affichage";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

type Ligne =
  | { type: "element"; element: Activite; profondeur: number; feuille: boolean }
  | { type: "sous-activite"; sousActivite: SousActivite; profondeur: number };

/** Lignes du tableau dans l'ordre de la planification : chaque élément, puis ce qu'il contient. */
function aplatir(elements: Activite[], profondeur = 0): Ligne[] {
  return elements.flatMap((e) => [
    { type: "element" as const, element: e, profondeur, feuille: e.enfants.length === 0 },
    ...aplatir(e.enfants, profondeur + 1),
    ...e.sous_activites.map((sa) => ({ type: "sous-activite" as const, sousActivite: sa, profondeur: profondeur + 1 })),
  ]);
}

/** Budget de l'élément, ou la somme de ceux en dessous s'il n'en porte pas lui-même. */
function budget(element: Activite): number | null {
  if (element.budget_alloue !== null) return Number(element.budget_alloue);
  const sous = element.enfants.map(budget).filter((b): b is number => b !== null);
  return sous.length ? sous.reduce((a, b) => a + b, 0) : null;
}

/** L'élément est-il prévu pendant ce trimestre (dates de début et de fin qui le recoupent) ? */
function prevuAuTrimestre(debut: string | null, fin: string | null, annee: number, trimestre: number) {
  if (!debut && !fin) return false;
  const debutT = `${annee}-${String(trimestre * 3 - 2).padStart(2, "0")}-01`;
  const finT = `${annee}-${String(trimestre * 3).padStart(2, "0")}-${trimestre === 1 || trimestre === 4 ? 31 : 30}`;
  return (debut ?? fin!) <= finT && (fin ?? debut!) >= debutT;
}

/** L'élément est-il prévu ce jour-là (AAAA-MM-JJ) ? */
function prevuLe(debut: string | null, fin: string | null, jour: string) {
  if (!debut && !fin) return false;
  return (debut ?? fin!) <= jour && (fin ?? debut!) >= jour;
}

/** L'élément, ou ce qu'il contient, est-il prévu ce jour-là ? (vue « jour précis » : ses niveaux restent affichés) */
function actifLe(e: Activite, jour: string): boolean {
  return prevuLe(e.date_debut, e.date_fin, jour) || e.enfants.some((x) => actifLe(x, jour))
    || e.sous_activites.some((sa) => prevuLe(sa.date_debut, sa.date_fin, jour));
}

// Jours en AAAA-MM-JJ, calculés en temps universel : aucun décalage de fuseau horaire.
const versJour = (d: Date) => d.toISOString().slice(0, 10);
const decaler = (jour: string, n: number) => { const d = new Date(`${jour}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return versJour(d); };
/** Les 7 jours (lundi → dimanche) de la semaine qui contient ce jour. */
function semaine(jour: string): string[] {
  const lundi = decaler(jour, -((new Date(`${jour}T00:00:00Z`).getUTCDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, i) => decaler(lundi, i));
}
const aujourdHui = () => { const d = new Date(); return versJour(new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))); };
const enteteJour = (jour: string) =>
  new Date(`${jour}T00:00:00Z`).toLocaleDateString(locale(), { weekday: "short", day: "2-digit", month: "2-digit", timeZone: "UTC" });

/**
 * Diagramme de la semaine (une ligne) : une flèche du premier au dernier jour prévus de la semaine,
 * sur la grille des 7 jours ; le jour choisi est surligné.
 */
function DiagrammeSemaine({ jours, jour, debut, fin, niveau, fond }: {
  jours: string[]; jour: string; debut: string | null; fin: string | null; niveau: boolean; fond: boolean;
}) {
  const prevus = jours.map((j) => prevuLe(debut, fin, j));
  const premier = prevus.indexOf(true);
  const dernier = prevus.lastIndexOf(true);
  const choisi = jours.indexOf(jour);
  const colonne = (i: number) => `${(i * 100) / 7}%`;
  return (
    <div style={{ position: "absolute", inset: 0, minHeight: 40 }}>
      {!fond && choisi >= 0 && (
        <div style={{ position: "absolute", top: 0, bottom: 0, left: colonne(choisi), width: colonne(1), background: "var(--mantine-color-yellow-0)" }} />
      )}
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} style={{ position: "absolute", top: 0, bottom: 0, left: colonne(i), borderLeft: "1px solid var(--mantine-color-gray-4)" }} />
      ))}
      {premier >= 0 && (
        <Tooltip label={voc`Du ${date(debut ?? fin)} au ${date(fin ?? debut)}`}>
          <div style={{
            position: "absolute", top: "50%", transform: "translateY(-50%)", height: niveau ? 20 : 18,
            left: `calc(${colonne(premier)} + 3px)`, width: `calc(${colonne(dernier - premier + 1)} - 6px)`,
            background: niveau ? "var(--mantine-color-blue-8)" : "#6a9bd1",
            clipPath: "polygon(0 0, calc(100% - 9px) 0, 100% 50%, calc(100% - 9px) 100%, 0 100%)",
          }} />
        </Tooltip>
      )}
    </div>
  );
}

function annees(lignes: Ligne[]): number[] {
  const dates = lignes
    .flatMap((l) => (l.type === "element" ? [l.element.date_debut, l.element.date_fin] : [l.sousActivite.date_debut, l.sousActivite.date_fin]))
    .filter((d): d is string => !!d)
    .map((d) => Number(d.slice(0, 4)));
  if (dates.length === 0) return [new Date().getFullYear()];
  const premiere = Math.min(...dates);
  return Array.from({ length: Math.max(...dates) - premiere + 1 }, (_, i) => premiere + i);
}

// Bandeaux par niveau, du plus haut au plus bas, comme un cadre logique de programmation (PTA).
const FONDS_NIVEAUX = ["var(--mantine-color-blue-3)", "var(--mantine-color-blue-2)", "var(--mantine-color-blue-1)", "var(--mantine-color-blue-0)"];
const ENTETE = { bg: "var(--mantine-color-green-1)", fz: "xs", style: { verticalAlign: "middle" as const } };
const date = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "");

/**
 * Planification d'un projet présentée comme un cadre logique de programmation : une ligne par
 * élément (tous niveaux) avec sa logique d'intervention, ses attributs, sa programmation (par
 * trimestre pour l'année choisie, par dates, ou jour par jour sur une semaine ou un jour choisi) et son
 * budget ; les niveaux sont distingués par des bandeaux.
 */
export function PlanificationTableau({
  elements,
  nomNiveau,
  nomsAttributs: attributs,
  editionActive,
  onAvancement,
  onEditer,
  onAjouterEnfant,
  onAjouterSousActivite,
  onSupprimer,
  onEditerSousActivite,
  onSupprimerSousActivite,
  outils,
}: {
  elements: Activite[];
  nomNiveau: (profondeur: number) => string;
  /** Attributs du projet, dans l'ordre des colonnes du fichier importé. */
  nomsAttributs: string[];
  editionActive: boolean;
  onAvancement: (act: Activite) => void;
  onEditer: (act: Activite) => void;
  /** Absents : projet en lecture seule, pas d'ajout possible. */
  onAjouterEnfant?: (act: Activite, profondeurEnfant: number) => void;
  onAjouterSousActivite?: (id: number) => void;
  onSupprimer: (act: Activite, profondeur: number) => void;
  onEditerSousActivite: (sa: SousActivite) => void;
  onSupprimerSousActivite: (sa: SousActivite) => void;
  /** Boutons à droite de la programmation (export…), qui reçoivent la programmation et l'année affichées. */
  outils?: (programmation: "trimestres" | "dates", annee: number) => ReactNode;
}) {
  const toutes = aplatir(elements);
  const anneesPossibles = annees(toutes);
  const anneeCourante = new Date().getFullYear();
  const [annee, setAnnee] = useState(anneesPossibles.includes(anneeCourante) ? anneeCourante : anneesPossibles[0]);
  // Programmation : un X par trimestre couvert, les dates de début et de fin, ou un X par jour d'une
  // semaine choisie (au choix, mémorisé). « Jour précis » : seulement ce qui est prévu ce jour-là.
  const [programmation, setProgrammation] = usePreference("programmation-planification", ["trimestres", "dates", "semaines"] as const);
  const parTrimestre = programmation === "trimestres";
  const parSemaine = programmation === "semaines";
  const [jour, setJour] = useState(aujourdHui);
  const [jourPrecis, setJourPrecis] = useState(false);
  const jours = parSemaine ? (jourPrecis ? [jour] : semaine(jour)) : [];
  const lignes = parSemaine && jourPrecis
    ? toutes.filter((l) => (l.type === "element" ? actifLe(l.element, jour) : prevuLe(l.sousActivite.date_debut, l.sousActivite.date_fin, jour)))
    : toutes;
  const avecServices = toutes.some((l) => l.type === "element" && (l.element.structures_noms?.length ?? 0) > 0);

  function actions(l: Ligne) {
    if (l.type === "sous-activite") {
      const sa = l.sousActivite;
      return (
        <Group gap={2} wrap="nowrap">
          <Tooltip label={voc("Modifier la sous-activité")}>
            <ActionIcon size="sm" variant="subtle" onClick={() => onEditerSousActivite(sa)}><Pencil size={12} /></ActionIcon>
          </Tooltip>
          <Tooltip label={voc("Supprimer la sous-activité")}>
            <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onSupprimerSousActivite(sa)}><Trash2 size={12} /></ActionIcon>
          </Tooltip>
        </Group>
      );
    }
    const { element: act, profondeur } = l;
    return (
      <Group gap={2} wrap="nowrap">
        <Tooltip label={voc("Modifier")}>
          <ActionIcon size="sm" variant="subtle" onClick={() => onEditer(act)}><Pencil size={12} /></ActionIcon>
        </Tooltip>
        {onAjouterEnfant && (
          <Tooltip label={voc`Ajouter un « ${nomNiveau(profondeur + 1)} » en dessous`}>
            <ActionIcon size="sm" variant="subtle" onClick={() => onAjouterEnfant(act, profondeur + 1)}><Plus size={13} /></ActionIcon>
          </Tooltip>
        )}
        {onAjouterSousActivite && (
          <Tooltip label={voc("Ajouter une sous-activité")}>
            <ActionIcon size="sm" variant="subtle" onClick={() => onAjouterSousActivite(act.id)}><ListPlus size={13} /></ActionIcon>
          </Tooltip>
        )}
        <Tooltip label={voc("Supprimer")}>
          <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onSupprimer(act, profondeur)}><Trash2 size={12} /></ActionIcon>
        </Tooltip>
      </Group>
    );
  }

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
            { value: "semaines", label: voc("Semaines") },
          ]}
        />
        {parSemaine && (
          <Group gap="xs">
            <Tooltip label={jourPrecis ? voc("Jour précédent") : voc("Semaine précédente")}>
              <ActionIcon variant="default" onClick={() => setJour(decaler(jour, jourPrecis ? -1 : -7))}><ChevronLeft size={16} /></ActionIcon>
            </Tooltip>
            <DateInput size="xs" w={140} value={jour} onChange={(v) => v && setJour(String(v).slice(0, 10))} valueFormat="DD/MM/YYYY"
              aria-label={voc("Jour ou semaine à afficher")} />
            <Tooltip label={jourPrecis ? voc("Jour suivant") : voc("Semaine suivante")}>
              <ActionIcon variant="default" onClick={() => setJour(decaler(jour, jourPrecis ? 1 : 7))}><ChevronRight size={16} /></ActionIcon>
            </Tooltip>
            <Button size="compact-xs" variant="subtle" onClick={() => setJour(aujourdHui())}>{voc("Aujourd'hui")}</Button>
            <Switch size="xs" label={voc("Jour précis")} checked={jourPrecis} onChange={(e) => setJourPrecis(e.currentTarget.checked)} />
          </Group>
        )}
        {parTrimestre && anneesPossibles.length > 1 && (
          <Group gap="xs">
            <Text size="sm">{voc("Programmation de l'année")}</Text>
            <Select
              size="xs"
              w={100}
              value={String(annee)}
              onChange={(v) => v && setAnnee(Number(v))}
              data={anneesPossibles.map(String)}
              allowDeselect={false}
            />
          </Group>
        )}
        </Group>
        {outils?.(parSemaine ? "dates" : programmation, annee)}
      </Group>
      <Table.ScrollContainer minWidth={900 + attributs.length * 150}>
        <Table withTableBorder withColumnBorders verticalSpacing={6} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th rowSpan={2} w={80} {...ENTETE}>{voc("Code activité")}</Table.Th>
              <Table.Th rowSpan={2} miw={260} {...ENTETE}>{voc("Logique d'intervention")}</Table.Th>
              {attributs.map((nom) => (
                <Table.Th key={nom} rowSpan={2} miw={140} {...ENTETE}>{nom}</Table.Th>
              ))}
              {avecServices && <Table.Th rowSpan={2} {...ENTETE}>{voc("Services")}</Table.Th>}
              {parTrimestre ? (
                <Table.Th colSpan={4} ta="center" {...ENTETE}>{voc`Programmation ${annee}`}</Table.Th>
              ) : parSemaine ? (
                <Table.Th colSpan={jours.length} ta="center" {...ENTETE}>
                  {jourPrecis ? voc`Programmation du ${date(jour)}` : voc`Semaine du ${date(jours[0])} au ${date(jours[6])}`}
                </Table.Th>
              ) : (
                <>
                  <Table.Th rowSpan={2} w={100} {...ENTETE}>{voc("Date début")}</Table.Th>
                  <Table.Th rowSpan={2} w={100} {...ENTETE}>{voc("Date fin")}</Table.Th>
                </>
              )}
              <Table.Th rowSpan={2} w={130} ta="right" {...ENTETE}>{voc("Budget alloué (FCFA)")}</Table.Th>
              <Table.Th rowSpan={2} w={80} ta="center" {...ENTETE}>{voc("Taux")}</Table.Th>
              {editionActive && <Table.Th rowSpan={2} w={110} {...ENTETE} />}
            </Table.Tr>
            <Table.Tr>
              {parTrimestre &&
                [1, 2, 3, 4].map((t) => (
                  <Table.Th key={t} w={34} ta="center" {...ENTETE}>{`T${t}`}</Table.Th>
                ))}
              {parSemaine &&
                jours.map((j) => (
                  <Table.Th key={j} w={58} ta="center" {...ENTETE} bg={j === jour ? "var(--mantine-color-yellow-2)" : ENTETE.bg}
                    style={{ ...ENTETE.style, whiteSpace: "nowrap", cursor: "pointer" }} onClick={() => setJour(j)}>
                    {enteteJour(j)}
                  </Table.Th>
                ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {parSemaine && jourPrecis && lignes.length === 0 && (
              <Table.Tr><Table.Td colSpan={99}><Text size="sm" c="dimmed">{voc("Aucune activité prévue ce jour-là.")}</Text></Table.Td></Table.Tr>
            )}
            {lignes.map((l) => {
              const estElement = l.type === "element";
              const champs = estElement ? l.element : l.sousActivite;
              // Bandeau de couleur pour les niveaux qui regroupent d'autres éléments ; lignes de travail en blanc.
              const fond = estElement && !l.feuille ? FONDS_NIVEAUX[Math.min(l.profondeur, FONDS_NIVEAUX.length - 1)] : undefined;
              const titre = estElement && !l.feuille;
              const montant = estElement ? budget(l.element) : null;
              return (
                <Table.Tr key={estElement ? `e${l.element.id}` : `s${l.sousActivite.id}`} bg={fond}>
                  <Table.Td ta="center" fw={titre ? 700 : undefined} style={{ verticalAlign: "middle" }}>
                    {estElement ? l.element.code_activite : ""}
                  </Table.Td>
                  <Table.Td fw={titre ? 700 : undefined} pl={estElement ? undefined : "lg"}>
                    {titre && <>{nomNiveau(l.profondeur)} : </>}
                    {!estElement && <Text span size="xs" c="dimmed">{voc("Sous-activité")} : </Text>}
                    {champs.libelle}
                  </Table.Td>
                  {attributs.map((nom) => (
                    <Table.Td key={nom} fw={titre ? 700 : undefined}>{champs.attributs?.[nom] ?? ""}</Table.Td>
                  ))}
                  {avecServices && <Table.Td>{estElement ? l.element.structures_noms?.join(", ") : ""}</Table.Td>}
                  {parTrimestre ? (
                    [1, 2, 3, 4].map((t) => (
                      <Table.Td key={t} ta="center" fw={700} style={{ verticalAlign: "middle" }}>
                        {prevuAuTrimestre(champs.date_debut, champs.date_fin, annee, t) ? "X" : ""}
                      </Table.Td>
                    ))
                  ) : parSemaine && !jourPrecis ? (
                    <Table.Td colSpan={7} p={0} style={{ position: "relative", height: 1 }}>
                      <DiagrammeSemaine jours={jours} jour={jour} debut={champs.date_debut} fin={champs.date_fin} niveau={titre} fond={!!fond} />
                    </Table.Td>
                  ) : parSemaine ? (
                    <Table.Td ta="center" fw={700} style={{ verticalAlign: "middle" }}>
                      {prevuLe(champs.date_debut, champs.date_fin, jour) ? "X" : ""}
                    </Table.Td>
                  ) : (
                    <>
                      <Table.Td style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{date(champs.date_debut)}</Table.Td>
                      <Table.Td style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{date(champs.date_fin)}</Table.Td>
                    </>
                  )}
                  <Table.Td ta="right" fw={titre ? 700 : undefined} style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                    {montant !== null ? montant.toLocaleString(locale()) : ""}
                  </Table.Td>
                  <Table.Td ta="center" style={{ verticalAlign: "middle" }}>
                    {estElement ? (
                      <Button size="compact-xs" variant="white" color={l.element.taux_avertissements.length ? "orange" : "teal"} onClick={() => onAvancement(l.element)}>
                        {l.element.taux_realisation === null ? "—" : `${l.element.taux_realisation.toLocaleString(locale())} %`}
                      </Button>
                    ) : l.sousActivite.avancement !== null ? (
                      `${Number(l.sousActivite.avancement).toLocaleString(locale())} %`
                    ) : (
                      ""
                    )}
                  </Table.Td>
                  {editionActive && <Table.Td style={{ verticalAlign: "middle" }}>{actions(l)}</Table.Td>}
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </>
  );
}
