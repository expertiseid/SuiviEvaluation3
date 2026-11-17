import { useMemo, useState } from "react";
import { Button, Divider, Group, MultiSelect, NumberInput, SegmentedControl, Select, SimpleGrid, Stack, Text, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useCreateIndicateur, useUpdateIndicateur } from "../../api/indicators";
import { useElementsStrategiques } from "../../api/strategy";
import { FormuleEditeur } from "../../components/indicators/FormuleEditeur";
import { messageErreurApi } from "../../utils/erreurs";
import { useHierarchyOptions } from "./useHierarchyOptions";
import type { FormuleIndicateur, Indicateur } from "../../types";
import { voc } from "../../utils/vocabulaire";

const FORMULE_VIDE: FormuleIndicateur = { termes: [{ mesure: "beneficiaires", filtres: {} }], expression: "A" };

const FREQUENCES = [
  { value: "MENSUELLE", label: voc("Mensuelle") },
  { value: "TRIMESTRIELLE", label: voc("Trimestrielle") },
  { value: "SEMESTRIELLE", label: voc("Semestrielle") },
  { value: "ANNUELLE", label: voc("Annuelle") },
];

// Un indicateur se rattache au projet lui-même, ou à un élément de sa
// planification à n'importe quel niveau (objectif, résultat, pilier, activité...).
type Rattachement = "AUCUN" | "PROJET" | "ACTIVITE";

function rattachementInitial(indicateur?: Indicateur): { type: Rattachement; id: string | null } {
  if (!indicateur) return { type: "AUCUN", id: null };
  if (indicateur.projet) return { type: "PROJET", id: String(indicateur.projet) };
  if (indicateur.activite) return { type: "ACTIVITE", id: String(indicateur.activite) };
  return { type: "AUCUN", id: null };
}

