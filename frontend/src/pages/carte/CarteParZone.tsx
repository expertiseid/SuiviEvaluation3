import { Fragment } from "react";
import { Link } from "react-router-dom";
import { Group, Progress, Table, Text } from "@mantine/core";
import { GeoJSON, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { useLimitesAdministratives, type IndicateurZone, type SyntheseZone } from "../../api/geo";
import { SANS_DONNEE, classes, couleur, degrade, entier, formatValeur, infoIndicateur, normaliser, valeurZone } from "../../utils/carteParZone";
import { voc } from "../../utils/vocabulaire";

/** Étiquette d'une zone : son nom, puis une ligne par indicateur choisi. */
function etiquetteValeur(nom: string, lignes: string[]) {
  const span = document.createElement("span");
  const petit = document.createElement("small");
  petit.textContent = nom;
  span.append(petit);
  lignes.forEach((ligne, i) => {
    if (i > 0) span.append(document.createElement("br"));
    span.append(ligne);
  });
  return L.divIcon({ className: "etiquette-carte valeur-zone", html: span.outerHTML, iconSize: [0, 0] });
}

/** Détail d'une zone : indicateurs choisis, chiffres et projets présents. */
function DetailZone({ z, niveau, indicateurs }: { z: SyntheseZone; niveau: string; indicateurs: IndicateurZone[] }) {
  return (
    <div style={{ minWidth: 300 }}>
      <Text fw={700} size="sm">{niveau} {z.nom}</Text>
      <Text size="xs" c="dimmed" mb={6}>
        {z.projets} {z.projets > 1 ? voc("projets") : voc("projet")} · {z.beneficiaires} {z.beneficiaires > 1 ? voc("bénéficiaires") : voc("bénéficiaire")} ({voc`${z.femmes} F, ${z.hommes} H`}) · {voc("budget")} {formatValeur("budget", z.budget)} {voc("FCFA")}
      </Text>
      {indicateurs.length > 0 && (
        <Table fz="xs" verticalSpacing={2} horizontalSpacing={4} mb={6} withRowBorders={false}>
          <Table.Tbody>
            {indicateurs.map((i) => (
              <Table.Tr key={i}>
                <Table.Td c="dimmed">{infoIndicateur(i).libelle}</Table.Td>
                <Table.Td ta="right" fw={700}>{formatValeur(i, valeurZone(z, i))}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {z.liste_projets.length > 0 && (
        <div style={{ maxHeight: 240, overflowY: "auto" }}>
          <Table fz="xs" verticalSpacing={3} horizontalSpacing={4}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Projet")}</Table.Th>
                <Table.Th>{voc("Physique")}</Table.Th>
                <Table.Th>{voc("Financier")}</Table.Th>
                <Table.Th ta="right">{voc("Bénéf.")}</Table.Th>
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

/**
 * Zones colorées selon le premier indicateur choisi ; les valeurs de tous les indicateurs choisis
 * sont écrites dessus (et au survol), le détail s'ouvre au clic.
 */
export function CarteParZone({ pays, niveau, nomNiveau, indicateurs, zones }: {
  pays: string | undefined;
  niveau: number;
  nomNiveau: string;
  indicateurs: IndicateurZone[];
  zones: SyntheseZone[];
}) {
  const { data: limites } = useLimitesAdministratives(pays, niveau);
  if (!limites || indicateurs.length === 0) return null;
  const indicateur = indicateurs[0];
  const plusieurs = indicateurs.length > 1;
  const texte = (z: SyntheseZone) =>
    indicateurs.map((i) => (plusieurs ? `${infoIndicateur(i).court} : ${formatValeur(i, valeurZone(z, i))}` : formatValeur(i, valeurZone(z, i))));
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
        key={`${niveau}-${indicateurs.join("+")}-${zones.map((z) => `${z.zone}:${valeurZone(z, indicateur)}`).join(",")}`}
        data={{ type: "FeatureCollection", features } as GeoJSON.FeatureCollection}
        style={(f) => {
          const z = trouver(f?.properties?.shapeName);
          return { color: "#374151", weight: 1.2, fillColor: couleur(indicateur, z ? valeurZone(z, indicateur) : null, bornes), fillOpacity: 0.72 };
        }}
        onEachFeature={(f, calque) => {
          const z = trouver(f.properties?.shapeName);
          if (z) calque.bindTooltip(`<b>${z.nom.replace(/</g, "&lt;")}</b><br>${texte(z).join("<br>")}`, { sticky: true });
        }}
      />
      {zones.filter((z) => z.lat !== null && indicateurs.some((i) => (valeurZone(z, i) ?? 0) > 0)).map((z) => (
        <Marker key={`v-${z.zone}-${indicateurs.join("+")}`} position={[z.lat!, z.lng!]} icon={etiquetteValeur(z.nom, texte(z))}>
          <Popup maxWidth={380}>
            <DetailZone z={z} niveau={nomNiveau} indicateurs={indicateurs} />
          </Popup>
        </Marker>
      ))}
    </>
  );
}

/** Légende des classes de couleur. */
export function LegendeParZone({ indicateur, libelle, zones }: { indicateur: IndicateurZone; libelle: string; zones: SyntheseZone[] }) {
  const bornes = classes(indicateur, zones);
  const libelles = entier(indicateur)
    ? [
        bornes[0] - 1 <= 1 ? "1" : `1 – ${bornes[0] - 1}`,
        ...bornes.slice(0, 3).map((b, i) => (bornes[i + 1] - 1 > b ? `${b} – ${bornes[i + 1] - 1}` : `${b}`)),
        voc`${bornes[3]} et plus`,
      ]
    : [
        `< ${formatValeur(indicateur, bornes[0])}`,
        ...bornes.slice(0, 3).map((b, i) => `${formatValeur(indicateur, b)} – ${formatValeur(indicateur, bornes[i + 1])}`),
        `≥ ${formatValeur(indicateur, bornes[3])}`,
      ];
  return (
    <Group gap="sm">
      <Text size="xs" fw={600}>{libelle} :</Text>
      {degrade(indicateur).map((c, i) => (
        <Group key={c} gap={4}>
          <span style={{ width: 16, height: 11, background: c, border: "1px solid #9ca3af", display: "inline-block" }} />
          <Text size="xs" c="dimmed">{libelles[i]}</Text>
        </Group>
      ))}
      <Group gap={4}>
        <span style={{ width: 16, height: 11, background: SANS_DONNEE, border: "1px solid #9ca3af", display: "inline-block" }} />
        <Text size="xs" c="dimmed">{voc("aucun")}</Text>
      </Group>
    </Group>
  );
}
