import { useState } from "react";
import { ActionIcon, Badge, Button, Card, Checkbox, Group, Stack, Table, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FileText, Folder, RotateCcw, Trash2 } from "lucide-react";
import { type ElementCorbeille, useCorbeille, useRestaurerCorbeille, useViderCorbeille } from "../../api/documents";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";

const cle = (e: ElementCorbeille) => `${e.type}${e.id}`;

/**
 * Corbeille des documents : dossiers et documents supprimés, à restaurer (à leur place, ou à la racine
 * si leur dossier n'existe plus) ou à supprimer définitivement. Un dossier revient avec son contenu.
 */
export function CorbeillePage() {
  const { data, isLoading } = useCorbeille();
  const restaurer = useRestaurerCorbeille();
  const vider = useViderCorbeille();
  const { peutEcrire } = useAccesModules();
  const ecriture = peutEcrire("/documents");
  const [selection, setSelection] = useState<Set<string>>(new Set());

  const elements = [...(data?.dossiers ?? []), ...(data?.documents ?? [])]
    .sort((a, b) => b.supprime_le.localeCompare(a.supprime_le));
  const toutCoche = elements.length > 0 && elements.every((e) => selection.has(cle(e)));
  const designer = (liste: ElementCorbeille[]) => ({
    dossiers: liste.filter((e) => e.type === "dossier").map((e) => e.id),
    documents: liste.filter((e) => e.type === "document").map((e) => e.id),
  });
  const choisis = elements.filter((e) => selection.has(cle(e)));
  const basculer = (k: string) => setSelection((avant) => {
    const apres = new Set(avant);
    if (apres.has(k)) apres.delete(k);
    else apres.add(k);
    return apres;
  });

  const restaurerListe = async (liste: ElementCorbeille[]) => {
    try {
      const { nombre } = await restaurer.mutateAsync(designer(liste));
      setSelection(new Set());
      notifications.show({ color: "teal", message: voc`${nombre} élément(s) restauré(s)` });
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("La restauration n'a pas abouti.")) });
    }
  };
  const supprimerDefinitivement = (liste: ElementCorbeille[] | "tout") => confirmerSuppression({
    message: liste === "tout"
      ? voc("Vider la corbeille ? Tous les éléments qu'elle contient seront supprimés définitivement, fichiers compris. Cette action est irréversible.")
      : voc`Supprimer définitivement ${liste.length} élément(s), fichiers compris ? Cette action est irréversible.`,
    labelConfirmer: liste === "tout" ? voc("Vider la corbeille") : voc("Supprimer définitivement"),
    onConfirm: async () => {
      try {
        const { nombre } = await vider.mutateAsync(liste === "tout" ? { tout: true } : designer(liste));
        setSelection(new Set());
        notifications.show({ color: "green", message: voc`${nombre} élément(s) supprimé(s) définitivement` });
      } catch (error) {
        notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de la suppression")) });
      }
    },
  });

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <div>
          <TitreRubrique route="/corbeille" defaut={voc("Corbeille")} />
          <Text c="dimmed">{voc("Dossiers et documents supprimés : restaurez-les ou supprimez-les définitivement.")}</Text>
          <Text c="dimmed" size="sm">{voc`Ce qui reste plus de ${data?.duree_conservation_jours ?? 30} jours dans la corbeille est supprimé définitivement, automatiquement.`}</Text>
        </div>
        {ecriture && elements.length > 0 && (
          <Button color="red" variant="light" leftSection={<Trash2 size={16} />} onClick={() => supprimerDefinitivement("tout")}>
            {voc("Vider la corbeille")}
          </Button>
        )}
      </Group>

      <Card withBorder padding="md" radius="md">
        {isLoading ? (
          <Text c="dimmed">{voc("Chargement…")}</Text>
        ) : elements.length === 0 ? (
          <Stack align="center" gap={6} py="xl">
            <Trash2 size={44} strokeWidth={1.3} color="var(--mantine-color-gray-5)" />
            <Text c="dimmed" size="sm">{voc("La corbeille est vide.")}</Text>
          </Stack>
        ) : (
          <Stack gap="sm">
            {ecriture && (
              <Group justify="space-between" gap="xs" px="xs" py={6} bg={selection.size ? "teal.0" : undefined} style={{ borderRadius: 8 }}>
                <Checkbox size="sm" label={selection.size ? voc`${selection.size} sélectionné(s)` : voc("Tout sélectionner")}
                  checked={toutCoche} indeterminate={selection.size > 0 && !toutCoche}
                  onChange={() => setSelection(toutCoche ? new Set() : new Set(elements.map(cle)))} />
                {selection.size > 0 && (
                  <Group gap="xs">
                    <Button size="xs" variant="default" leftSection={<RotateCcw size={14} />} loading={restaurer.isPending}
                      onClick={() => restaurerListe(choisis)}>{voc("Restaurer")}</Button>
                    <Button size="xs" color="red" variant="light" leftSection={<Trash2 size={14} />}
                      onClick={() => supprimerDefinitivement(choisis)}>{voc("Supprimer définitivement")}</Button>
                  </Group>
                )}
              </Group>
            )}
            <Table.ScrollContainer minWidth={640}>
              <Table verticalSpacing="xs" highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    {ecriture && <Table.Th w={36} />}
                    <Table.Th>{voc("Nom")}</Table.Th>
                    <Table.Th>{voc("Emplacement")}</Table.Th>
                    <Table.Th>{voc("Supprimé le")}</Table.Th>
                    <Table.Th>{voc("Par")}</Table.Th>
                    <Table.Th>{voc("Suppression définitive le")}</Table.Th>
                    {ecriture && <Table.Th w={80} />}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {elements.map((e) => (
                    <Table.Tr key={cle(e)} bg={selection.has(cle(e)) ? "teal.0" : undefined}>
                      {ecriture && (
                        <Table.Td>
                          <Checkbox size="sm" checked={selection.has(cle(e))} aria-label={voc`Sélectionner ${e.nom}`} onChange={() => basculer(cle(e))} />
                        </Table.Td>
                      )}
                      <Table.Td>
                        <Group gap="xs" wrap="nowrap">
                          {e.type === "dossier"
                            ? <Folder size={20} fill="white" color="var(--mantine-color-teal-7)" />
                            : <FileText size={20} color="var(--mantine-color-blue-6)" />}
                          <Text size="sm" fw={e.type === "dossier" ? 600 : 500}>{e.nom}</Text>
                          {e.type === "dossier" && !!e.nombre_elements && (
                            <Badge size="xs" variant="light" color="gray">{voc`${e.nombre_elements} élément(s)`}</Badge>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td><Text size="sm" c={e.projet_nom ? undefined : "dimmed"}>{e.projet_nom || voc("Documents libres")}</Text></Table.Td>
                      <Table.Td><Text size="sm">{new Date(e.supprime_le).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" })}</Text></Table.Td>
                      <Table.Td><Text size="sm">{e.supprime_par_nom || "—"}</Text></Table.Td>
                      <Table.Td><Text size="sm" c="orange.8">{new Date(e.supprime_definitivement_le).toLocaleDateString(locale())}</Text></Table.Td>
                      {ecriture && (
                        <Table.Td>
                          <Group gap={4} wrap="nowrap">
                            <Tooltip label={voc("Restaurer")}>
                              <ActionIcon variant="subtle" color="teal" aria-label={voc("Restaurer")} onClick={() => restaurerListe([e])}>
                                <RotateCcw size={16} />
                              </ActionIcon>
                            </Tooltip>
                            <Tooltip label={voc("Supprimer définitivement")}>
                              <ActionIcon variant="subtle" color="red" aria-label={voc("Supprimer définitivement")} onClick={() => supprimerDefinitivement([e])}>
                                <Trash2 size={16} />
                              </ActionIcon>
                            </Tooltip>
                          </Group>
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
