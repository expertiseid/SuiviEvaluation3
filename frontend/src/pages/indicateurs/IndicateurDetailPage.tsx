import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ActionIcon, Badge, Group, Modal, Paper, Stack, Text, Title, Tooltip } from "@mantine/core";
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
import { locale } from "../../utils/i18n";
import type { Indicateur } from "../../types";

export function IndicateurDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const indicateurId = Number(id);
  const { data: indicateur, isLoading } = useIndicateur(indicateurId);
  const deleteIndicateur = useDeleteIndicateur();
  const [modalEditionOuvert, setModalEditionOuvert] = useState(false);
  const [editionActive, setEditionActive] = useState(false);

  if (isLoading || !indicateur) return <Text>{voc("Chargement…")}</Text>;

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
            {voc("Unité :")} {indicateur.unite} {voc("· Valeur de base :")} {indicateur.valeur_reference ?? "—"} {voc("· Cible :")}{" "}
            {indicateur.valeur_cible} {voc("· Fréquence :")} {indicateur.frequence_collecte}
          </Text>
          {indicateur.formule ? (
            <Paper withBorder p="sm" radius="md" mt="xs" maw={720}>
              <Text size="sm" fw={600} mb={4}>{voc("Calculé automatiquement par une formule : aucune valeur à saisir.")}</Text>
              {indicateur.formule_explication?.map((ligne, i) => <Text key={i} size="sm" c="dimmed">{ligne}</Text>)}
            </Paper>
          ) : (
            <Text c="dimmed" size="sm">
              {voc("La saisie des valeurs réalisées et leur évolution dans le temps se font depuis le module Suivi.")}</Text>
          )}
          <EtatIndicateur indicateur={indicateur} />
        </div>
        <Group gap="xs">
          <AlerteBadge palier={indicateur.palier_actuel} taux={indicateur.taux_realisation_actuel ?? undefined} />
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

      {!indicateur.formule && (
        <div>
          <Text size="sm" fw={600} mb="xs">{voc("Suivi détaillé par période")}</Text>
          <TranchesPlanifieesTab indicateurId={indicateurId} unite={indicateur.unite} />
        </div>
      )}

      <HistoriqueModification appLabel="indicators" modelName="indicateur" objectId={indicateurId} />

      <Modal opened={modalEditionOuvert} onClose={() => setModalEditionOuvert(false)} title={voc("Modifier l'indicateur")} size="xl">
        <IndicateurForm indicateur={indicateur} onDone={() => setModalEditionOuvert(false)} />
      </Modal>
    </Stack>
  );
}

/**
 * Calcul et état de l'indicateur : valeur retenue, taux (ou « non calculable »), règles de calcul,
 * variation entre les deux dernières périodes, actualisation selon la fréquence de collecte.
 */
function EtatIndicateur({ indicateur }: { indicateur: Indicateur }) {
  const nombre = (x: string | number | null) => (x === null || x === undefined ? "—" : Number(x).toLocaleString(locale()));
  const date = (d: string | null) => (d ? new Date(d).toLocaleDateString(locale()) : "—");
  const { variation, actualisation } = indicateur;
  const progres = variation && Number(variation.ecart) !== 0
    ? (Number(variation.ecart) > 0) === (indicateur.sens === "HAUSSE")
    : null;
  return (
    <Group gap="xs" mt="xs">
      <Badge variant="light" color="gray">
        {voc("Valeur retenue :")} {nombre(indicateur.valeur_actuelle)} {indicateur.unite}
        {indicateur.formule ? voc(" (calculée)") : indicateur.agregation === "DERNIERE" ? voc(" (dernière saisie)") : voc(" (somme des saisies)")}
      </Badge>
      <Badge variant="light" color={indicateur.taux_realisation_actuel === null ? "gray" : "blue"}>
        {indicateur.taux_realisation_actuel === null
          ? voc("Taux non calculable")
          : `${voc("Taux :")} ${indicateur.taux_realisation_actuel.toLocaleString(locale())} %`}
        {indicateur.calcul_taux === "PROGRESSION" ? voc(" · progression depuis la valeur de base") : ""}
      </Badge>
      {indicateur.sens === "BAISSE" && <Badge variant="light" color="grape">{voc("Plus bas = mieux")}</Badge>}
      {variation && (
        <Badge variant="light" color={progres === null ? "gray" : progres ? "teal" : "red"}>
          {voc("Dernière période :")} {Number(variation.ecart) > 0 ? "+" : ""}{nombre(variation.ecart)} {indicateur.unite}
          {variation.pourcent !== null ? ` (${variation.pourcent > 0 ? "+" : ""}${variation.pourcent.toLocaleString(locale())} %)` : ""}
        </Badge>
      )}
      {actualisation.en_retard ? (
        <Badge variant="filled" color="orange">
          {voc`Non actualisé : valeur attendue depuis le ${date(actualisation.attendue_le)}`}
        </Badge>
      ) : actualisation.attendue_le && (
        <Badge variant="light" color="gray">{voc`Prochaine valeur attendue le ${date(actualisation.attendue_le)}`}</Badge>
      )}
    </Group>
  );
}
