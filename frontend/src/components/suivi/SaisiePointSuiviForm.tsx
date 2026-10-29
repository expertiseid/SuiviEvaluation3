import { useMemo, useState } from "react";
import { Button, Divider, Group, NumberInput, Select, Stack, Text, Textarea } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreatePointSuivi, useUpdatePointSuivi } from "../../api/suivi";
import { DocumentsTab } from "../documents/DocumentsTab";
import { messageErreurApi } from "../../utils/erreurs";
import type { SuiviHistoriquePoint } from "../../types";
import { voc } from "../../utils/vocabulaire";

export function SaisiePointSuiviForm({
  activiteId,
  sousActiviteId,
  statutsDisponibles,
  avecBudget,
  avecQuantite = true,
  pointExistant,
  historiqueExistant,
  bornes,
  onDone,
}: {
  activiteId?: number;
  sousActiviteId?: number;
  statutsDisponibles: { value: string; label: string }[];
  avecBudget: boolean;
  /** false : méthode de calcul sans quantité (tâches, livrables...) — période, budget, statut et commentaire seulement. */
  avecQuantite?: boolean;
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
      notifications.show({ message: voc("Merci de renseigner la période."), color: "orange" });
      return;
    }
    try {
      const payload = {
        activite: activiteId ?? null,
        sous_activite: sousActiviteId ?? null,
        periode_debut: periodeDebut,
        periode_fin: periodeFin,
        quantite_realisee: !avecQuantite || quantiteRealisee === "" ? null : Number(quantiteRealisee),
        budget_realise: avecBudget && budgetRealise !== "" ? Number(budgetRealise) : null,
        statut: statut ?? "",
        commentaire,
      };
      if (enEdition) {
        await updatePoint.mutateAsync({ id: pointExistant!.id, payload } as never);
      } else {
        await createPoint.mutateAsync(payload as never);
      }
      notifications.show({ message: enEdition ? voc("Point de suivi modifié") : voc("Point de suivi enregistré"), color: "green" });
      onDone();
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("Erreur lors de la saisie")), color: "red" });
    }
  }

  return (
    <Stack gap="sm">
      <Group grow>
        <DateInput
          label={voc("Début de période")}
          value={periodeDebut}
          onChange={setPeriodeDebut}
          minDate={bornes?.debut}
          maxDate={bornes?.fin}
          required
        />
        <DateInput
          label={voc("Fin de période")}
          value={periodeFin}
          onChange={setPeriodeFin}
          minDate={bornes?.debut}
          maxDate={bornes?.fin}
          required
        />
      </Group>
      <Group grow>
        {avecQuantite && (
        <NumberInput
          label={voc("Quantité réalisée pendant cette période")}
          description={voc("Ce qui a été fait entre le début et la fin de cette période précise (pas le total depuis le début).")}
          value={quantiteRealisee}
          onChange={setQuantiteRealisee}
          min={0}
        />
        )}
        {avecBudget && (
          <NumberInput
            label={voc("Budget dépensé pendant cette période (FCFA)")}
            value={budgetRealise}
            onChange={setBudgetRealise}
            min={0}
          />
        )}
      </Group>
      {avecQuantite && nouveauCumul !== null && (
        <Text size="xs" c="dimmed">
          {voc("Total cumulé après cette saisie :")} {nouveauCumul}
        </Text>
      )}
      <Select label={voc("Statut à cette date")} data={statutsDisponibles} value={statut} onChange={setStatut} clearable />
      <Textarea label={voc("Commentaire")} value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />
      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createPoint.isPending || updatePoint.isPending}>
          {enEdition ? voc("Enregistrer les modifications") : voc("Enregistrer")}
        </Button>
      </Group>

      {activiteId !== undefined && (
        <>
          <Divider label={voc("Documents liés à cette activité")} labelPosition="left" mt="sm" />
          <DocumentsTab activiteId={activiteId} />
        </>
      )}
    </Stack>
  );
}
