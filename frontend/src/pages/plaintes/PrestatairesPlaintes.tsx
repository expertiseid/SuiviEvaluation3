import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { ActionIcon, Button, Group, Select, Stack, Switch, Table, Text, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  type Prestataire,
  type TypePrestataire,
  TYPES_PRESTATAIRE,
  libelleTypePrestataire,
  useEnregistrerPrestataire,
  usePrestataires,
  useSupprimerPrestataire,
} from "../../api/plaintes";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

/** Annuaire des prestataires d'assistance (médicale, psychosociale, juridique, sécurité). */
export function PrestatairesPlaintes({ modifiable }: { modifiable: boolean }) {
  const { data: prestataires = [] } = usePrestataires();
  const enregistrer = useEnregistrerPrestataire();
  const supprimer = useSupprimerPrestataire();
  const [nouveau, setNouveau] = useState<Partial<Prestataire>>({ type: "PSYCHOSOCIAL" });
  const sauver = async (p: Partial<Prestataire> & { id?: number }) => {
    try {
      await enregistrer.mutateAsync(p);
      return true;
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" });
      return false;
    }
  };
  const options = TYPES_PRESTATAIRE.map((t) => ({ value: t, label: libelleTypePrestataire(t) }));
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("Prestataires vers qui orienter une personne, avec son consentement, depuis un dossier confidentiel. Seuls le prestataire, la date et le consentement sont enregistrés.")}
      </Text>
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Nom")}</Table.Th>
            <Table.Th w={200}>{voc("Type d'assistance")}</Table.Th>
            <Table.Th>{voc("Contact")}</Table.Th>
            <Table.Th>{voc("Zone couverte")}</Table.Th>
            <Table.Th w={70}>{voc("Actif")}</Table.Th>
            {modifiable && <Table.Th w={50} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {prestataires.map((p) => (
            <Table.Tr key={p.id}>
              <Table.Td>{p.nom}</Table.Td>
              <Table.Td>
                <Select size="xs" data={options} value={p.type} disabled={!modifiable} allowDeselect={false}
                  onChange={(v) => v && sauver({ id: p.id, type: v as TypePrestataire })} />
              </Table.Td>
              <Table.Td>{p.contact || "—"}</Table.Td>
              <Table.Td>{p.zone || "—"}</Table.Td>
              <Table.Td>
                <Switch size="xs" checked={p.actif} disabled={!modifiable} aria-label={voc("Actif")}
                  onChange={(e) => { const actif = e.currentTarget.checked; sauver({ id: p.id, actif }); }} />
              </Table.Td>
              {modifiable && (
                <Table.Td>
                  <ActionIcon size="sm" variant="subtle" color="red" aria-label={voc("Supprimer")}
                    onClick={() => supprimer.mutate(p.id, { onError: (e) => notifications.show({ message: messageErreurApi(e, voc("Suppression impossible")), color: "red" }) })}>
                    <Trash2 size={13} />
                  </ActionIcon>
                </Table.Td>
              )}
            </Table.Tr>
          ))}
          {prestataires.length === 0 && (
            <Table.Tr><Table.Td colSpan={6}><Text size="sm" c="dimmed" ta="center">{voc("Aucun prestataire.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
      {modifiable && (
        <Group align="flex-end" gap="sm">
          <TextInput label={voc("Nom")} value={nouveau.nom ?? ""} onChange={(e) => { const nom = e.currentTarget.value; setNouveau((n) => ({ ...n, nom })); }} w={220} />
          <Select label={voc("Type d'assistance")} data={options} value={nouveau.type ?? null} allowDeselect={false}
            onChange={(v) => setNouveau((n) => ({ ...n, type: v as TypePrestataire }))} w={200} />
          <TextInput label={voc("Contact")} value={nouveau.contact ?? ""} onChange={(e) => { const contact = e.currentTarget.value; setNouveau((n) => ({ ...n, contact })); }} w={200} />
          <TextInput label={voc("Zone couverte")} value={nouveau.zone ?? ""} onChange={(e) => { const zone = e.currentTarget.value; setNouveau((n) => ({ ...n, zone })); }} w={180} />
          <Button leftSection={<Plus size={14} />} disabled={!nouveau.nom?.trim()}
            onClick={async () => { if (await sauver({ ...nouveau, nom: nouveau.nom?.trim(), actif: true })) setNouveau({ type: "PSYCHOSOCIAL" }); }}>
            {voc("Ajouter")}
          </Button>
        </Group>
      )}
    </Stack>
  );
}
