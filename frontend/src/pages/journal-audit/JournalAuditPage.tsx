import { useState } from "react";
import { Download, ScrollText } from "lucide-react";
import { Badge, Button, Card, Group, Pagination, Select, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  type ActionAudit,
  type EvenementAudit,
  type FiltresAudit,
  ACTIONS_AUDIT,
  exporterJournalAudit,
  libelleActionAudit,
  useJournalAudit,
} from "../../api/journalAudit";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const PAR_PAGE = 25;
const COULEUR: Partial<Record<ActionAudit, string>> = {
  CONNEXION_ECHOUEE: "red", CONSULTATION_SENSIBLE: "grape", HABILITATION: "grape", PERMISSION: "orange",
  CONFIGURATION: "blue", EXPORT: "cyan", TELECHARGEMENT: "cyan", DROITS_PERSONNES: "teal",
};

const libelleOperation = (o: string): string =>
  ({
    creation: voc("création"),
    modification: voc("modification"),
    suppression: voc("suppression"),
    activation: voc("activation"),
    desactivation: voc("désactivation"),
    application: voc("application d'un modèle"),
    import: voc("import"),
    demande: voc("demande"),
    demande_premiere: voc("première demande (code par courriel)"),
    validation: voc("validation"),
    refus: voc("refus"),
    confirmation_courriel: voc("confirmation par courriel"),
    retrait: voc("retrait"),
    entree_en_vigueur: voc("entrée en vigueur"),
    reprise_existant: voc("reprise de l'existant"),
    habilitation_d_office: voc("habilitation d'office"),
    enregistrement: voc("enregistrement"),
    traitement: voc("traitement"),
  })[o] ?? o;

/** Détails lisibles, sans jargon : opération, champs modifiés, type d'action sur un dossier… */
function Details({ e }: { e: EvenementAudit }) {
  const d = e.details;
  const morceaux: string[] = [];
  if (d.operation) morceaux.push(libelleOperation(String(d.operation)));
  if (Array.isArray(d.champs)) morceaux.push(voc`champs : ${(d.champs as string[]).join(", ")}`);
  if (d.type && e.action !== "DROITS_PERSONNES") morceaux.push(String(d.type));
  if (d.identifiant && e.action === "CONNEXION_ECHOUEE") morceaux.push(voc`identifiant tenté : ${String(d.identifiant)}`);
  if (d.sensible) morceaux.push(voc("confidentiel"));
  if (d.nombre !== undefined) morceaux.push(voc`${Number(d.nombre)} ligne(s)`);
  for (const champ of ["role", "niveau_acces", "is_active", "acces_modules"]) {
    if (Array.isArray(d[champ])) {
      const [de, a] = d[champ] as unknown[];
      morceaux.push(`${champ} : ${JSON.stringify(de)} → ${JSON.stringify(a)}`);
    }
  }
  return <Text size="xs" c="dimmed">{morceaux.join(" · ") || "—"}</Text>;
}

/**
 * Journal d'audit (Administrateur) : connexions, consultations de dossiers confidentiels, actions sur
 * les dossiers, exports, configuration, droits et habilitations. En ajout uniquement : rien ne s'y
 * modifie ni ne s'y supprime.
 */
export function JournalAuditPage() {
  const [filtres, setFiltres] = useState<FiltresAudit>({ page: 1 });
  const { data, isFetching } = useJournalAudit(filtres);
  const [exportEnCours, setExportEnCours] = useState(false);
  const changer = (f: Partial<FiltresAudit>) => setFiltres((a) => ({ ...a, ...f, page: f.page ?? 1 }));
  const pages = Math.ceil((data?.count ?? 0) / PAR_PAGE);

  const exporter = async () => {
    setExportEnCours(true);
    try {
      const { page: _page, ...reste } = filtres;
      await exporterJournalAudit(reste);
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("L'export n'a pas abouti.")) });
    } finally {
      setExportEnCours(false);
    }
  };

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <Stack gap={2}>
          <Group gap="xs"><ScrollText size={22} /><Title order={2}>{voc("Journal d'audit")}</Title></Group>
          <Text size="sm" c="dimmed" maw={760}>
            {voc("Connexions, consultations de dossiers confidentiels, actions sur les dossiers, téléchargements, exports, modifications de la configuration, des droits et des habilitations. Le journal est en ajout uniquement : personne ne peut le modifier ni le supprimer. Il ne contient jamais le contenu des plaintes.")}
          </Text>
        </Stack>
        <Button leftSection={<Download size={14} />} variant="light" loading={exportEnCours} onClick={exporter}>{voc("Exporter (Excel)")}</Button>
      </Group>
      <Card withBorder>
        <Group align="flex-end" gap="sm">
          <Select label={voc("Action")} placeholder={voc("Toutes")} clearable w={260} value={filtres.action ?? null}
            data={ACTIONS_AUDIT.map((a) => ({ value: a, label: libelleActionAudit(a) }))} onChange={(v) => changer({ action: v })} />
          <TextInput label={voc("Personne")} w={180} value={filtres.utilisateur ?? ""} onChange={(e) => changer({ utilisateur: e.currentTarget.value })} />
          <TextInput label={voc("Objet")} placeholder="MGP-2026-…" w={180} value={filtres.objet ?? ""} onChange={(e) => changer({ objet: e.currentTarget.value })} />
          <DateInput label={voc("Du")} valueFormat="DD/MM/YYYY" clearable w={140} value={filtres.du ?? null} onChange={(v) => changer({ du: v })} />
          <DateInput label={voc("Au")} valueFormat="DD/MM/YYYY" clearable w={140} value={filtres.au ?? null} onChange={(v) => changer({ au: v })} />
        </Group>
      </Card>
      <Text size="sm" c="dimmed">{voc`${data?.count ?? 0} événement(s)`}</Text>
      <Table withTableBorder striped verticalSpacing={6} style={{ opacity: isFetching ? 0.6 : 1 }}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={150}>{voc("Date")}</Table.Th>
            <Table.Th>{voc("Personne")}</Table.Th>
            <Table.Th>{voc("Action")}</Table.Th>
            <Table.Th>{voc("Objet")}</Table.Th>
            <Table.Th>{voc("Détails")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(data?.results ?? []).map((e) => (
            <Table.Tr key={e.id}>
              <Table.Td><Text size="xs">{new Date(e.date).toLocaleString(locale(), { dateStyle: "short", timeStyle: "medium" })}</Text></Table.Td>
              <Table.Td><Text size="sm">{e.utilisateur || voc("Système")}</Text></Table.Td>
              <Table.Td><Badge variant="light" tt="none" color={COULEUR[e.action] ?? "gray"}>{libelleActionAudit(e.action)}</Badge></Table.Td>
              <Table.Td><Text size="sm" dir="auto">{e.objet || "—"}</Text></Table.Td>
              <Table.Td><Details e={e} /></Table.Td>
            </Table.Tr>
          ))}
          {data && data.results.length === 0 && (
            <Table.Tr><Table.Td colSpan={5}><Text size="sm" c="dimmed">{voc("Aucun événement pour ces critères.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
      {pages > 1 && <Pagination value={filtres.page} onChange={(page) => changer({ page })} total={pages} size="sm" />}
    </Stack>
  );
}
