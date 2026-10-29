import { useMemo, useState } from "react";
import { Autocomplete, Button, Group, NumberInput, Select, Stack, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useCreateSousActivite, useUpdateSousActivite } from "../../api/projects";
import { AttributsLibres } from "../../components/common/AttributsLibres";
import type { Attributs } from "../../utils/attributs";
import { useElementsStrategiques, useTypesNiveaux } from "../../api/strategy";
import type { SousActivite } from "../../types";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { libelleDuree } from "../../utils/periode";

/** Création, ou modification si `sousActivite` est donnée, d'une sous-activité. */
export function SousActiviteForm({
  activiteId,
  cadreStrategiqueId,
  sousActivite,
  nomsAttributs = [],
  onDone,
}: {
  activiteId: number;
  cadreStrategiqueId: number | null;
  sousActivite?: SousActivite;
  /** Noms d'attributs déjà utilisés dans le projet, proposés à la saisie. */
  nomsAttributs?: string[];
  onDone: () => void;
}) {
  const { data: axes } = useElementsStrategiques(cadreStrategiqueId ? { cadre_strategique: cadreStrategiqueId } : undefined);
  const { data: niveaux } = useTypesNiveaux(cadreStrategiqueId);
  const createSousActivite = useCreateSousActivite();
  const updateSousActivite = useUpdateSousActivite();

  const niveauFeuille = useMemo(
    () => (niveaux && niveaux.length > 0 ? niveaux.reduce((a, b) => (b.ordre > a.ordre ? b : a)) : null),
    [niveaux],
  );
  const activitesDuCadre = useMemo(
    () => (niveauFeuille ? (axes ?? []).filter((a) => a.type_niveau === niveauFeuille.id) : []),
    [axes, niveauFeuille],
  );

  const [libelle, setLibelle] = useState(sousActivite?.libelle ?? "");
  const [axeStrategique, setAxeStrategique] = useState<string | null>(
    sousActivite?.axe_strategique ? String(sousActivite.axe_strategique) : null,
  );
  const [quantitePrevue, setQuantitePrevue] = useState<number | string>(sousActivite?.quantite_prevue ?? "");
  const [uniteQuantite, setUniteQuantite] = useState(sousActivite?.unite_quantite ?? "");
  const [dateDebut, setDateDebut] = useState<string | null>(sousActivite?.date_debut ?? null);
  const [dateFin, setDateFin] = useState<string | null>(sousActivite?.date_fin ?? null);
  const [attributs, setAttributs] = useState<Attributs>(sousActivite?.attributs ?? {});

  async function handleSubmit() {
    if (!libelle.trim()) {
      notifications.show({ message: voc("Le libellé est requis."), color: "orange" });
      return;
    }
    const payload = {
      libelle: libelle.trim(),
      axe_strategique: axeStrategique ? Number(axeStrategique) : null,
      quantite_prevue: quantitePrevue === "" ? null : Number(quantitePrevue),
      unite_quantite: uniteQuantite,
      date_debut: dateDebut,
      date_fin: dateFin,
      attributs,
    };
    try {
      if (sousActivite) {
        await updateSousActivite.mutateAsync({ id: sousActivite.id, payload });
        notifications.show({ message: voc("Sous-activité modifiée"), color: "green" });
      } else {
        await createSousActivite.mutateAsync({ activite: activiteId, ...payload } as never);
        notifications.show({ message: voc("Sous-activité créée"), color: "green" });
      }
      onDone();
    } catch (error) {
      notifications.show({
        message: messageErreurApi(
          error,
          sousActivite ? voc("Erreur lors de la modification de la sous-activité") : voc("Erreur lors de la création de la sous-activité"),
        ),
        color: "red",
      });
    }
  }

  return (
    <Stack gap="sm">
      {activitesDuCadre.length > 0 ? (
        <Autocomplete
          label={voc("Libellé")}
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
        <TextInput label={voc("Libellé")} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} required />
      )}
      <Group grow>
        <DateInput label={voc("Date de début prévue")} value={dateDebut} onChange={setDateDebut} />
        <DateInput
          label={voc("Date de fin prévue")}
          value={dateFin}
          onChange={setDateFin}
          minDate={dateDebut ?? undefined}
          description={libelleDuree(dateDebut, dateFin) ? voc`Durée : ${libelleDuree(dateDebut, dateFin)}` : undefined}
        />
      </Group>
      <Group grow>
        <NumberInput label={voc("Quantité prévue")} value={quantitePrevue} onChange={setQuantitePrevue} min={0} />
        <TextInput label={voc("Unité")} value={uniteQuantite} onChange={(e) => setUniteQuantite(e.currentTarget.value)} />
      </Group>
      <Select
        label={voc("Élément stratégique")}
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
      <AttributsLibres value={attributs} onChange={setAttributs} suggestions={nomsAttributs} />
      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createSousActivite.isPending || updateSousActivite.isPending}>
          {sousActivite ? voc("Enregistrer") : voc("Créer")}
        </Button>
      </Group>
    </Stack>
  );
}
