import { Fragment, useState } from "react";
import { ActionIcon, Badge, Button, Card, Group, Modal, NumberInput, SimpleGrid, Stack, Table, Text, Textarea, Tooltip } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useProjet } from "../../api/projects";
import {
  useBailleurs,
  useCreateBailleur,
  useCreateFinancement,
  useEnregistrerRallonge,
  useFinancements,
  useSupprimerRallonge,
} from "../../api/referentiels";
import { StatCard } from "../../components/common/StatCard";
import { SelectOrCreate } from "../../components/common/SelectOrCreate";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { Wallet, Landmark, PiggyBank, Plus, Trash2 } from "lucide-react";
import { voc } from "../../utils/vocabulaire";
import type { Financement } from "../../types";

import { locale } from "../../utils/i18n";
const fcfa = (montant: string | number) => `${Number(montant).toLocaleString(locale())} FCFA`;
const dateFr = (d: string) => new Date(d).toLocaleDateString(locale());

/** Fonds supplémentaires accordés par un bailleur en cours de projet : montant, date, motif. */
function RallongeModal({ financement, projetId, onClose }: { financement: Financement; projetId: number; onClose: () => void }) {
  const enregistrer = useEnregistrerRallonge(projetId);
  const [montant, setMontant] = useState<number | string>("");
  const [date, setDate] = useState<string | null>(new Date().toISOString().slice(0, 10));
  const [motif, setMotif] = useState("");

  async function valider() {
    if (montant === "" || Number(montant) <= 0 || !date || !motif.trim()) {
      notifications.show({ message: voc("Montant, date et motif sont requis."), color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync({ financement: financement.id, montant: Number(montant), date, motif: motif.trim() });
      notifications.show({ message: voc("Rallonge enregistrée : le coût total du projet est mis à jour."), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc`Rallonge de fonds — ${financement.bailleur_nom}`}>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {voc("Financement actuel :")} {fcfa(financement.montant_total)}
          {Number(financement.montant_rallonges) > 0 && voc` (dont ${fcfa(financement.montant_rallonges)} de rallonges)`}
        </Text>
        <Group grow align="flex-start">
          <NumberInput label={voc("Montant ajouté (FCFA)")} value={montant} onChange={setMontant} min={0} thousandSeparator=" " required data-autofocus />
          <DateInput label={voc("Date d'accord")} value={date} onChange={setDate} valueFormat="DD/MM/YYYY" required />
        </Group>
        <Textarea
          label={voc("Motif")}
          placeholder={voc("Ex : extension de la zone d'intervention à deux nouvelles communes")}
          value={motif}
          onChange={(e) => setMotif(e.currentTarget.value)}
          autosize
          minRows={3}
          required
        />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
          <Button onClick={valider} loading={enregistrer.isPending}>{voc("Enregistrer la rallonge")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function FinancementsTab({ projetId, lectureSeule = false }: { projetId: number; lectureSeule?: boolean }) {
  const { data: projet } = useProjet(projetId);
  const { data: financements } = useFinancements(projetId);
  const { data: bailleurs } = useBailleurs();
  const createFinancement = useCreateFinancement();
  const createBailleur = useCreateBailleur();
  const supprimerRallonge = useSupprimerRallonge(projetId);

  const [bailleur, setBailleur] = useState<string | null>(null);
  const [montant, setMontant] = useState<number | string>("");
  const [rallongePour, setRallongePour] = useState<Financement | null>(null);

  async function handleAdd() {
    if (!bailleur || montant === "") {
      notifications.show({ message: voc("Bailleur et montant requis."), color: "orange" });
      return;
    }
    try {
      await createFinancement.mutateAsync({ projet: projetId, bailleur: Number(bailleur), montant_finance: Number(montant) });
      notifications.show({ message: voc("Financement ajouté"), color: "green" });
      setBailleur(null);
      setMontant("");
    } catch {
      notifications.show({ message: voc("Erreur — ce bailleur finance peut-être déjà ce projet."), color: "red" });
    }
  }

  if (!projet) return <Text c="dimmed">{voc("Chargement…")}</Text>;
  const totalRallonges = (financements ?? []).reduce((s, f) => s + Number(f.montant_rallonges), 0);

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <StatCard label={voc("Coût total")} value={fcfa(projet.budget_total)} icon={<Wallet size={20} />} color="teal" />
        <StatCard label={voc("Fonds propres")} value={fcfa(projet.fonds_propres)} icon={<PiggyBank size={20} />} color="indigo" />
        <StatCard
          label={totalRallonges > 0 ? voc`Financements bailleurs (dont ${fcfa(totalRallonges)} de rallonges)` : voc("Financements bailleurs")}
          value={fcfa(projet.financement_bailleurs_total)}
          icon={<Landmark size={20} />}
          color="grape"
        />
      </SimpleGrid>

      {!lectureSeule && (
        <Card withBorder padding="md" radius="md">
          <Text size="sm" fw={600} mb="xs">{voc("Ajouter un financement")}</Text>
          <Group align="flex-end">
            <SelectOrCreate
              label={voc("Bailleur")}
              data={bailleurs?.map((b) => ({ value: String(b.id), label: b.nom })) ?? []}
              value={bailleur}
              onChange={setBailleur}
              creating={createBailleur.isPending}
              onCreate={async (nom) => {
                try {
                  const cree = await createBailleur.mutateAsync({ nom, type: "AUTRE" });
                  setBailleur(String(cree.id));
                } catch {
                  notifications.show({ message: voc("Erreur lors de la création du bailleur"), color: "red" });
                }
              }}
            />
            <NumberInput label={voc("Montant financé (FCFA)")} value={montant} onChange={setMontant} min={0} w={200} thousandSeparator=" " />
            <Button onClick={handleAdd} loading={createFinancement.isPending}>{voc("Ajouter")}</Button>
          </Group>
        </Card>
      )}

      <Card withBorder padding="md" radius="md">
        <Table.ScrollContainer minWidth={620}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Bailleur")}</Table.Th>
                <Table.Th ta="right">{voc("Montant initial")}</Table.Th>
                <Table.Th ta="right">{voc("Rallonges")}</Table.Th>
                <Table.Th ta="right">{voc("Total")}</Table.Th>
                {!lectureSeule && <Table.Th w={150} />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {financements?.map((f) => (
                <Fragment key={f.id}>
                  <Table.Tr>
                    <Table.Td fw={500}>{f.bailleur_nom}</Table.Td>
                    <Table.Td ta="right">{fcfa(f.montant_finance)}</Table.Td>
                    <Table.Td ta="right">
                      {Number(f.montant_rallonges) > 0 ? <Text span c="grape.7" fw={500}>+ {fcfa(f.montant_rallonges)}</Text> : "—"}
                    </Table.Td>
                    <Table.Td ta="right" fw={600}>{fcfa(f.montant_total)}</Table.Td>
                    {!lectureSeule && (
                      <Table.Td ta="right">
                        <Button size="compact-xs" variant="light" color="grape" leftSection={<Plus size={12} />} onClick={() => setRallongePour(f)}>
                          {voc("Rallonge")}
                        </Button>
                      </Table.Td>
                    )}
                  </Table.Tr>
                  {f.rallonges.map((r) => (
                    <Table.Tr key={`r-${r.id}`} bg="var(--mantine-color-grape-0)">
                      <Table.Td colSpan={2} pl="xl">
                        <Group gap={6} wrap="nowrap" align="flex-start">
                          <Badge size="xs" variant="light" color="grape" style={{ flexShrink: 0 }}>{voc("Rallonge du")} {dateFr(r.date)}</Badge>
                          <Text size="xs">{r.motif}</Text>
                        </Group>
                        {r.saisi_par_nom && <Text size="xs" c="dimmed" mt={2}>{voc("Saisie par")} {r.saisi_par_nom}</Text>}
                      </Table.Td>
                      <Table.Td ta="right"><Text size="sm" c="grape.7">+ {fcfa(r.montant)}</Text></Table.Td>
                      <Table.Td />
                      {!lectureSeule && (
                        <Table.Td ta="right">
                          <Tooltip label={voc("Supprimer la rallonge")}>
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="red"
                              onClick={() =>
                                confirmerSuppression({
                                  message: voc`Supprimer la rallonge de ${fcfa(r.montant)} du ${dateFr(r.date)} ?`,
                                  onConfirm: () => supprimerRallonge.mutate(r.id),
                                })
                              }
                            >
                              <Trash2 size={13} />
                            </ActionIcon>
                          </Tooltip>
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                </Fragment>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>
      {rallongePour && <RallongeModal financement={rallongePour} projetId={projetId} onClose={() => setRallongePour(null)} />}
    </Stack>
  );
}
