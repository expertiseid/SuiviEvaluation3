import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, FileDown, FileSpreadsheet, Info, Lock, Plus, RotateCcw, Settings2, Trash2 } from "lucide-react";
import { ActionIcon, Alert, Badge, Button, Group, Loader, Modal, Select, Stack, Table, Tabs, Text } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  type ElementConfiguration,
  type FiltresTableau,
  exporterTableau,
  useCatalogueTableau,
  useConfigurationTableau,
  useEnregistrerConfigurationTableau,
  useRevenirVueOrganisation,
  useTableauPlaintes,
} from "../../api/plaintes";
import { useProjets } from "../../api/projects";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { ElementsTableau } from "./ElementsTableau";
import { EnTetePlaintes } from "./EnTetePlaintes";

/** Composer une vue : ajouter, retirer, ordonner ; pour soi, ou pour toute l'organisation (Administrateur). */
function PersonnaliserVue({ vue, onClose }: { vue: string; onClose: () => void }) {
  const { data: catalogue } = useCatalogueTableau();
  const { data: configuration } = useConfigurationTableau(vue);
  const enregistrer = useEnregistrerConfigurationTableau();
  const revenir = useRevenirVueOrganisation();
  const [elements, setElements] = useState<ElementConfiguration[]>([]);
  const [ajout, setAjout] = useState<string | null>(null);
  useEffect(() => setElements(configuration?.elements ?? []), [configuration]);
  const libelle = (code: string) => catalogue?.elements.find((e) => e.code === code)?.libelle ?? code;
  const disponibles = (catalogue?.elements ?? []).filter(
    (e) => e.confidentiel === (vue === "confidentielle") && !elements.some((x) => x.code === e.code),
  );
  const deplacer = (i: number, sens: number) =>
    setElements((l) => { const c = [...l]; [c[i], c[i + sens]] = [c[i + sens], c[i]]; return c; });
  const sauver = async (portee: "utilisateur" | "organisation") => {
    try {
      await enregistrer.mutateAsync({ vue, elements, portee });
      notifications.show({ message: portee === "organisation" ? voc("Vue de l'organisation enregistrée") : voc("Votre vue est enregistrée"), color: "teal" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc("Personnaliser la vue")} size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          {voc("Votre vue personnelle ne change rien pour les autres. Les règles de sécurité restent fixes : masquage des petits effectifs confidentiels, aucun détail sur les dossiers confidentiels.")}
        </Text>
        <Table withTableBorder verticalSpacing={4}>
          <Table.Tbody>
            {elements.map((e, i) => (
              <Table.Tr key={e.code}>
                <Table.Td>{libelle(e.code)}</Table.Td>
                <Table.Td w={110}>
                  <Group gap={2} wrap="nowrap">
                    <ActionIcon size="sm" variant="subtle" disabled={i === 0} onClick={() => deplacer(i, -1)} aria-label={voc("Monter")}><ArrowUp size={13} /></ActionIcon>
                    <ActionIcon size="sm" variant="subtle" disabled={i === elements.length - 1} onClick={() => deplacer(i, 1)} aria-label={voc("Descendre")}><ArrowDown size={13} /></ActionIcon>
                    <ActionIcon size="sm" variant="subtle" color="red" onClick={() => setElements((l) => l.filter((x) => x.code !== e.code))} aria-label={voc("Retirer")}><Trash2 size={13} /></ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group align="flex-end" gap="xs">
          <Select label={voc("Ajouter un élément")} data={disponibles.map((e) => ({ value: e.code, label: e.libelle }))} value={ajout}
            onChange={setAjout} searchable style={{ flex: 1 }} />
          <Button variant="light" leftSection={<Plus size={14} />} disabled={!ajout}
            onClick={() => { if (ajout) { setElements((l) => [...l, { code: ajout, graphique: "barres" }]); setAjout(null); } }}>
            {voc("Ajouter")}
          </Button>
        </Group>
        <Group justify="space-between">
          {configuration?.source === "utilisateur" ? (
            <Button variant="subtle" leftSection={<RotateCcw size={14} />} loading={revenir.isPending}
              onClick={async () => { await revenir.mutateAsync(vue); onClose(); }}>
              {voc("Revenir à la vue de l'organisation")}
            </Button>
          ) : <span />}
          <Group gap="xs">
            {catalogue?.peut_regler_organisation && (
              <Button variant="default" onClick={() => sauver("organisation")} loading={enregistrer.isPending}>{voc("Enregistrer pour l'organisation")}</Button>
            )}
            <Button onClick={() => sauver("utilisateur")} loading={enregistrer.isPending}>{voc("Enregistrer pour moi")}</Button>
          </Group>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Tableaux de bord du mécanisme : quatre vues prêtes, personnalisables, filtres communs, clic vers les dossiers, exports. */
export function TableauPlaintesPage() {
  const { data: catalogue } = useCatalogueTableau();
  const { data: projets = [] } = useProjets();
  const [vue, setVue] = useState("operationnelle");
  const [filtres, setFiltres] = useState<FiltresTableau>({});
  const [personnaliser, setPersonnaliser] = useState(false);
  const { data: tableau, isLoading } = useTableauPlaintes(vue, filtres);
  const enregistrer = useEnregistrerConfigurationTableau();
  const exporter = async (format: "excel" | "pdf") => {
    try {
      await exporterTableau(format, vue, filtres);
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Export impossible")), color: "red" });
    }
  };
  // Changer le type d'un graphique enregistre la copie personnelle de la vue.
  const changerType = (code: string, graphique: string) => {
    if (!tableau) return;
    const elements = tableau.elements.map((e) => ({ code: e.code, graphique: e.code === code ? graphique : (e.graphique ?? "barres") }));
    enregistrer.mutate({ vue, elements, portee: "utilisateur" });
  };

  return (
    <Stack>
      <EnTetePlaintes
        actions={
          <>
            <Button variant="default" leftSection={<Settings2 size={14} />} onClick={() => setPersonnaliser(true)}>{voc("Personnaliser")}</Button>
            <Button variant="light" leftSection={<FileSpreadsheet size={14} />} onClick={() => exporter("excel")}>{voc("Excel")}</Button>
            <Button variant="light" leftSection={<FileDown size={14} />} onClick={() => exporter("pdf")}>{voc("PDF")}</Button>
          </>
        }
      />
      <Tabs value={vue} onChange={(v) => v && setVue(v)}>
        <Tabs.List>
          {(catalogue?.vues ?? []).map((v) => (
            <Tabs.Tab key={v.code} value={v.code} leftSection={v.code === "confidentielle" ? <Lock size={13} /> : undefined}>{v.libelle}</Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      <Group gap="sm" align="flex-end">
        <DatePickerInput type="range" label={voc("Période")} valueFormat="DD/MM/YYYY" w={260} clearable
          placeholder={voc("12 derniers mois")}
          value={[filtres.du ?? null, filtres.au ?? null]} onChange={([du, au]) => setFiltres((f) => ({ ...f, du, au }))} />
        <Select label={voc("Projet")} placeholder={voc("Tous les projets")} w={260} clearable searchable
          data={projets.map((p) => ({ value: String(p.id), label: p.code ? `${p.code} — ${p.nom}` : p.nom }))}
          value={filtres.projet ?? null} onChange={(p) => setFiltres((f) => ({ ...f, projet: p }))} />
        {tableau && (
          <Badge variant="light" color="gray" tt="none" size="lg">
            {tableau.source === "utilisateur" ? voc("Ma vue") : tableau.source === "organisation" ? voc("Vue de l'organisation") : voc("Vue par défaut")}
          </Badge>
        )}
      </Group>
      {vue === "pilotage" && (
        <Alert color="blue" icon={<Info size={16} />} py={6}>
          {voc("Une hausse du nombre de plaintes peut traduire une meilleure accessibilité du mécanisme, pas une dégradation du projet.")}
        </Alert>
      )}
      {vue === "confidentielle" && (
        <Alert color="grape" icon={<Lock size={16} />} py={6}>
          {voc`Totaux seulement, sans aucun détail individuel ; tout effectif inférieur à ${tableau?.seuil_masquage ?? 5} est affiché « moins de ${tableau?.seuil_masquage ?? 5} ».`}
        </Alert>
      )}
      {isLoading || !tableau ? <Loader /> : <ElementsTableau elements={tableau.elements} onType={changerType} />}
      {personnaliser && <PersonnaliserVue vue={vue} onClose={() => setPersonnaliser(false)} />}
    </Stack>
  );
}
