import { useMemo, useState } from "react";
import { Group, Select, Text } from "@mantine/core";
import { useCreateZone, useNiveauxAdministratifs, useZones } from "../../api/geo";
import type { NiveauAdministratif, Zone } from "../../types";
import { voc } from "../../utils/vocabulaire";

/** Zone choisie à chaque niveau administratif (clé = id du NiveauAdministratif). */
export type ZoneCascadeValue = Record<number, string | null>;

export const ZONE_CASCADE_VIDE: ZoneCascadeValue = {};

const PREFIXE_CREATION = "__creer__";

/** La zone la plus précise renseignée (le niveau le plus profond ayant une valeur) — celle à sauvegarder. */
export function zoneResolueDe(value: ZoneCascadeValue, niveaux: NiveauAdministratif[]): number | null {
  const duPlusProfondAuMoinsProfond = [...niveaux].sort((a, b) => b.ordre - a.ordre);
  for (const niveau of duPlusProfondAuMoinsProfond) {
    const v = value[niveau.id];
    if (v) return Number(v);
  }
  return null;
}

/**
 * Opération inverse de zoneResolueDe : reconstruit la valeur de chaque
 * niveau de la cascade en remontant la chaîne `parent` à partir d'une seule
 * zone (la plus précise) déjà enregistrée — utile pour pré-remplir le
 * formulaire en édition, où seule cette zone finale est connue.
 */
export function zoneCascadeDepuis(zoneId: number | null | undefined, zones: Zone[]): ZoneCascadeValue {
  if (!zoneId) return {};
  const zonesParId = new Map(zones.map((z) => [z.id, z]));
  const valeur: ZoneCascadeValue = {};
  let courante = zonesParId.get(zoneId);
  while (courante) {
    valeur[courante.niveau_administratif] = String(courante.id);
    courante = courante.parent ? zonesParId.get(courante.parent) : undefined;
  }
  return valeur;
}

function NiveauSelect({
  niveau,
  zones,
  parentId,
  value,
  disabled,
  creerEnCours,
  onChange,
  onCreer,
}: {
  niveau: NiveauAdministratif;
  zones: Zone[];
  parentId: string | null;
  value: string | null;
  disabled: boolean;
  creerEnCours: boolean;
  onChange: (v: string | null) => void;
  onCreer: (nom: string) => void;
}) {
  const [recherche, setRecherche] = useState("");
  const options = zones.filter(
    (z) => z.niveau_administratif === niveau.id && (!parentId || String(z.parent) === parentId),
  );
  const data = options.map((z) => ({ value: String(z.id), label: z.nom }));
  const texte = recherche.trim();
  const dejaExistant = options.some((z) => z.nom.toLowerCase() === texte.toLowerCase());
  if (texte && !dejaExistant) {
    data.push({ value: `${PREFIXE_CREATION}${texte}`, label: `+ Créer « ${texte} »` });
  }

  return (
    <Select
      label={niveau.nom_niveau}
      placeholder={disabled ? "—" : niveau.aide_code || "Choisir…"}
      data={data}
      value={value}
      searchable
      clearable
      searchValue={recherche}
      onSearchChange={setRecherche}
      disabled={disabled || creerEnCours}
      onChange={(v) => {
        if (v?.startsWith(PREFIXE_CREATION)) {
          onCreer(v.slice(PREFIXE_CREATION.length));
          setRecherche("");
          return;
        }
        onChange(v);
        setRecherche("");
      }}
    />
  );
}

/**
 * Cascade de sélecteurs entièrement dérivée des niveaux administratifs
 * configurés pour le pays choisi (nombre, noms, ordre paramétrables — voir
 * « Zones administratives ») — pas de Région/Province/Village en dur.
 * Chaque niveau permet de créer une zone à la volée en tapant son nom. Le
 * saut de niveau (ex : ne renseigner que la région) est autorisé par défaut,
 * paramétrable niveau par niveau.
 */
export function ZoneCascadeFields({
  pays,
  value,
  onChange,
}: {
  pays: string | null;
  value: ZoneCascadeValue;
  onChange: (v: ZoneCascadeValue) => void;
}) {
  const { data: niveaux } = useNiveauxAdministratifs(pays);
  const { data: zones } = useZones({ pays: pays ?? undefined });
  const createZone = useCreateZone();

  const niveauxTries = useMemo(() => [...(niveaux ?? [])].sort((a, b) => a.ordre - b.ordre), [niveaux]);

  if (!pays) {
    return (
      <Text size="sm" c="dimmed">
        Choisis un pays pour renseigner la localisation.
      </Text>
    );
  }

  if (niveauxTries.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {voc("Aucun niveau administratif configuré pour ce pays — configure-le dans « Zones administratives ».")}</Text>
    );
  }

  return (
    <Group grow align="flex-end" wrap="wrap">
      {niveauxTries.map((niveau, index) => {
        const parentValue = niveau.niveau_parent ? value[niveau.niveau_parent] ?? null : null;
        const disabled = !!niveau.niveau_parent && !parentValue && !niveau.saut_niveau_autorise;

        function reinitialiserNiveauxEnfants(base: ZoneCascadeValue) {
          const suivant = { ...base };
          niveauxTries.slice(index + 1).forEach((n) => {
            suivant[n.id] = null;
          });
          return suivant;
        }

        return (
          <NiveauSelect
            key={niveau.id}
            niveau={niveau}
            zones={zones ?? []}
            parentId={parentValue}
            value={value[niveau.id] ?? null}
            disabled={disabled}
            creerEnCours={createZone.isPending}
            onChange={(v) => onChange(reinitialiserNiveauxEnfants({ ...value, [niveau.id]: v }))}
            onCreer={(nom) => {
              createZone.mutate(
                { nom, niveau_administratif: niveau.id, parent: parentValue ? Number(parentValue) : null },
                {
                  onSuccess: (zoneCreee) => {
                    onChange(reinitialiserNiveauxEnfants({ ...value, [niveau.id]: String(zoneCreee.id) }));
                  },
                },
              );
            }}
          />
        );
      })}
    </Group>
  );
}
