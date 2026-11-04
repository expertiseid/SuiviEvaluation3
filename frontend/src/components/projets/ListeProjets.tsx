import { type ReactNode, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarRange, FolderKanban, Search } from "lucide-react";
import { Avatar, Badge, Card, Group, Progress, SimpleGrid, Stack, Table, Text, TextInput, Tooltip, UnstyledButton } from "@mantine/core";
import { StatusBadge } from "../common/StatusBadge";
import { EmptyState } from "../common/EmptyState";
import { PROJET_STATUT_LABEL, PROJET_STATUT_TONE } from "../../utils/statusTones";
import { correspond } from "../../utils/recherche";
import { locale, nombreCourt } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { initiales } from "../../utils/texte";
import type { ProjetResume, StatutProjet } from "../../types";

const STATUTS: StatutProjet[] = ["EN_COURS", "EN_PREPARATION", "CLOTURE"];
const COULEUR_STATUT: Record<StatutProjet, string> = { EN_COURS: "teal", EN_PREPARATION: "gray", CLOTURE: "blue" };

const dateCourte = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(locale(), { day: "2-digit", month: "short", year: "numeric" });

/** Part de la période déjà écoulée (0 avant le début, 100 après la fin). */
function tempsEcoule(debut: string, fin: string) {
  const d = new Date(debut).getTime(), f = new Date(fin).getTime();
  if (!(f > d)) return null;
  return Math.min(100, Math.max(0, Math.round(((Date.now() - d) / (f - d)) * 100)));
}

/**
 * Liste des projets (pages Projets et Suivi) : compteurs par statut qui servent de filtre, recherche,
 * puis un tableau lisible (nom, code et bailleur, période avec le temps écoulé, budget, chef de projet).
 * Un clic sur une ligne mène à `lien(projet)`.
 */
export function ListeProjets({ projets, isLoading, lien, actions }: {
  projets: ProjetResume[] | undefined;
  isLoading: boolean;
  lien: (p: ProjetResume) => string;
  /** Boutons de fin de ligne (mode édition) ; colonne absente si non fourni. */
  actions?: (p: ProjetResume) => ReactNode;
}) {
  const navigate = useNavigate();
  const [recherche, setRecherche] = useState("");
  const [statut, setStatut] = useState<StatutProjet | "TOUS">("TOUS");

  const compte = (s: StatutProjet) => (projets ?? []).filter((p) => p.statut === s).length;
  const projetsFiltres = useMemo(
    () => (projets ?? []).filter((p) => (statut === "TOUS" || p.statut === statut) && (correspond(p.nom, recherche) || correspond(p.code, recherche))),
    [projets, recherche, statut],
  );
  const budgetFiltre = projetsFiltres.reduce((total, p) => total + (Number(p.budget_total) || 0), 0);

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        {(["TOUS", ...STATUTS] as const).map((s) => {
          const actif = statut === s;
          return (
            <UnstyledButton key={s} onClick={() => setStatut(s)} aria-pressed={actif}>
              <Card withBorder radius="md" padding="sm" bg={actif ? "teal.0" : undefined}
                style={{ borderColor: actif ? "var(--mantine-color-teal-5)" : undefined }}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={600}>{s === "TOUS" ? voc("Tous les projets") : PROJET_STATUT_LABEL[s]}</Text>
                <Text fw={700} fz={26} c={s === "TOUS" ? "teal.9" : `${COULEUR_STATUT[s]}.8`}>{s === "TOUS" ? projets?.length ?? 0 : compte(s)}</Text>
              </Card>
            </UnstyledButton>
          );
        })}
      </SimpleGrid>

      <Group justify="space-between" gap="sm">
        <TextInput placeholder={voc("Rechercher un projet (nom ou code)…")} leftSection={<Search size={15} />} value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)} w={400} maw="100%" />
        {projetsFiltres.length > 0 && (
          <Text size="sm" c="dimmed">{voc`${projetsFiltres.length} projet(s) · budget total ${nombreCourt(budgetFiltre)} FCFA`}</Text>
        )}
      </Group>

      <Card withBorder padding="md" radius="md">
        {isLoading ? (
          <Text c="dimmed">{voc("Chargement…")}</Text>
        ) : !projets || projets.length === 0 ? (
          <EmptyState icon={<FolderKanban size={32} strokeWidth={1.5} />} message={voc("Aucun projet pour le moment.")} />
        ) : projetsFiltres.length === 0 ? (
          <EmptyState icon={<FolderKanban size={32} strokeWidth={1.5} />} message={voc("Aucun projet ne correspond à la recherche.")} />
        ) : (
          <Table.ScrollContainer minWidth={900}>
            <Table highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Projet")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Statut")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed" w={230}>{voc("Période")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed" ta="right">{voc("Budget (FCFA)")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Chef de projet")}</Table.Th>
                  {actions && <Table.Th />}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {projetsFiltres.map((p) => {
                  const ecoule = tempsEcoule(p.date_debut, p.date_fin);
                  const budget = Number(p.budget_total) || 0;
                  return (
                    <Table.Tr key={p.id} style={{ cursor: "pointer" }} onClick={() => navigate(lien(p))}>
                      <Table.Td maw={520}>
                        <Text component={Link} to={lien(p)} size="sm" fw={600} c="dark.7" lineClamp={2} onClick={(e) => e.stopPropagation()}>
                          {p.nom}
                        </Text>
                        <Group gap={6} mt={4} wrap="nowrap">
                          <Badge size="xs" variant="outline" color="gray" radius="sm" style={{ flexShrink: 0 }}>{p.code}</Badge>
                          {(p.partenaire_bailleur_nom || p.element_strategique_libelle) && (
                            <Text size="xs" c="dimmed" truncate>{p.partenaire_bailleur_nom || p.element_strategique_libelle}</Text>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <StatusBadge tone={PROJET_STATUT_TONE[p.statut]}>{PROJET_STATUT_LABEL[p.statut]}</StatusBadge>
                      </Table.Td>
                      <Table.Td>
                        <Group gap={6} wrap="nowrap">
                          <CalendarRange size={14} color="var(--mantine-color-gray-6)" style={{ flexShrink: 0 }} />
                          <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>{dateCourte(p.date_debut)} → {dateCourte(p.date_fin)}</Text>
                        </Group>
                        {ecoule !== null && p.statut !== "CLOTURE" && (
                          <Tooltip label={voc`${ecoule} % de la période écoulée`}>
                            <Progress value={ecoule} size="sm" mt={6} radius="xl" color={ecoule >= 100 ? "orange" : "teal"} aria-label={voc("Période écoulée")} />
                          </Tooltip>
                        )}
                      </Table.Td>
                      <Table.Td ta="right">
                        <Tooltip label={`${budget.toLocaleString(locale())} FCFA`} disabled={!budget}>
                          <Text size="sm" fw={600} style={{ whiteSpace: "nowrap" }}>{budget ? nombreCourt(budget) : "—"}</Text>
                        </Tooltip>
                      </Table.Td>
                      <Table.Td>
                        {p.chef_de_projet_nom ? (
                          <Group gap={8} wrap="nowrap">
                            <Avatar size={28} radius="xl" color="teal" variant="light">{initiales(p.chef_de_projet_nom)}</Avatar>
                            <Text size="sm" style={{ whiteSpace: "nowrap" }}>{p.chef_de_projet_nom}</Text>
                          </Group>
                        ) : <Text size="sm" c="dimmed">—</Text>}
                      </Table.Td>
                      {actions && <Table.Td onClick={(e) => e.stopPropagation()}>{actions(p)}</Table.Td>}
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>
    </Stack>
  );
}
