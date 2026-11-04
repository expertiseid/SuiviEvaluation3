import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Download, History, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Autocomplete,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Menu,
  Modal,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Timeline,
  Tooltip,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useActivitesPourProjet } from "../../api/projects";
import { useIntervenants } from "../../api/intervenants";
import {
  useEnregistrerEvaluationRisque,
  useEnregistrerRisque,
  useRisques,
  useSupprimerEvaluationRisque,
  useSupprimerRisque,
} from "../../api/risques";
import { telecharger } from "../../api/suivi";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import type { NiveauRisque, Risque, StatutRisque } from "../../types";

import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
const NIVEAUX_RISQUE: Record<NiveauRisque, { label: string; couleur: string }> = {
  CRITIQUE: { label: voc("Critique"), couleur: "red" },
  ELEVE: { label: voc("Élevé"), couleur: "orange" },
  MOYEN: { label: voc("Moyen"), couleur: "yellow" },
  FAIBLE: { label: voc("Faible"), couleur: "green" },
};
const STATUTS: { value: StatutRisque; label: string; couleur: string }[] = [
  { value: "ACTIF", label: voc("Actif"), couleur: "blue" },
  { value: "SURVENU", label: voc("Survenu"), couleur: "red" },
  { value: "MAITRISE", label: voc("Maîtrisé"), couleur: "teal" },
  { value: "CLOS", label: voc("Clos"), couleur: "gray" },
];
const CATEGORIES = [
  "Financier", voc("Opérationnel"), voc("Sécuritaire"), voc("Politique et institutionnel"), voc("Climatique et environnemental"),
  voc("Social et communautaire"), "Sanitaire", "Juridique", "Fiduciaire", "Autre",
];
const PROBABILITES = ["Rare", "Peu probable", "Possible", "Probable", "Quasi certain"];
const IMPACTS = [voc("Négligeable"), "Mineur", voc("Modéré"), "Important", "Majeur"];

function niveauPour(criticite: number): NiveauRisque {
  if (criticite >= 16) return "CRITIQUE";
  if (criticite >= 10) return "ELEVE";
  if (criticite >= 5) return "MOYEN";
  return "FAIBLE";
}
const ouvert = (r: Risque) => r.statut === "ACTIF" || r.statut === "SURVENU";
const dateFr = (d: string | null) => (d ? new Date(d).toLocaleDateString(locale()) : "—");
const aujourdhui = () => new Date().toISOString().slice(0, 10);

function BadgeNiveau({ niveau, criticite }: { niveau: NiveauRisque; criticite?: number }) {
  const n = NIVEAUX_RISQUE[niveau];
  return <Badge color={n.couleur} variant="light">{n.label}{criticite !== undefined ? ` · ${criticite}` : ""}</Badge>;
}

/** Cotation 1 à 5, avec le libellé de chaque niveau. */
function Cotation({ label, libelles, value, onChange }: { label: string; libelles: string[]; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <Text size="sm" fw={500} mb={4}>{label} : <Text span c="dimmed">{value} — {libelles[value - 1]}</Text></Text>
      <SegmentedControl fullWidth value={String(value)} onChange={(v) => onChange(Number(v))} data={libelles.map((_l, i) => String(i + 1))} />
    </div>
  );
}

