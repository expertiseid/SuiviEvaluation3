import { useMemo, useState } from "react";
import { ListTree, Pencil, Trash2 } from "lucide-react";
import { ActionIcon, Button, Card, Group, Modal, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useCreateNiveauActivite,
  useDeleteNiveauActivite,
  useNiveauxActivite,
  useUpdateNiveauActivite,
} from "../../api/projects";
import { EmptyState } from "../../components/common/EmptyState";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";
import type { NiveauActivite } from "../../types";
import { voc } from "../../utils/vocabulaire";

function ModalRenommer({
  opened,
  onClose,
  niveau,
}: {
  opened: boolean;
  onClose: () => void;
  niveau: NiveauActivite | null;
}) {
  const updateNiveau = useUpdateNiveauActivite();
  const [nom, setNom] = useState(niveau?.nom_niveau ?? "");

  async function enregistrer() {
    if (!niveau || !nom.trim()) {
      notifications.show({ message: voc("Le nom du niveau est requis."), color: "orange" });
      return;
    }
    try {
      await updateNiveau.mutateAsync({ id: niveau.id, payload: { nom_niveau: nom.trim() } });
      notifications.show({ message: voc("Niveau renommé"), color: "green" });
      onClose();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors du renommage")), color: "red" });
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={voc("Renommer le niveau")}>
      <Stack gap="sm">
        <TextInput label={voc("Nom affiché")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} required />
        <Group justify="flex-end">
          <Button onClick={enregistrer} loading={updateNiveau.isPending}>{voc("Enregistrer")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Noms des niveaux de la planification de ce projet, du plus haut au plus bas
 * (ex : « Objectif général » → « Objectif spécifique » → « Activité », ou
 * « Résultat » → « Pilier » → « Activité ») — aucun niveau n'est imposé.
 * Créés automatiquement à l'import Excel (une colonne avant « Sous-activité »
 * = un niveau), modifiables ici sans devoir réimporter. Purement cosmétique : renommer ou supprimer un
 * niveau ne change rien aux activités déjà créées à cette profondeur.
 */
export function NiveauxActiviteTab({ projetId }: { projetId: number }) {
  const { data: niveaux, isLoading } = useNiveauxActivite(projetId);
  const createNiveau = useCreateNiveauActivite();
  const deleteNiveau = useDeleteNiveauActivite();
  const [nomNouveauNiveau, setNomNouveauNiveau] = useState("");
  const [niveauEnEdition, setNiveauEnEdition] = useState<NiveauActivite | null>(null);

  const tries = useMemo(() => [...(niveaux ?? [])].sort((a, b) => a.profondeur - b.profondeur), [niveaux]);

  async function ajouter() {
    if (!nomNouveauNiveau.trim()) {
      notifications.show({ message: voc("Le nom du niveau est requis."), color: "orange" });
      return;
    }
    const prochaineProfondeur = tries.length > 0 ? tries[tries.length - 1].profondeur + 1 : 0;
    try {
      await createNiveau.mutateAsync({
        projet: projetId,
        profondeur: prochaineProfondeur,
        nom_niveau: nomNouveauNiveau.trim(),
      });
      notifications.show({ message: voc("Niveau ajouté"), color: "green" });
      setNomNouveauNiveau("");
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'ajout du niveau")), color: "red" });
    }
  }

  function supprimer(niveau: NiveauActivite) {
    confirmerSuppression({
      message: voc`Supprimer le niveau « ${niveau.nom_niveau} » ? Les éléments déjà créés à ce niveau ne sont pas affectés — ils s'afficheront simplement avec le nom par défaut « Activité ».`,
      onConfirm: async () => {
        try {
          await deleteNiveau.mutateAsync(niveau.id);
          notifications.show({ message: voc("Niveau supprimé"), color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression")), color: "red" });
        }
      },
    });
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Text fw={600} mb="xs">{voc("Configuration des niveaux")}</Text>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Les niveaux de la planification de ce projet, du plus haut au plus bas. Leur nom et leur nombre sont libres : par exemple « Objectif général » → « Objectif spécifique » → « Activité », ou « Résultat » → « Composante » → « Activité ». Renommer un niveau change seulement son nom affiché, jamais les éléments déjà saisis.")}</Text>

      {isLoading ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : tries.length === 0 ? (
        <EmptyState
          icon={<ListTree size={32} strokeWidth={1.5} />}
          message={voc("Aucun niveau nommé pour l'instant — les éléments s'affichent sous le nom « Activité ». Ajoute ci-dessous les niveaux de ta planification, du plus haut au plus bas.")}
        />
      ) : (
        <Stack gap={6} mb="sm">
          {tries.map((niveau) => (
            <Group key={niveau.id} gap={6} wrap="nowrap" justify="space-between">
              <Group gap={6} wrap="nowrap">
                <Text size="sm" c="dimmed" w={20}>{niveau.profondeur + 1}.</Text>
                <Text size="sm" fw={500}>{niveau.nom_niveau}</Text>
              </Group>
              <Group gap={2} wrap="nowrap">
                <Tooltip label={voc("Renommer")}>
                  <ActionIcon size="sm" variant="subtle" onClick={() => setNiveauEnEdition(niveau)}>
                    <Pencil size={13} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label={voc("Supprimer")}>
                  <ActionIcon size="sm" variant="subtle" color="red" loading={deleteNiveau.isPending} onClick={() => supprimer(niveau)}>
                    <Trash2 size={13} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          ))}
        </Stack>
      )}

      <Group gap="xs" align="flex-end">
        <TextInput
          size="xs"
          label={voc("Ajouter un niveau")}
          placeholder={voc("Ex : Résultat")}
          value={nomNouveauNiveau}
          onChange={(e) => setNomNouveauNiveau(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button size="xs" variant="light" onClick={ajouter} loading={createNiveau.isPending}>
          {voc("Ajouter")}
        </Button>
      </Group>

      <ModalRenommer
        key={niveauEnEdition?.id ?? "aucun"}
        opened={!!niveauEnEdition}
        onClose={() => setNiveauEnEdition(null)}
        niveau={niveauEnEdition}
      />
    </Card>
  );
}
