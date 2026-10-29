import { useState } from "react";
import { ActionIcon, Button, Group, SegmentedControl, Select, Table, Text, Tooltip } from "@mantine/core";
import { ListPlus, Pencil, Plus, Trash2 } from "lucide-react";
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
 * élément (tous niveaux) avec sa logique d'intervention, ses attributs, sa programmation par
 * trimestre pour l'année choisie et son budget ; les niveaux sont distingués par des bandeaux.
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
}) {
  const lignes = aplatir(elements);
  const anneesPossibles = annees(lignes);
  const anneeCourante = new Date().getFullYear();
  const [annee, setAnnee] = useState(anneesPossibles.includes(anneeCourante) ? anneeCourante : anneesPossibles[0]);
  // Programmation : un X par trimestre couvert, ou les dates de début et de fin (au choix, mémorisé).
  const [programmation, setProgrammation] = usePreference("programmation-planification", ["trimestres", "dates"] as const);
  const parTrimestre = programmation === "trimestres";
  const avecServices = lignes.some((l) => l.type === "element" && (l.element.structures_noms?.length ?? 0) > 0);

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
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
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