export function IndicateurForm({ indicateur, onDone }: { indicateur?: Indicateur; onDone: () => void }) {
  const enEdition = !!indicateur;
  const { projets, elementsParProjet, cadreParProjetId, projetIdParActivite } = useHierarchyOptions();
  const createIndicateur = useCreateIndicateur();
  const updateIndicateur = useUpdateIndicateur();

  const initial = rattachementInitial(indicateur);
  const [rattachementValue, setRattachementValue] = useState<string | null>(
    initial.type === "AUCUN" || !initial.id ? null : `${initial.type}:${initial.id}`,
  );
  const [rattachementType, rattachementId] = useMemo((): [Rattachement, string | null] => {
    if (!rattachementValue) return ["AUCUN", null];
    const [type, id] = rattachementValue.split(":");
    return [type as Rattachement, id];
  }, [rattachementValue]);
  const [libelle, setLibelle] = useState(indicateur?.libelle ?? "");
  const [unite, setUnite] = useState(indicateur?.unite ?? "");
  const [valeurReference, setValeurReference] = useState<number | string>(indicateur?.valeur_reference ?? "");
  const [valeurCible, setValeurCible] = useState<number | string>(indicateur?.valeur_cible ?? "");
  const [frequence, setFrequence] = useState<string | null>(indicateur?.frequence_collecte ?? "TRIMESTRIELLE");
  // Calcul du taux (par défaut : somme des saisies ÷ cible, plus haut = mieux).
  const [sens, setSens] = useState<string | null>(indicateur?.sens ?? "HAUSSE");
  const [calculTaux, setCalculTaux] = useState<string | null>(indicateur?.calcul_taux ?? "CIBLE");
  const [agregation, setAgregation] = useState<string | null>(indicateur?.agregation ?? "SOMME");
  // Valeurs saisies au fil du suivi, ou calculées par une formule (aucune saisie).
  const [mode, setMode] = useState<"SAISIE" | "FORMULE">(indicateur?.formule ? "FORMULE" : "SAISIE");
  const [formule, setFormule] = useState<FormuleIndicateur>(indicateur?.formule ?? FORMULE_VIDE);
  const aDesSaisies = !indicateur?.formule && (indicateur?.valeurs?.length ?? 0) > 0;
  const [elementsSelectionnes, setElementsSelectionnes] = useState<string[]>(
    indicateur?.elements_strategiques.map(String) ?? [],
  );

  // Un seul sélecteur, avec toutes les options regroupées (les projets, puis la
  // planification de chaque projet) — l'utilisateur tape et trouve, quel que
  // soit le niveau.
  const optionsRattachement = [
    ...(projets.length > 0
      ? [{ group: voc("Projets"), items: projets.map((o) => ({ value: voc`PROJET:${o.value}`, label: o.label })) }]
      : []),
    ...elementsParProjet.map((g) => ({
      group: voc`Planification — ${g.projetLabel}`,
      items: g.options.map((o) => ({ value: `ACTIVITE:${o.value}`, label: o.label })),
    })),
  ];

  // Détermine le projet concerné par le rattachement choisi (quel que soit
  // le niveau), pour ne proposer que les éléments stratégiques de son cadre.
  const projetIdCourant = useMemo(() => {
    if (!rattachementId) return null;
    const id = Number(rattachementId);
    if (rattachementType === "PROJET") return id;
    if (rattachementType === "ACTIVITE") return projetIdParActivite.get(id) ?? null;
    return null;
  }, [rattachementType, rattachementId, projetIdParActivite]);

  const cadreStrategiqueCourant = projetIdCourant ? cadreParProjetId.get(projetIdCourant) ?? null : null;

  const { data: elementsStrategiques } = useElementsStrategiques(
    cadreStrategiqueCourant ? { cadre_strategique: cadreStrategiqueCourant } : undefined,
  );

  async function handleSubmit() {
    if (!libelle || !unite || valeurCible === "" || !frequence) {
      notifications.show({ message: voc("Merci de compléter tous les champs requis."), color: "orange" });
      return;
    }
    const payload = {
      libelle,
      unite,
      valeur_reference: valeurReference === "" ? null : String(valeurReference),
      valeur_cible: String(valeurCible),
      frequence_collecte: frequence as never,
      sens: (sens ?? "HAUSSE") as never,
      calcul_taux: (calculTaux ?? "CIBLE") as never,
      agregation: (mode === "FORMULE" ? "DERNIERE" : agregation ?? "SOMME") as never,
      formule: mode === "FORMULE" ? formule : null,
      projet: rattachementType === "PROJET" ? Number(rattachementId) : null,
      activite: rattachementType === "ACTIVITE" ? Number(rattachementId) : null,
      elements_strategiques: elementsSelectionnes.map(Number),
    };
    try {
      if (enEdition) {
        await updateIndicateur.mutateAsync({ id: indicateur.id, payload });
        notifications.show({ message: voc("Indicateur modifié"), color: "green" });
      } else {
        await createIndicateur.mutateAsync(payload);
        notifications.show({ message: voc("Indicateur créé"), color: "green" });
      }
      onDone();
    } catch (e) {
      notifications.show({
        message: messageErreurApi(e, enEdition ? voc("Erreur lors de la modification de l'indicateur") : voc("Erreur lors de la création de l'indicateur")),
        color: "red",
      });
    }
  }

  return (
    <Stack gap="sm">
      <TextInput label={voc("Libellé")} value={libelle} onChange={(e) => setLibelle(e.currentTarget.value)} required />
      <Group grow>
        <TextInput label={voc("Unité")} value={unite} onChange={(e) => setUnite(e.currentTarget.value)} required />
        <NumberInput label={voc("Valeur de base")} value={valeurReference} onChange={setValeurReference} min={0} />
        <NumberInput label={voc("Valeur cible")} value={valeurCible} onChange={setValeurCible} min={0} required />
      </Group>
      <Select label={voc("Fréquence de collecte")} data={FREQUENCES} value={frequence} onChange={setFrequence} required />
      <SimpleGrid cols={1} spacing="sm">
        <Select label={voc("Sens")} value={sens} onChange={setSens} allowDeselect={false}
          description={voc("Une baisse est-elle un progrès ? (taux de malnutrition, délai, nombre de cas…)")}
          data={[{ value: "HAUSSE", label: voc("Plus haut = mieux") }, { value: "BAISSE", label: voc("Plus bas = mieux") }]} />
        {mode === "SAISIE" && (
          <Select label={voc("Valeurs saisies")} value={agregation} onChange={setAgregation} allowDeselect={false}
            description={voc("Cumulables (personnes formées, kits…) ou une mesure à chaque saisie (taux, prévalence, stock…).")}
            data={[{ value: "SOMME", label: voc("S'additionnent") }, { value: "DERNIERE", label: voc("Seule la dernière compte") }]}
            comboboxProps={{ width: 260 }} />
        )}
        <Select label={voc("Calcul du taux")} value={calculTaux} onChange={setCalculTaux} allowDeselect={false}
          description={calculTaux === "PROGRESSION"
            ? voc("(Valeur actuelle − valeur de base) ÷ (cible − valeur de base) × 100 : demande une valeur de base.")
            : voc("Valeur ÷ cible × 100 (plus bas = mieux : cible ÷ valeur × 100).")}
          data={[{ value: "CIBLE", label: voc("Réalisé ÷ cible") }, { value: "PROGRESSION", label: voc("Progression depuis la valeur de base") }]}
          comboboxProps={{ width: 300 }} />
      </SimpleGrid>

      <Select
        label={voc("Rattaché à")}
        description={voc("Facultatif — cherche et choisis directement le projet ou un élément de sa planification, quel que soit son niveau. L'indicateur suit la grille d'alerte (paliers/libellés/couleurs) du projet, configurable depuis Paramètres d'alerte.")}
        placeholder={voc("Rechercher…")}
        data={optionsRattachement}
        value={rattachementValue}
        onChange={setRattachementValue}
        searchable
        clearable
      />

      <MultiSelect
        label={voc("Éléments stratégiques rattachés")}
        description={
          cadreStrategiqueCourant
            ? voc("Limité au cadre stratégique du projet choisi ci-dessus.")
            : voc("Choisis d'abord un rattachement ci-dessus pour limiter la liste à son cadre stratégique — sinon tous les éléments sont proposés.")
        }
        data={elementsStrategiques?.map((el) => ({
          value: String(el.id),
          label: `${el.type_niveau_nom} · ${el.code ? el.code + " — " : ""}${el.nom}`,
        })) ?? []}
        value={elementsSelectionnes}
        onChange={setElementsSelectionnes}
        searchable
        clearable
      />

      <Divider label={voc("Valeur de l'indicateur")} labelPosition="left" mt="xs" />
      <SegmentedControl value={mode} onChange={(v) => setMode(v as "SAISIE" | "FORMULE")}
        data={[{ value: "SAISIE", label: voc("Valeurs saisies au fil du suivi") },
          { value: "FORMULE", label: voc("Calculé par une formule"), disabled: aDesSaisies }]} />
      {aDesSaisies && (
        <Text size="xs" c="dimmed">{voc("Cet indicateur a déjà des valeurs saisies : pour un calcul par formule, créez un nouvel indicateur.")}</Text>
      )}
      {mode === "FORMULE" && (
        <FormuleEditeur value={formule} onChange={setFormule} projetId={projetIdCourant}
          onModele={(m) => {
            if (!libelle) setLibelle(m.titre);
            if (!unite) setUnite(m.unite);
            setSens(m.sens);
          }} />
      )}

      <Group justify="flex-end">
        <Button onClick={handleSubmit} loading={createIndicateur.isPending || updateIndicateur.isPending}>
          {enEdition ? voc("Enregistrer") : voc("Créer")}
        </Button>
      </Group>
    </Stack>
  );
}
