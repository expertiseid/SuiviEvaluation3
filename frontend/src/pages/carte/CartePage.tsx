import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, FileDown, Layers, Upload } from "lucide-react";
import { Alert, Badge, Button, Card, Chip, Group, MultiSelect, SegmentedControl, SimpleGrid, Stack, Text } from "@mantine/core";
import { CircleMarker, GeoJSON, MapContainer, Marker, Popup, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useCarteBeneficiaires, useChoixProjetsVariables, type FicheCarte } from "../../api/beneficiaries";
import {
  useCoucheCarte,
  useCouchesImportees,
  useGeojsonCouche,
  useLimitesAdministratives,
  useLocalites,
  useSyntheseCarte,
  useZones,
  type IndicateurZone,
  type CoucheImportee,
  type LocaliteCarte,
} from "../../api/geo";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import { useAccesModules } from "../../utils/modules";
import { voc } from "../../utils/vocabulaire";
import { GererCouchesModal, ImportCoucheModal, TelechargerCarteModal } from "./FenetresCarte";
import { CarteParZone, LegendeParZone } from "./CarteParZone";
import { infoIndicateur, optionsIndicateursZone } from "../../utils/carteParZone";
import { FiltresTableauDeBord } from "../../components/dashboard/FiltresTableauDeBord";
import { FILTRES_PAR_DEFAUT, versParametres, type EtatFiltres } from "../../utils/filtresTableauDeBord";
import { OutilsCarte } from "./OutilsCarte";

import { locale, traduireDonnee } from "../../utils/i18n";
const CENTRE_PAR_DEFAUT: [number, number] = [12.3, -1.6]; // Burkina Faso

type Couche = "points" | "regions" | "provinces" | "communes" | "routes" | "villages" | "noms" | "beneficiaires";
const COUCHES: { value: Couche; label: string }[] = [
  { value: "points", label: voc("Bénéficiaires") },
  { value: "regions", label: voc("Régions") },
  { value: "provinces", label: voc("Provinces") },
  { value: "communes", label: voc("Communes") },
  { value: "routes", label: voc("Routes") },
  { value: "villages", label: voc("Villes et villages") },
  { value: "noms", label: voc("Noms") },
  { value: "beneficiaires", label: voc("Noms des bénéficiaires") },
];

