import { useMemo, useState } from "react";
import { Download, FileText, Paperclip, Pencil, Plus, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  FileInput,
  Grid,
  Group,
  Menu,
  Modal,
  NumberInput,
  Progress,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  useCreerIndicateurStrategique,
  useEnregistrerAppreciation,
  useSaisirValeurStrategique,
  useSuiviCadre,
  useSuiviElement,
  useSupprimerAppreciation,
  useSupprimerPiece,
  useSupprimerValeurStrategique,
  type AppreciationStrategique,
  type EtatAppreciation,
  type IndicateurStrategique,
  type LigneSuiviCadre,
  type PieceJointe,
} from "../../api/suiviStrategique";
import { telecharger } from "../../api/suivi";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

import { locale } from "../../utils/i18n";
const ETATS: Record<EtatAppreciation, { label: string; couleur: string }> = {
  BON: { label: voc("Bonne progression"), couleur: "teal" },
  MOYEN: { label: voc("Progression moyenne"), couleur: "yellow" },
  INSUFFISANT: { label: voc("Progression insuffisante"), couleur: "red" },
};
const FREQUENCES = [
  { value: "MENSUELLE", label: voc("Mensuelle") },
  { value: "TRIMESTRIELLE", label: voc("Trimestrielle") },
  { value: "SEMESTRIELLE", label: voc("Semestrielle") },
  { value: "ANNUELLE", label: voc("Annuelle") },
];
const nombre = (v: number | null | undefined) => (v === null || v === undefined ? "—" : Number(v).toLocaleString(locale(), { maximumFractionDigits: 2 }));
const dateFr = (d: string) => new Date(d).toLocaleDateString(locale());
const pct = (v: number | null) => (v === null ? "—" : `${v.toLocaleString(locale())} %`);

function BarreTaux({ taux, couleur = "teal" }: { taux: number | null; couleur?: string }) {
  if (taux === null) return <Text size="xs" c="dimmed">—</Text>;
  return (
    <Group gap={6} wrap="nowrap">
      <Progress value={Math.min(taux, 100)} color={couleur} size="sm" style={{ flex: 1 }} />
      <Text size="xs" w={48} ta="right">{pct(taux)}</Text>
    </Group>
  );
}

function Pieces({ pieces, modifiable }: { pieces: PieceJointe[]; modifiable: boolean }) {
  const supprimer = useSupprimerPiece();
  if (pieces.length === 0) return null;
  return (
    <Group gap={8} mt={4}>
      {pieces.map((p) => (
        <Group key={p.id} gap={2} wrap="nowrap">
          <Paperclip size={12} />
          <Anchor component="button" type="button" size="xs" onClick={() => telecharger(p.telechargement, p.nom)}>{p.nom}</Anchor>
          {modifiable && (
            <ActionIcon size="xs" variant="subtle" color="red" aria-label={voc("Retirer la pièce")}
              onClick={() => confirmerSuppression({ message: voc`Retirer « ${p.nom} » ?`, onConfirm: () => supprimer.mutate(p.id) })}>
              <Trash2 size={10} />
            </ActionIcon>
          )}
        </Group>
      ))}
    </Group>
  );
}

