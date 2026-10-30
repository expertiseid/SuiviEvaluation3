import { useEffect, useState } from "react";
import { ActionIcon, Badge, Group, NumberInput, Table, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Pencil, Trash2 } from "lucide-react";
import { useCreateTranchePlanifiee, useUpdateTranchePlanifiee } from "../../api/suivi";
import type { LignePeriode, PeriodePlanification } from "../../types";
import { messageErreurApi } from "../../utils/erreurs";
import { fmt, fmtDate, nombre } from "../../utils/periode";
import { voc } from "../../utils/vocabulaire";

// Bandeaux par niveau, comme le tableau de la planification.
const FONDS_NIVEAUX = ["var(--mantine-color-blue-3)", "var(--mantine-color-blue-2)", "var(--mantine-color-blue-1)", "var(--mantine-color-blue-0)"];
const ENTETE = { bg: "var(--mantine-color-green-1)", fz: "xs", style: { verticalAlign: "middle" as const } };
const MILIEU = { style: { verticalAlign: "middle" as const } };
const date = (iso: string | null) => (iso ? fmtDate(iso) : "");
const COULEUR_STATUT: Record<string, string> = { Atteinte: "green", "En retard": "red", "En cours": "blue", "À venir": "gray" };

/** Objectif (quantité ou avancement visé) ou budget de la période, saisi dans la cellule ; enregistré en quittant le champ. */
function CelluleSaisie({ ligne, champ, periode }: { ligne: LignePeriode; champ: "cible" | "budget"; periode: PeriodePlanification }) {
  const createTranche = useCreateTranchePlanifiee();
  const updateTranche = useUpdateTranchePlanifiee();
  const actuelle = nombre(champ === "cible" ? ligne.prevu_quantite : ligne.prevu_budget);
  const [valeur, setValeur] = useState<number | string>(actuelle ?? "");
  useEffect(() => setValeur(actuelle ?? ""), [actuelle]);

  async function enregistrer() {
    const nouvelle = nombre(valeur);
    if (nouvelle === actuelle) return;
    const payload = { [champ]: nouvelle };
    try {
      if (ligne.tranche_id) await updateTranche.mutateAsync({ id: ligne.tranche_id, payload });
      else await createTranche.mutateAsync({ periode: periode.id, [ligne.type]: ligne.id, ...payload });
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement de l'objectif")), color: "red" });
    }
  }

  return (
    <NumberInput
      size="xs"
      value={valeur}
      onChange={setValeur}
      onBlur={enregistrer}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      placeholder={voc("À définir")}
      min={0}
      max={champ === "cible" && ligne.mode === "avancement" ? 100 : undefined}
      thousandSeparator=" "
      hideControls
      disabled={createTranche.isPending || updateTranche.isPending}
      w={champ === "cible" ? 90 : 120}
    />
  );
}

/**
 * Planification par période en tableau (mode Tableau de l'onglet) : une ligne par élément, dans
 * l'ordre de la planification (bandeaux pour les niveaux qui en regroupent d'autres), avec ses
 * valeurs globales, ses objectifs sur la période (saisis dans les cellules en mode « Éditer »),
 * ses dates prévues, le réalisé, le taux et le statut.
 */
