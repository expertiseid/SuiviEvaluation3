import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { ActionIcon, Anchor, Badge, Button, Group, Modal, MultiSelect, Select, SimpleGrid, Stack, Table, Text, TextInput, Textarea, Title } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import {
  type ActionCorrective,
  type StatutActionCorrective,
  STATUTS_ACTION,
  dateLisible,
  libelleStatutAction,
  useActionsCorrectives,
  useEnregistrerActionCorrective,
  useNumerosDossiers,
  useSupprimerActionCorrective,
} from "../../api/plaintes";
import { useUtilisateurs } from "../../api/accounts";
import { useProjets } from "../../api/projects";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "./saisieRetour";

const COULEUR: Record<StatutActionCorrective, string> = { A_FAIRE: "blue", EN_COURS: "orange", REALISEE: "teal", ABANDONNEE: "gray" };

export function BadgeStatutAction({ statut }: { statut: StatutActionCorrective }) {
  return <Badge color={COULEUR[statut]} variant="light" tt="none">{libelleStatutAction(statut)}</Badge>;
}

/** Création ou modification d'une action corrective, reliée à un ou plusieurs dossiers. */
export function ActionCorrectiveModal({ action, dossierInitial, onClose }: {
  action?: ActionCorrective | null;
  dossierInitial?: number;
  onClose: () => void;
}) {
  const enregistrer = useEnregistrerActionCorrective();
  const { data: numeros = [] } = useNumerosDossiers();
  const { data: projets = [] } = useProjets();
  const { data: utilisateurs = [] } = useUtilisateurs();
  const [valeurs, setValeurs] = useState<Partial<ActionCorrective>>(action ?? { statut: "A_FAIRE" });
  // Seuls les dossiers visibles sont proposés ; le serveur conserve les liens vers les autres.
  const [dossiers, setDossiers] = useState<number[]>(
    action ? action.dossiers_lies.map((d) => d.id) : dossierInitial ? [dossierInitial] : [],
  );
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const changer = (v: Partial<ActionCorrective>) => setValeurs((a) => ({ ...a, ...v }));
  const sauver = async () => {
    setErreurs({});
    try {
      const { titre, description, projet, responsable, echeance, statut } = valeurs;
      await enregistrer.mutateAsync({ id: action?.id, titre, description, projet, responsable, echeance, statut, dossiers });
      notifications.show({ message: voc("Action corrective enregistrée"), color: "teal" });
      onClose();
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Modal opened onClose={onClose} title={action ? voc("Modifier l'action corrective") : voc("Nouvelle action corrective")} size="lg">
      <Stack>
        <TextInput label={voc("Action")} withAsterisk value={valeurs.titre ?? ""} onChange={(e) => { const titre = e.currentTarget.value; changer({ titre }); }} error={erreurs.titre} />
        <Textarea label={voc("Description")} autosize minRows={2} value={valeurs.description ?? ""} onChange={(e) => { const description = e.currentTarget.value; changer({ description }); }} />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select label={voc("Projet")} clearable searchable data={projets.map((p) => ({ value: String(p.id), label: p.code ? `${p.code} — ${p.nom}` : p.nom }))}
            value={valeurs.projet ? String(valeurs.projet) : null} onChange={(v) => changer({ projet: v ? Number(v) : null })} />
          <Select label={voc("Responsable")} clearable searchable
            data={utilisateurs.map((u) => ({ value: String(u.id), label: `${u.first_name} ${u.last_name}`.trim() || u.username }))}
            value={valeurs.responsable ? String(valeurs.responsable) : null} onChange={(v) => changer({ responsable: v ? Number(v) : null })} />
          <DateInput label={voc("Échéance")} valueFormat="DD/MM/YYYY" clearable value={valeurs.echeance ?? null} onChange={(v) => changer({ echeance: v })} />
          <Select label={voc("Statut")} allowDeselect={false} data={STATUTS_ACTION.map((s) => ({ value: s, label: libelleStatutAction(s) }))}
            value={valeurs.statut ?? "A_FAIRE"} onChange={(v) => changer({ statut: v as StatutActionCorrective })} />
        </SimpleGrid>
        <MultiSelect label={voc("Dossiers à l'origine de l'action")} searchable clearable error={erreurs.dossiers}
          data={numeros.map((d) => ({ value: String(d.id), label: d.numero }))}
          value={dossiers.map(String)}
          onChange={(v) => setDossiers(v.map(Number))} />
        {erreurs.detail && <Text c="red" size="sm">{erreurs.detail}</Text>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={sauver} loading={enregistrer.isPending} disabled={!valeurs.titre?.trim()}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Suivi des actions correctives décidées à la suite des plaintes. */
export function ActionsCorrectivesPage() {
  const [statut, setStatut] = useState<string | null>(null);
  const [projet, setProjet] = useState<string | null>(null);
  const { data: actions = [] } = useActionsCorrectives({ statut, projet });
  const { data: projets = [] } = useProjets();
  const supprimer = useSupprimerActionCorrective();
  const modifiable = useAccesModules().peutEcrire("/plaintes");
  const [ouverte, setOuverte] = useState<ActionCorrective | null | "nouvelle">(null);
  const aujourdhui = new Date().toISOString().slice(0, 10);
  return (
    <Stack>
      <Stack gap={2}>
        <Anchor component={Link} to="/plaintes" size="sm"><Group gap={4}><ArrowLeft size={14} />{voc("Plaintes et retours")}</Group></Anchor>
        <Group justify="space-between">
          <Title order={2}>{voc("Actions correctives")}</Title>
          {modifiable && <Button leftSection={<Plus size={14} />} onClick={() => setOuverte("nouvelle")}>{voc("Nouvelle action corrective")}</Button>}
        </Group>
      </Stack>
      <Group gap="sm">
        <Select placeholder={voc("Tous les statuts")} clearable w={200} data={STATUTS_ACTION.map((s) => ({ value: s, label: libelleStatutAction(s) }))} value={statut} onChange={setStatut} />
        <Select placeholder={voc("Tous les projets")} clearable searchable w={240} data={projets.map((p) => ({ value: String(p.id), label: p.code || p.nom }))} value={projet} onChange={setProjet} />
      </Group>
      <Table withTableBorder highlightOnHover verticalSpacing={6}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Action")}</Table.Th>
            <Table.Th>{voc("Projet")}</Table.Th>
            <Table.Th>{voc("Responsable")}</Table.Th>
            <Table.Th>{voc("Échéance")}</Table.Th>
            <Table.Th>{voc("Statut")}</Table.Th>
            <Table.Th>{voc("Dossiers")}</Table.Th>
            {modifiable && <Table.Th w={70} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {actions.map((a) => (
            <Table.Tr key={a.id}>
              <Table.Td>
                <Text size="sm" fw={500}>{a.titre}</Text>
                {a.description && <Text size="xs" c="dimmed" lineClamp={2}>{a.description}</Text>}
              </Table.Td>
              <Table.Td>{a.projet_code ?? "—"}</Table.Td>
              <Table.Td>{a.responsable_nom ?? "—"}</Table.Td>
              <Table.Td c={a.echeance && a.echeance < aujourdhui && ["A_FAIRE", "EN_COURS"].includes(a.statut) ? "red.8" : undefined}>
                {a.echeance ? dateLisible(a.echeance) : "—"}
              </Table.Td>
              <Table.Td><BadgeStatutAction statut={a.statut} /></Table.Td>
              <Table.Td>
                <Group gap={4}>
                  {a.dossiers_lies.map((d) => <Anchor key={d.id} component={Link} to={`/plaintes/dossiers/${d.id}`} size="sm">{d.numero}</Anchor>)}
                </Group>
              </Table.Td>
              {modifiable && (
                <Table.Td>
                  <Group gap={2} wrap="nowrap">
                    <ActionIcon size="sm" variant="subtle" onClick={() => setOuverte(a)} aria-label={voc("Modifier")}><Pencil size={13} /></ActionIcon>
                    <ActionIcon size="sm" variant="subtle" color="red" aria-label={voc("Supprimer")}
                      onClick={() => confirmerSuppression({ message: voc`Supprimer « ${a.titre} » ?`, onConfirm: () => supprimer.mutateAsync(a.id) })}>
                      <Trash2 size={13} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              )}
            </Table.Tr>
          ))}
          {actions.length === 0 && (
            <Table.Tr><Table.Td colSpan={7}><Text size="sm" c="dimmed" ta="center" py="md">{voc("Aucune action corrective.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
      {ouverte && <ActionCorrectiveModal action={ouverte === "nouvelle" ? null : ouverte} onClose={() => setOuverte(null)} />}
    </Stack>
  );
}
