import { useState } from "react";
import { Crown, Pencil, Plus, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Modal,
  MultiSelect,
  SegmentedControl,
  SimpleGrid,
  Table,
  Stack,
  Text,
  Textarea,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useEnregistrerPartenaireProjet,
  usePartenairesProjet,
  useSupprimerPartenaireProjet,
  useTousPartenaires,
} from "../../api/organisation";
import { useCreatePartenaire } from "../../api/referentiels";
import { SelectOrCreate } from "../../components/common/SelectOrCreate";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import type { Activite, PartenaireProjet, Projet } from "../../types";

type Edition = Partial<PartenaireProjet> & { partenaire?: number };

const NATURES = [
  { value: "CONSORTIUM", label: voc("Consortium") },
  { value: "MISE_EN_OEUVRE", label: voc("Mise en œuvre") },
];

/** Éléments de la planification à plat, indentés selon leur niveau (pour les listes de choix). */
function optionsElements(activites: Activite[], profondeur = 0): { value: string; label: string }[] {
  return activites.flatMap((a) => [
    { value: String(a.id), label: `${"  ".repeat(profondeur)}${a.code_activite ? a.code_activite + " " : ""}${a.libelle}` },
    ...optionsElements(a.enfants ?? [], profondeur + 1),
  ]);
}

