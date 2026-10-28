import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileDown, Layers, Upload } from "lucide-react";
import { Alert, Badge, Button, Card, Chip, Group, SegmentedControl, Select, SimpleGrid, Stack, Text } from "@mantine/core";
import { CircleMarker, GeoJSON, MapContainer, Marker, Popup, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useCarteBeneficiaires, useChoixProjetsVariables } from "../../api/beneficiaries";
import {
  useCoucheCarte,
  useCouchesImportees,
  useGeojsonCouche,
  useLimitesAdministratives,
  useLocalites,
  useZones,
  type CoucheImportee,
  type LocaliteCarte,
} from "../../api/geo";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import { GererCouchesModal, ImportCoucheModal, TelechargerCarteModal } from "./FenetresCarte";

const CENTRE_PAR_DEFAUT: [number, number] = [12.3, -1.6]; // Burkina Faso

type Couche = "regions" | "provinces" | "communes" | "routes" | "villages" | "noms";
const COUCHES: { value: Couche; label: string }[] = [
  { value: "regions", label: "Régions" },
  { value: "provinces", label: "Provinces" },
  { value: "communes", label: "Communes" },
  { value: "routes", label: "Routes" },
  { value: "villages", label: "Villes et villages" },
  { value: "noms", label: "Noms" },
];

// Fonds de carte : « neutre » sans noms, pour que ceux de la base importée restent lisibles.
const FONDS: Record<string, { label: string; url: string; attribution: string } | null> = {
  neutre: {
    label: "Neutre",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attribution: "Fond &copy; Esri",
  },
  osm: {
    label: "OpenStreetMap",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    label: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Imagerie &copy; Esri, Maxar, Earthstar Geographics",
  },
  aucun: null,
};

// Contours : du plus marqué (régions) au plus discret (communes).
const STYLE_LIMITES: Record<number, L.PathOptions> = {
  1: { color: "#1f2937", weight: 2.2, fillOpacity: 0.02 },
  2: { color: "#4b5563", weight: 1.3, fillOpacity: 0, dashArray: "5 4" },
  3: { color: "#9ca3af", weight: 0.8, fillOpacity: 0, dashArray: "2 3" },
};
const STYLE_ROUTES: Record<string, { color: string; weight: number; libelle: string }> = {
  NATIONALE: { color: "#dc2626", weight: 2.6, libelle: "Nationale" },
  REGIONALE: { color: "#ea580c", weight: 1.8, libelle: "Régionale" },
  DEPARTEMENTALE: { color: "#ca8a04", weight: 1.2, libelle: "Départementale" },
};
// Noms affichés selon le zoom, pour ne pas surcharger la carte.
const ZOOM_NOMS: Record<number, [number, number]> = { 1: [0, 9], 2: [8, 11], 3: [9, 30] };
const ZOOM_VILLAGES = 10;
const ZOOM_NOMS_VILLAGES = 12;

const STYLE_ETIQUETTES = `
.etiquette-carte { background: none; border: none; white-space: nowrap; pointer-events: none;
  font: 600 11px/1 system-ui, sans-serif; color: #374151; text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 2px #fff; }
.etiquette-carte span { display: inline-block; transform: translate(-50%, -50%); }
.etiquette-carte.n1 { font-size: 13px; font-weight: 700; color: #111827; text-transform: uppercase; letter-spacing: .5px; }
.etiquette-carte.n3 { font-weight: 500; color: #6b7280; font-size: 10px; }
.etiquette-carte.village span { transform: translate(5px, -50%); font-weight: 500; font-size: 10px; color: #1f2937; }
`;

function etiquette(texte: string, classe: string) {
  const span = document.createElement("span");
  span.textContent = texte;
  return L.divIcon({ className: `etiquette-carte ${classe}`, html: span.outerHTML, iconSize: [0, 0] });
}

function Chiffre({ valeur, libelle, couleur }: { valeur: number; libelle: string; couleur?: string }) {
  return (
    <div>
      <Text size="xl" fw={700} c={couleur} lh={1.1}>{valeur.toLocaleString("fr-FR")}</Text>
      <Text size="xs" c="dimmed">{libelle}</Text>
    </div>
  );
}

