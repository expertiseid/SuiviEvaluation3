import { useState } from "react";
import { Button, Group, MultiSelect, Stack, TextInput } from "@mantine/core";
import type { Intervenant } from "../../types";
import { voc } from "../../utils/vocabulaire";

/**
 * Choix de plusieurs personnes déjà enregistrées (recherche parmi les
 * intervenants existants), avec possibilité d'en créer une nouvelle à la
 * volée (nom + prénom) sans quitter le formulaire — la personne créée
 * apparaît alors partout où les intervenants sont listés (ex : onglet
 * Équipe de projet), au lieu d'un simple texte libre déconnecté.
 */
export function IntervenantsMultiples({
  label,
  description,
  value,
  onChange,
  intervenants,
  onCreerNouveau,
  creating,
}: {
  label: string;
  description?: string;
  value: number[];
  onChange: (value: number[]) => void;
  intervenants: Intervenant[];
  onCreerNouveau: (nom: string, prenom: string) => Promise<Intervenant | null>;
  creating?: boolean;
}) {
  const [modeCreation, setModeCreation] = useState(false);
  const [nom, setNom] = useState("");
  const [prenom, setPrenom] = useState("");

  async function ajouter() {
    if (!nom.trim() || !prenom.trim()) return;
    const cree = await onCreerNouveau(nom.trim(), prenom.trim());
    if (cree) {
      onChange([...value, cree.id]);
      setNom("");
      setPrenom("");
      setModeCreation(false);
    }
  }

  return (
    <Stack gap={4}>
      <MultiSelect
        label={label}
        description={description}
        placeholder={voc("Choisir une ou plusieurs personnes déjà enregistrées…")}
        data={intervenants.map((i) => ({
          value: String(i.id),
          label: `${i.nom} ${i.prenom}${i.fonction ? " — " + i.fonction : ""}`,
        }))}
        value={value.map(String)}
        onChange={(vals) => onChange(vals.map(Number))}
        searchable
        clearable
      />
      {modeCreation ? (
        <Group gap={6} align="flex-end" wrap="wrap">
          <TextInput size="xs" label={voc("Nom")} value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
          <TextInput size="xs" label={voc("Prénom")} value={prenom} onChange={(e) => setPrenom(e.currentTarget.value)} />
          <Button size="xs" onClick={ajouter} loading={creating}>{voc("Ajouter")}</Button>
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => {
              setModeCreation(false);
              setNom("");
              setPrenom("");
            }}
          >
            {voc("Annuler")}
          </Button>
        </Group>
      ) : (
        <Button size="xs" variant="subtle" onClick={() => setModeCreation(true)}>
          {voc("+ Créer une nouvelle personne")}
        </Button>
      )}
    </Stack>
  );
}
