import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import {
  ActionIcon, Alert, Badge, Button, Card, Group, Loader, MultiSelect, NumberInput, Paper, Select, SimpleGrid, Stack, Text, TextInput, Tooltip,
} from "@mantine/core";
import { apercuFormule, useCatalogueFormules, useIndicateursPourProjet } from "../../api/indicators";
import { useEnquetes, useModalitesEnquete } from "../../api/enquetes";
import { useZones } from "../../api/geo";
import type { ApercuFormule, CatalogueFormules, FormuleIndicateur, TermeFormule } from "../../types";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

const CODES = "ABCDEFGH";

/** Champ de filtre d'un terme, selon son type. */
function Filtre({ cle, valeur, onChange, catalogue, projetId, filtres }: {
  cle: string; valeur: string | number | string[] | null | undefined; onChange: (v: string | number | string[] | null) => void;
  catalogue: CatalogueFormules; projetId: number | null;
  /** Les autres filtres du terme (l'enquête choisie, sa colonne…). */
  filtres: TermeFormule["filtres"];
}) {
  const { data: zones = [] } = useZones();
  const { data: indicateurs = [] } = useIndicateursPourProjet(cle === "indicateur" ? projetId : null);
  const { data: enquetes = [] } = useEnquetes();
  const enquete = enquetes.find((e) => e.id === Number(filtres.enquete));
  const colonneModalites = cle === "valeurs" ? filtres.colonne : cle === "sous_groupe_valeur" ? filtres.sous_groupe_colonne : null;
  const { data: modalites = [] } = useModalitesEnquete(enquete?.id, typeof colonneModalites === "string" ? colonneModalites : null);
  if (cle === "valeurs") {
    if (filtres.calcul_enquete === "moyenne" || !filtres.colonne) return null;
    return (
      <MultiSelect size="xs" label={voc("Réponses comptées")} searchable data={modalites.map((m) => m.valeur)}
        value={Array.isArray(valeur) ? valeur : []} onChange={(v) => onChange(v.length ? v : null)} comboboxProps={{ withinPortal: true }} />
    );
  }
  const choix: Record<string, { label: string; data: { value: string; label: string }[] }> = {
    sexe: { label: voc("Sexe"), data: [{ value: "F", label: voc("Femmes") }, { value: "M", label: voc("Hommes") }] },
    statut_particulier: { label: voc("Statut particulier"), data: catalogue.statuts_particuliers },
    statut_participation: { label: voc("Parcours"), data: catalogue.statuts_participation },
    periode: { label: voc("Période"), data: catalogue.periodes },
    statut_activite: { label: voc("Statut"), data: catalogue.statuts_activite },
    delai: { label: voc("Délais"), data: catalogue.delais },
    variante: { label: voc("Quelle valeur"), data: catalogue.variantes },
    enquete: { label: voc("Enquête"), data: enquetes.map((e) => ({ value: String(e.id), label: e.titre })) },
    calcul_enquete: { label: voc("Calcul"), data: catalogue.calculs_enquete },
    colonne: { label: voc("Question (colonne)"), data: (enquete?.colonnes ?? []).map((c) => ({ value: c.nom, label: c.nom })) },
    sous_groupe_colonne: {
      label: voc("Seulement si (colonne)"),
      data: (enquete?.colonnes ?? []).filter((c) => c.type === "TEXTE").map((c) => ({ value: c.nom, label: c.nom })),
    },
    sous_groupe_valeur: { label: voc("… vaut"), data: modalites.map((m) => ({ value: m.valeur, label: m.valeur })) },
    zone: { label: voc("Zone"), data: zones.map((z) => ({ value: String(z.id), label: `${z.nom} (${z.niveau_administratif_nom})` })) },
    indicateur: {
      label: voc("Indicateur"),
      data: indicateurs.map((i) => ({ value: String(i.id), label: i.libelle })),
    },
  };
  if (cle === "age_min" || cle === "age_max") {
    return (
      <NumberInput size="xs" label={cle === "age_min" ? voc("Âge minimum") : voc("Âge maximum")} min={0} max={120} allowDecimal={false}
        value={typeof valeur === "number" ? valeur : ""} onChange={(v) => onChange(v === "" ? null : Number(v))} />
    );
  }
  const c = choix[cle];
  if (!c) return null;
  if (cle === "indicateur" && !projetId) {
    return <Text size="xs" c="dimmed">{voc("Rattachez d'abord l'indicateur à un projet pour choisir un de ses indicateurs.")}</Text>;
  }
  return (
    <Select size="xs" label={c.label} data={c.data} searchable clearable placeholder={voc("Tous")}
      value={valeur == null ? null : String(valeur)} onChange={(v) => onChange(v)} comboboxProps={{ withinPortal: true }} />
  );
}

/**
 * Éditeur d'un indicateur calculé : des termes (A, B…) choisis dans le catalogue et restreints par des filtres,
 * un calcul simple qui les combine, et le résultat immédiat sur les vraies données avec son explication.
 */
