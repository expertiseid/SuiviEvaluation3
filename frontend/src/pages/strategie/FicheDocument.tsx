import type { ReactNode } from "react";
import { Card, Group, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import type { CadreStrategique } from "../../types";
import { StatusBadge } from "../../components/common/StatusBadge";
import { PROJET_STATUT_LABEL, PROJET_STATUT_TONE } from "../../utils/statusTones";
import { PAYS_MONDE } from "../../utils/pays";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const montant = (v: string | number | null | undefined) => `${Number(v ?? 0).toLocaleString(locale())} FCFA`;
const nombre = (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString(locale()));

/** Une ligne « libellé : valeur » ; rien d'affiché si la valeur est vide. */
function Ligne({ libelle, children }: { libelle: string; children: ReactNode }) {
  if (children == null || children === "" || (Array.isArray(children) && children.length === 0)) return null;
  return (
    <Group gap={6} align="flex-start" wrap="nowrap">
      <Text size="sm" c="dimmed" miw={190}>{libelle}</Text>
      <Text size="sm" fw={500} style={{ flex: 1 }}>{children}</Text>
    </Group>
  );
}

/**
 * Fiche d'un document de la chaîne (Programme, Pilier…), présentée comme celle d'un projet :
 * identification et calendrier, financement (bailleurs), mise en œuvre et zones, cibles,
 * organisation et capitalisation. En lecture : la saisie passe par « Modifier ».
 */
export function FicheDocument({ cadre }: { cadre: CadreStrategique }) {
  const financements = cadre.financements ?? [];
  const pays = (cadre.pays ?? []).map((code) => PAYS_MONDE.find((p) => p.code === code)?.nom ?? code);
  const cibles: [string, number | null | undefined][] = [
    [voc("Cible totale"), cadre.cible_totale],
    [voc("Dont hommes"), cadre.cible_hommes],
    [voc("Dont femmes"), cadre.cible_femmes],
    [voc("Dont jeunes"), cadre.cible_jeunes],
    [voc("Dont PDI"), cadre.cible_pdi],
  ];

  return (
    <SimpleGrid cols={{ base: 1, md: 2 }}>
      <Card withBorder radius="md" padding="md">
        <Title order={5} mb="sm">{voc("Général")}</Title>
        <Stack gap={6}>
          <Ligne libelle={voc("Code")}>{cadre.code}</Ligne>
          <Ligne libelle={voc("Statut")}>
            {cadre.statut ? <StatusBadge tone={PROJET_STATUT_TONE[cadre.statut]}>{PROJET_STATUT_LABEL[cadre.statut]}</StatusBadge> : null}
          </Ligne>
          <Ligne libelle={voc("Période")}>
            {cadre.date_debut || cadre.date_fin ? `${cadre.date_debut ?? "…"} → ${cadre.date_fin ?? "…"}` : null}
          </Ligne>
          <Ligne libelle={voc("Rattaché aussi à")}>
            {(cadre.elements_parents_secondaires_noms ?? []).length > 0
              ? `${cadre.elements_parents_secondaires_noms!.join(", ")} (${voc("pour information")})`
              : null}
          </Ligne>
          <Ligne libelle={voc("Responsable")}>{cadre.responsable_nom}</Ligne>
          <Ligne libelle={voc("Utilisateurs affectés")}>{(cadre.utilisateurs_affectes_noms ?? []).join(", ")}</Ligne>
          <Ligne libelle={voc("Description")}>{cadre.description}</Ligne>
        </Stack>
      </Card>

      <Card withBorder radius="md" padding="md">
        <Title order={5} mb="sm">{voc("Financement")}</Title>
        <Stack gap={6}>
          <Ligne libelle={voc("Budget total")}>{Number(cadre.budget_total ?? 0) > 0 ? montant(cadre.budget_total) : null}</Ligne>
          <Ligne libelle={voc("Fonds propres")}>{Number(cadre.fonds_propres ?? 0) > 0 ? montant(cadre.fonds_propres) : null}</Ligne>
          {financements.length > 0 ? (
            <Table withTableBorder verticalSpacing={4} mt={4}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Bailleur")}</Table.Th>
                  <Table.Th ta="right">{voc("Montant")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {financements.map((f) => (
                  <Table.Tr key={f.id}>
                    <Table.Td>{f.bailleur_nom}</Table.Td>
                    <Table.Td ta="right">{montant(f.montant)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Text size="xs" c="dimmed">{voc("Aucun bailleur : financé sur fonds propres.")}</Text>
          )}
        </Stack>
      </Card>

      <Card withBorder radius="md" padding="md">
        <Title order={5} mb="sm">{voc("Mise en œuvre")}</Title>
        <Stack gap={6}>
          <Ligne libelle={voc("Type de mise en œuvre")}>
            {cadre.type_mise_en_oeuvre === "CONSORTIUM" ? voc("En consortium") : voc("Direct")}
          </Ligne>
          <Ligne libelle={voc("Partenaire de mise en œuvre")}>{cadre.partenaire_mise_en_oeuvre_nom}</Ligne>
          <Ligne libelle={voc("Partenaires du consortium")}>{(cadre.partenaires_consortium_noms ?? []).join(", ")}</Ligne>
          <Ligne libelle={voc("Pays d'intervention")}>{pays.join(", ")}</Ligne>
          <Ligne libelle={voc("Zones d'intervention")}>
            {cadre.tout_le_pays ? voc("Tout le pays") : (cadre.zones_noms ?? []).join(", ")}
          </Ligne>
          <Ligne libelle={voc("Services chargés")}>{(cadre.structures_noms ?? []).join(", ")}</Ligne>
          <Ligne libelle={voc("Parties prenantes")}>{(cadre.parties_prenantes_noms ?? []).join(", ")}</Ligne>
        </Stack>
      </Card>

      <Card withBorder radius="md" padding="md">
        <Title order={5} mb="sm">{voc("Cibles bénéficiaires")}</Title>
        <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="xs">
          {cibles.map(([libelle, valeur]) => (
            <Stack key={libelle} gap={0}>
              <Text size="xs" c="dimmed">{libelle}</Text>
              <Text fw={600}>{nombre(valeur)}</Text>
            </Stack>
          ))}
        </SimpleGrid>
        {cadre.elements_capitalisation && (
          <>
            <Title order={5} mt="md" mb={4}>{voc("Éléments de capitalisation")}</Title>
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{cadre.elements_capitalisation}</Text>
          </>
        )}
      </Card>
    </SimpleGrid>
  );
}