function AppreciationModal({ elementId, appreciation, onClose }: { elementId: number; appreciation: Partial<AppreciationStrategique>; onClose: () => void }) {
  const enregistrer = useEnregistrerAppreciation();
  const [a, setA] = useState<Partial<AppreciationStrategique>>({ etat: "BON", ...appreciation });
  const [fichiers, setFichiers] = useState<File[]>([]);
  const set = (champs: Partial<AppreciationStrategique>) => setA((x) => ({ ...x, ...champs }));

  async function valider() {
    if (!a.periode_debut || !a.periode_fin) {
      notifications.show({ message: voc("Indiquez la période."), color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync({ ...a, element: elementId, pieces: undefined, fichiers });
      notifications.show({ message: voc("Appréciation enregistrée"), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={a.id ? voc("Modifier l'appréciation") : voc("Nouvelle appréciation")} size="lg">
      <Stack gap="sm">
        <TextInput label={voc("Période")} placeholder={voc("Ex : Année 2026, 1er semestre 2027")} value={a.libelle_periode ?? ""} onChange={(e) => set({ libelle_periode: e.currentTarget.value })} data-autofocus />
        <SimpleGrid cols={{ base: 1, xs: 2 }}>
          <DateInput label={voc("Du")} required valueFormat="DD/MM/YYYY" value={a.periode_debut ?? null} onChange={(v) => set({ periode_debut: v ?? undefined })} />
          <DateInput label={voc("Au")} required valueFormat="DD/MM/YYYY" value={a.periode_fin ?? null} onChange={(v) => set({ periode_fin: v ?? undefined })} minDate={a.periode_debut} />
        </SimpleGrid>
        <div>
          <Text size="sm" fw={500} mb={4}>{voc("Appréciation de l'avancement")}</Text>
          <SegmentedControl
            fullWidth
            value={a.etat}
            onChange={(v) => set({ etat: v as EtatAppreciation })}
            data={(Object.keys(ETATS) as EtatAppreciation[]).map((e) => ({ value: e, label: ETATS[e].label }))}
          />
        </div>
        <Textarea label={voc("Analyse")} description={voc("Ce qui a été réalisé, au-delà des projets suivis dans la plateforme.")} autosize minRows={3} value={a.commentaire ?? ""} onChange={(e) => set({ commentaire: e.currentTarget.value })} />
        <Textarea label={voc("Difficultés")} autosize minRows={2} value={a.difficultes ?? ""} onChange={(e) => set({ difficultes: e.currentTarget.value })} />
        <Textarea label={voc("Recommandations")} autosize minRows={2} value={a.recommandations ?? ""} onChange={(e) => set({ recommandations: e.currentTarget.value })} />
        <FileInput label={voc("Pièces justificatives")} placeholder={voc("Rapports, études, comptes rendus…")} multiple clearable value={fichiers} onChange={setFichiers} leftSection={<Paperclip size={14} />} />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function IndicateurModal({ elementId, onClose }: { elementId: number; onClose: () => void }) {
  const creer = useCreerIndicateurStrategique();
  const [libelle, setLibelle] = useState("");
  const [unite, setUnite] = useState("");
  const [reference, setReference] = useState<number | string>("");
  const [cible, setCible] = useState<number | string>("");
  const [frequence, setFrequence] = useState<string | null>("ANNUELLE");

  async function valider() {
    if (!libelle.trim() || !unite.trim() || cible === "") {
      notifications.show({ message: voc("Libellé, unité et cible sont requis."), color: "orange" });
      return;
    }
    try {
      await creer.mutateAsync({
        libelle: libelle.trim(), unite: unite.trim(), valeur_reference: reference === "" ? null : Number(reference),
        valeur_cible: Number(cible), frequence_collecte: frequence ?? "ANNUELLE", elements_strategiques: [elementId],
      });
      notifications.show({ message: voc("Indicateur ajouté"), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc("Nouvel indicateur de l'élément")}>
      <Stack gap="sm">
        <Text size="xs" c="dimmed">{voc("Indicateur propre au document stratégique (ex. donnée nationale) : ses valeurs se saisissent ici, sans passer par un projet.")}</Text>
        <Textarea label={voc("Indicateur")} required autosize minRows={2} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} data-autofocus />
        <SimpleGrid cols={2}>
          <TextInput label={voc("Unité")} required value={unite} onChange={(e) => setUnite(e.currentTarget.value)} placeholder={voc("%, ménages…")} />
          <Select label={voc("Fréquence")} data={FREQUENCES} value={frequence} onChange={setFrequence} allowDeselect={false} />
          <NumberInput label={voc("Valeur de référence")} value={reference} onChange={setReference} decimalSeparator="," />
          <NumberInput label={voc("Cible")} required value={cible} onChange={setCible} decimalSeparator="," />
        </SimpleGrid>
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={creer.isPending}>{voc("Ajouter")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function ValeurModal({ indicateur, onClose }: { indicateur: IndicateurStrategique; onClose: () => void }) {
  const saisir = useSaisirValeurStrategique();
  const [debut, setDebut] = useState<string | null>(null);
  const [fin, setFin] = useState<string | null>(null);
  const [valeur, setValeur] = useState<number | string>("");
  const [commentaire, setCommentaire] = useState("");
  const [fichiers, setFichiers] = useState<File[]>([]);

  async function valider() {
    if (!debut || !fin || valeur === "") {
      notifications.show({ message: voc("Période et valeur sont requises."), color: "orange" });
      return;
    }
    try {
      await saisir.mutateAsync({ indicateur: indicateur.id, periode_debut: debut, periode_fin: fin, valeur_realisee: Number(valeur), commentaire: commentaire.trim(), fichiers });
      notifications.show({ message: voc("Valeur enregistrée"), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc("Saisir une valeur")} size="lg">
      <Stack gap="sm">
        <Text size="sm" fw={500}>{indicateur.libelle}</Text>
        <Text size="xs" c="dimmed">{voc("Ce qui a été réalisé pendant la période (les valeurs des périodes s'additionnent). Cible :")} {nombre(indicateur.valeur_cible)} {indicateur.unite}.</Text>
        <SimpleGrid cols={{ base: 1, xs: 3 }}>
          <DateInput label={voc("Du")} required valueFormat="DD/MM/YYYY" value={debut} onChange={setDebut} />
          <DateInput label={voc("Au")} required valueFormat="DD/MM/YYYY" value={fin} onChange={setFin} minDate={debut ?? undefined} />
          <NumberInput label={voc`Valeur (${indicateur.unite})`} required value={valeur} onChange={setValeur} decimalSeparator="," />
        </SimpleGrid>
        <Textarea label={voc("Commentaire / source")} autosize minRows={2} value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />
        <FileInput label={voc("Pièces justificatives")} multiple clearable value={fichiers} onChange={setFichiers} leftSection={<Paperclip size={14} />} />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={saisir.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function PanneauElement({ elementId, modifiable }: { elementId: number; modifiable: boolean }) {
  const { data, isLoading } = useSuiviElement(elementId);
  const supprimerAppreciation = useSupprimerAppreciation();
  const supprimerValeur = useSupprimerValeurStrategique();
  const [appreciation, setAppreciation] = useState<Partial<AppreciationStrategique> | null>(null);
  const [nouvelIndicateur, setNouvelIndicateur] = useState(false);
  const [valeurPour, setValeurPour] = useState<IndicateurStrategique | null>(null);
  if (isLoading || !data) return <Text c="dimmed">{voc("Chargement…")}</Text>;
  const { calcule } = data;

  return (
    <Stack gap="md">
      <div>
        <Badge variant="light" size="sm">{data.element.niveau}</Badge>
        <Text fw={700} size="lg">{data.element.code && <Text span c="dimmed" mr={6}>{data.element.code}</Text>}{data.element.nom}</Text>
      </div>

      <Card withBorder padding="md" radius="md">
        <Text size="sm" fw={600} mb={4}>{voc("Avancement calculé à partir des projets")}</Text>
        {calcule.projets.length === 0 ? (
          <Text size="sm" c="dimmed">{voc("Aucun projet ne contribue encore à cet élément.")}</Text>
        ) : (
          <Stack gap={6}>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <div><Text size="xs" c="dimmed">{voc("Exécution physique (")}{calcule.nombre_activites} {voc("élément(s) de planification)")}</Text><BarreTaux taux={calcule.taux_physique} couleur="blue" /></div>
              <div><Text size="xs" c="dimmed">{voc("Exécution financière :")} {nombre(calcule.budget_realise)} / {nombre(calcule.budget_alloue)} {voc("FCFA")}</Text><BarreTaux taux={calcule.taux_financier} /></div>
            </SimpleGrid>
            <Group gap={6}>
              {calcule.projets.map((p) => (
                <Tooltip key={p.id} label={`${p.nom} — ${pct(p.taux_physique)}`}><Badge variant="outline">{p.code}</Badge></Tooltip>
              ))}
            </Group>
          </Stack>
        )}
      </Card>

      <Card withBorder padding="md" radius="md">
        <Group justify="space-between" mb="xs">
          <Text size="sm" fw={600}>{voc("Indicateurs")}</Text>
          {modifiable && <Button size="compact-xs" variant="light" leftSection={<Plus size={12} />} onClick={() => setNouvelIndicateur(true)}>{voc("Ajouter un indicateur")}</Button>}
        </Group>
        {data.indicateurs.length === 0 && <Text size="sm" c="dimmed">{voc("Aucun indicateur rattaché à cet élément.")}</Text>}
        <Stack gap="sm">
          {data.indicateurs.map((i) => (
            <Box key={i.id} p="xs" style={{ border: "1px solid var(--mantine-color-gray-2)", borderRadius: 6 }}>
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <div>
                  <Text size="sm" fw={500}>{i.libelle}</Text>
                  <Text size="xs" c="dimmed">{voc("Réf.")} {nombre(i.valeur_reference)} {voc("· Cible")} {nombre(i.valeur_cible)} {i.unite} · <b>{voc("Réalisé")} {nombre(i.realise)}</b></Text>
                </div>
                <Group gap={4} wrap="nowrap">
                  <Badge size="xs" variant="light" color={i.saisie_directe ? "grape" : "blue"}>{i.origine}</Badge>
                  {modifiable && i.saisie_directe && (
                    <Button size="compact-xs" variant="light" onClick={() => setValeurPour(i)}>{voc("Saisir")}</Button>
                  )}
                </Group>
              </Group>
              <BarreTaux taux={i.taux} />
              {i.valeurs.map((v) => (
                <Group key={v.id} gap={6} mt={4} wrap="nowrap" align="flex-start">
                  <Text size="xs" c="dimmed" w={170} style={{ flexShrink: 0 }}>{dateFr(v.periode_debut)} → {dateFr(v.periode_fin)}</Text>
                  <div style={{ flex: 1 }}>
                    <Text size="xs"><b>{nombre(v.valeur_realisee)} {i.unite}</b>{v.etat_approbation !== "APPROUVEE" && <Badge size="xs" ml={6} color="orange" variant="light">{v.etat_approbation === "EN_ATTENTE" ? voc("En attente d'approbation") : voc("Rejetée")}</Badge>}{v.commentaire && ` — ${v.commentaire}`}</Text>
                    <Pieces pieces={v.pieces} modifiable={modifiable} />
                  </div>
                  {modifiable && (
                    <ActionIcon size="xs" variant="subtle" color="red" aria-label={voc("Supprimer la valeur")}
                      onClick={() => confirmerSuppression({ message: voc("Supprimer cette valeur ?"), onConfirm: () => supprimerValeur.mutate(v.id) })}>
                      <Trash2 size={11} />
                    </ActionIcon>
                  )}
                </Group>
              ))}
            </Box>
          ))}
        </Stack>
      </Card>

      <Card withBorder padding="md" radius="md">
        <Group justify="space-between" mb="xs">
          <Text size="sm" fw={600}>{voc("Appréciations par période")}</Text>
          {modifiable && <Button size="compact-xs" variant="light" leftSection={<Plus size={12} />} onClick={() => setAppreciation({})}>{voc("Nouvelle appréciation")}</Button>}
        </Group>
        {data.appreciations.length === 0 && <Text size="sm" c="dimmed">{voc("Aucune appréciation pour l'instant.")}</Text>}
        <Stack gap="sm">
          {data.appreciations.map((a) => (
            <Box key={a.id} p="xs" style={{ borderLeft: `3px solid var(--mantine-color-${ETATS[a.etat].couleur}-6)`, background: "var(--mantine-color-gray-0)", borderRadius: 4 }}>
              <Group justify="space-between" wrap="nowrap">
                <Group gap={6}>
                  <Text size="sm" fw={600}>{a.libelle_periode || `${dateFr(a.periode_debut)} → ${dateFr(a.periode_fin)}`}</Text>
                  <Badge size="sm" variant="light" color={ETATS[a.etat].couleur}>{ETATS[a.etat].label}</Badge>
                  <Text size="xs" c="dimmed">{a.saisi_par_nom}</Text>
                </Group>
                {modifiable && (
                  <Group gap={2} wrap="nowrap">
                    <ActionIcon size="sm" variant="subtle" aria-label={voc("Modifier")} onClick={() => setAppreciation(a)}><Pencil size={13} /></ActionIcon>
                    <ActionIcon size="sm" variant="subtle" color="red" aria-label={voc("Supprimer")}
                      onClick={() => confirmerSuppression({ message: voc("Supprimer cette appréciation et ses pièces ?"), onConfirm: () => supprimerAppreciation.mutate(a.id) })}>
                      <Trash2 size={13} />
                    </ActionIcon>
                  </Group>
                )}
              </Group>
              {a.commentaire && <Text size="sm" mt={4} style={{ whiteSpace: "pre-wrap" }}>{a.commentaire}</Text>}
              {a.difficultes && <Text size="sm" mt={4}><b>{voc("Difficultés :")}</b> {a.difficultes}</Text>}
              {a.recommandations && <Text size="sm" mt={4}><b>{voc("Recommandations :")}</b> {a.recommandations}</Text>}
              <Pieces pieces={a.pieces} modifiable={modifiable} />
            </Box>
          ))}
        </Stack>
      </Card>

      {appreciation && <AppreciationModal elementId={elementId} appreciation={appreciation} onClose={() => setAppreciation(null)} />}
      {nouvelIndicateur && <IndicateurModal elementId={elementId} onClose={() => setNouvelIndicateur(false)} />}
      {valeurPour && <ValeurModal indicateur={valeurPour} onClose={() => setValeurPour(null)} />}
    </Stack>
  );
}

/**
 * Suivi propre au document stratégique : à côté de l'avancement calculé depuis les projets,
 * les valeurs d'indicateurs saisies directement, les appréciations par période et leurs pièces.
 */
export function SuiviStrategiqueTab({ cadreId, modifiable }: { cadreId: number; modifiable: boolean }) {
  const { data: elements = [], isLoading } = useSuiviCadre(cadreId);
  const [choisi, setChoisi] = useState<number | null>(null);

  // Ordre de l'arbre : chaque élément suivi de ceux en dessous.
  const ordonnes = useMemo(() => {
    const enfants = new Map<number | null, LigneSuiviCadre[]>();
    elements.forEach((e) => enfants.set(e.element_parent, [...(enfants.get(e.element_parent) ?? []), e]));
    const ids = new Set(elements.map((e) => e.id));
    const resultat: { ligne: LigneSuiviCadre; profondeur: number }[] = [];
    const visiter = (e: LigneSuiviCadre, profondeur: number) => {
      resultat.push({ ligne: e, profondeur });
      (enfants.get(e.id) ?? []).forEach((enfant) => visiter(enfant, profondeur + 1));
    };
    elements.filter((e) => e.element_parent === null || !ids.has(e.element_parent)).forEach((e) => visiter(e, 0));
    return resultat;
  }, [elements]);

  if (isLoading) return <Text c="dimmed">{voc("Chargement…")}</Text>;
  const selection = choisi ?? ordonnes[0]?.ligne.id ?? null;

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed" maw={760}>
          {voc("En plus de l'avancement calculé depuis les projets, renseignez pour chaque élément ses indicateurs propres, une appréciation par période et les pièces qui la justifient.")}
        </Text>
        <Menu position="bottom-end">
          <Menu.Target>
            <Button variant="light" leftSection={<Download size={16} />}>{voc("Rapport de suivi")}</Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item leftSection={<FileText size={14} />} onClick={() => telecharger(`/rapports/suivi-strategique/${cadreId}/?fichier=pdf`, `suivi_strategique_${cadreId}.pdf`)}>{voc("PDF")}</Menu.Item>
            <Menu.Item leftSection={<FileText size={14} />} onClick={() => telecharger(`/rapports/suivi-strategique/${cadreId}/?fichier=docx`, `suivi_strategique_${cadreId}.docx`)}>{voc("Word")}</Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
      {ordonnes.length === 0 ? (
        <Text c="dimmed">{voc("Aucun élément dans ce document stratégique.")}</Text>
      ) : (
        <Grid gap="md">
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card withBorder padding={0} radius="md">
              <ScrollArea.Autosize mah={640}>
                {ordonnes.map(({ ligne, profondeur }) => {
                  const actif = ligne.id === selection;
                  const etat = ligne.derniere_appreciation ? ETATS[ligne.derniere_appreciation.etat] : null;
                  return (
                    <UnstyledButton
                      key={ligne.id}
                      onClick={() => setChoisi(ligne.id)}
                      w="100%"
                      p="xs"
                      pl={10 + profondeur * 14}
                      style={{ borderBottom: "1px solid var(--mantine-color-gray-2)", background: actif ? "var(--mantine-color-teal-0)" : undefined }}
                    >
                      <Group justify="space-between" wrap="nowrap" gap={6}>
                        <div style={{ minWidth: 0 }}>
                          <Text size="10px" c="dimmed" tt="uppercase" fw={600}>{ligne.niveau}</Text>
                          <Text size="sm" fw={actif ? 600 : 400} lineClamp={2}>{ligne.nom}</Text>
                        </div>
                        <Stack gap={2} align="flex-end" style={{ flexShrink: 0 }}>
                          {ligne.taux_physique !== null && <Text size="xs" c="dimmed">{pct(ligne.taux_physique)}</Text>}
                          {etat && <Tooltip label={`${etat.label} — ${ligne.derniere_appreciation!.libelle_periode || dateFr(ligne.derniere_appreciation!.periode_fin)}`}><Badge size="xs" variant="dot" color={etat.couleur}>{ligne.derniere_appreciation!.libelle_periode || voc("Appréciée")}</Badge></Tooltip>}
                        </Stack>
                      </Group>
                    </UnstyledButton>
                  );
                })}
              </ScrollArea.Autosize>
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 8 }}>
            {selection && <PanneauElement key={selection} elementId={selection} modifiable={modifiable} />}
          </Grid.Col>
        </Grid>
      )}
    </Stack>
  );
}
