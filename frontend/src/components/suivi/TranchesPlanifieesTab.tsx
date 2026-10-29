import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { ActionIcon, Button, Card, Group, NumberInput, Progress, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateTranchePlanifiee, useDeleteTranchePlanifiee, useTranchesPlanifiees } from "../../api/suivi";
import { EmptyState } from "../common/EmptyState";
import { confirmerSuppression } from "../common/confirmerSuppression";
import { StatusBadge, type StatusTone } from "../common/StatusBadge";
import { messageErreurApi } from "../../utils/erreurs";
import type { TranchePlanifiee } from "../../types";
import { voc } from "../../utils/vocabulaire";

const LIBELLE_STATUT: Record<TranchePlanifiee["statut"], string> = {
  ATTEINTE: voc("Atteinte"),
  EN_RETARD: voc("En retard"),
  EN_COURS: voc("En cours"),
};

const TONE_STATUT: Record<TranchePlanifiee["statut"], StatusTone> = {
  ATTEINTE: "success",
  EN_RETARD: "danger",
  EN_COURS: "neutral",
};

/**
 * Découpe d'une cible globale (Activité ou Indicateur) en sous-cibles par
 * période choisie librement (année, trimestre, mois...) — le réalisé par
 * tranche est calculé côté backend à partir des PointSuivi/ValeurIndicateur
 * déjà saisis, rien à ressaisir ici.
 */
export function TranchesPlanifieesTab({
  activiteId,
  indicateurId,
  unite,
}: {
  activiteId?: number;
  indicateurId?: number;
  unite?: string;
}) {
  const { data: tranches, isLoading } = useTranchesPlanifiees({ activite: activiteId, indicateur: indicateurId });
  const createTranche = useCreateTranchePlanifiee();
  const deleteTranche = useDeleteTranchePlanifiee();

  const [libelle, setLibelle] = useState("");
  const [debut, setDebut] = useState<string | null>(null);
  const [fin, setFin] = useState<string | null>(null);
  const [cible, setCible] = useState<number | string>("");

  const sommeCibles = (tranches ?? []).reduce((total, t) => total + Number(t.cible ?? 0), 0);

  async function ajouter() {
    if (!libelle.trim() || !debut || !fin || cible === "") {
      notifications.show({ message: voc("Libellé, dates et cible sont requis."), color: "orange" });
      return;
    }
    try {
      await createTranche.mutateAsync({
        activite: activiteId,
        indicateur: indicateurId,
        libelle: libelle.trim(),
        periode_debut: debut,
        periode_fin: fin,
        cible: Number(cible),
      });
      notifications.show({ message: voc("Tranche ajoutée"), color: "green" });
      setLibelle("");
      setDebut(null);
      setFin(null);
      setCible("");
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'ajout de la tranche")), color: "red" });
    }
  }

  function supprimer(tranche: TranchePlanifiee) {
    confirmerSuppression({
      message: voc`Supprimer la tranche "${tranche.libelle}" ? Les saisies de suivi déjà faites ne sont pas supprimées, seule cette répartition par période l'est.`,
      onConfirm: async () => {
        try {
          await deleteTranche.mutateAsync(tranche.id);
          notifications.show({ message: voc("Tranche supprimée"), color: "green" });
        } catch (error) {
          notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la suppression")), color: "red" });
        }
      },
    });
  }

  return (
    <Card withBorder padding="md" radius="md">
      <Group align="flex-end" mb="md" wrap="wrap">
        <TextInput label={voc("Période")} placeholder={voc("Ex : Année 1, T1 2026…")} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} />
        <DateInput label={voc("Du")} value={debut} onChange={setDebut} />
        <DateInput label={voc("Au")} value={fin} onChange={setFin} />
        <NumberInput label={voc`Cible${unite ? ` (${unite})` : ""}`} value={cible} onChange={setCible} min={0} w={140} />
        <Button leftSection={<Plus size={16} />} onClick={ajouter} loading={createTranche.isPending}>
          {voc("Ajouter")}
        </Button>
      </Group>

      {isLoading ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : !tranches || tranches.length === 0 ? (
        <EmptyState message={voc("Aucune tranche définie — la cible reste suivie uniquement en cumul global.")} />
      ) : (
        <>
          <Table.ScrollContainer minWidth={600}>
            <Table verticalSpacing="sm" striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Période")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Dates")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Progression")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Statut")}</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {tranches.map((t) => (
                  <Table.Tr key={t.id}>
                    <Table.Td>
                      <Text size="sm" fw={500}>{t.libelle}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">{t.periode_debut} → {t.periode_fin}</Text>
                    </Table.Td>
                    <Table.Td style={{ minWidth: 160 }}>
                      <Text size="xs" mb={2}>
                        {t.realise ?? 0} / {t.cible ?? "—"}{unite ? ` ${unite}` : ""}{t.taux !== null ? ` · ${t.taux}%` : ""}
                      </Text>
                      <Progress value={t.taux ?? 0} color={TONE_STATUT[t.statut] === "danger" ? "red" : TONE_STATUT[t.statut] === "success" ? "green" : "blue"} size="sm" />
                    </Table.Td>
                    <Table.Td>
                      <StatusBadge tone={TONE_STATUT[t.statut]}>{LIBELLE_STATUT[t.statut]}</StatusBadge>
                    </Table.Td>
                    <Table.Td>
                      <Tooltip label={voc("Supprimer")}>
                        <ActionIcon variant="subtle" color="red" onClick={() => supprimer(t)}>
                          <Trash2 size={16} />
                        </ActionIcon>
                      </Tooltip>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Text size="xs" c="dimmed" mt="sm">
            {voc("Somme des cibles de toutes les tranches :")} {sommeCibles}{unite ? ` ${unite}` : ""} {voc(" — à comparer à la cible globale de l'activité/indicateur.")}</Text>
        </>
      )}
    </Card>
  );
}
