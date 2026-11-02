import { useState } from "react";
import { Alert, Badge, Button, Group, Modal, SegmentedControl, Select, SimpleGrid, Stack, Table, Text, Textarea, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { FileSpreadsheet, Plus } from "lucide-react";
import {
  type DemandeDroits,
  type StatutDemandeDroits,
  TYPES_DROIT,
  dateLisible,
  libelleStatutDemandeDroits,
  libelleTypeDroit,
  telechargerRegistre,
  useDemandesDroits,
  useEnregistrerDemandeDroits,
} from "../../api/plaintes";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "./saisieRetour";

const COULEUR: Record<StatutDemandeDroits, string> = { RECUE: "blue", EN_COURS: "orange", SATISFAITE: "teal", REFUSEE: "gray" };
const aide = (type: string) =>
  type === "RECTIFICATION" ? voc("Rectifiez les coordonnées depuis la fiche du dossier (« Modifier » dans le bloc Plaignant).")
    : type === "EFFACEMENT" ? voc("L'effacement se fait en anonymisant le dossier clôturé (impossible pendant une suspension légale).")
      : null;

function FenetreDemande({ demande, onClose }: { demande: DemandeDroits | null; onClose: () => void }) {
  const enregistrer = useEnregistrerDemandeDroits();
  const [v, setV] = useState<Record<string, unknown>>(
    demande ? { statut: demande.statut === "RECUE" ? "EN_COURS" : demande.statut, reponse: demande.reponse } : { type: "ACCES", date_reception: new Date().toISOString().slice(0, 10) },
  );
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const changer = (x: Record<string, unknown>) => setV((a) => ({ ...a, ...x }));
  const texte = (c: string) => String(v[c] ?? "");
  const envoyer = async () => {
    setErreurs({});
    try {
      await enregistrer.mutateAsync(demande ? { id: demande.id, ...v } : v);
      notifications.show({ color: "teal", message: voc("Demande enregistrée") });
      onClose();
    } catch (error) {
      const parChamp = erreursParChamp(error);
      setErreurs(Object.keys(parChamp).length ? parChamp : { detail: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Modal opened onClose={onClose} size="lg" title={demande ? voc("Traiter la demande") : voc("Nouvelle demande sur les données")}>
      <Stack>
        {demande ? (
          <>
            <Text size="sm"><b>{libelleTypeDroit(demande.type)}</b> — {demande.demandeur}{demande.contact && ` (${demande.contact})`}</Text>
            {demande.description && <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-line" }}>{demande.description}</Text>}
            {aide(demande.type) && <Alert color="blue" p="xs">{aide(demande.type)}</Alert>}
            <SegmentedControl value={texte("statut")} onChange={(x) => changer({ statut: x })}
              data={(["EN_COURS", "SATISFAITE", "REFUSEE"] as StatutDemandeDroits[]).map((s) => ({ value: s, label: libelleStatutDemandeDroits(s) }))} />
            <Textarea label={voc("Réponse donnée à la personne")} description={voc("Obligatoire pour conclure ; motivez tout refus.")}
              autosize minRows={3} value={texte("reponse")} onChange={(e) => changer({ reponse: e.currentTarget.value })} error={erreurs.reponse ?? erreurs.statut} />
          </>
        ) : (
          <>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <Select label={voc("Droit exercé")} withAsterisk allowDeselect={false} value={texte("type")}
                data={TYPES_DROIT.map((t) => ({ value: t, label: libelleTypeDroit(t) }))} onChange={(x) => changer({ type: x })} error={erreurs.type} />
              <DateInput label={voc("Reçue le")} valueFormat="DD/MM/YYYY" maxDate={new Date().toISOString().slice(0, 10)}
                value={texte("date_reception") || null} onChange={(x) => changer({ date_reception: x })} error={erreurs.date_reception} />
              <TextInput label={voc("Personne qui exerce son droit")} withAsterisk value={texte("demandeur")}
                onChange={(e) => changer({ demandeur: e.currentTarget.value })} error={erreurs.demandeur} />
              <TextInput label={voc("Contact")} value={texte("contact")} onChange={(e) => changer({ contact: e.currentTarget.value })} />
            </SimpleGrid>
            <TextInput label={voc("Dossier concerné (numéro, facultatif)")} placeholder="MGP-2026-00012" dir="ltr" value={texte("numero_dossier")}
              onChange={(e) => changer({ numero_dossier: e.currentTarget.value })} error={erreurs.numero_dossier} />
            <Textarea label={voc("Demande")} autosize minRows={2} value={texte("description")} onChange={(e) => changer({ description: e.currentTarget.value })} />
            <Text size="xs" c="dimmed">{voc("Une réponse est attendue au plus tard un mois après la réception.")}</Text>
          </>
        )}
        {erreurs.detail && <Alert color="red">{erreurs.detail}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={envoyer} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Demandes des personnes sur leurs données (accès, rectification, effacement, opposition) et registre des traitements. */
export function DonneesPersonnellesPlaintes() {
  const { data: demandes = [] } = useDemandesDroits();
  const [fenetre, setFenetre] = useState<DemandeDroits | "nouvelle" | null>(null);
  const [export_, setExport] = useState(false);
  const exporter = async () => {
    setExport(true);
    try {
      await telechargerRegistre();
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("L'export n'a pas abouti.")) });
    } finally {
      setExport(false);
    }
  };
  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-start">
        <Text size="sm" c="dimmed" maw={760}>
          {voc("Toute personne peut demander l'accès à ses données, leur rectification, leur effacement ou s'opposer à leur traitement. Chaque demande est enregistrée, suivie jusqu'à la réponse (sous un mois) et inscrite au journal d'audit.")}
        </Text>
        <Group gap="xs">
          <Button size="xs" variant="light" leftSection={<FileSpreadsheet size={14} />} loading={export_} onClick={exporter}>
            {voc("Registre des traitements")}
          </Button>
          <Button size="xs" leftSection={<Plus size={14} />} onClick={() => setFenetre("nouvelle")}>{voc("Nouvelle demande")}</Button>
        </Group>
      </Group>
      <Table withTableBorder verticalSpacing={6}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Reçue le")}</Table.Th>
            <Table.Th>{voc("Droit exercé")}</Table.Th>
            <Table.Th>{voc("Personne")}</Table.Th>
            <Table.Th>{voc("Dossier")}</Table.Th>
            <Table.Th>{voc("Échéance")}</Table.Th>
            <Table.Th>{voc("État")}</Table.Th>
            <Table.Th w={90} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {demandes.map((d) => (
            <Table.Tr key={d.id}>
              <Table.Td>{dateLisible(d.date_reception)}</Table.Td>
              <Table.Td>{libelleTypeDroit(d.type)}</Table.Td>
              <Table.Td>{d.demandeur}</Table.Td>
              <Table.Td>{d.numero_dossier || "—"}</Table.Td>
              <Table.Td><Text size="sm" c={d.en_retard ? "red" : undefined}>{dateLisible(d.echeance)}</Text></Table.Td>
              <Table.Td><Badge variant="light" tt="none" color={COULEUR[d.statut]}>{libelleStatutDemandeDroits(d.statut)}</Badge></Table.Td>
              <Table.Td><Button size="compact-xs" variant="light" onClick={() => setFenetre(d)}>{d.statut === "RECUE" || d.statut === "EN_COURS" ? voc("Traiter") : voc("Voir")}</Button></Table.Td>
            </Table.Tr>
          ))}
          {demandes.length === 0 && (
            <Table.Tr><Table.Td colSpan={7}><Text size="sm" c="dimmed">{voc("Aucune demande enregistrée.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
      {fenetre && <FenetreDemande demande={fenetre === "nouvelle" ? null : fenetre} onClose={() => setFenetre(null)} />}
    </Stack>
  );
}
