import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ActionIcon, Group, Modal, Stack, Text, Title, Tooltip } from "@mantine/core";
import { Pencil, Trash2 } from "lucide-react";
import { notifications } from "@mantine/notifications";
import { useDeleteIndicateur, useIndicateur } from "../../api/indicators";
import { AlerteBadge } from "../../components/indicators/AlerteBadge";
import { HistoriqueModification } from "../../components/audit/HistoriqueModification";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { BoutonModeEdition } from "../../components/common/BoutonModeEdition";
import { TranchesPlanifieesTab } from "../../components/suivi/TranchesPlanifieesTab";
import { IndicateurForm } from "./IndicateurForm";
import { voc } from "../../utils/vocabulaire";

export function IndicateurDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const indicateurId = Number(id);
  const { data: indicateur, isLoading } = useIndicateur(indicateurId);
  const deleteIndicateur = useDeleteIndicateur();
  const [modalEditionOuvert, setModalEditionOuvert] = useState(false);
  const [editionActive, setEditionActive] = useState(false);

  if (isLoading || !indicateur) return <Text>Chargement…</Text>;

  function handleSupprimer() {
    if (!indicateur) return;
    confirmerSuppression({
      message: voc`Supprimer l'indicateur "${indicateur.libelle}" ainsi que toutes ses valeurs saisies ? Cette action est irréversible.`,
      onConfirm: async () => {
        try {
          await deleteIndicateur.mutateAsync(indicateurId);
          notifications.show({ message: voc("Indicateur supprimé"), color: "green" });
          navigate("/indicateurs");
        } catch {
          notifications.show({ message: voc("Erreur lors de la suppression de l'indicateur"), color: "red" });
        }
      },
    });
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2}>{indicateur.libelle}</Title>
          <Text c="dimmed">
            Unité : {indicateur.unite} · Valeur de base : {indicateur.valeur_reference ?? "—"} · Cible :{" "}
            {indicateur.valeur_cible} · Fréquence : {indicateur.frequence_collecte}
          </Text>
          <Text c="dimmed" size="sm">
            {voc("La saisie des valeurs réalisées et leur évolution dans le temps se font depuis le module Suivi.")}</Text>
        </div>
        <Group gap="xs">
          <AlerteBadge palier={indicateur.palier_actuel} taux={indicateur.taux_realisation_actuel} />
          <BoutonModeEdition actif={editionActive} onToggle={() => setEditionActive((v) => !v)} />
          {editionActive && (
          <Group gap="xs">
            <Tooltip label={voc("Modifier l'indicateur")}>
              <ActionIcon variant="subtle" onClick={() => setModalEditionOuvert(true)}>
                <Pencil size={18} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={voc("Supprimer l'indicateur")}>
              <ActionIcon variant="subtle" color="red" loading={deleteIndicateur.isPending} onClick={handleSupprimer}>
                <Trash2 size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
          )}
        </Group>
      </Group>

      <div>
        <Text size="sm" fw={600} mb="xs">{voc("Suivi détaillé par période")}</Text>
        <TranchesPlanifieesTab indicateurId={indicateurId} unite={indicateur.unite} />
      </div>

      <HistoriqueModification appLabel="indicators" modelName="indicateur" objectId={indicateurId} />

      <Modal opened={modalEditionOuvert} onClose={() => setModalEditionOuvert(false)} title={voc("Modifier l'indicateur")} size="lg">
        <IndicateurForm indicateur={indicateur} onDone={() => setModalEditionOuvert(false)} />
      </Modal>
    </Stack>
  );
}
