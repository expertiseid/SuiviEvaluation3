import { useState } from "react";
import { Button, Divider, MultiSelect, NumberInput, Select, SimpleGrid, Stack, Text, TextInput } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { useVariablesBeneficiaires } from "../../api/beneficiaries";
import { voc } from "../../utils/vocabulaire";
import type { Beneficiaire, VariableBeneficiaire } from "../../types";
import { concerne } from "../../utils/variablesBeneficiaires";

type Reponses = Beneficiaire["reponses"];

function Champ({ variable, valeur, onChange }: { variable: VariableBeneficiaire; valeur: Reponses[string] | undefined; onChange: (v: Reponses[string] | undefined) => void }) {
  const commun = { label: variable.libelle, description: variable.aide || undefined };
  switch (variable.type) {
    case "NOMBRE":
      return (
        <NumberInput
          {...commun}
          rightSection={variable.unite ? <Text size="xs" c="dimmed">{variable.unite}</Text> : undefined}
          rightSectionWidth={variable.unite ? 70 : undefined}
          value={typeof valeur === "number" ? valeur : ""}
          onChange={(v) => onChange(v === "" ? undefined : Number(v))}
        />
      );
    case "DATE":
      return (
        <DateInput {...commun} valueFormat="DD/MM/YYYY" clearable value={typeof valeur === "string" ? valeur : null} onChange={(v) => onChange(v ?? undefined)} />
      );
    case "OUI_NON":
      return (
        <Select
          {...commun}
          data={[{ value: "oui", label: voc("Oui") }, { value: "non", label: voc("Non") }]}
          value={valeur === undefined ? null : valeur ? "oui" : "non"}
          onChange={(v) => onChange(v === null ? undefined : v === "oui")}
          clearable
        />
      );
    case "CHOIX":
      return <Select {...commun} data={variable.choix} value={typeof valeur === "string" ? valeur : null} onChange={(v) => onChange(v ?? undefined)} clearable searchable />;
    case "CHOIX_MULTIPLE":
      return <MultiSelect {...commun} data={variable.choix} value={Array.isArray(valeur) ? valeur : []} onChange={(v) => onChange(v.length ? v : undefined)} clearable />;
    default:
      return <TextInput {...commun} value={typeof valeur === "string" ? valeur : ""} onChange={(e) => onChange(e.currentTarget.value || undefined)} />;
  }
}

/**
 * Variables personnalisées dans le formulaire bénéficiaire : celles des projets du bénéficiaire
 * (et celles de tous les projets) ; les autres restent accessibles mais repliées, car elles
 * vaudront « NA » pour ses projets.
 */
export function ChampsVariables({ projetIds, value, onChange }: { projetIds: number[]; value: Reponses; onChange: (r: Reponses) => void }) {
  const { data: variables = [] } = useVariablesBeneficiaires();
  const [autresVisibles, setAutresVisibles] = useState(false);
  if (variables.length === 0) return null;
  const concernees = variables.filter((v) => concerne(v, projetIds));
  const autres = variables.filter((v) => !concerne(v, projetIds));

  const changer = (id: number) => (valeur: Reponses[string] | undefined) => {
    const suite = { ...value };
    if (valeur === undefined) delete suite[String(id)];
    else suite[String(id)] = valeur;
    onChange(suite);
  };

  return (
    <Stack gap="xs">
      <Divider label={voc("Informations complémentaires")} labelPosition="left" />
      {concernees.length > 0 && (
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          {concernees.map((v) => <Champ key={v.id} variable={v} valeur={value[String(v.id)]} onChange={changer(v.id)} />)}
        </SimpleGrid>
      )}
      {autres.length > 0 && (
        <>
          <Button size="compact-xs" variant="subtle" onClick={() => setAutresVisibles((x) => !x)} style={{ alignSelf: "flex-start" }}>
            {autresVisibles ? voc("Masquer") : voc("Afficher")} {voc("les variables d'autres projets")} ({autres.length})
          </Button>
          {autresVisibles && (
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              {autres.map((v) => <Champ key={v.id} variable={v} valeur={value[String(v.id)]} onChange={changer(v.id)} />)}
            </SimpleGrid>
          )}
        </>
      )}
    </Stack>
  );
}
