import { Button, Group, MultiSelect, Paper, SegmentedControl, Select, Text } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { RotateCcw } from "lucide-react";
import { PROJET_STATUT_LABEL } from "../../utils/statusTones";
import { FILTRES_PAR_DEFAUT, type EtatFiltres, type ModeDates } from "../../utils/filtresTableauDeBord";
import type { StatutProjet } from "../../types";
import { voc } from "../../utils/vocabulaire";

const PERIODES: { value: EtatFiltres["periode"]; label: string }[] = [
  { value: "actifs", label: "En cours pendant la période" },
  { value: "demarres", label: "Ont commencé dans la période" },
  { value: "demarres_fin_prevue", label: "Ont commencé et doivent finir dans la période" },
  { value: "demarres_termines", label: "Ont commencé et se sont terminés (clôturés) dans la période" },
];

export function FiltresTableauDeBord({
  valeur,
  onChange,
  nombreProjets,
}: {
  valeur: EtatFiltres;
  onChange: (f: EtatFiltres) => void;
  nombreProjets: number | undefined;
}) {
  const anneeCourante = new Date().getFullYear();
  const annees = Array.from({ length: 12 }, (_, i) => String(anneeCourante + 3 - i));
  const maj = (partiel: Partial<EtatFiltres>) => onChange({ ...valeur, ...partiel });
  const avecDates = valeur.mode !== "toutes";

  return (
    <Paper withBorder p="md" radius="md">
      <Group align="flex-end" gap="md" wrap="wrap">
        <div>
          <Text size="sm" fw={600} mb={4}>Période</Text>
          <SegmentedControl
            value={valeur.mode}
            onChange={(v) => maj({ mode: v as ModeDates })}
            data={[
              { value: "toutes", label: "Toutes" },
              { value: "annee", label: "Année" },
              { value: "plage", label: "Plage de dates" },
            ]}
          />
        </div>
        {valeur.mode === "annee" && (
          <Select label="Année" data={annees} value={valeur.annee} onChange={(v) => maj({ annee: v })} w={110} allowDeselect={false} />
        )}
        {valeur.mode === "plage" && (
          <>
            <DateInput
              label="Du"
              value={valeur.dateDebut}
              onChange={(v) => maj({ dateDebut: v })}
              valueFormat="DD/MM/YYYY"
              clearable
              w={150}
            />
            <DateInput
              label="Au"
              value={valeur.dateFin}
              onChange={(v) => maj({ dateFin: v })}
              valueFormat="DD/MM/YYYY"
              minDate={valeur.dateDebut ?? undefined}
              clearable
              w={150}
            />
          </>
        )}
        {avecDates && (
          <Select
            label={voc("Projets retenus")}
            data={PERIODES}
            value={valeur.periode}
            onChange={(v) => v && maj({ periode: v as EtatFiltres["periode"] })}
            allowDeselect={false}
            w={420}
          />
        )}
        <MultiSelect
          label={voc("Statut des projets")}
          placeholder={valeur.statuts.length ? undefined : "Tous les statuts"}
          data={(Object.keys(PROJET_STATUT_LABEL) as StatutProjet[]).map((s) => ({ value: s, label: PROJET_STATUT_LABEL[s] }))}
          value={valeur.statuts}
          onChange={(v) => maj({ statuts: v as StatutProjet[] })}
          clearable
          w={300}
        />
        <Button variant="subtle" leftSection={<RotateCcw size={15} />} onClick={() => onChange(FILTRES_PAR_DEFAUT)}>
          Réinitialiser
        </Button>
      </Group>
      {nombreProjets !== undefined && (
        <Text size="sm" c="dimmed" mt="sm">
          {nombreProjets} {voc(" projet")}{nombreProjets > 1 ? "s" : ""} retenu{nombreProjets > 1 ? "s" : ""} {voc(" — tous les chiffres et graphiques ci-dessous portent sur ces projets.")}{valeur.periode === "demarres_termines" && avecDates &&
            voc(" « Terminé » = projet au statut Clôturé dont la date de fin tombe dans la période.")}
        </Text>
      )}
    </Paper>
  );
}