export function FormuleEditeur({ value, onChange, projetId, onModele }: {
  value: FormuleIndicateur;
  onChange: (f: FormuleIndicateur) => void;
  /** Projet de l'indicateur : ses données servent à l'aperçu (sinon toute l'organisation). */
  projetId: number | null;
  onModele?: (modele: CatalogueFormules["modeles"][number]) => void;
}) {
  const { data: catalogue } = useCatalogueFormules();
  const [apercu, setApercu] = useState<ApercuFormule | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [calcul, setCalcul] = useState(false);

  // Aperçu recalculé une demi-seconde après la dernière modification.
  useEffect(() => {
    let annule = false;
    const minuteur = setTimeout(async () => {
      setCalcul(true);
      try {
        const r = await apercuFormule(value, projetId);
        if (!annule) { setApercu(r); setErreur(null); }
      } catch (e) {
        if (!annule) { setApercu(null); setErreur(messageErreurApi(e, voc("Formule incomplète."))); }
      } finally {
        if (!annule) setCalcul(false);
      }
    }, 500);
    return () => { annule = true; clearTimeout(minuteur); };
  }, [value, projetId]);

  if (!catalogue) return <Loader size="sm" />;
  const mesures = Object.fromEntries(catalogue.mesures.map((m) => [m.cle, m]));
  const changerTerme = (i: number, terme: TermeFormule) => onChange({ ...value, termes: value.termes.map((t, j) => (j === i ? terme : t)) });
  const inserer = (texte: string) => onChange({ ...value, expression: `${value.expression}${value.expression && !value.expression.endsWith(" ") ? " " : ""}${texte}` });
  const nombre = (x: string | null) => (x === null ? "—" : Number(x).toLocaleString(locale(), { maximumFractionDigits: 2 }));

  return (
    <Stack gap="sm">
      <Select label={voc("Partir d'un modèle")} placeholder={voc("Choisir un modèle prêt à adapter (facultatif)")} clearable
        data={catalogue.modeles.map((m, i) => ({ value: String(i), label: m.titre }))} value={null}
        onChange={(v) => {
          if (v === null) return;
          const modele = catalogue.modeles[Number(v)];
          onChange(structuredClone(modele.formule));
          onModele?.(modele);
        }} />

      {value.termes.map((terme, i) => {
        const mesure = mesures[terme.mesure];
        return (
          <Card key={i} withBorder padding="xs" radius="md">
            <Group align="flex-end" gap="xs" wrap="nowrap">
              <Badge size="lg" variant="filled" color="indigo" mb={4}>{CODES[i]}</Badge>
              <Select size="xs" style={{ flex: 1 }} label={voc("Mesure")} allowDeselect={false}
                data={catalogue.mesures.map((m) => ({ value: m.cle, label: m.libelle }))} value={terme.mesure}
                onChange={(v) => v && changerTerme(i, { mesure: v, filtres: {} })} />
              {value.termes.length > 1 && (
                <Tooltip label={voc("Retirer ce terme")}>
                  <ActionIcon variant="subtle" color="red" mb={4} aria-label={voc("Retirer ce terme")}
                    onClick={() => onChange({ ...value, termes: value.termes.filter((_t, j) => j !== i) })}><Trash2 size={15} /></ActionIcon>
                </Tooltip>
              )}
            </Group>
            {mesure && mesure.filtres.length > 0 && (
              <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="xs" mt="xs">
                {mesure.filtres.map((f) => (
                  <Filtre key={f} cle={f} catalogue={catalogue} projetId={projetId} filtres={terme.filtres} valeur={terme.filtres[f]}
                    onChange={(v) => changerTerme(i, { ...terme, filtres: { ...terme.filtres, [f]: v } })} />
                ))}
              </SimpleGrid>
            )}
          </Card>
        );
      })}
      {value.termes.length < CODES.length && (
        <Button size="xs" variant="light" leftSection={<Plus size={14} />} style={{ alignSelf: "flex-start" }}
          onClick={() => onChange({ ...value, termes: [...value.termes, { mesure: "beneficiaires", filtres: {} }] })}>
          {voc`Ajouter le terme ${CODES[value.termes.length]}`}
        </Button>
      )}

      <TextInput label={voc("Calcul")} description={voc("Avec les lettres des termes, des nombres, + − × ÷ et des parenthèses. Ex : A ÷ B × 100")}
        value={value.expression} onChange={(e) => onChange({ ...value, expression: e.currentTarget.value })} />
      <Group gap={4}>
        {[...CODES.slice(0, value.termes.length)].map((c) => (
          <Button key={c} size="compact-xs" variant="light" color="indigo" onClick={() => inserer(c)}>{c}</Button>
        ))}
        {[["+", "+"], ["−", "-"], ["×", "*"], ["÷", "/"], ["(", "("], [")", ")"], ["100", "100"], ["1 000", "1000"]].map(([libelle, texte]) => (
          <Button key={libelle} size="compact-xs" variant="default" onClick={() => inserer(texte)}>{libelle}</Button>
        ))}
        <Button size="compact-xs" variant="subtle" color="gray" onClick={() => onChange({ ...value, expression: "" })}>{voc("Effacer")}</Button>
      </Group>

      <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-gray-0)">
        <Group justify="space-between" mb={4}>
          <Text size="sm" fw={600}>{projetId ? voc("Résultat sur les données du projet") : voc("Résultat sur les données de tous les projets")}</Text>
          {calcul && <Loader size="xs" />}
        </Group>
        {erreur ? (
          <Alert color="orange" variant="light" py={6}>{erreur}</Alert>
        ) : apercu && (
          <Stack gap={4}>
            <Text size="xl" fw={700} c={apercu.valeur === null ? "orange.8" : undefined}>
              {apercu.valeur === null ? voc`Non calculable : ${apercu.non_calculable ?? ""}` : nombre(apercu.valeur)}
            </Text>
            {apercu.explication.map((ligne, i) => (
              <Text key={i} size="xs" c="dimmed">
                {ligne}{i < apercu.explication.length - 1 && apercu.termes[CODES[i]] !== undefined ? ` → ${nombre(apercu.termes[CODES[i]])}` : ""}
                {apercu.marges?.[CODES[i]] !== undefined ? voc` (± ${nombre(String(apercu.marges[CODES[i]]))} à 95 %)` : ""}
              </Text>
            ))}
          </Stack>
        )}
      </Paper>
    </Stack>
  );
}
