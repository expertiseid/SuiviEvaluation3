import { useMemo, useState } from "react";
import { Button, FileInput, Group, NumberInput, Stack, Text, Textarea } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateValeurIndicateur, useUpdateValeurIndicateur } from "../../api/indicators";
import { useUploadPieceJustificative } from "../../api/documents";
import { messageErreurApi } from "../../utils/erreurs";
import type { SuiviHistoriqueValeurIndicateur } from "../../types";
import { voc } from "../../utils/vocabulaire";

export function SaisieValeurIndicateurForm({
  indicateurId,
  valeurExistante,
  historiqueExistant,
  bornes,
  onDone,
}: {
  indicateurId: number;
  valeurExistante?: SuiviHistoriqueValeurIndicateur;
  historiqueExistant?: { id: number; valeur_realisee: string }[];
  /** Saisie depuis le suivi par période : dates pré-remplies et limitées à la période. */
  bornes?: { debut: string; fin: string };
  onDone: () => void;
}) {
  const enEdition = !!valeurExistante;
  const createValeur = useCreateValeurIndicateur();
  const updateValeur = useUpdateValeurIndicateur();
  const uploadPiece = useUploadPieceJustificative();

  const [periodeDebut, setPeriodeDebut] = useState<string | null>(valeurExistante?.periode_debut ?? bornes?.debut ?? null);
  const [periodeFin, setPeriodeFin] = useState<string | null>(valeurExistante?.periode_fin ?? bornes?.fin ?? null);
  const [valeur, setValeur] = useState<number | string>(valeurExistante?.valeur_realisee ?? "");
  const [commentaire, setCommentaire] = useState(valeurExistante?.commentaire ?? "");
  const [fichier, setFichier] = useState<File | null>(null);

  const cumulAutresSaisies = useMemo(() => {
    if (!historiqueExistant) return null;
    return historiqueExistant
      .filter((h) => h.id !== valeurExistante?.id)
      .reduce((somme, h) => somme + Number(h.valeur_realisee), 0);
  }, [historiqueExistant, valeurExistante]);

  const nouveauCumul = cumulAutresSaisies !== null && valeur !== "" ? cumulAutresSaisies + Number(valeur) : null;

  async function handleSubmit() {
    if (!periodeDebut || !periodeFin || valeur === "") {
      notifications.show({ message: voc("Merci de renseigner la période et la valeur."), color: "orange" });
      return;
    }
    try {
      const payload = {
        indicateur: indicateurId,
        periode_debut: periodeDebut,
        periode_fin: periodeFin,
        valeur_realisee: String(valeur),
        commentaire,
      };
      const resultat = enEdition
        ? await updateValeur.mutateAsync({ id: valeurExistante!.id, payload })
        : await createValeur.mutateAsync(payload as never);

      if (fichier) {
        const formData = new FormData();
        formData.append("fichier", fichier);
        formData.append("nom", fichier.name);
        formData.append("valeur_indicateur", String(resultat.id));
        await uploadPiece.mutateAsync(formData);
      }

      notifications.show({ message: enEdition ? voc("Valeur modifiée") : voc("Valeur enregistrée"), color: "green" });
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
      <NumberInput
        label={voc("Valeur réalisée pendant cette période")}
        description={voc("Ce qui a été atteint entre le début et la fin de cette période précise (pas le total depuis le début).")}
        value={valeur}
        onChange={setValeur}
        min={0}
        required
      />
      {nouveauCumul !== null && (
        <Text size="xs" c="dimmed">
          {voc("Total cumulé après cette saisie :")} {nouveauCumul}
        </Text>
      )}
      <Textarea label={voc("Commentaire")} value={commentaire} onChange={(e) => setCommentaire(e.currentTarget.value)} />
      <FileInput label={voc("Pièce justificative (optionnel)")} value={fichier} onChange={setFichier} clearable />
      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createValeur.isPending || updateValeur.isPending || uploadPiece.isPending}>
          {enEdition ? voc("Enregistrer les modifications") : voc("Enregistrer")}
        </Button>
      </Group>
    </Stack>
  );
}
