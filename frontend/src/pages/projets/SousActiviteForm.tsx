import { useMemo, useState } from "react";
import { Autocomplete, Button, Group, NumberInput, Select, Stack, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateSousActivite } from "../../api/projects";
import { useElementsStrategiques, useTypesNiveaux } from "../../api/strategy";
import { voc } from "../../utils/vocabulaire";

export function SousActiviteForm({
  activiteId,
  cadreStrategiqueId,
  onDone,
}: {
  activiteId: number;
  cadreStrategiqueId: number | null;
  onDone: () => void;
}) {
  const { data: axes } = useElementsStrategiques(cadreStrategiqueId ? { cadre_strategique: cadreStrategiqueId } : undefined);
  const { data: niveaux } = useTypesNiveaux(cadreStrategiqueId);
  const createSousActivite = useCreateSousActivite();

  const niveauFeuille = useMemo(
    () => (niveaux && niveaux.length > 0 ? niveaux.reduce((a, b) => (b.ordre > a.ordre ? b : a)) : null),
    [niveaux],
  );
  const activitesDuCadre = useMemo(
    () => (niveauFeuille ? (axes ?? []).filter((a) => a.type_niveau === niveauFeuille.id) : []),
    [axes, niveauFeuille],
  );

  const [libelle, setLibelle] = useState("");
  const [axeStrategique, setAxeStrategique] = useState<string | null>(null);
  const [quantitePrevue, setQuantitePrevue] = useState<number | string>("");
  const [uniteQuantite, setUniteQuantite] = useState("");
  const [dateDebut, setDateDebut] = useState<string | null>(null);
  const [dateFin, setDateFin] = useState<string | null>(null);

  async function handleSubmit() {
    if (!libelle.trim()) {
      notifications.show({ message: "Le libellé est requis.", color: "orange" });
      return;
    }
    try {
      await createSousActivite.mutateAsync({
        activite: activiteId,
        libelle: libelle.trim(),
        axe_strategique: axeStrategique ? Number(axeStrategique) : null,
        quantite_prevue: quantitePrevue === "" ? null : Number(quantitePrevue),
        unite_quantite: uniteQuantite,
        date_debut: dateDebut,
        date_fin: dateFin,
      } as never);
      notifications.show({ message: "Sous-activité créée", color: "green" });
      onDone();
    } catch {
      notifications.show({ message: "Erreur lors de la création de la sous-activité", color: "red" });
    }
  }

  return (
    <Stack gap="sm">
      {activitesDuCadre.length > 0 ? (
        <Autocomplete
          label="Libellé"
          description={voc`Suggestions issues du niveau « ${niveauFeuille!.nom_niveau} » du cadre stratégique — vous pouvez aussi taper un nouveau libellé.`}
          data={activitesDuCadre.map((a) => a.nom)}
          value={libelle}
          onChange={(v) => {
            setLibelle(v);
            const correspondance = activitesDuCadre.find((a) => a.nom === v);
            if (correspondance) setAxeStrategique(String(correspondance.id));
          }}
          required
        />
      ) : (
        <TextInput label="Libellé" value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} required />
      )}
      <Group grow>
        <DateInput label="Date de début prévue" value={dateDebut} onChange={setDateDebut} />
        <DateInput label="Date de fin prévue" value={dateFin} onChange={setDateFin} />
      </Group>
      <Group grow>
        <NumberInput label="Quantité prévue" value={quantitePrevue} onChange={setQuantitePrevue} min={0} />
        <TextInput label="Unité" value={uniteQuantite} onChange={(e) => setUniteQuantite(e.currentTarget.value)} />
      </Group>
      <Select
        label="Élément stratégique"
        description={
          cadreStrategiqueId
            ? voc("Peut être rattaché à n'importe quelle ligne du cadre stratégique (orientation, axe, activité, sous-activité…), limité au cadre de ce projet.")
            : voc("Ce projet n'a pas de cadre stratégique associé — tous les éléments existants sont proposés.")
        }
        data={axes?.map((a) => ({ value: String(a.id), label: `${a.type_niveau_nom} · ${a.code ? a.code + " — " : ""}${a.nom}` })) ?? []}
        value={axeStrategique}
        onChange={setAxeStrategique}
        clearable
        searchable
      />
      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createSousActivite.isPending}>Créer</Button>
      </Group>
    </Stack>
  );
}
