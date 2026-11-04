import { Badge, Select, Stack, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useDemandesInscription, useStatutDemandeInscription } from "../../api/identite";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const STATUTS = [
  { value: "ABONNEMENT_REQUIS", label: () => voc("Abonnement requis"), couleur: "orange" },
  { value: "OFFRE_CHOISIE", label: () => voc("Offre choisie, à contacter"), couleur: "blue" },
  { value: "ACTIVEE", label: () => voc("Abonnement activé"), couleur: "teal" },
  { value: "REFUSEE", label: () => voc("Refusée"), couleur: "gray" },
];

/** Profils créés depuis la page d'accueil par des organisations (en attente d'abonnement). */
export function DemandesInscription() {
  const { data: demandes = [] } = useDemandesInscription();
  const changer = useStatutDemandeInscription();
  const modifier = async (id: number, statut: string | null) => {
    if (!statut) return;
    try {
      await changer.mutateAsync({ id, statut });
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {voc("Organisations qui ont créé leur profil depuis la page d'accueil. Elles n'ont aucun accès tant que leur abonnement n'est pas activé ; chaque demande est aussi envoyée par courriel à Expertise-ID.")}
      </Text>
      <Table.ScrollContainer minWidth={900}>
        <Table withTableBorder striped verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{voc("Reçue le")}</Table.Th>
              <Table.Th>{voc("Organisation")}</Table.Th>
              <Table.Th>{voc("Contact")}</Table.Th>
              <Table.Th>{voc("Identifiant")}</Table.Th>
              <Table.Th>{voc("Offre")}</Table.Th>
              <Table.Th w={230}>{voc("État")}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {demandes.map((d) => {
              const statut = STATUTS.find((s) => s.value === d.statut);
              return (
                <Table.Tr key={d.id} style={{ verticalAlign: "top" }}>
                  <Table.Td><Text size="sm">{new Date(d.cree_le).toLocaleDateString(locale())}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={600}>{d.organisation}</Text>
                    <Text size="xs" c="dimmed">{[d.type_organisation, d.pays, d.secteur, d.taille].filter(Boolean).join(" · ")}</Text>
                    {d.message && <Text size="xs" mt={4} style={{ whiteSpace: "pre-wrap" }}>{d.message}</Text>}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{d.contact_nom}{d.contact_fonction && ` — ${d.contact_fonction}`}</Text>
                    <Text size="xs"><a href={`mailto:${d.courriel}`}>{d.courriel}</a> · {d.telephone}</Text>
                  </Table.Td>
                  <Table.Td><Text size="sm" ff="monospace">{d.identifiant}</Text></Table.Td>
                  <Table.Td>{d.offre_libelle ? <Badge variant="light">{d.offre_libelle}</Badge> : <Text size="sm" c="dimmed">—</Text>}</Table.Td>
                  <Table.Td>
                    <Select size="xs" allowDeselect={false} value={d.statut} onChange={(v) => modifier(d.id, v)}
                      data={STATUTS.map((s) => ({ value: s.value, label: s.label() }))}
                      leftSection={<Badge size="xs" circle color={statut?.couleur}> </Badge>} />
                  </Table.Td>
                </Table.Tr>
              );
            })}
            {demandes.length === 0 && (
              <Table.Tr><Table.Td colSpan={6}><Text size="sm" c="dimmed">{voc("Aucune demande pour l'instant.")}</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}