// Fonds de carte : « neutre » sans noms, pour que ceux de la base importée restent lisibles.
const FONDS: Record<string, { label: string; url: string; attribution: string } | null> = {
  neutre: {
    label: voc("Neutre"),
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attribution: "Fond &copy; Esri",
  },
  osm: {
    label: voc("OpenStreetMap"),
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    label: voc("Satellite"),
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
  NATIONALE: { color: "#dc2626", weight: 2.6, libelle: voc("Nationale") },
  REGIONALE: { color: "#ea580c", weight: 1.8, libelle: voc("Régionale") },
  DEPARTEMENTALE: { color: "#ca8a04", weight: 1.2, libelle: voc("Départementale") },
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
.encadre-carte:fullscreen { border-radius: 0; }
.encadre-carte:fullscreen .leaflet-container { height: 100vh !important; }
.etiquette-carte.valeur-zone { pointer-events: auto; cursor: pointer; }
.etiquette-carte.valeur-zone span { font-size: 12px; font-weight: 800; color: #111827; background: rgba(255,255,255,.88); border: 1px solid #6b7280; border-radius: 8px; padding: 2px 6px; text-align: center; line-height: 1.15; }
.etiquette-carte.valeur-zone small { display: block; font-size: 9px; font-weight: 600; color: #4b5563; text-transform: uppercase; letter-spacing: .3px; }
.etiquette-carte.beneficiaire span { transform: translate(8px, -50%); font-weight: 600; font-size: 11px; color: #9a3412; }
`;

function etiquette(texte: string, classe: string) {
  const span = document.createElement("span");
  span.textContent = texte;
  return L.divIcon({ className: `etiquette-carte ${classe}`, html: span.outerHTML, iconSize: [0, 0] });
}

function Chiffre({ valeur, libelle, couleur }: { valeur: number; libelle: string; couleur?: string }) {
  return (
    <div>
      <Text size="xl" fw={700} c={couleur} lh={1.1}>{valeur.toLocaleString(locale())}</Text>
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
          <Tooltip>{l.nom}{l.commune && l.commune !== l.nom ? voc` (commune de ${l.commune})` : ""}</Tooltip>
        </CircleMarker>
      ))}
      {noms && zoom >= ZOOM_NOMS_VILLAGES &&
        data.localites.map((l) => (
          <Marker key={`ln-${l.lat}-${l.lng}`} position={[l.lat, l.lng]} icon={etiquette(l.nom, "village")} interactive={false} />
        ))}
    </>
  );
}

/** Infos d'un bénéficiaire dans les fenêtres de la carte. */
function LigneFiche({ b }: { b: FicheCarte }) {
  return (
    <div style={{ padding: "4px 0", borderBottom: "1px solid var(--mantine-color-gray-2)" }}>
      <Group gap={6} wrap="nowrap">
        <Text component={Link} to={`/beneficiaires/${b.id}`} size="sm" fw={600} c="teal.8">{b.nom}</Text>
        <Badge size="xs" variant="outline">{b.identifiant}</Badge>
      </Group>
      <Text size="xs" c="dimmed">
        {b.sexe === "F" ? voc("Femme") : voc("Homme")}
        {b.tranche_age && ` · ${b.tranche_age}`}
        {b.telephone && ` · ${b.telephone}`}
        {b.localite && ` · ${b.localite}`}
      </Text>
      {b.projets.length > 0 && <Text size="xs">{voc("Projets")} : {b.projets.join(", ")}</Text>}
    </div>
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
  // Filtres : un ou plusieurs projets, une ou plusieurs zones (vides = tous).
  const [projetsChoisis, setProjetsChoisis] = useState<string[]>([]);
  const [zonesChoisies, setZonesChoisies] = useState<string[]>([]);
  const idsProjets = useMemo(() => projetsChoisis.map(Number), [projetsChoisis]);
  const idsZones = useMemo(() => zonesChoisies.map(Number), [zonesChoisies]);
  // Mêmes filtres que le tableau de bord (période, statuts) : projets retenus sur la carte.
  const [filtres, setFiltres] = useState<EtatFiltres>(FILTRES_PAR_DEFAUT);
  const parametresFiltres = useMemo(() => versParametres(filtres), [filtres]);
  const [importeesVisibles, setImporteesVisibles] = useState<string[]>([]);
  const [fenetre, setFenetre] = useState<"import" | "gerer" | "telecharger" | null>(null);
  // Encadré de la carte (mis en plein écran par OutilsCarte).
  const [encadre, setEncadre] = useState<HTMLDivElement | null>(null);
  // Carte par zone : indicateurs choisis (le premier colorie les zones ; aucun = carte des
  // bénéficiaires) et niveau (1 = régions…).
  const [parZone, setParZone] = useState<IndicateurZone[]>([]);
  const parZoneActif = parZone.length > 0;
  const [niveauZone, setNiveauZone] = useState("1");
  const { data: couchesImportees = [] } = useCouchesImportees();
  const { peutEcrire } = useAccesModules();
  const [couches, setCouches] = useState<Couche[]>(["points", "regions", "provinces", "routes", "villages", "noms"]);
  const [fond, setFond] = useState<string | null>(null);
  const [vue, setVue] = useState<{ zoom: number; bbox: string | null }>({ zoom: 6, bbox: null });
  const { data: projets = [] } = useChoixProjetsVariables(true);
  const { data, isLoading } = useCarteBeneficiaires(idsProjets, idsZones, parametresFiltres);
  const pays = data?.pays;
  const { data: zones = [] } = useZones({ pays: pays ?? null });
  const { data: synthese } = useSyntheseCarte(pays, Number(niveauZone), idsProjets, idsZones, parametresFiltres, parZoneActif);
  // Zones regroupées par niveau (Région, Province…) pour le filtre.
  const choixZones = useMemo(() => {
    const groupes = new Map<string, { value: string; label: string }[]>();
    zones.forEach((z) => groupes.set(traduireDonnee(z.niveau_administratif_nom), [...(groupes.get(traduireDonnee(z.niveau_administratif_nom)) ?? []), { value: String(z.id), label: z.nom }]));
    return [...groupes.entries()].map(([group, items]) => ({ group, items: items.sort((a, b) => a.label.localeCompare(b.label)) }));
  }, [zones]);
  const { data: regions, isError: limitesIndisponibles } = useLimitesAdministratives(pays, 1);
  const { data: routes } = useCoucheCarte(pays, "routes", couches.includes("routes"));
  const active = (c: Couche) => couches.includes(c);
  // Par défaut : fond neutre si une base nationale (avec ses noms) est importée, sinon OpenStreetMap.
  const fondChoisi = fond ?? (regions && regions.source !== "geoBoundaries" ? "neutre" : "osm");
  const tuiles = FONDS[fondChoisi];
  const noms = active("noms");
  // Carte par zone : le nom des zones colorées est déjà dans leur étiquette (avec la valeur).
  const nomsNiveau = (n: number) => noms && !(parZoneActif && n === Number(niveauZone));

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
        <TitreRubrique route="/carte" defaut={voc("Carte")} />
        <Group gap="xs">
          {peutEcrire("/carte") && (
            <Button variant="light" color="grape" leftSection={<Upload size={16} />} onClick={() => setFenetre("import")}>{voc("Importer une couche")}</Button>
          )}
          <Button leftSection={<FileDown size={16} />} onClick={() => setFenetre("telecharger")}>{voc("Télécharger la carte")}</Button>
        </Group>
      </Group>

      <FiltresTableauDeBord
        valeur={filtres}
        onChange={setFiltres}
        nombreProjets={data?.projets_retenus ? data.projets_retenus.length : undefined}
        portee={voc(" — la carte ne montre que ces projets et leurs bénéficiaires.")}
      />

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <MultiSelect
          placeholder={projetsChoisis.length ? "" : data?.projets_zone ? voc`${voc("Tous les projets")} de la zone (${data.projets_zone.length})` : voc("Tous les projets")}
          data={projets.filter(
            (p) =>
              projetsChoisis.includes(p.value) ||
              ((!data?.projets_zone || data.projets_zone.some((pz) => String(pz.id) === p.value)) &&
                (!data?.projets_retenus || data.projets_retenus.includes(Number(p.value)))),
          )}
          value={projetsChoisis}
          onChange={setProjetsChoisis}
          clearable
          searchable
          nothingFoundMessage={voc("Aucun projet dans cette zone")}
          comboboxProps={{ zIndex: 1000 }}
        />
        <MultiSelect
          placeholder={zonesChoisies.length ? "" : voc("Toutes les zones (région, province, commune…)")}
          data={choixZones}
          value={zonesChoisies}
          onChange={setZonesChoisies}
          clearable
          searchable
          nothingFoundMessage={voc("Aucune zone")}
          comboboxProps={{ zIndex: 1000 }}
        />
      </SimpleGrid>

      {data?.projets_zone && (
        <Card withBorder padding="sm">
          <Text size="sm" fw={600} mb={6}>
            {voc("Projets")} {data.zone_filtre ? `— ${data.zone_filtre.niveau} ${data.zone_filtre.nom}` : ""} ({data.projets_zone.length})
          </Text>
          {data.projets_zone.length === 0 ? (
            <Text size="sm" c="dimmed">{voc("Aucun projet n'intervient dans cette zone.")}</Text>
          ) : (
            <Group gap={6}>
              {data.projets_zone.map((p) => (
                <Chip
                  key={p.id}
                  size="xs"
                  checked={projetsChoisis.includes(String(p.id))}
                  onChange={() =>
                    setProjetsChoisis((choix) => (choix.includes(String(p.id)) ? choix.filter((x) => x !== String(p.id)) : [...choix, String(p.id)]))
                  }
                  title={p.nom}
                >
                  {p.code} · {p.beneficiaires} {p.beneficiaires > 1 ? voc("bénéficiaires") : voc("bénéficiaire")}
                </Chip>
              ))}
            </Group>
          )}
        </Card>
      )}

      {data && (
        <Card withBorder padding="sm">
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <Chiffre valeur={data.total} libelle={`${voc("bénéficiaires")} (${voc`${data.femmes} F, ${data.hommes} H`})`} />
            <Chiffre valeur={data.points.length} libelle={voc("positionnés par GPS")} couleur="orange.7" />
            <Chiffre valeur={data.zones.reduce((s, z) => s + z.nombre, 0)} libelle={voc("placés selon leur localité")} couleur="teal.7" />
            <Chiffre valeur={data.non_localises} libelle={voc("sans localisation")} couleur={data.non_localises ? "red.7" : undefined} />
          </SimpleGrid>
        </Card>
      )}

      {limitesIndisponibles && (
        <Alert color="orange" variant="light">
          {voc("Contours administratifs indisponibles (pas d'accès à Internet ?) : la carte s'affiche sans les limites.")}
        </Alert>
      )}

      <Group gap="md" justify="space-between">
      <Group gap="xs">
        <Text size="sm" fw={500}>{voc("Couches :")}</Text>
        {/* Une seule liste : couches de base et couches importées (valeurs « import:<id> »). */}
        <MultiSelect
          size="xs"
          w={{ base: "100%", sm: 560 }}
          placeholder={voc("Choisir les couches à afficher")}
          value={[...couches, ...importeesVisibles.map((id) => `import:${id}`)]}
          onChange={(valeurs) => {
            setCouches(valeurs.filter((v) => !v.startsWith("import:")) as Couche[]);
            setImporteesVisibles(valeurs.filter((v) => v.startsWith("import:")).map((v) => v.slice(7)));
          }}
          data={[
            {
              group: voc("Couches de base"),
              items: COUCHES.filter((c) => c.value !== "routes" || routes !== undefined || active("routes")),
            },
            ...(couchesImportees.length
              ? [{ group: voc("Couches importées"), items: couchesImportees.map((c) => ({ value: `import:${c.id}`, label: c.nom })) }]
              : []),
          ]}
          renderOption={({ option, checked }) => {
            const importee = couchesImportees.find((c) => `import:${c.id}` === option.value);
            return (
              <Group gap={6} wrap="nowrap">
                {checked ? <Check size={13} /> : <span style={{ width: 13 }} />}
                {importee && <span style={{ width: 10, height: 10, borderRadius: 2, background: importee.couleur, display: "inline-block" }} />}
                <Text size="xs">{option.label}</Text>
              </Group>
            );
          }}
          hidePickedOptions={false}
          clearable
          searchable
          comboboxProps={{ zIndex: 1000 }}
        />
        {couchesImportees.length > 0 && peutEcrire("/carte") && (
          <Button size="compact-xs" variant="subtle" leftSection={<Layers size={12} />} onClick={() => setFenetre("gerer")}>{voc("Gérer")}</Button>
        )}
      </Group>
      <Group gap="xs">
        <Text size="sm" fw={500}>{voc("Par zone :")}</Text>
        <MultiSelect
          size="xs"
          w={{ base: "100%", sm: 340 }}
          placeholder={parZoneActif ? "" : voc("Rien (bénéficiaires seulement)")}
          value={parZone}
          onChange={(choix) => {
            // Carte par zone : les cercles des bénéficiaires masqueraient les couleurs ; on les
            // retire (recochables), et on les remet en revenant à la carte des bénéficiaires.
            if (choix.length > 0 && !parZoneActif) setCouches((c) => c.filter((x) => x !== "points" && x !== "beneficiaires"));
            if (choix.length === 0 && parZoneActif) setCouches((c) => (c.includes("points") ? c : ["points", ...c]));
            setParZone(choix);
          }}
          data={optionsIndicateursZone()}
          clearable
          searchable
          maxDropdownHeight={360}
          comboboxProps={{ zIndex: 1000 }}
        />
        {parZoneActif && (
          <SegmentedControl
            size="xs"
            value={niveauZone}
            onChange={setNiveauZone}
            data={[{ value: "1", label: voc("Régions") }, { value: "2", label: voc("Provinces") }, { value: "3", label: voc("Communes") }]}
          />
        )}
      </Group>
      <Group gap="xs">
        <Text size="sm" fw={500}>{voc("Fond :")}</Text>
        <SegmentedControl
          size="xs"
          value={fondChoisi}
          onChange={setFond}
          data={Object.entries(FONDS).map(([value, f]) => ({ value, label: f?.label ?? voc("Aucun") }))}
        />
      </Group>
      </Group>

      {/* « isolate » : les calques Leaflet (z-index 400+) restent sous les fenêtres et menus. */}
      <Card ref={setEncadre} className="encadre-carte" withBorder padding={0} radius="md" style={{ overflow: "hidden", isolation: "isolate" }}>
        {isLoading ? (
          <Text p="md">{voc("Chargement…")}</Text>
        ) : (
          <MapContainer
            key={JSON.stringify(cadre)}
            {...(cadre ? { bounds: cadre } : { center: CENTRE_PAR_DEFAUT, zoom: 6 })}
            style={{ height: "min(600px, 70vh)", width: "100%" }}
            scrollWheelZoom
            preferCanvas
          >
            <SuiviVue onChange={(zoom, bbox) => setVue({ zoom, bbox })} />
            <OutilsCarte cible={encadre} />
            {tuiles && (
              <TileLayer key={fondChoisi} attribution={tuiles.attribution} url={tuiles.url} />
            )}
            {parZoneActif && synthese?.niveau && (
              <CarteParZone pays={pays} niveau={synthese.niveau.ordre} nomNiveau={traduireDonnee(synthese.niveau.nom)} indicateurs={parZone} zones={synthese.zones} />
            )}
            {active("communes") && <Limites pays={pays} niveau={3} zoom={vue.zoom} noms={nomsNiveau(3)} />}
            {active("provinces") && <Limites pays={pays} niveau={2} zoom={vue.zoom} noms={nomsNiveau(2)} />}
            {active("regions") && <Limites pays={pays} niveau={1} zoom={vue.zoom} noms={nomsNiveau(1)} />}
            {active("routes") && <Routes pays={pays} />}
            {active("villages") && <Villages pays={pays} bbox={vue.bbox} zoom={vue.zoom} noms={noms} />}
            {contourZone && (
              <GeoJSON key={`zone-${data?.zone_filtre?.ids.join("-")}`} data={contourZone as GeoJSON.Geometry} style={{ color: "#0c8a5f", weight: 3, fillColor: "#12b886", fillOpacity: 0.06 }} interactive={false} />
            )}
            {couchesImportees.filter((c) => importeesVisibles.includes(String(c.id))).map((c) => <CoucheImporteeCarte key={c.id} couche={c} />)}
            {active("points") && data?.zones.map((z) => (
              <CircleMarker
                key={`z-${z.zone}`}
                center={[z.lat, z.lng]}
                radius={8 + 22 * Math.sqrt(z.nombre / maxZone)}
                pathOptions={{ color: "#0c8a5f", fillColor: "#12b886", fillOpacity: 0.55, weight: 2 }}
              >
                <Tooltip direction="top">
                  <b>{z.nom}</b> : {z.nombre} {z.nombre > 1 ? voc("bénéficiaires") : voc("bénéficiaire")} ({voc`${z.femmes} F, ${z.hommes} H`}) — {voc("cliquer pour la liste")}
                </Tooltip>
                <Popup maxWidth={340}>
                  <Text size="sm" fw={700}>{z.nom} — {z.nombre} {z.nombre > 1 ? voc("bénéficiaires") : voc("bénéficiaire")}</Text>
                  <Text size="xs" c="dimmed" mb={4}>{z.femmes} {voc("femme(s),")} {z.hommes} {voc("homme(s) · placés au centre de la localité (pas de GPS)")}</Text>
                  <div style={{ maxHeight: 260, overflowY: "auto" }}>
                    {z.beneficiaires.map((b) => <LigneFiche key={b.id} b={b} />)}
                  </div>
                  {z.beneficiaires.length < z.nombre && <Text size="xs" c="dimmed" mt={4}>{voc("Liste limitée à")} {z.beneficiaires.length} {voc(": voir l'écran")} {voc("Bénéficiaires")}.</Text>}
                </Popup>
              </CircleMarker>
            ))}
            {active("points") && data?.points.map((p) => (
              <CircleMarker key={`p-${p.id}`} center={[p.lat, p.lng]} radius={6} pathOptions={{ color: "#c2410c", fillColor: "#fb923c", fillOpacity: 0.9, weight: 1.5 }}>
                <Tooltip direction="top">{p.nom}</Tooltip>
                <Popup maxWidth={320}>
                  <LigneFiche b={p} />
                  <Text size="xs" c="dimmed" mt={4}>{voc("Position GPS :")} {p.lat.toFixed(5)}, {p.lng.toFixed(5)}</Text>
                </Popup>
              </CircleMarker>
            ))}
            {active("points") && active("beneficiaires") && (vue.zoom >= 9 || (data?.points.length ?? 0) <= 50) &&
              data?.points.map((p) => (
                <Marker key={`pn-${p.id}`} position={[p.lat, p.lng]} icon={etiquette(p.nom, "beneficiaire")} interactive={false} />
              ))}
          </MapContainer>
        )}
      </Card>
      {parZoneActif && synthese && (
        <Stack gap={2}>
          <LegendeParZone indicateur={parZone[0]} libelle={infoIndicateur(parZone[0]).libelle} zones={synthese.zones} />
          {parZone.length > 1 && (
            <Text size="xs" c="dimmed">{voc("Les zones sont colorées selon le premier indicateur choisi ; les autres sont écrits sur chaque zone.")}</Text>
          )}
          <Text size="xs" c="dimmed">
            {voc("Cliquez sur la valeur d'une zone pour voir ses projets. Un projet compte dans chaque zone où il intervient (son budget n'est pas réparti entre les zones).")}
          </Text>
        </Stack>
      )}
      <Group gap="md">
        {active("routes") && routes &&
          Object.values(STYLE_ROUTES).map((s) => (
            <Group key={s.libelle} gap={6}>
              <div style={{ width: 22, height: s.weight + 1, background: s.color, borderRadius: 2 }} />
              <Text size="xs" c="dimmed">{voc("Route")} {s.libelle.toLowerCase()}</Text>
            </Group>
          ))}
        {active("villages") && vue.zoom < ZOOM_VILLAGES && (
          <Text size="xs" c="dimmed">{voc("Zoomer pour voir les villes et villages.")}</Text>
        )}
      </Group>
      {regions?.source === "geoBoundaries" && (
        <Text size="xs" c="dimmed">
          {voc`Contours : geoBoundaries (${regions.annee}) — un découpage plus récent que la source n'y figure pas encore ; ses zones sont placées au centre de leurs zones rattachées.`}
        </Text>
      )}
      {fenetre === "import" && <ImportCoucheModal onClose={() => setFenetre(null)} />}
      {fenetre === "gerer" && <GererCouchesModal couches={couchesImportees} onClose={() => setFenetre(null)} />}
      {fenetre === "telecharger" && (
        <TelechargerCarteModal
          options={{ projets: idsProjets, zones: idsZones, filtres: parametresFiltres, couches, importees: importeesVisibles.map(Number), fond: fondChoisi, parZone, niveauZone: Number(niveauZone) }}
          couchesImportees={couchesImportees}
          onClose={() => setFenetre(null)}
        />
      )}
    </Stack>
  );
}
