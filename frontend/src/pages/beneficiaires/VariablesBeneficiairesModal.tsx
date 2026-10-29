import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Modal,
  MultiSelect,
  Select,
  Stack,
  Switch,
  Table,
  TagsInput,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useChoixProjetsVariables,
  useEnregistrerVariableBeneficiaire,
  useSupprimerVariableBeneficiaire,
  useVariablesBeneficiaires,
} from "../../api/beneficiaries";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import type { TypeVariableBeneficiaire, VariableBeneficiaire } from "../../types";

const TYPES_VARIABLE: { value: TypeVariableBeneficiaire; label: string }[] = [
  { value: "TEXTE", label: voc("Texte") },
  { value: "NOMBRE", label: voc("Nombre") },
  { value: "DATE", label: voc("Date") },
  { value: "OUI_NON", label: voc("Oui / non") },
  { value: "CHOIX", label: voc("Choix unique") },
  { value: "CHOIX_MULTIPLE", label: voc("Choix multiple") },
];

function FormulaireVariable({ variable, onFini }: { variable: Partial<VariableBeneficiaire>; onFini: () => void }) {
  const enregistrer = useEnregistrerVariableBeneficiaire();
  const { data: projets = [] } = useChoixProjetsVariables(true);
  const [v, setV] = useState<Partial<VariableBeneficiaire>>({ type: "TEXTE", tous_les_projets: true, choix: [], projets: [], ...variable });
  const avecChoix = v.type === "CHOIX" || v.type === "CHOIX_MULTIPLE";

  async function valider() {
    if (!v.libelle?.trim()) {
      notifications.show({ message: voc("Indique le libellé."), color: "orange" });
      return;
    }
    try {
      await enregistrer.mutateAsync({ ...v, libelle: v.libelle.trim() });
      notifications.show({ message: voc("Variable enregistrée"), color: "green" });
      onFini();
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, voc("Erreur lors de l'enregistrement")), color: "red" });
    }
  }

  return (
    <Stack gap="sm" p="sm" style={{ border: "1px solid var(--mantine-color-gray-3)", borderRadius: 8 }}>
      <Group grow align="flex-start">
        <TextInput label={voc("Libellé")} placeholder={voc("Ex : Taille du ménage")} required value={v.libelle ?? ""} onChange={(e) => setV({ ...v, libelle: e.currentTarget.value })} data-autofocus />
        <Select label={voc("Type de réponse")} data={TYPES_VARIABLE} value={v.type} onChange={(t) => setV({ ...v, type: (t ?? "TEXTE") as TypeVariableBeneficiaire })} allowDeselect={false} />
        {v.type === "NOMBRE" && (
          <TextInput label={voc("Unité")} placeholder={voc("personnes, ha…")} value={v.unite ?? ""} onChange={(e) => setV({ ...v, unite: e.currentTarget.value })} />
        )}
      </Group>
      {avecChoix && (
        <TagsInput
          label={voc("Réponses proposées")}
          description={voc("Taper une réponse puis Entrée")}
          value={v.choix ?? []}
          onChange={(choix) => setV({ ...v, choix })}
        />
      )}
      <TextInput label={voc("Aide (facultatif)")} value={v.aide ?? ""} onChange={(e) => setV({ ...v, aide: e.currentTarget.value })} />
      <Switch
        label={voc("Pour tous les projets")}
        description={voc("Sinon, seulement les projets choisis : pour les autres, la variable n'est pas demandée et vaut « NA ».")}
        checked={!!v.tous_les_projets}
        onChange={(e) => setV({ ...v, tous_les_projets: e.currentTarget.checked })}
      />
      {!v.tous_les_projets && (
        <MultiSelect
          label={voc("Projets concernés")}
          data={projets}
          value={(v.projets ?? []).map(String)}
          onChange={(ids) => setV({ ...v, projets: ids.map(Number) })}
          searchable
        />
      )}
      <Group justify="flex-end">
        <Button variant="subtle" onClick={onFini}>{voc("Annuler")}</Button>
        <Button onClick={valider} loading={enregistrer.isPending}>{voc("Enregistrer")}</Button>
      </Group>
    </Stack>
  );
}

/** Paramétrage des variables à collecter sur les bénéficiaires (Administrateur). */
export function VariablesBeneficiairesModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { data: variables = [] } = useVariablesBeneficiaires();
  const supprimer = useSupprimerVariableBeneficiaire();
  const [edition, setEdition] = useState<Partial<VariableBeneficiaire> | null>(null);

  return (
    <Modal opened={opened} onClose={onClose} size="xl" title={voc("Variables à collecter sur les bénéficiaires")}>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {voc("Informations propres à vos projets (taille du ménage, superficie cultivée…). Une variable peut concerner tous les projets ou seulement certains : pour un projet qu'elle ne concerne pas, elle n'est pas demandée et vaut « NA » dans les exports. Elle apparaît aussi comme colonne dans le modèle d'import Excel.")}
        </Text>
        {edition ? (
          <FormulaireVariable key={edition.id ?? "nouvelle"} variable={edition} onFini={() => setEdition(null)} />
        ) : (
          <Group justify="flex-end">
            <Button leftSection={<Plus size={16} />} onClick={() => setEdition({})}>{voc("Ajouter une variable")}</Button>
          </Group>
        )}
        {variables.length === 0 ? (
          <Text size="sm" c="dimmed">{voc("Aucune variable pour l'instant.")}</Text>
        ) : (
          <Table verticalSpacing={6} highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Variable")}</Table.Th>
                <Table.Th>{voc("Type")}</Table.Th>
                <Table.Th>{voc("Projets")}</Table.Th>
                <Table.Th>{voc("Réponses")}</Table.Th>
                <Table.Th w={70} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {variables.map((variable) => (
                <Table.Tr key={variable.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{variable.libelle}</Text>
                    {variable.choix.length > 0 && <Text size="xs" c="dimmed">{variable.choix.join(" · ")}</Text>}
                  </Table.Td>
                  <Table.Td>
                    {TYPES_VARIABLE.find((t) => t.value === variable.type)?.label}
                    {variable.unite && <Text span size="xs" c="dimmed"> ({variable.unite})</Text>}
                  </Table.Td>
                  <Table.Td>
                    {variable.tous_les_projets ? (
                      <Badge variant="light" color="teal">{voc("Tous les projets")}</Badge>
                    ) : (
                      <Group gap={4}>
                        {variable.projets_codes.map((c) => <Badge key={c} variant="outline" size="sm">{c}</Badge>)}
                      </Group>
                    )}
                  </Table.Td>
                  <Table.Td>{variable.nb_reponses}</Table.Td>
                  <Table.Td>
                    <Group gap={2} wrap="nowrap">
                      <ActionIcon size="sm" variant="subtle" onClick={() => setEdition(variable)}>
                        <Pencil size={13} />
                      </ActionIcon>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        onClick={() =>
                          confirmerSuppression({
                            message: voc`Supprimer « ${variable.libelle} » ?${variable.nb_reponses ? ` Les ${variable.nb_reponses} réponse(s) saisie(s) seront effacées.` : ""}`,
                            onConfirm: () => supprimer.mutate(variable.id),
                          })
                        }
                      >
                        <Trash2 size={13} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Stack>
    </Modal>
  );
}
