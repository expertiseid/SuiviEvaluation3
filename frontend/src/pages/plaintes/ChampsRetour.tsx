import { Checkbox, Radio, Select, SimpleGrid, Stack, Text, TextInput, Textarea } from "@mantine/core";
import { libelleModeReponse, MODES_REPONSE, type ModeReponse, type SaisieRetour } from "../../api/plaintes";
import { optionsCategories } from "./saisieRetour";
import { voc } from "../../utils/vocabulaire";

const ouiNon = (v: boolean | null) => (v === null ? "" : v ? "oui" : "non");

/**
 * Champs d'un retour, communs au formulaire public et à la saisie par un agent : type,
 * catégorie, projet, lieu, description, question système sur le personnel, anonymat et
 * coordonnées (jamais obligatoires quand l'anonymat est autorisé).
 */
export function ChampsRetour({
  valeurs,
  onChange,
  types,
  categories,
  projets,
  projetFixe = false,
  anonymatAutorise,
  erreurs,
  agent = false,
}: {
  valeurs: SaisieRetour;
  onChange: (v: Partial<SaisieRetour>) => void;
  types: { id: number; nom: string; description?: string }[];
  categories: { id: number; nom: string; parent: number | null }[];
  projets: { id: number; code: string; nom: string }[];
  projetFixe?: boolean;
  anonymatAutorise: boolean;
  erreurs: Record<string, string>;
  agent?: boolean;
}) {
  return (
    <Stack gap="sm">
      <Radio.Group
        label={agent ? voc("Type de retour") : voc("De quoi s'agit-il ?")}
        withAsterisk
        value={valeurs.type_retour ? String(valeurs.type_retour) : ""}
        onChange={(v) => onChange({ type_retour: Number(v) })}
        error={erreurs.type_retour}
      >
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing={6} mt={6}>
          {types.map((t) => (
            <Radio key={t.id} value={String(t.id)} label={t.nom} description={t.description || undefined} />
          ))}
        </SimpleGrid>
      </Radio.Group>
      <Select
        label={voc("Catégorie")}
        placeholder={agent ? voc("À classer plus tard") : voc("Je ne sais pas")}
        data={optionsCategories(categories)}
        value={valeurs.categorie ? String(valeurs.categorie) : null}
        onChange={(v) => onChange({ categorie: v ? Number(v) : null })}
        error={erreurs.categorie}
        searchable
        clearable
      />
      {projets.length > 0 && !projetFixe && (
        <Select
          label={voc("Projet concerné")}
          placeholder={voc("Je ne sais pas")}
          data={projets.map((p) => ({ value: String(p.id), label: p.code ? `${p.code} — ${p.nom}` : p.nom }))}
          value={valeurs.projet ? String(valeurs.projet) : null}
          onChange={(v) => onChange({ projet: v ? Number(v) : null })}
          error={erreurs.projet}
          searchable
          clearable
        />
      )}
      <TextInput
        label={voc("Lieu")}
        placeholder={voc("Village, quartier, site…")}
        value={valeurs.lieu}
        onChange={(e) => onChange({ lieu: e.currentTarget.value })}
      />
      <Textarea
        label={agent ? voc("Description du retour") : voc("Votre message")}
        withAsterisk
        autosize
        minRows={4}
        value={valeurs.description}
        onChange={(e) => onChange({ description: e.currentTarget.value })}
        error={erreurs.description}
      />
      <Radio.Group
        label={voc("Ce retour concerne-t-il le comportement d'un membre du personnel ou d'un partenaire ?")}
        description={voc("Si oui, il est traité de façon confidentielle par des personnes désignées.")}
        value={ouiNon(valeurs.concerne_personnel)}
        onChange={(v) => onChange({ concerne_personnel: v === "" ? null : v === "oui" })}
      >
        <SimpleGrid cols={3} spacing={6} mt={6} maw={420}>
          <Radio value="oui" label={voc("Oui")} />
          <Radio value="non" label={voc("Non")} />
          <Radio value="" label={voc("Je ne sais pas")} />
        </SimpleGrid>
      </Radio.Group>

      {anonymatAutorise && (
        <Checkbox
          label={agent ? voc("Retour anonyme (aucune information d'identité)") : voc("Je souhaite rester anonyme")}
          description={voc("Aucune coordonnée n'est alors enregistrée. Le code de suivi permet quand même de suivre le dossier.")}
          checked={valeurs.anonyme}
          onChange={(e) => onChange({ anonyme: e.currentTarget.checked })}
          error={erreurs.anonyme}
        />
      )}
      {!valeurs.anonyme && (
        <>
          <Text size="sm" fw={500}>
            {anonymatAutorise || agent ? voc("Coordonnées (facultatives)") : voc("Vos coordonnées")}
          </Text>
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
            <TextInput
              label={voc("Nom")}
              withAsterisk={!anonymatAutorise && !agent}
              value={valeurs.nom}
              onChange={(e) => onChange({ nom: e.currentTarget.value })}
              error={erreurs.nom}
            />
            <TextInput
              label={voc("Téléphone")}
              type="tel"
              value={valeurs.telephone}
              onChange={(e) => onChange({ telephone: e.currentTarget.value })}
              error={erreurs.telephone}
            />
            <TextInput
              label={voc("Courriel")}
              type="email"
              value={valeurs.courriel}
              onChange={(e) => onChange({ courriel: e.currentTarget.value })}
              error={erreurs.courriel}
            />
          </SimpleGrid>
          <Select
            label={voc("Réponse souhaitée")}
            data={MODES_REPONSE.map((m) => ({ value: m, label: libelleModeReponse(m) }))}
            value={valeurs.mode_reponse}
            onChange={(v) => onChange({ mode_reponse: (v ?? "AUCUN") as ModeReponse })}
            error={erreurs.mode_reponse}
            allowDeselect={false}
            maw={320}
          />
        </>
      )}
    </Stack>
  );
}
