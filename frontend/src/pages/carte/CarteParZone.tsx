import { Fragment } from "react";
import { Link } from "react-router-dom";
import { Group, Progress, Table, Text } from "@mantine/core";
import { GeoJSON, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { useLimitesAdministratives, type IndicateurZone, type SyntheseZone } from "../../api/geo";
import { DEGRADES, SANS_DONNEE, classes, couleur, formatValeur, normaliser } from "../../utils/carteParZone";
import { voc } from "../../utils/vocabulaire";

function etiquetteValeur(nom: string, texte: string) {
  const span = document.createElement("span");
  const petit = document.createElement("small");
  petit.textContent = nom;
  span.append(petit, texte);
  return L.divIcon({ className: "etiquette-carte valeur-zone", html: span.outerHTML, iconSize: [0, 0] });
}

/** Détail d'une zone : chiffres et projets présents. */
function DetailZone({ z, niveau }: { z: SyntheseZone; niveau: string }) {
  return (
    <div style={{ minWidth: 300 }}>
      <Text fw={700} size="sm">{niveau} {z.nom}</Text>
      <Text size="xs" c="dimmed" mb={6}>
        {z.projets} {voc("projet")}{z.projets > 1 ? "s" : ""} · {z.beneficiaires} {voc("bénéficiaire")}{z.beneficiaires > 1 ? "s" : ""} ({z.femmes} F, {z.hommes} H) ·
        budget {formatValeur("budget", z.budget)} FCFA
      </Text>
      {z.liste_projets.length > 0 && (
        <div style={{ maxHeight: 240, overflowY: "auto" }}>
          <Table fz="xs" verticalSpacing={3} horizontalSpacing={4}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Projet")}</Table.Th>
                <Table.Th>Physique</Table.Th>
                <Table.Th>Financier</Table.Th>
                <Table.Th ta="right">Bénéf.</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {z.liste_projets.map((p) => (
                <Fragment key={p.id}>
                  <Table.Tr>
                    <Table.Td>
                      <Text component={Link} to={`/projets/${p.id}`} size="xs" fw={600} c="teal.8" title={p.nom}>{p.code}</Text>
                    </Table.Td>
                    <Table.Td w={70}>
                      <Progress value={Math.min(p.taux_physique ?? 0, 100)} size="sm" color="blue" />
                      <Text size="10px">{formatValeur("taux_physique", p.taux_physique)}</Text>
                    </Table.Td>
                    <Table.Td w={70}>
                      <Progress value={Math.min(p.taux_financier ?? 0, 100)} size="sm" color="teal" />
                      <Text size="10px">{formatValeur("taux_financier", p.taux_financier)}</Text>
                    </Table.Td>
                    <Table.Td ta="right">{p.beneficiaires}</Table.Td>
                  </Table.Tr>
                </Fragment>
              ))}
            </Table.Tbody>
          </Table>
        </div>
      )}
    </div>
  );
}

/** Zones colorées selon l'indicateur choisi, valeur écrite dessus, détail au clic. */
export function CarteParZone({ pays, niveau, nomNiveau, indicateur, zones }: {
  pays: string | undefined;
  niveau: number;
  nomNiveau: string;
  indicateur: IndicateurZone;
  zones: SyntheseZone[];
}) {
  const { data: limites } = useLimitesAdministratives(pays, niveau);
  if (!limites) return null;
  const parNom = new Map(zones.map((z) => [normaliser(z.nom), z]));
  const bornes = classes(indicateur, zones);
  const trouver = (nom: unknown) => {
    const cle = normaliser(String(nom ?? ""));
    return parNom.get(cle) ?? zones.find((z) => z.nom_contour && normaliser(z.nom_contour) === cle);
  };
  // Seules les zones de la synthèse (filtre de zone) sont dessinées.
  const features = limites.geojson.features.filter((f) => trouver(f.properties?.shapeName));
  return (
    <>
      <GeoJSON
        key={`${niveau}-${indicateur}-${zones.map((z) => `${z.zone}:${z[indicateur]}`).join(",")}`}
        data={{ type: "FeatureCollection", features } as GeoJSON.FeatureCollection}
        style={(f) => {
          const z = trouver(f?.properties?.shapeName);
          return { color: "#374151", weight: 1.2, fillColor: couleur(indicateur, z ? (z[indicateur] as number | null) : null, bornes), fillOpacity: 0.72 };
        }}
        onEachFeature={(f, calque) => {
          const z = trouver(f.properties?.shapeName);
          if (z) calque.bindTooltip(`${z.nom} : ${formatValeur(indicateur, z[indicateur] as number | null)}`, { sticky: true });
        }}
      />
      {zones.filter((z) => z.lat !== null && z[indicateur] !== null && (z[indicateur] as number) > 0).map((z) => (
        <Marker key={`v-${z.zone}`} position={[z.lat!, z.lng!]} icon={etiquetteValeur(z.nom, formatValeur(indicateur, z[indicateur] as number | null))}>
          <Popup maxWidth={380}>
            <DetailZone z={z} niveau={nomNiveau} />
          </Popup>
        </Marker>
      ))}
    </>
  );
}

/** Légende des classes de couleur. */
export function LegendeParZone({ indicateur, libelle, zones }: { indicateur: IndicateurZone; libelle: string; zones: SyntheseZone[] }) {
  const bornes = classes(indicateur, zones);
  const entier = indicateur === "projets" || indicateur === "beneficiaires";
  const libelles = entier
    ? [
        bornes[0] - 1 <= 1 ? "1" : `1 – ${bornes[0] - 1}`,
        ...bornes.slice(0, 3).map((b, i) => (bornes[i + 1] - 1 > b ? `${b} – ${bornes[i + 1] - 1}` : `${b}`)),
        `${bornes[3]} et plus`,
      ]
    : [
        `< ${formatValeur(indicateur, bornes[0])}`,
        ...bornes.slice(0, 3).map((b, i) => `${formatValeur(indicateur, b)} – ${formatValeur(indicateur, bornes[i + 1])}`),
        `≥ ${formatValeur(indicateur, bornes[3])}`,
      ];
  return (
    <Group gap="sm">
      <Text size="xs" fw={600}>{libelle} :</Text>
      {DEGRADES[indicateur].map((c, i) => (
        <Group key={c} gap={4}>
          <span style={{ width: 16, height: 11, background: c, border: "1px solid #9ca3af", display: "inline-block" }} />
          <Text size="xs" c="dimmed">{libelles[i]}</Text>
        </Group>
      ))}
      <Group gap={4}>
        <span style={{ width: 16, height: 11, background: SANS_DONNEE, border: "1px solid #9ca3af", display: "inline-block" }} />
        <Text size="xs" c="dimmed">aucun</Text>
      </Group>
    </Group>
  );
}