/** Suit le zoom et la zone visible (pour les noms et le chargement des villages). */
function SuiviVue({ onChange }: { onChange: (zoom: number, bbox: string) => void }) {
  const carte = useMapEvents({
    moveend: () => signaler(),
    zoomend: () => signaler(),
  });
  function signaler() {
    const b = carte.getBounds().pad(0.2);
    onChange(carte.getZoom(), [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()].map((x) => x.toFixed(2)).join(","));
  }
  // Vue de départ (le cadrage initial a lieu avant l'écoute des déplacements).
  useEffect(() => {
    carte.whenReady(signaler);
  }, [carte]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function Limites({ pays, niveau, zoom, noms }: { pays: string | undefined; niveau: number; zoom: number; noms: boolean }) {
  const { data } = useLimitesAdministratives(pays, niveau);
  if (!data) return null;
  const [min, max] = ZOOM_NOMS[niveau];
  return (
    <>
      <GeoJSON
        key={`${data.pays}-${data.niveau}-${data.source}`}
        data={data.geojson}
        style={STYLE_LIMITES[niveau]}
        onEachFeature={(feature, couche) => couche.bindTooltip(String(feature.properties?.shapeName ?? ""), { sticky: true })}
      />
      {noms && zoom >= min && zoom < max &&
        data.geojson.features.map((f) =>
          f.properties?.lat != null ? (
            <Marker
              key={`n${niveau}-${f.properties.shapeName}-${f.properties.lat}`}
              position={[f.properties.lat, f.properties.lng]}
              icon={etiquette(f.properties.shapeName, `n${niveau}`)}
              interactive={false}
            />
          ) : null,
        )}
    </>
  );
}

function Routes({ pays }: { pays: string | undefined }) {
  const { data } = useCoucheCarte(pays, "routes", true);
  if (!data) return null;
  return (
    <GeoJSON
      key={`routes-${pays}`}
      data={data.geojson}
      style={(f) => {
        const s = STYLE_ROUTES[f?.properties?.classe] ?? STYLE_ROUTES.DEPARTEMENTALE;
        return { color: s.color, weight: s.weight, opacity: 0.85 };
      }}
      onEachFeature={(f, couche) => {
        const s = STYLE_ROUTES[f.properties?.classe];
        if (f.properties?.nom || s) couche.bindTooltip(`${f.properties?.nom || "Route"}${s ? ` — ${s.libelle.toLowerCase()}` : ""}`, { sticky: true });
      }}
    />
  );
}

const RAYON_LOCALITE: Record<LocaliteCarte["statut"], number> = { VILLE: 4.5, VILLAGE_ADMIN: 3, VILLAGE: 2.5 };

function Villages({ pays, bbox, zoom, noms }: { pays: string | undefined; bbox: string | null; zoom: number; noms: boolean }) {
  const { data } = useLocalites(pays, zoom >= ZOOM_VILLAGES ? bbox : null);
  if (zoom < ZOOM_VILLAGES || !data) return null;
  return (
    <>
      {data.localites.map((l) => (
        <CircleMarker
          key={`l-${l.lat}-${l.lng}`}
          center={[l.lat, l.lng]}
          radius={RAYON_LOCALITE[l.statut]}
          pathOptions={{ color: "#1f2937", weight: 1, fillColor: l.statut === "VILLE" ? "#1f2937" : "#fff", fillOpacity: 1 }}
        >
          <Tooltip>{l.nom}{l.commune && l.commune !== l.nom ? ` (commune de ${l.commune})` : ""}</Tooltip>
        </CircleMarker>
      ))}
      {noms && zoom >= ZOOM_NOMS_VILLAGES &&
        data.localites.map((l) => (
          <Marker key={`ln-${l.lat}-${l.lng}`} position={[l.lat, l.lng]} icon={etiquette(l.nom, "village")} interactive={false} />
        ))}
    </>
  );
}

/** Couche importée (shapefile…) : sa couleur, ses noms au survol et ses attributs au clic. */
function CoucheImporteeCarte({ couche }: { couche: CoucheImportee }) {
  const { data } = useGeojsonCouche(couche.id, true);
  if (!data) return null;
  return (
    <GeoJSON
      key={`${couche.id}-${couche.couleur}-${couche.champ_etiquette}`}
      data={data}
      style={{ color: couche.couleur, weight: couche.geometrie === "LIGNE" ? 3 : 1.6, fillOpacity: 0.15 }}
      pointToLayer={(_f, position) => L.circleMarker(position, { radius: 5, color: "#fff", weight: 1, fillColor: couche.couleur, fillOpacity: 1 })}
      onEachFeature={(f, calque) => {
        const p = f.properties ?? {};
        const nom = couche.champ_etiquette ? p[couche.champ_etiquette] : null;
        if (nom) calque.bindTooltip(String(nom), { sticky: true });
        const lignes = Object.entries(p).filter(([, v]) => v !== null && v !== "").map(([k, v]) => `<b>${k}</b> : ${String(v).replace(/</g, "&lt;")}`);
        calque.bindPopup(`<div style="font-size:12px"><div style="font-weight:600;margin-bottom:4px">${couche.nom.replace(/</g, "&lt;")}</div>${lignes.join("<br>")}</div>`);
      }}
    />
  );
}

/**
 * Carte (rubrique du menu) : bénéficiaires positionnés par GPS (points orange) ou regroupés au
 * centre de leur localité (cercles verts), filtrés par projet et par zone ; couches de fond au
 * choix, couches importées (shapefile…) et carte imprimable à télécharger.
 */
export function CartePage() {
  const [projet, setProjet] = useState<string | null>(null);
  const [zone, setZone] = useState<string | null>(null);
  const [importeesVisibles, setImporteesVisibles] = useState<string[]>([]);
  const [fenetre, setFenetre] = useState<"import" | "gerer" | "telecharger" | null>(null);
  const { data: couchesImportees = [] } = useCouchesImportees();
  const { peutEcrire } = useAccesModules();
  const [couches, setCouches] = useState<Couche[]>(["regions", "provinces", "routes", "villages", "noms"]);
  const [fond, setFond] = useState<string | null>(null);
  const [vue, setVue] = useState<{ zoom: number; bbox: string | null }>({ zoom: 6, bbox: null });
  const { data: projets = [] } = useChoixProjetsVariables(true);
  const { data, isLoading } = useCarteBeneficiaires(projet ? Number(projet) : null, zone ? Number(zone) : null);
  const pays = data?.pays;
  const { data: zones = [] } = useZones({ pays: pays ?? null });
  // Zones regroupées par niveau (Région, Province…) pour le filtre.
  const choixZones = useMemo(() => {
    const groupes = new Map<string, { value: string; label: string }[]>();
    zones.forEach((z) => groupes.set(z.niveau_administratif_nom, [...(groupes.get(z.niveau_administratif_nom) ?? []), { value: String(z.id), label: z.nom }]));
    return [...groupes.entries()].map(([group, items]) => ({ group, items: items.sort((a, b) => a.label.localeCompare(b.label)) }));
  }, [zones]);
  const { data: regions, isError: limitesIndisponibles } = useLimitesAdministratives(pays, 1);
  const { data: routes } = useCoucheCarte(pays, "routes", couches.includes("routes"));
  const active = (c: Couche) => couches.includes(c);
  // Par défaut : fond neutre si une base nationale (avec ses noms) est importée, sinon OpenStreetMap.
  const fondChoisi = fond ?? (regions && regions.source !== "geoBoundaries" ? "neutre" : "osm");
  const tuiles = FONDS[fondChoisi];
  const noms = active("noms");

  // Vue cadrée sur la zone choisie, sinon sur les bénéficiaires (avec une marge), sinon sur le pays.
  const contourZone = data?.zone_filtre?.contour ?? null;
  const cadre = useMemo<[[number, number], [number, number]] | null>(() => {
    if (contourZone) {
      const b = L.geoJSON(contourZone as GeoJSON.Geometry).getBounds();
      return [[b.getSouth(), b.getWest()], [b.getNorth(), b.getEast()]];
    }
    const positions = [...(data?.points ?? []), ...(data?.zones ?? [])];
    if (positions.length === 0) return null;
    const lats = positions.map((p) => p.lat);
    const lngs = positions.map((p) => p.lng);
    return [
      [Math.min(...lats) - 0.6, Math.min(...lngs) - 0.6],
      [Math.max(...lats) + 0.6, Math.max(...lngs) + 0.6],
    ];
  }, [data, contourZone]);
  const maxZone = Math.max(1, ...(data?.zones ?? []).map((z) => z.nombre));

  return (
    <Stack gap="md">
      <style>{STYLE_ETIQUETTES}</style>
      <Group justify="space-between">
        <TitreRubrique route="/carte" defaut="Carte" />
        <Group gap="xs">
          {peutEcrire("/carte") && (
            <Button variant="light" color="grape" leftSection={<Upload size={16} />} onClick={() => setFenetre("import")}>Importer une couche</Button>
          )}
          <Button leftSection={<FileDown size={16} />} onClick={() => setFenetre("telecharger")}>Télécharger la carte</Button>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Select placeholder={voc("Tous les projets")} data={projets} value={projet} onChange={setProjet} clearable searchable />
        <Select
          placeholder="Toutes les zones (région, province, commune…)"
          data={choixZones}
          value={zone}
          onChange={setZone}
          clearable
          searchable
          nothingFoundMessage="Aucune zone"
        />
      </SimpleGrid>

      {data && (
        <Card withBorder padding="sm">
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <Chiffre valeur={data.total} libelle={`${voc("bénéficiaires")} (${data.femmes} F, ${data.hommes} H)`} />
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

      <Group gap="md" justify="space-between">
      <Group gap="xs">
        <Text size="sm" fw={500}>Couches :</Text>
        <Chip.Group multiple value={couches} onChange={(v) => setCouches(v as Couche[])}>
          {COUCHES.filter((c) => c.value !== "routes" || routes !== undefined || active("routes")).map((c) => (
            <Chip key={c.value} value={c.value} size="xs" variant="light">
              {c.label}
            </Chip>
          ))}
        </Chip.Group>
        {couchesImportees.length > 0 && (
          <Chip.Group multiple value={importeesVisibles} onChange={setImporteesVisibles}>
            {couchesImportees.map((c) => (
              <Chip key={c.id} value={String(c.id)} size="xs" variant="light" color="grape">
                <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 2, background: c.couleur, marginRight: 5 }} />
                {c.nom}
              </Chip>
            ))}
          </Chip.Group>
        )}
        {couchesImportees.length > 0 && peutEcrire("/carte") && (
          <Button size="compact-xs" variant="subtle" leftSection={<Layers size={12} />} onClick={() => setFenetre("gerer")}>Gérer</Button>
        )}
      </Group>
      <Group gap="xs">
        <Text size="sm" fw={500}>Fond :</Text>
        <SegmentedControl
          size="xs"
          value={fondChoisi}
          onChange={setFond}
          data={Object.entries(FONDS).map(([value, f]) => ({ value, label: f?.label ?? "Aucun" }))}
        />
      </Group>
      </Group>

      {/* « isolate » : les calques Leaflet (z-index 400+) restent sous les fenêtres et menus. */}
      <Card withBorder padding={0} radius="md" style={{ overflow: "hidden", isolation: "isolate" }}>
        {isLoading ? (
          <Text p="md">Chargement…</Text>
        ) : (
          <MapContainer
            key={JSON.stringify(cadre)}
            {...(cadre ? { bounds: cadre } : { center: CENTRE_PAR_DEFAUT, zoom: 6 })}
            style={{ height: "min(600px, 70vh)", width: "100%" }}
            scrollWheelZoom
            preferCanvas
          >
            <SuiviVue onChange={(zoom, bbox) => setVue({ zoom, bbox })} />
            {tuiles && (
              <TileLayer key={fondChoisi} attribution={tuiles.attribution} url={tuiles.url} />
            )}
            {active("communes") && <Limites pays={pays} niveau={3} zoom={vue.zoom} noms={noms} />}
            {active("provinces") && <Limites pays={pays} niveau={2} zoom={vue.zoom} noms={noms} />}
            {active("regions") && <Limites pays={pays} niveau={1} zoom={vue.zoom} noms={noms} />}
            {active("routes") && <Routes pays={pays} />}
            {active("villages") && <Villages pays={pays} bbox={vue.bbox} zoom={vue.zoom} noms={noms} />}
            {contourZone && (
              <GeoJSON key={`zone-${data?.zone_filtre?.id}`} data={contourZone as GeoJSON.Geometry} style={{ color: "#0c8a5f", weight: 3, fillColor: "#12b886", fillOpacity: 0.06 }} interactive={false} />
            )}
            {couchesImportees.filter((c) => importeesVisibles.includes(String(c.id))).map((c) => <CoucheImporteeCarte key={c.id} couche={c} />)}
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
      <Group gap="md">
        {active("routes") && routes &&
          Object.values(STYLE_ROUTES).map((s) => (
            <Group key={s.libelle} gap={6}>
              <div style={{ width: 22, height: s.weight + 1, background: s.color, borderRadius: 2 }} />
              <Text size="xs" c="dimmed">Route {s.libelle.toLowerCase()}</Text>
            </Group>
          ))}
        {active("villages") && vue.zoom < ZOOM_VILLAGES && (
          <Text size="xs" c="dimmed">Zoomer pour voir les villes et villages.</Text>
        )}
      </Group>
      {regions?.source === "geoBoundaries" && (
        <Text size="xs" c="dimmed">
          {`Contours : geoBoundaries (${regions.annee}) — un découpage plus récent que la source n'y figure pas encore ; ses zones sont placées au centre de leurs zones rattachées.`}
        </Text>
      )}
      {fenetre === "import" && <ImportCoucheModal onClose={() => setFenetre(null)} />}
      {fenetre === "gerer" && <GererCouchesModal couches={couchesImportees} onClose={() => setFenetre(null)} />}
      {fenetre === "telecharger" && (
        <TelechargerCarteModal
          options={{ projet: projet ? Number(projet) : null, zone: zone ? Number(zone) : null, couches, importees: importeesVisibles.map(Number) }}
          couchesImportees={couchesImportees}
          onClose={() => setFenetre(null)}
        />
      )}
    </Stack>
  );
}