function RoleModal({ projet, edition, onClose }: { projet: Projet; edition: Edition | null; onClose: () => void }) {
  const { data: partenaires = [] } = useTousPartenaires();
  const creerPartenaire = useCreatePartenaire();
  const enregistrer = useEnregistrerPartenaireProjet(projet.id);
  const [valeurs, setValeurs] = useState<Edition>({});
  const [cle, setCle] = useState<unknown>(null);
  if (edition !== cle) {
    setCle(edition);
    setValeurs({ nature: "CONSORTIUM", chef_de_file: false, role: "", elements: [], ...edition });
  }

  async function valider() {
    if (!valeurs.partenaire) {
      notifications.show({ message: voc("Choisis le partenaire."), color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync({
        id: valeurs.id,
        partenaire: valeurs.partenaire,
        nature: valeurs.nature,
        chef_de_file: valeurs.chef_de_file,
        role: valeurs.role,
        elements: valeurs.elements,
      });
      notifications.show({ message: voc("Rôle du partenaire enregistré"), color: "green" });
      onClose();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur (ce partenaire a peut-être déjà un rôle dans le projet)")), color: "red" });
    }
  }

  return (
    <Modal opened={edition !== null} onClose={onClose} size="lg" title={edition?.id ? voc`Rôle de ${edition.partenaire_nom}` : voc("Ajouter un partenaire au projet")}>
      <Stack gap="sm">
        {!edition?.id && (
          <SelectOrCreate
            label={voc("Partenaire")}
            data={partenaires
              .filter((p) => p.type !== "BAILLEUR")
              .map((p) => ({ value: String(p.id), label: p.nom }))}
            value={valeurs.partenaire ? String(valeurs.partenaire) : null}
            onChange={(v) => setValeurs({ ...valeurs, partenaire: v ? Number(v) : undefined })}
            creating={creerPartenaire.isPending}
            onCreate={async (nom) => {
              const cree = await creerPartenaire.mutateAsync({ nom, type: valeurs.nature ?? "CONSORTIUM" });
              setValeurs((v) => ({ ...v, partenaire: cree.id }));
            }}
          />
        )}
        <Group>
          <SegmentedControl
            data={NATURES}
            value={valeurs.nature ?? "CONSORTIUM"}
            onChange={(nature) => setValeurs({ ...valeurs, nature: nature as PartenaireProjet["nature"] })}
          />
          <Checkbox
            label={voc("Chef de file")}
            checked={!!valeurs.chef_de_file}
            onChange={(e) => setValeurs({ ...valeurs, chef_de_file: e.currentTarget.checked })}
          />
        </Group>
        <Textarea
          label={voc("Rôle et responsabilités")}
          autosize
          minRows={3}
          value={valeurs.role ?? ""}
          onChange={(e) => setValeurs({ ...valeurs, role: e.currentTarget.value })}
        />
        <MultiSelect
          label={voc("Ce qu'il réalise")}
          description={voc("Objectifs, résultats, activités… de la planification dont ce partenaire est chargé (ce qui est en dessous en fait partie).")}
          data={optionsElements(projet.activites)}
          value={(valeurs.elements ?? []).map(String)}
          onChange={(ids) => setValeurs({ ...valeurs, elements: ids.map(Number) })}
          searchable
          clearable
          placeholder={voc("Aucun élément")}
        />
        <Group justify="flex-end">
          <Button onClick={valider} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Onglet « Partenaires » d'un projet : rôle de chaque partenaire de consortium ou de mise en
 * œuvre et éléments de la planification qu'il réalise ; rappel des services chargés et des
 * parties prenantes (réglés dans le formulaire du projet).
 */
export function PartenairesProjetTab({ projet, editable }: { projet: Projet; editable: boolean }) {
  const { data: roles = [] } = usePartenairesProjet(projet.id);
  const supprimer = useSupprimerPartenaireProjet(projet.id);
  const [edition, setEdition] = useState<Edition | null>(null);

  // Partenaires déjà associés au projet (formulaire du projet) dont le rôle n'est pas encore précisé.
  const avecRole = new Set(roles.map((r) => r.partenaire));
  const sansRole: Edition[] = [
    ...(projet.partenaire_mise_en_oeuvre
      ? [{ partenaire: projet.partenaire_mise_en_oeuvre, partenaire_nom: projet.partenaire_mise_en_oeuvre_nom ?? "", nature: "MISE_EN_OEUVRE" as const }]
      : []),
    ...projet.partenaires_consortium.map((id, i) => ({
      partenaire: id,
      partenaire_nom: projet.partenaires_consortium_noms[i] ?? "",
      nature: "CONSORTIUM" as const,
    })),
  ].filter((p, i, tous) => !avecRole.has(p.partenaire) && tous.findIndex((x) => x.partenaire === p.partenaire) === i);

  const carteRole = (r: PartenaireProjet) => (
      <Card key={r.id} withBorder padding="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Group gap={6}>
              <Text fw={600}>{r.partenaire_nom}</Text>
              {r.chef_de_file && (
                <Badge size="sm" color="yellow" variant="light" leftSection={<Crown size={11} />}>{voc("Chef de file")}</Badge>
              )}
            </Group>
            <Badge size="sm" variant="light" color={r.nature === "CONSORTIUM" ? "teal" : "blue"} mt={4}>
              {r.nature === "CONSORTIUM" ? voc("Consortium") : voc("Mise en œuvre")}
            </Badge>
          </div>
          {editable && (
            <Group gap={4} wrap="nowrap">
              <Tooltip label={voc("Modifier")}>
                <ActionIcon variant="subtle" size="sm" onClick={() => setEdition(r)}>
                  <Pencil size={14} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label={voc("Retirer le rôle")}>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  color="red"
                  onClick={() =>
                    confirmerSuppression({
                      message: voc`Retirer le rôle de « ${r.partenaire_nom} » ? Il reste associé au projet.`,
                      onConfirm: () => supprimer.mutate(r.id),
                    })
                  }
                >
                  <Trash2 size={14} />
                </ActionIcon>
              </Tooltip>
            </Group>
          )}
        </Group>
        {r.role && <Text size="sm" mt="xs" style={{ whiteSpace: "pre-wrap" }}>{r.role}</Text>}
        {r.elements_libelles.length > 0 && (
          <Stack gap={2} mt="xs">
            <Text size="xs" fw={600} c="dimmed">{voc("Réalise")}</Text>
            {r.elements_libelles.map((l) => (
              <Text key={l} size="xs">• {l}</Text>
            ))}
          </Stack>
        )}
      </Card>
  );
  const carteSansRole = (p: Edition) => (
      <Card key={`sans-${p.partenaire}`} withBorder padding="md" style={{ borderStyle: "dashed" }}>
        <Group justify="space-between">
          <div>
            <Text fw={600}>{p.partenaire_nom}</Text>
            <Text size="xs" c="dimmed">
              {p.nature === "CONSORTIUM" ? voc("Consortium") : voc("Mise en œuvre")} {voc("· rôle non précisé")}
            </Text>
          </div>
          {editable && (
            <Button size="xs" variant="light" onClick={() => setEdition(p)}>
              {voc("Préciser le rôle")}
            </Button>
          )}
        </Group>
      </Card>
  );

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {voc("Rôle de chaque partenaire de consortium ou de mise en œuvre et éléments de la planification qu'il réalise.")}
        </Text>
        {editable && (
          <Button leftSection={<Plus size={16} />} onClick={() => setEdition({})}>
            {voc("Ajouter un partenaire")}
          </Button>
        )}
      </Group>

      {roles.length === 0 && sansRole.length === 0 && (
        <Card withBorder><Text size="sm" c="dimmed">{voc("Aucun partenaire pour ce projet.")}</Text></Card>
      )}

      {NATURES.map(({ value: nature }) => {
        const r = roles.filter((x) => x.nature === nature);
        const sr = sansRole.filter((x) => x.nature === nature);
        return (
          <div key={nature}>
            <Group gap={8} mb={6}>
              <Title order={5}>{nature === "MISE_EN_OEUVRE" ? voc("Partenaires de mise en œuvre") : voc("Partenaires du consortium")}</Title>
              <Badge variant="light" color={nature === "CONSORTIUM" ? "teal" : "blue"}>{r.length + sr.length}</Badge>
            </Group>
            {r.length + sr.length === 0 ? (
              <Text size="sm" c="dimmed">{voc("Aucun.")}</Text>
            ) : (
              <SimpleGrid cols={{ base: 1, md: 2 }}>
                {r.map(carteRole)}
                {sr.map(carteSansRole)}
              </SimpleGrid>
            )}
          </div>
        );
      })}

      <Card withBorder padding="md">
        <Title order={5} mb="xs">{voc("Services de l'organisation qui travaillent sur le projet")}</Title>
        {(projet.services_detail ?? []).length === 0 ? (
          <Text size="sm" c="dimmed">{voc("Aucun service affecté (formulaire du projet, onglet « Organisation », ou écran Organisation).")}</Text>
        ) : (
          <Table verticalSpacing={6} fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Service")}</Table.Th>
                <Table.Th>{voc("Sur")}</Table.Th>
                <Table.Th>{voc("Membres")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {projet.services_detail!.map((sv) => (
                <Table.Tr key={sv.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{sv.nom}</Text>
                    {sv.type && <Text size="xs" c="dimmed">{sv.type}</Text>}
                  </Table.Td>
                  <Table.Td>
                    {sv.tout_le_projet && <Badge size="sm" variant="light">{voc("Tout le projet")}</Badge>}
                    {sv.parties.map((l) => (
                      <Text key={l} size="xs">• {l}</Text>
                    ))}
                  </Table.Td>
                  <Table.Td>{sv.membres.join(", ") || "—"}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

      <Card withBorder padding="md">
        <Title order={5} mb="xs">{voc("Parties prenantes")}</Title>
        <Text size="sm">{projet.parties_prenantes_noms?.join(", ") || "—"}</Text>
        {(projet.elements_strategiques_secondaires_noms?.length ?? 0) > 0 && (
          <Text size="sm">
            <b>{voc("Contribue aussi à :")}</b> {projet.elements_strategiques_secondaires_noms.join(", ")}
          </Text>
        )}
        <Text size="xs" c="dimmed" mt={4}>{voc("Se règlent dans le formulaire du projet (crayon), onglet « Organisation ».")}</Text>
      </Card>

      <RoleModal projet={projet} edition={edition} onClose={() => setEdition(null)} />
    </Stack>
  );
}
