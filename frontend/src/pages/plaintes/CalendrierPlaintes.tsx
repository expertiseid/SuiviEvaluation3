import { useState } from "react";
import { CalendarPlus, Plus, Trash2 } from "lucide-react";
import { ActionIcon, Button, Group, NumberInput, Stack, Table, Text, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { dateLisible, useEnregistrerJourFerie, useJoursFeries, useMecanisme, useSupprimerJourFerie } from "../../api/plaintes";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

// Jours fériés à date fixe du Burkina Faso ; les fêtes mobiles (Pâques, Ascension, Pentecôte,
// Ramadan, Tabaski, Maouloud) sont ajoutées par l'organisation chaque année.
const FERIES_FIXES_BF: [string, string][] = [
  ["01-01", "Jour de l'an"],
  ["01-03", "Anniversaire du soulèvement populaire du 3 janvier 1966"],
  ["03-08", "Journée internationale de la femme"],
  ["05-01", "Fête du travail"],
  ["08-05", "Fête de l'indépendance"],
  ["08-15", "Assomption"],
  ["11-01", "Toussaint"],
  ["12-11", "Proclamation de la République"],
  ["12-25", "Noël"],
];

/** Jours fériés exclus du calcul des délais en jours ouvrés. */
export function CalendrierPlaintes({ modifiable }: { modifiable: boolean }) {
  const { data: mecanisme } = useMecanisme();
  const { data: jours = [] } = useJoursFeries();
  const enregistrer = useEnregistrerJourFerie();
  const supprimer = useSupprimerJourFerie();
  const [date, setDate] = useState<string | null>(null);
  const [libelle, setLibelle] = useState("");
  const [annee, setAnnee] = useState<number>(new Date().getFullYear());

  const ajouter = async (d: string, l: string) => {
    try {
      await enregistrer.mutateAsync({ date: d, libelle: l });
      return true;
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
      return false;
    }
  };
  const ajouterFixes = async () => {
    const existants = new Set(jours.map((j) => j.date));
    let ajoutes = 0;
    for (const [mmjj, nom] of FERIES_FIXES_BF) {
      const d = `${annee}-${mmjj}`;
      if (!existants.has(d) && (await ajouter(d, nom))) ajoutes += 1;
    }
    notifications.show({ message: voc`${ajoutes} jour(s) férié(s) ajouté(s).`, color: "teal" });
  };

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {mecanisme?.jours_ouvres
          ? voc("Les délais sont comptés en jours ouvrés : samedis, dimanches et jours fériés ci-dessous sont exclus.")
          : voc("Les délais sont actuellement comptés en jours calendaires : ce calendrier ne servira que si vous choisissez les jours ouvrés (onglet Mécanisme).")}
      </Text>
      {modifiable && (
        <Group align="flex-end" gap="sm">
          <DateInput label={voc("Date")} value={date} onChange={setDate} valueFormat="DD/MM/YYYY" w={160} />
          <TextInput label={voc("Libellé")} placeholder={voc("Ex : Tabaski")} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} w={260} />
          <Button leftSection={<Plus size={14} />} disabled={!date || !libelle.trim()}
            onClick={async () => { if (date && (await ajouter(date, libelle.trim()))) { setDate(null); setLibelle(""); } }}>
            {voc("Ajouter")}
          </Button>
          <NumberInput label={voc("Année")} value={annee} onChange={(v) => setAnnee(Number(v) || annee)} min={2020} max={2100} w={100} />
          <Button variant="light" leftSection={<CalendarPlus size={14} />} onClick={ajouterFixes} loading={enregistrer.isPending}>
            {voc("Ajouter les jours fériés fixes du Burkina Faso")}
          </Button>
        </Group>
      )}
      <Table withTableBorder verticalSpacing={4} maw={620}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={140}>{voc("Date")}</Table.Th>
            <Table.Th>{voc("Libellé")}</Table.Th>
            {modifiable && <Table.Th w={50} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {jours.map((j) => (
            <Table.Tr key={j.id}>
              <Table.Td>{dateLisible(j.date)}</Table.Td>
              <Table.Td>{j.libelle}</Table.Td>
              {modifiable && (
                <Table.Td>
                  <ActionIcon size="sm" variant="subtle" color="red" aria-label={voc("Supprimer")} onClick={() => supprimer.mutate(j.id)}>
                    <Trash2 size={13} />
                  </ActionIcon>
                </Table.Td>
              )}
            </Table.Tr>
          ))}
          {jours.length === 0 && (
            <Table.Tr><Table.Td colSpan={3}><Text size="sm" c="dimmed" ta="center">{voc("Aucun jour férié.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
      <Text size="xs" c="dimmed">{voc("Les fêtes à date mobile (Pâques, Ascension, Pentecôte, Ramadan, Tabaski, Maouloud) sont à ajouter chaque année.")}</Text>
    </Stack>
  );
}
