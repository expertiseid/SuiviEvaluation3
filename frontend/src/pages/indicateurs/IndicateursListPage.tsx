import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileSpreadsheet, Gauge, Pencil, Search, Trash2 } from "lucide-react";
import {
  Accordion, ActionIcon, Badge, Button, Card, Group, Modal, Progress, SimpleGrid, Stack, Table, Text, TextInput, Tooltip, UnstyledButton,
} from "@mantine/core";
import { EmptyState } from "../../components/common/EmptyState";
import { locale } from "../../utils/i18n";
import { notifications } from "@mantine/notifications";
import { useDeleteIndicateur, useIndicateurs } from "../../api/indicators";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { correspond } from "../../utils/recherche";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { IndicateurForm } from "./IndicateurForm";
import { ImportIndicateursModal } from "./ImportIndicateursModal";
import type { Indicateur } from "../../types";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { voc } from "../../utils/vocabulaire";

const SANS_PROJET = voc("Indicateurs stratégiques (sans projet rattaché)");

function grouperParProjet(indicateurs: Indicateur[]): [string, Indicateur[]][] {
  const groupes = new Map<string, Indicateur[]>();
  for (const indicateur of indicateurs) {
    const cle = indicateur.projet_rattache_nom ?? SANS_PROJET;
    if (!groupes.has(cle)) groupes.set(cle, []);
    groupes.get(cle)!.push(indicateur);
  }
  for (const liste of groupes.values()) {
    liste.sort((a, b) => a.libelle.localeCompare(b.libelle, "fr"));
  }
  return [...groupes.entries()].sort(([a], [b]) => {
    if (a === SANS_PROJET) return 1;
    if (b === SANS_PROJET) return -1;
    return a.localeCompare(b, "fr");
  });
}

const nombre = (v: string | null | undefined) =>
  v === null || v === undefined || v === "" ? "—" : Number(v).toLocaleString(locale(), { maximumFractionDigits: 2 });
