import { Select } from "@mantine/core";
import { useZones } from "../../api/geo";
import { traduireDonnee } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

/** Choix d'une zone administrative (région, commune, village…) dans une seule liste avec recherche. */
export function SelecteurZone({ value, onChange, label, description, error }: {
  value: number | null;
  onChange: (zone: number | null) => void;
  label: string;
  description?: string;
  error?: string;
}) {
  const { data: zones = [] } = useZones();
  return (
    <Select
      label={label}
      description={description}
      placeholder={voc("Rechercher…")}
      data={zones.map((z) => ({
        value: String(z.id),
        label: `${z.nom} — ${traduireDonnee(z.niveau_administratif_nom)}${z.parent_nom ? ` (${z.parent_nom})` : ""}`,
      }))}
      value={value ? String(value) : null}
      onChange={(v) => onChange(v ? Number(v) : null)}
      error={error}
      searchable
      clearable
      limit={50}
    />
  );
}