export function PeriodeTableau({
  lignes,
  periode,
  modifiable,
  onEditer,
  onEffacer,
}: {
  lignes: LignePeriode[];
  periode: PeriodePlanification;
  /** Mode « Éditer » et droit d'écriture : objectifs et budget saisis dans le tableau. */
  modifiable: boolean;
  onEditer: (ligne: LignePeriode) => void;
  onEffacer: (trancheId: number, libelle: string) => void;
}) {
  const parents = new Set(lignes.filter((l) => l.type === "activite").map((l) => l.parent_id));
  return (
    <Table.ScrollContainer minWidth={1250}>
      <Table withTableBorder withColumnBorders verticalSpacing={6} fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th rowSpan={2} w={80} {...ENTETE}>{voc("Code")}</Table.Th>
            <Table.Th rowSpan={2} miw={300} {...ENTETE}>{voc("Logique d'intervention")}</Table.Th>
            <Table.Th rowSpan={2} w={90} {...ENTETE}>{voc("Unité")}</Table.Th>
            <Table.Th colSpan={2} ta="center" {...ENTETE}>{voc("Global")}</Table.Th>
            <Table.Th colSpan={4} ta="center" {...ENTETE}>{periode.libelle}</Table.Th>
            <Table.Th colSpan={3} ta="center" {...ENTETE}>{voc("Réalisé")}</Table.Th>
            <Table.Th rowSpan={2} w={95} ta="center" {...ENTETE}>{voc("Statut")}</Table.Th>
            {modifiable && <Table.Th rowSpan={2} w={60} {...ENTETE} />}
          </Table.Tr>
          <Table.Tr>
            <Table.Th ta="right" {...ENTETE}>{voc("Prévu")}</Table.Th>
            <Table.Th ta="right" {...ENTETE}>{voc("Budget")}</Table.Th>
            <Table.Th ta="right" {...ENTETE}>{voc("Objectif")}</Table.Th>
            <Table.Th ta="right" {...ENTETE}>{voc("Budget")}</Table.Th>
            <Table.Th {...ENTETE}>{voc("Début")}</Table.Th>
            <Table.Th {...ENTETE}>{voc("Fin")}</Table.Th>
            <Table.Th ta="right" {...ENTETE}>{voc("Quantité")}</Table.Th>
            <Table.Th ta="center" {...ENTETE}>{voc("Taux")}</Table.Th>
            <Table.Th ta="right" {...ENTETE}>{voc("Budget")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lignes.map((l) => {
            const activite = l.type === "activite";
            const titre = activite && parents.has(l.id);
            const fond = titre ? FONDS_NIVEAUX[Math.min(l.profondeur, FONDS_NIVEAUX.length - 1)] : undefined;
            // L'unité est dans sa propre colonne : les cellules ne portent que des nombres.
            const unite = l.mode === "avancement" ? "%" : l.unite;
            const defini = l.source === "saisi";
            return (
              <Table.Tr key={`${l.type}-${l.id}`} bg={fond}>
                <Table.Td ta="center" fw={titre ? 700 : undefined} {...MILIEU}>{l.code}</Table.Td>
                <Table.Td fw={titre ? 700 : undefined} pl={activite ? undefined : "lg"}>
                  {activite ? (
                    titre ? <>{l.niveau} : {l.libelle}</> : l.libelle
                  ) : (
                    <><Text span size="xs" c="dimmed">{voc("Sous-activité")} : </Text>{l.libelle}</>
                  )}
                  {l.dans_dates_globales === false && (
                    <Text size="xs" c="dimmed" fw={400}>{voc("Hors de ses dates dans la planification globale")}</Text>
                  )}
                </Table.Td>
                <Table.Td {...MILIEU}><Text size="xs" c="dimmed">{unite}</Text></Table.Td>
                <Table.Td ta="right" style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                  {l.mode === "avancement" ? "100" : fmt(l.global_quantite)}
                </Table.Td>
                <Table.Td ta="right" style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{activite ? fmt(l.global_budget) : ""}</Table.Td>
                <Table.Td ta="right" style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                  {modifiable ? (
                    <CelluleSaisie ligne={l} champ="cible" periode={periode} />
                  ) : defini ? (
                    fmt(l.prevu_quantite)
                  ) : (
                    <Badge size="xs" variant="light" color="orange">{voc("À définir")}</Badge>
                  )}
                </Table.Td>
                <Table.Td ta="right" style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                  {activite ? (modifiable ? <CelluleSaisie ligne={l} champ="budget" periode={periode} /> : defini ? fmt(l.prevu_budget) : "") : ""}
                </Table.Td>
                <Table.Td style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{date(l.debut_prevu)}</Table.Td>
                <Table.Td style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{date(l.fin_prevue)}</Table.Td>
                <Table.Td ta="right" style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                  {fmt(l.realise_quantite)}
                </Table.Td>
                <Table.Td ta="center" c="teal.7" fw={500} style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>
                  {l.taux === null ? "—" : `${fmt(l.taux)} %`}
                </Table.Td>
                <Table.Td ta="right" style={{ whiteSpace: "nowrap", verticalAlign: "middle" }}>{activite ? fmt(l.budget_realise) : ""}</Table.Td>
                <Table.Td ta="center" {...MILIEU}>
                  <Badge size="xs" variant="light" color={defini ? (COULEUR_STATUT[l.statut] ?? "blue") : "orange"}>
                    {voc(l.statut)}
                  </Badge>
                </Table.Td>
                {modifiable && (
                  <Table.Td {...MILIEU}>
                    <Group gap={2} wrap="nowrap">
                      <Tooltip label={voc("Dates prévues et commentaire")}>
                        <ActionIcon size="sm" variant="subtle" onClick={() => onEditer(l)}><Pencil size={12} /></ActionIcon>
                      </Tooltip>
                      {l.tranche_id !== null && defini && (
                        <Tooltip label={voc("Effacer l'objectif de la période")}>
                          <ActionIcon size="sm" variant="subtle" color="red" onClick={() => onEffacer(l.tranche_id!, l.libelle)}>
                            <Trash2 size={12} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