function RisqueForm({ projetId, risque, onClose }: { projetId: number; risque: Partial<Risque>; onClose: () => void }) {
  const enregistrer = useEnregistrerRisque();
  const { data: elements = [] } = useActivitesPourProjet(projetId);
  const { data: intervenants = [] } = useIntervenants();
  const [r, setR] = useState<Partial<Risque>>({ nature: "EXTERNE", probabilite: 3, impact: 3, statut: "ACTIF", date_identification: aujourdhui(), ...risque });
  const set = (champs: Partial<Risque>) => setR((x) => ({ ...x, ...champs }));
  const criticite = (r.probabilite ?? 3) * (r.impact ?? 3);

  async function valider() {
    if (!r.libelle?.trim()) {
      notifications.show({ message: voc("Indiquez le risque."), color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync({ ...r, projet: projetId, libelle: r.libelle.trim(), evaluations: undefined });
      notifications.show({ message: voc("Risque enregistré"), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={risque.id ? voc`Modifier le risque ${risque.code}` : voc("Nouveau risque")} size="lg">
      <Stack gap="sm">
        <TextInput label={voc("Risque")} placeholder={voc("Ex : Dégradation de la situation sécuritaire dans la zone")} required value={r.libelle ?? ""} onChange={(e) => set({ libelle: e.currentTarget.value })} data-autofocus />
        <Textarea label={voc("Causes et conséquences")} autosize minRows={2} value={r.description ?? ""} onChange={(e) => set({ description: e.currentTarget.value })} />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <div>
            <Text size="sm" fw={500} mb={4}>{voc("Nature")}</Text>
            <SegmentedControl fullWidth value={r.nature} onChange={(v) => set({ nature: v as Risque["nature"] })} data={[{ value: "INTERNE", label: voc("Interne") }, { value: "EXTERNE", label: voc("Externe") }]} />
          </div>
          <Autocomplete label={voc("Catégorie")} data={CATEGORIES} value={r.categorie ?? ""} onChange={(v) => set({ categorie: v })} />
        </SimpleGrid>
        <Select
          label={voc("Élément de la planification le plus exposé")}
          placeholder={voc("Tout le projet")}
          data={elements.map((e) => ({ value: String(e.id), label: e.libelle }))}
          value={r.element ? String(r.element) : null}
          onChange={(v) => set({ element: v ? Number(v) : null })}
          searchable
          clearable
        />
        <Card withBorder padding="sm" radius="md">
          <Stack gap="xs">
            <Cotation label={voc("Probabilité")} libelles={PROBABILITES} value={r.probabilite ?? 3} onChange={(probabilite) => set({ probabilite })} />
            <Cotation label={voc("Impact")} libelles={IMPACTS} value={r.impact ?? 3} onChange={(impact) => set({ impact })} />
            <Group gap="xs">
              <Text size="sm">{voc("Niveau de risque :")}</Text>
              <BadgeNiveau niveau={niveauPour(criticite)} criticite={criticite} />
            </Group>
          </Stack>
        </Card>
        <Textarea label={voc("Mesures d'atténuation")} description={voc("Ce qui est fait pour réduire la probabilité ou l'impact.")} autosize minRows={2} value={r.mesures_attenuation ?? ""} onChange={(e) => set({ mesures_attenuation: e.currentTarget.value })} />
        <Textarea label={voc("Plan de contingence")} description={voc("Ce qui sera fait si le risque survient.")} autosize minRows={2} value={r.plan_contingence ?? ""} onChange={(e) => set({ plan_contingence: e.currentTarget.value })} />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select
            label={voc("Responsable du suivi")}
            data={intervenants.map((i) => ({ value: String(i.id), label: `${i.nom} ${i.prenom}`.trim() }))}
            value={r.responsable ? String(r.responsable) : null}
            onChange={(v) => set({ responsable: v ? Number(v) : null })}
            searchable
            clearable
          />
          {!risque.id && (
            <Select label={voc("Statut")} data={STATUTS} value={r.statut} onChange={(v) => set({ statut: (v ?? "ACTIF") as StatutRisque })} allowDeselect={false} />
          )}
          <DateInput label={voc("Identifié le")} valueFormat="DD/MM/YYYY" value={r.date_identification ?? null} onChange={(v) => set({ date_identification: v ?? aujourdhui() })} />
          <DateInput label={voc("Prochaine revue")} valueFormat="DD/MM/YYYY" clearable value={r.date_prochaine_revue ?? null} onChange={(v) => set({ date_prochaine_revue: v })} />
        </SimpleGrid>
        {risque.id && <Text size="xs" c="dimmed">{voc("La cotation et le statut évoluent ensuite par les réévaluations (bouton « Réévaluer »).")}</Text>}
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function ReevaluationModal({ risque, onClose }: { risque: Risque; onClose: () => void }) {
  const enregistrer = useEnregistrerEvaluationRisque();
  const [date, setDate] = useState<string | null>(aujourdhui());
  const [probabilite, setProbabilite] = useState(risque.probabilite);
  const [impact, setImpact] = useState(risque.impact);
  const [statut, setStatut] = useState<StatutRisque>(risque.statut);
  const [actions, setActions] = useState("");
  const [commentaire, setCommentaire] = useState("");

  async function valider() {
    try {
      await enregistrer.mutateAsync({ risque: risque.id, date: date ?? aujourdhui(), probabilite, impact, statut, actions_menees: actions.trim(), commentaire: commentaire.trim() });
      notifications.show({ message: voc("Réévaluation enregistrée"), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc`Réévaluer ${risque.code} — ${risque.libelle}`} size="lg">
      <Stack gap="sm">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <DateInput label={voc("Date")} valueFormat="DD/MM/YYYY" value={date} onChange={setDate} />
          <Select label={voc("Statut")} data={STATUTS} value={statut} onChange={(v) => setStatut((v ?? "ACTIF") as StatutRisque)} allowDeselect={false} />
        </SimpleGrid>
        <Cotation label={voc("Probabilité")} libelles={PROBABILITES} value={probabilite} onChange={setProbabilite} />
        <Cotation label={voc("Impact")} libelles={IMPACTS} value={impact} onChange={setImpact} />
        <Group gap="xs">
          <Text size="sm">{voc("Niveau :")}</Text>
          <BadgeNiveau niveau={risque.niveau} criticite={risque.criticite} />
          <Text size="sm">→</Text>
          <BadgeNiveau niveau={niveauPour(probabilite * impact)} criticite={probabilite * impact} />
        </Group>
        <Textarea label={voc("Actions menées depuis la dernière revue")} autosize minRows={2} value={actions} onChange={(e) => setActions(e.currentTarget.value)} />
        <Textarea label={voc("Commentaire")} autosize minRows={2} value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Matrice probabilité × impact des risques ouverts ; un clic filtre la liste. */
function Matrice({ risques, filtre, onFiltre }: { risques: Risque[]; filtre: [number, number] | null; onFiltre: (f: [number, number] | null) => void }) {
  return (
    <Box>
      <Group gap={6} align="stretch" wrap="nowrap">
        <Text size="xs" c="dimmed" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", textAlign: "center" }}>{voc("Probabilité")}</Text>
        <Box style={{ flex: 1 }}>
          {[5, 4, 3, 2, 1].map((p) => (
            <Group key={p} gap={3} wrap="nowrap" mb={3}>
              <Text size="xs" w={14} ta="right" c="dimmed">{p}</Text>
              {[1, 2, 3, 4, 5].map((i) => {
                const ici = risques.filter((r) => ouvert(r) && r.probabilite === p && r.impact === i);
                const actif = filtre?.[0] === p && filtre?.[1] === i;
                const couleur = NIVEAUX_RISQUE[niveauPour(p * i)].couleur;
                return (
                  <Tooltip key={i} label={ici.length ? ici.map((r) => `${r.code} ${r.libelle}`).join(" · ") : `P${p} × I${i}`} multiline maw={320}>
                    <Box
                      onClick={() => ici.length && onFiltre(actif ? null : [p, i])}
                      style={{
                        flex: 1, height: 34, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center",
                        background: `var(--mantine-color-${couleur}-${ici.length ? 4 : 1})`, cursor: ici.length ? "pointer" : "default",
                        outline: actif ? "2px solid var(--mantine-color-dark-6)" : undefined, fontWeight: 700, fontSize: 13,
                      }}
                    >
                      {ici.length || ""}
                    </Box>
                  </Tooltip>
                );
              })}
            </Group>
          ))}
          <Group gap={3} wrap="nowrap">
            <Text size="xs" w={14} />
            {[1, 2, 3, 4, 5].map((i) => <Text key={i} size="xs" c="dimmed" ta="center" style={{ flex: 1 }}>{i}</Text>)}
          </Group>
          <Text size="xs" c="dimmed" ta="center">{voc("Impact")}</Text>
        </Box>
      </Group>
    </Box>
  );
}

/** Une ligne du registre ; l'historique des réévaluations se déplie sous la ligne. */
function LigneRisque({ risque, modifiable, onModifier, onReevaluer }: { risque: Risque; modifiable: boolean; onModifier: () => void; onReevaluer: () => void }) {
  const [historique, setHistorique] = useState(false);
  const supprimer = useSupprimerRisque();
  const supprimerEvaluation = useSupprimerEvaluationRisque();
  const statut = STATUTS.find((s) => s.value === risque.statut)!;
  const revueDepassee = risque.date_prochaine_revue && ouvert(risque) && risque.date_prochaine_revue < aujourdhui();
  const texte = (t: string | null | undefined) => <Text size="xs" c={t ? undefined : "dimmed"} style={{ whiteSpace: "pre-wrap" }}>{t || "—"}</Text>;

  return (
    <>
      <Table.Tr style={{ verticalAlign: "top", opacity: ouvert(risque) ? 1 : 0.7 }}>
        <Table.Td style={{ borderLeft: `4px solid var(--mantine-color-${NIVEAUX_RISQUE[risque.niveau].couleur}-6)` }}>
          <Badge variant="outline" color="dark">{risque.code}</Badge>
        </Table.Td>
        <Table.Td>
          <Text size="sm" fw={600}>{risque.libelle}</Text>
          {risque.description && <Text size="xs" c="dimmed" mt={2}>{risque.description}</Text>}
        </Table.Td>
        <Table.Td>
          <Stack gap={4} align="flex-start">
            <BadgeNiveau niveau={risque.niveau} criticite={risque.criticite} />
            <Text size="xs" c="dimmed">P{risque.probabilite} × I{risque.impact}</Text>
          </Stack>
        </Table.Td>
        <Table.Td><Badge variant="dot" color={statut.couleur}>{statut.label}</Badge></Table.Td>
        <Table.Td>
          <Text size="xs">{risque.nature === "INTERNE" ? voc("Interne") : voc("Externe")}</Text>
          {risque.categorie && <Text size="xs" c="dimmed">{risque.categorie}</Text>}
        </Table.Td>
        <Table.Td>{texte(risque.mesures_attenuation)}</Table.Td>
        <Table.Td>{texte(risque.plan_contingence)}</Table.Td>
        <Table.Td>{texte(risque.element_libelle)}</Table.Td>
        <Table.Td>{texte(risque.responsable_nom)}</Table.Td>
        <Table.Td>
          <Text size="xs" c={revueDepassee ? "red" : undefined} fw={revueDepassee ? 600 : undefined} style={{ whiteSpace: "nowrap" }}>
            {dateFr(risque.date_prochaine_revue)}
          </Text>
          {revueDepassee && <Text size="xs" c="red">{voc("dépassée")}</Text>}
        </Table.Td>
        <Table.Td>
          <Group gap={2} wrap="nowrap">
            {modifiable && (
              <Tooltip label={voc("Réévaluer")}>
                <ActionIcon variant="light" aria-label={voc("Réévaluer")} onClick={onReevaluer}><RefreshCw size={14} /></ActionIcon>
              </Tooltip>
            )}
            {risque.evaluations.length > 0 && (
              <Tooltip label={voc("Historique des réévaluations")}>
                <ActionIcon variant="subtle" aria-label={voc("Historique des réévaluations")} onClick={() => setHistorique((x) => !x)}>
                  {historique ? <ChevronUp size={15} /> : <History size={15} />}
                </ActionIcon>
              </Tooltip>
            )}
            {modifiable && (
              <>
                <Tooltip label={voc("Modifier")}>
                  <ActionIcon variant="subtle" onClick={onModifier} aria-label={voc("Modifier")}><Pencil size={14} /></ActionIcon>
                </Tooltip>
                <Tooltip label={voc("Supprimer")}>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    aria-label={voc("Supprimer")}
                    onClick={() => confirmerSuppression({ message: voc`Supprimer le risque ${risque.code} et son historique ?`, onConfirm: () => supprimer.mutate(risque.id) })}
                  >
                    <Trash2 size={14} />
                  </ActionIcon>
                </Tooltip>
              </>
            )}
          </Group>
        </Table.Td>
      </Table.Tr>
      {historique && (
        <Table.Tr>
          <Table.Td colSpan={11} bg="gray.0">
            <Text size="xs" fw={600} mb={6}>{voc("Historique des réévaluations")}</Text>
            <Timeline bulletSize={14} lineWidth={2}>
              {risque.evaluations.map((e) => (
                <Timeline.Item key={e.id} color={NIVEAUX_RISQUE[e.niveau].couleur} title={
                  <Group gap={6}>
                    <Text size="sm" fw={500}>{dateFr(e.date)}</Text>
                    <BadgeNiveau niveau={e.niveau} criticite={e.probabilite * e.impact} />
                    <Text size="xs" c="dimmed">{STATUTS.find((s) => s.value === e.statut)?.label} · {e.saisi_par_nom}</Text>
                    {modifiable && (
                      <ActionIcon size="xs" variant="subtle" color="red" aria-label={voc("Supprimer la réévaluation")}
                        onClick={() => confirmerSuppression({ message: voc`Supprimer la réévaluation du ${dateFr(e.date)} ?`, onConfirm: () => supprimerEvaluation.mutate(e.id) })}>
                        <Trash2 size={11} />
                      </ActionIcon>
                    )}
                  </Group>
                }>
                  {e.actions_menees && <Text size="xs">{voc("Actions :")} {e.actions_menees}</Text>}
                  {e.commentaire && <Text size="xs" c="dimmed">{e.commentaire}</Text>}
                </Timeline.Item>
              ))}
            </Timeline>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
}

/** Risques internes et externes du projet : registre coté, matrice, suivi par réévaluations. */
export function RisquesTab({ projetId, codeProjet, modifiable }: { projetId: number; codeProjet: string; modifiable: boolean }) {
  const { data: risques = [], isLoading } = useRisques(projetId);
  const [edition, setEdition] = useState<Partial<Risque> | null>(null);
  const [reevaluation, setReevaluation] = useState<Risque | null>(null);
  const [filtre, setFiltre] = useState<[number, number] | null>(null);
  const [voirFermes, setVoirFermes] = useState(false);

  const visibles = useMemo(
    () =>
      risques
        .filter((r) => (filtre ? r.probabilite === filtre[0] && r.impact === filtre[1] && ouvert(r) : voirFermes || ouvert(r)))
        .sort((a, b) => Number(ouvert(b)) - Number(ouvert(a)) || b.criticite - a.criticite),
    [risques, filtre, voirFermes],
  );
  if (isLoading) return <Text c="dimmed">{voc("Chargement…")}</Text>;
  const ouverts = risques.filter(ouvert);
  const fermes = risques.length - ouverts.length;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          {(Object.keys(NIVEAUX_RISQUE) as NiveauRisque[]).map((n) => (
            <Badge key={n} size="lg" variant="light" color={NIVEAUX_RISQUE[n].couleur}>
              {ouverts.filter((r) => r.niveau === n).length} {NIVEAUX_RISQUE[n].label.toLowerCase()}
            </Badge>
          ))}
          <Text size="sm" c="dimmed">{voc("risque(s) ouvert(s)")}</Text>
        </Group>
        <Group gap="xs">
          <Menu position="bottom-end">
            <Menu.Target>
              <Button variant="light" leftSection={<Download size={16} />}>{voc("Exporter")}</Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={() => telecharger(`/rapports/risques/${projetId}/?fichier=pdf`, `risques_${codeProjet}.pdf`)}>{voc("PDF")}</Menu.Item>
              <Menu.Item onClick={() => telecharger(`/rapports/risques/${projetId}/?fichier=docx`, `risques_${codeProjet}.docx`)}>{voc("Word")}</Menu.Item>
            </Menu.Dropdown>
          </Menu>
          {modifiable && <Button leftSection={<Plus size={16} />} onClick={() => setEdition({})}>{voc("Nouveau risque")}</Button>}
        </Group>
      </Group>

      <Card withBorder padding="md" radius="md" maw={420}>
        <Text size="sm" fw={600} mb="xs">{voc("Matrice des risques ouverts")}</Text>
        <Matrice risques={risques} filtre={filtre} onFiltre={setFiltre} />
        {filtre && (
          <Button size="compact-xs" variant="subtle" mt="xs" onClick={() => setFiltre(null)}>{voc("Afficher tous les risques")}</Button>
        )}
      </Card>

      {risques.length === 0 ? (
        <Card withBorder padding="lg" radius="md">
          <Text c="dimmed" ta="center">
            {voc("Aucun risque identifié. Ajoutez les risques internes (organisation, finances…) et externes (sécurité, climat, prix…) qui pourraient compromettre le projet.")}
          </Text>
        </Card>
      ) : (
        <Table.ScrollContainer minWidth={1350}>
          <Table withTableBorder withColumnBorders verticalSpacing="sm" horizontalSpacing="xs" highlightOnHover>
            <Table.Thead>
              <Table.Tr style={{ background: "var(--mantine-color-teal-9)" }}>
                {[
                  [voc("Code"), 70], [voc("Risque"), 240], [voc("Criticité"), 110], [voc("Statut"), 100], [voc("Nature"), 110],
                  [voc("Atténuation"), 200], [voc("Si survenu"), 200], [voc("Élément concerné"), 170], [voc("Responsable"), 130],
                  [voc("Prochaine revue"), 100], ["", 130],
                ].map(([t, w], i) => (
                  <Table.Th key={i} w={w} c="white" fz="xs" tt="uppercase">{t}</Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visibles.map((r) => (
                <LigneRisque key={r.id} risque={r} modifiable={modifiable} onModifier={() => setEdition(r)} onReevaluer={() => setReevaluation(r)} />
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {!filtre && fermes > 0 && (
        <Button variant="subtle" size="xs" leftSection={voirFermes ? <ChevronUp size={14} /> : <ChevronDown size={14} />} onClick={() => setVoirFermes((x) => !x)} style={{ alignSelf: "flex-start" }}>
          {voirFermes ? voc("Masquer") : voc("Afficher")} {voc("les risques maîtrisés ou clos (")}{fermes})
        </Button>
      )}

      {edition && <RisqueForm projetId={projetId} risque={edition} onClose={() => setEdition(null)} />}
      {reevaluation && <ReevaluationModal risque={reevaluation} onClose={() => setReevaluation(null)} />}
    </Stack>
  );
}
