import { useState } from "react";
import { Button, Card, Group, NumberInput, SimpleGrid, Stack, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useProjet } from "../../api/projects";
import { useBailleurs, useCreateBailleur, useCreateFinancement, useFinancements } from "../../api/referentiels";
import { StatCard } from "../../components/common/StatCard";
import { SelectOrCreate } from "../../components/common/SelectOrCreate";
import { Wallet, Landmark, PiggyBank } from "lucide-react";
import { voc } from "../../utils/vocabulaire";

export function FinancementsTab({ projetId }: { projetId: number }) {
  const { data: projet } = useProjet(projetId);
  const { data: financements } = useFinancements(projetId);
  const { data: bailleurs } = useBailleurs();
  const createFinancement = useCreateFinancement();
  const createBailleur = useCreateBailleur();

  const [bailleur, setBailleur] = useState<string | null>(null);
  const [montant, setMontant] = useState<number | string>("");

  async function handleAdd() {
    if (!bailleur || montant === "") {
      notifications.show({ message: "Bailleur et montant requis.", color: "orange" });
      return;
    }
    try {
      await createFinancement.mutateAsync({ projet: projetId, bailleur: Number(bailleur), montant_finance: Number(montant) });
      notifications.show({ message: "Financement ajouté", color: "green" });
      setBailleur(null);
      setMontant("");
    } catch {
      notifications.show({ message: voc("Erreur — ce bailleur finance peut-être déjà ce projet."), color: "red" });
    }
  }

  if (!projet) return <Text c="dimmed">Chargement…</Text>;

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <StatCard label="Coût total" value={`${Number(projet.budget_total).toLocaleString("fr-FR")} FCFA`} icon={<Wallet size={20} />} color="teal" />
        <StatCard label="Fonds propres" value={`${Number(projet.fonds_propres).toLocaleString("fr-FR")} FCFA`} icon={<PiggyBank size={20} />} color="indigo" />
        <StatCard label="Financements bailleurs" value={`${Number(projet.financement_bailleurs_total).toLocaleString("fr-FR")} FCFA`} icon={<Landmark size={20} />} color="grape" />
      </SimpleGrid>

      <Card withBorder padding="md" radius="md">
        <Text size="sm" fw={600} mb="xs">Ajouter un financement</Text>
        <Group align="flex-end">
          <SelectOrCreate
            label="Bailleur"
            data={bailleurs?.map((b) => ({ value: String(b.id), label: b.nom })) ?? []}
            value={bailleur}
            onChange={setBailleur}
            creating={createBailleur.isPending}
            onCreate={async (nom) => {
              try {
                const cree = await createBailleur.mutateAsync({ nom, type: "AUTRE" });
                setBailleur(String(cree.id));
              } catch {
                notifications.show({ message: "Erreur lors de la création du bailleur", color: "red" });
              }
            }}
          />
          <NumberInput label="Montant financé (FCFA)" value={montant} onChange={setMontant} min={0} w={200} />
          <Button onClick={handleAdd} loading={createFinancement.isPending}>Ajouter</Button>
        </Group>
      </Card>

      <Card withBorder padding="md" radius="md">
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Bailleur</Table.Th>
              <Table.Th>Montant financé</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {financements?.map((f) => (
              <Table.Tr key={f.id}>
                <Table.Td>{f.bailleur_nom}</Table.Td>
                <Table.Td>{Number(f.montant_finance).toLocaleString("fr-FR")} FCFA</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  );
}
