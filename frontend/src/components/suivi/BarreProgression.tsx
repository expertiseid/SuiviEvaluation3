import { Group, Text, Tooltip } from "@mantine/core";
import { STATUS_HEX } from "../common/statusPalette";
import type { StatusTone } from "../common/StatusBadge";
import { voc } from "../../utils/vocabulaire";

export function toneDeTaux(taux: number | null): StatusTone {
  if (taux === null) return "neutral";
  if (taux < 50) return "danger";
  if (taux < 80) return "warning";
  return "success";
}

export interface SegmentProgression {
  key: string | number;
  valeur: number;
  titre: string;
}

/**
 * Barre de progression empilée : chaque segment = ce qui a été réalisé
 * PENDANT une période donnée (pas un cumul), mis bout à bout pour former le
 * total réalisé — avec un repère gris pour la valeur attendue aujourd'hui
 * au vu du planning, et un repère teal pour la cible. Lisible même avec un
 * seul segment (contrairement à une courbe, qui a besoin d'au moins deux
 * points pour tracer un trait).
 */
export function BarreProgression({
  label,
  segments,
  cible,
  attendu,
  unite,
  tone = "success",
  couleur,
}: {
  label?: string;
  segments: SegmentProgression[];
  cible: number;
  attendu?: number | null;
  unite?: string;
  tone?: StatusTone;
  /** Couleur hexadécimale — prioritaire sur `tone` (utilisée pour les paliers d'alerte configurables). */
  couleur?: string;
}) {
  const couleurBarre = couleur ?? STATUS_HEX[tone];
  const total = segments.reduce((somme, s) => somme + s.valeur, 0);
  const maxValeur = Math.max(cible, total, attendu ?? 0, 1);
  const pctCible = Math.min(100, (cible / maxValeur) * 100);
  const pctAttendu = attendu != null ? Math.min(100, (attendu / maxValeur) * 100) : null;
  const tauxReel = cible ? Math.round((total / cible) * 1000) / 10 : null;

  let curseur = 0;
  const segmentsPositionnes = segments.map((s) => {
    const largeur = Math.max(0, (s.valeur / maxValeur) * 100);
    const gauche = curseur;
    curseur += largeur;
    return { ...s, gauche, largeur };
  });

  return (
    <div style={{ marginBottom: 8 }}>
      {label && (
        <Text size="sm" fw={600} c="dimmed" tt="uppercase" style={{ letterSpacing: 0.3 }}>
          {label}
        </Text>
      )}
      <div
        style={{
          position: "relative",
          height: 18,
          marginTop: 6,
          marginBottom: 2,
          background: "var(--mantine-color-gray-2)",
          borderRadius: 9,
        }}
      >
        {segmentsPositionnes.map((s, i) => (
          <Tooltip key={s.key} label={s.titre}>
            <div
              style={{
                position: "absolute",
                left: `${s.gauche}%`,
                top: 0,
                bottom: 0,
                width: `${s.largeur}%`,
                background: couleurBarre,
                borderRight: i < segmentsPositionnes.length - 1 ? "2px solid var(--mantine-color-gray-2)" : "none",
                borderTopLeftRadius: i === 0 ? 9 : 0,
                borderBottomLeftRadius: i === 0 ? 9 : 0,
                borderTopRightRadius: i === segmentsPositionnes.length - 1 ? 9 : 0,
                borderBottomRightRadius: i === segmentsPositionnes.length - 1 ? 9 : 0,
              }}
            />
          </Tooltip>
        ))}
        {pctAttendu != null && (
          <div
            title={voc`Attendu aujourd'hui : ${Math.round(attendu!)}${unite ? " " + unite : ""}`}
            style={{
              position: "absolute",
              left: `calc(${pctAttendu}% - 1px)`,
              top: -3,
              bottom: -3,
              width: 2,
              background: "var(--mantine-color-gray-6)",
            }}
          />
        )}
        <div
          title={voc`Cible : ${cible}${unite ? " " + unite : ""}`}
          style={{
            position: "absolute",
            left: `calc(${pctCible}% - 1px)`,
            top: -3,
            bottom: -3,
            width: 2,
            background: "var(--mantine-color-teal-7)",
          }}
        />
      </div>
      <Group justify="space-between" gap="xs">
        <Text size="md" fw={600}>
          {total} / {cible}{unite ? ` ${unite}` : ""}{tauxReel !== null ? ` · ${tauxReel}%` : ""}
        </Text>
        {attendu != null && (
          <Text size="sm" c="dimmed">
            {voc("Attendu aujourd'hui :")} {Math.round(attendu)}{unite ? ` ${unite}` : ""}
          </Text>
        )}
      </Group>
    </div>
  );
}
