import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Alert, Badge, Button, Card, Group, SegmentedControl, Select, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { CircleMarker, GeoJSON, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useCarteBeneficiaires, useChoixProjetsVariables } from "../../api/beneficiaries";
import { useLimitesAdministratives } from "../../api/geo";
import { voc } from "../../utils/vocabulaire";

const CENTRE_PAR_DEFAUT: [number, number] = [12.3, -1.6]; // Burkina Faso

function Chiffre({ valeur, libelle, couleur }: { valeur: number; libelle: string; couleur?: string }) {
  return (
    <div>
      <Text size="xl" fw={700} c={couleur} lh={1.1}>{valeur.toLocaleString("fr-FR")}</Text>
      <Text size="xs" c="dimmed">{libelle}</Text>
    </div>
  );
}

/**
 * Carte des bénéficiaires : limites administratives du pays (geoBoundaries), bénéficiaires
 * positionnés par GPS (points orange) et, pour les autres, regroupés au centre de leur localité
 * (cercles verts, taille selon le nombre).
 */
export function CarteBeneficiairesPage() {
  const [projet, setProjet] = useState<string | null>(null);
  const [niveauLimites, setNiveauLimites] = useState("2");
  const { data: projets = [] } = useChoixProjetsVariables(true);
  const { data, isLoading } = useCarteBeneficiaires(projet ? Number(projet) : null);
  const { data: limites, isError: limitesIndisponibles } = useLimitesAdministratives(data?.pays, Number(niveauLimites));

  // Vue cadrée sur les bénéficiaires (avec une marge), sinon sur le pays par défaut.
  const cadre = useMemo<[[number, number], [number, number]] | null>(() => {
    const positions = [...(data?.points ?? []), ...(data?.zones ?? [])];
    if (positions.length === 0) return null;
    const lats = positions.map((p) => p.lat);
    const lngs = positions.map((p) => p.lng);
    return [
      [Math.min(...lats) - 0.6, Math.min(...lngs) - 0.6],
      [Math.max(...lats) + 0.6, Math.max(...lngs) + 0.6],
    ];
  }, [data]);
  const maxZone = Math.max(1, ...(data?.zones ?? []).map((z) => z.nombre));

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <Button component={Link} to="/beneficiaires" variant="subtle" leftSection={<ArrowLeft size={16} />} px={6}>
            {voc("Bénéficiaires")}
          </Button>
          <Title order={2}>{voc("Carte des bénéficiaires")}</Title>
        </Group>
        <Group>
          <Select
            placeholder={voc("Tous les projets")}
            data={projets}
            value={projet}
            onChange={setProjet}
            clearable
            searchable
            w={320}
          />
          <SegmentedControl
            value={niveauLimites}
            onChange={setNiveauLimites}
            data={[
              { value: "1", label: "Régions" },
              { value: "2", label: "Provinces" },
            ]}
          />
        </Group>
      </Group>

      {data && (
        <Card withBorder padding="sm">
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <Chiffre valeur={data.total} libelle={voc("bénéficiaires")} />
            <Chiffre valeur={data.points.length} libelle="positionnés par GPS" couleur="orange.7" />
            <Chiffre valeur={data.zones.reduce((s, z) => s + z.nombre, 0)} libelle="placés selon leur localité" couleur="teal.7" />
            <Chiffre valeur={data.non_localises} libelle="sans localisation" couleur={data.non_localises ? "red.7" : undefined} />
          </SimpleGrid>
        </Card>
      )}

      {limitesIndisponibles && (
        <Alert color="orange" variant="light">
          Contours administratifs indisponibles (pas d'accès à Internet ?) : la carte s'affiche sans les limites.
        </Alert>
      )}

      <Card withBorder padding={0} radius="md" style={{ overflow: "hidden" }}>
        {isLoading ? (
          <Text p="md">Chargement…</Text>
        ) : (
          <MapContainer
            key={JSON.stringify(cadre)}
            {...(cadre ? { bounds: cadre } : { center: CENTRE_PAR_DEFAUT, zoom: 6 })}
            style={{ height: 600, width: "100%" }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · limites : geoBoundaries'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {limites && (
              <GeoJSON
                key={`${limites.pays}-${limites.niveau}`}
                data={limites.geojson}
                style={{ color: "#4b5563", weight: 1, fillOpacity: 0.03 }}
                onEachFeature={(feature, couche) => couche.bindTooltip(String(feature.properties?.shapeName ?? ""), { sticky: true })}
              />
            )}
            {data?.zones.map((z) => (
              <CircleMarker
                key={`z-${z.zone}`}
                center={[z.lat, z.lng]}
                radius={8 + 22 * Math.sqrt(z.nombre / maxZone)}
                pathOptions={{ color: "#0c8a5f", fillColor: "#12b886", fillOpacity: 0.55, weight: 2 }}
              >
                <Tooltip direction="top">
                  <b>{z.nom}</b> : {z.nombre} {voc("bénéficiaire")}{z.nombre > 1 ? "s" : ""} ({z.femmes} F, {z.hommes} H)
                </Tooltip>
              </CircleMarker>
            ))}
            {data?.points.map((p) => (
              <CircleMarker key={`p-${p.id}`} center={[p.lat, p.lng]} radius={6} pathOptions={{ color: "#c2410c", fillColor: "#fb923c", fillOpacity: 0.9, weight: 1.5 }}>
                <Popup>
                  <Stack gap={2}>
                    <Text size="sm" fw={600}>{p.nom}</Text>
                    <Badge size="xs" variant="outline">{p.identifiant}</Badge>
                    <Link to={`/beneficiaires/${p.id}`}>Ouvrir la fiche</Link>
                  </Stack>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        )}
      </Card>
      {limites && (
        <Text size="xs" c="dimmed">
          {`Contours : ${limites.nom_niveau || "niveau " + limites.niveau} (${limites.annee}), source geoBoundaries — un découpage plus récent que la source n'y figure pas encore ; ses zones sont placées au centre de leurs zones rattachées.`}
        </Text>
      )}
    </Stack>
  );
}
