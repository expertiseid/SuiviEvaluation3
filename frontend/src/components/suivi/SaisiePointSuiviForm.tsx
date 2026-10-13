import { useMemo, useState } from "react";
import { Button, Divider, Group, NumberInput, Select, Stack, Text, Textarea } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreatePointSuivi, useUpdatePointSuivi } from "../../api/suivi";
import { DocumentsTab } from "../documents/DocumentsTab";
import { messageErreurApi } from "../../utils/erreurs";
import type { SuiviHistoriquePoint } from "../../types";

export function SaisiePointSuiviForm({
  activiteId,
  sousActiviteId,
  statutsDisponibles,
  avecBudget,
  pointExistant,
  historiqueExistant,
  bornes,
  onDone,
}: {
  activiteId?: number;
  sousActiviteId?: number;
  statutsDisponibles: { value: string; label: string }[];
  avecBudget: boolean;
  pointExistant?: SuiviHistoriquePoint;
  historiqueExistant?: { id: number; quantite_realisee: string | null }[];
  /** Saisie depuis le suivi par période : dates pré-remplies et limitées à la période. */
  bornes?: { debut: string; fin: string };
  onDone: () => void;
}) {
  const enEdition = !!pointExistant;
  const createPoint = useCreatePointSuivi();
  const updatePoint = useUpdatePointSuivi();
  const [periodeDebut, setPeriodeDebut] = useState<string | null>(pointExistant?.periode_debut ?? bornes?.debut ?? null);
  const [periodeFin, setPeriodeFin] = useState<string | null>(pointExistant?.periode_fin ?? bornes?.fin ?? null);
  const [quantiteRealisee, setQuantiteRealisee] = useState<number | string>(pointExistant?.quantite_realisee ?? "");
  const [budgetRealise, setBudgetRealise] = useState<number | string>(pointExistant?.budget_realise ?? "");
  const [statut, setStatut] = useState<string | null>(pointExistant?.statut || null);
  const [commentaire, setCommentaire] = useState(pointExistant?.commentaire ?? "");

  const cumulAutresSaisies = useMemo(() => {
    if (!historiqueExistant) return null;
    return historiqueExistant
      .filter((h) => h.id !== pointExistant?.id && h.quantite_realisee !== null)
      .reduce((somme, h) => somme + Number(h.quantite_realisee), 0);
  }, [historiqueExistant, pointExistant]);

  const nouveauCumul =
    cumulAutresSaisies !== null && quantiteRealisee !== "" ? cumulAutresSaisies + Number(quantiteRealisee) : null;

  async function handleSubmit() {
    if (!periodeDebut || !periodeFin) {
      notifications.show({ message: "Merci de renseigner la période.", color: "orange" });
      return;
    }
    try {
      const payload = {
        activite: activiteId ?? null,
        sous_activite: sousActiviteId ?? null,
        periode_debut: periodeDebut,
        periode_fin: periodeFin,
        quantite_realisee: quantiteRealisee === "" ? null : Number(quantiteRealisee),
        budget_realise: avecBudget && budgetRealise !== "" ? Number(budgetRealise) : null,
        statut: statut ?? "",
        commentaire,
      };
      if (enEdition) {
        await updatePoint.mutateAsync({ id: pointExistant!.id, payload } as never);
      } else {
        await createPoint.mutateAsync(payload as never);
      }
      notifications.show({ message: enEdition ? "Point de suivi modifié" : "Point de suivi enregistré", color: "green" });
      onDone();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, "Erreur lors de la saisie"), color: "red" });
    }
  }

  return (
    <Stack gap="sm">
      <Group grow>
        <DateInput
          label="Début de période"
          value={periodeDebut}
          onChange={setPeriodeDebut}
          minDate={bornes?.debut}
          maxDate={bornes?.fin}
          required
        />
        <DateInput
          label="Fin de période"
          value={periodeFin}
          onChange={setPeriodeFin}
          minDate={bornes?.debut}
          maxDate={bornes?.fin}
          required
        />
      </Group>
      <Group grow>
        <NumberInput
          label="Quantité réalisée pendant cette période"
          description="Ce qui a été fait entre le début et la fin de cette période précise (pas le total depuis le début)."
          value={quantiteRealisee}
          onChange={setQuantiteRealisee}
          min={0}
        />
        {avecBudget && (
          <NumberInput
            label="Budget dépensé pendant cette période (FCFA)"
            value={budgetRealise}
            onChange={setBudgetRealise}
            min={0}
          />
        )}
      </Group>
      {nouveauCumul !== null && (
        <Text size="xs" c="dimmed">
          Total cumulé après cette saisie : {nouveauCumul}
        </Text>
      )}
      <Select label="Statut à cette date" data={statutsDisponibles} value={statut} onChange={setStatut} clearable />
      <Textarea label="Commentaire" value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />
      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createPoint.isPending || updatePoint.isPending}>
          {enEdition ? "Enregistrer les modifications" : "Enregistrer"}
        </Button>
      </Group>

      {activiteId !== undefined && (
        <>
          <Divider label="Documents liés à cette activité" labelPosition="left" mt="sm" />
          <DocumentsTab activiteId={activiteId} />
        </>
      )}
    </Stack>
  );
}