/** Fond léger d'une couleur de palier (« #rrggbb », réglée dans les paramètres d'alerte). */
const teinte = (couleur: string) => (/^#[0-9a-f]{6}$/i.test(couleur) ? `${couleur}1A` : undefined);
const FREQUENCES: Record<Indicateur["frequence_collecte"], string> = {
  MENSUELLE: voc("Mensuelle"), TRIMESTRIELLE: voc("Trimestrielle"), SEMESTRIELLE: voc("Semestrielle"), ANNUELLE: voc("Annuelle"),
};

export function IndicateursListPage() {
  const { data: indicateurs, isLoading } = useIndicateurs();
  const deleteIndicateur = useDeleteIndicateur();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImportOuvert, setModalImportOuvert] = useState(false);
  const [indicateurEnEdition, setIndicateurEnEdition] = useState<Indicateur | null>(null);
  const [recherche, setRecherche] = useState("");
  const [editionActive, setEditionActive] = useState(false);

  const navigate = useNavigate();
  // Filtre par état (palier d'alerte) : les compteurs du haut servent de boutons.
  const [palier, setPalier] = useState<string | null>(null);
  const paliers = useMemo(() => {
    const parLibelle = new Map<string, { libelle: string; couleur: string; borne: number; nombre: number }>();
    for (const i of indicateurs ?? []) {
      if (!i.palier_actuel) continue;
      const p = parLibelle.get(i.palier_actuel.libelle) ?? { libelle: i.palier_actuel.libelle, couleur: i.palier_actuel.couleur, borne: i.palier_actuel.borne_min, nombre: 0 };
      p.nombre += 1;
      parLibelle.set(p.libelle, p);
    }
    return [...parLibelle.values()].sort((a, b) => b.borne - a.borne);
  }, [indicateurs]);
  const indicateursFiltres = useMemo(
    () => (indicateurs ?? []).filter((i) => (!palier || i.palier_actuel?.libelle === palier)
      && (correspond(i.libelle, recherche) || correspond(i.projet_rattache_nom ?? "", recherche))),
    [indicateurs, recherche, palier],
  );
  const groupes = useMemo(() => grouperParProjet(indicateursFiltres), [indicateursFiltres]);
  // Groupes dépliés par défaut ; on mémorise ceux que l'utilisateur replie.
  const [replies, setReplies] = useState<string[]>([]);

  function handleSupprimer(id: number, libelle: string) {
    confirmerSuppression({
      message: voc`Supprimer l'indicateur "${libelle}" ainsi que toutes ses valeurs saisies ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteIndicateur.mutateAsync(id);
          notifications.show({ message: voc("Indicateur supprimé"), color: "green" });
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression de l'indicateur"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <TitreRubrique route="/indicateurs" defaut={voc("Indicateurs")} />
        <Group gap="xs">
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          <Button variant="light" leftSection={<FileSpreadsheet size={16} />} onClick={() => setModalImportOuvert(true)}>
            {voc("Importer depuis Excel")}
          </Button>
          <Button onClick={() => setModalOpen(true)}>{voc("Nouvel indicateur")}</Button>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 2, sm: Math.min(paliers.length + 1, 5) }} spacing="sm">
        {[{ libelle: null as string | null, couleur: "#0ca678", nombre: indicateurs?.length ?? 0 }, ...paliers].map((p) => {
          const actif = palier === p.libelle;
          return (
            <UnstyledButton key={p.libelle ?? "tous"} onClick={() => setPalier(p.libelle)} aria-pressed={actif}>
              <Card withBorder radius="md" padding="sm" bg={actif ? teinte(p.couleur) : undefined}
                style={{ borderColor: actif ? p.couleur : undefined }}>
                <Group gap={6} wrap="nowrap">
                  {p.libelle && <span style={{ width: 9, height: 9, borderRadius: 9, flexShrink: 0, background: p.couleur }} />}
                  <Text size="xs" c="dimmed" tt="uppercase" fw={600} truncate>{p.libelle ?? voc("Tous les indicateurs")}</Text>
                </Group>
                <Text fw={700} fz={26} c={p.couleur}>{p.nombre}</Text>
              </Card>
            </UnstyledButton>
          );
        })}
      </SimpleGrid>

      <Group justify="space-between" gap="sm">
        <TextInput placeholder={voc("Rechercher un indicateur ou un projet…")} leftSection={<Search size={15} />} value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)} w={400} maw="100%" />
        {groupes.length > 1 && (
          <Group gap="xs">
            <Button size="xs" variant="subtle" color="gray" onClick={() => setReplies([])}>{voc("Tout déplier")}</Button>
            <Button size="xs" variant="subtle" color="gray" onClick={() => setReplies(groupes.map(([nom]) => nom))}>{voc("Tout replier")}</Button>
          </Group>
        )}
      </Group>

      {isLoading ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : groupes.length === 0 ? (
        <Card withBorder radius="md">
          <EmptyState icon={<Gauge size={32} strokeWidth={1.5} />}
            message={recherche || palier ? voc("Aucun indicateur ne correspond à la recherche.") : voc("Aucun indicateur pour le moment.")} />
        </Card>
      ) : (
        <Accordion multiple variant="separated" radius="md"
          value={groupes.map(([nom]) => nom).filter((nom) => !replies.includes(nom))}
          onChange={(ouverts) => setReplies(groupes.map(([nom]) => nom).filter((nom) => !ouverts.includes(nom)))}>
          {groupes.map(([nomProjet, liste]) => (
            <Accordion.Item key={nomProjet} value={nomProjet} bg="white">
              <Accordion.Control>
                <Group justify="space-between" wrap="nowrap" pe="sm">
                  <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                    <Text fw={600} size="sm" truncate>{nomProjet}</Text>
                    <Badge variant="light" color="teal" size="sm" style={{ flexShrink: 0 }}>{voc`${liste.length} indicateur(s)`}</Badge>
                  </Group>
                  {/* Répartition des indicateurs du projet par état, en pastilles. */}
                  <Group gap={4} wrap="nowrap" visibleFrom="sm">
                    {paliers.map((p) => {
                      const n = liste.filter((i) => i.palier_actuel?.libelle === p.libelle).length;
                      return n ? <Tooltip key={p.libelle} label={`${p.libelle} : ${n}`}><Badge size="sm" variant="filled" color={p.couleur} radius="xl">{n}</Badge></Tooltip> : null;
                    })}
                  </Group>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Table.ScrollContainer minWidth={760}>
                  <Table highlightOnHover verticalSpacing="sm">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Indicateur")}</Table.Th>
                        <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Unité")}</Table.Th>
                        <Table.Th tt="uppercase" fz="xs" c="dimmed" ta="right">{voc("Valeur de base")}</Table.Th>
                        <Table.Th tt="uppercase" fz="xs" c="dimmed" ta="right">{voc("Cible")}</Table.Th>
                        <Table.Th tt="uppercase" fz="xs" c="dimmed" w={240}>{voc("Réalisation")}</Table.Th>
                        {editionActive && <Table.Th />}
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {liste.map((i) => (
                        <Table.Tr key={i.id} style={{ cursor: "pointer" }} onClick={() => navigate(`/indicateurs/${i.id}`)}>
                          <Table.Td maw={460}>
                            <Text component={Link} to={`/indicateurs/${i.id}`} size="sm" fw={600} c="dark.7" lineClamp={2} onClick={(e) => e.stopPropagation()}>
                              {i.libelle}
                            </Text>
                            <Text size="xs" c="dimmed">{FREQUENCES[i.frequence_collecte] ?? i.frequence_collecte}</Text>
                          </Table.Td>
                          <Table.Td><Text size="sm">{i.unite || "—"}</Text></Table.Td>
                          <Table.Td ta="right"><Text size="sm" c="dimmed">{nombre(i.valeur_reference)}</Text></Table.Td>
                          <Table.Td ta="right"><Text size="sm" fw={600}>{nombre(i.valeur_cible)}</Text></Table.Td>
                          <Table.Td>
                            {i.palier_actuel ? (
                              <Stack gap={4}>
                                <Group justify="space-between" gap={6} wrap="nowrap">
                                  <Text size="xs" fw={600} c={i.palier_actuel.couleur}>{i.palier_actuel.libelle}</Text>
                                  <Text size="xs" fw={700}>{i.taux_realisation_actuel.toLocaleString(locale())} %</Text>
                                </Group>
                                <Progress value={Math.min(100, i.taux_realisation_actuel)} color={i.palier_actuel.couleur} size="sm" radius="xl"
                                  aria-label={voc("Taux de réalisation")} />
                              </Stack>
                            ) : <Text size="xs" c="dimmed">{voc("Pas encore de valeur")}</Text>}
                          </Table.Td>
                          {editionActive && (
                            <Table.Td onClick={(e) => e.stopPropagation()}>
                              <Group gap={4} wrap="nowrap">
                                <Tooltip label={voc("Modifier l'indicateur")}>
                                  <ActionIcon variant="subtle" onClick={() => setIndicateurEnEdition(i)}>
                                    <Pencil size={15} />
                                  </ActionIcon>
                                </Tooltip>
                                <Tooltip label={voc("Supprimer l'indicateur")}>
                                  <ActionIcon variant="subtle" color="red" loading={deleteIndicateur.isPending} onClick={() => handleSupprimer(i.id, i.libelle)}>
                                    <Trash2 size={15} />
                                  </ActionIcon>
                                </Tooltip>
                              </Group>
                            </Table.Td>
                          )}
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title={voc("Nouvel indicateur")} size="lg">
        <IndicateurForm onDone={() => setModalOpen(false)} />
      </Modal>

      <Modal opened={!!indicateurEnEdition} onClose={() => setIndicateurEnEdition(null)} title={voc("Modifier l'indicateur")} size="lg">
        {indicateurEnEdition && (
          <IndicateurForm indicateur={indicateurEnEdition} onDone={() => setIndicateurEnEdition(null)} />
        )}
      </Modal>

      <ImportIndicateursModal opened={modalImportOuvert} onClose={() => setModalImportOuvert(false)} />
    </Stack>
  );
}
