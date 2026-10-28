import { useState } from "react";
import { FileDown, Trash2, Upload } from "lucide-react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  ColorInput,
  FileInput,
  Group,
  Modal,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { telechargerCarteImprimable, type OptionsCarteImprimable } from "../../api/beneficiaries";
import { useImporterCouche, useModifierCouche, useSupprimerCouche, type CoucheImportee } from "../../api/geo";
import { confirmerSuppression } from "../../components/common/confirmerSuppression";
import { messageErreurApi } from "../../utils/erreurs";

const GEOMETRIES = { POINT: "Points", LIGNE: "Lignes", POLYGONE: "Polygones" } as const;
const COULEURS = ["#7048e8", "#e8590c", "#1c7ed6", "#c2255c", "#2f9e44", "#f08c00", "#0c8599", "#495057"];

/** Import d'une couche SIG : shapefile (.zip), GeoPackage, GeoJSON ou KML. */
export function ImportCoucheModal({ onClose }: { onClose: () => void }) {
  const importer = useImporterCouche();
  const [fichier, setFichier] = useState<File | null>(null);
  const [nom, setNom] = useState("");
  const [couleur, setCouleur] = useState(COULEURS[0]);
  const [resultat, setResultat] = useState<CoucheImportee | null>(null);

  async function valider() {
    if (!fichier) {
      notifications.show({ message: "Choisissez un fichier.", color: "orange" });
      return;
    }
    try {
      setResultat(await importer.mutateAsync({ fichier, nom: nom.trim(), couleur }));
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, "Import impossible"), color: "red", autoClose: 10000 });
    }
  }

  return (
    <Modal opened onClose={onClose} title="Importer une couche sur la carte" size="lg">
      {resultat ? (
        <Stack gap="sm">
          <Alert color="teal" title={`« ${resultat.nom} » importée`}>
            {resultat.nombre_objets} objet(s) ({GEOMETRIES[resultat.geometrie].toLowerCase()}) · projection d'origine : {resultat.projection_source || "—"}, convertie en WGS 84.
            {resultat.champ_etiquette ? ` Noms affichés : attribut « ${resultat.champ_etiquette} ».` : " Aucun attribut de nom reconnu (modifiable dans « Gérer les couches »)."}
          </Alert>
          <Text size="xs" c="dimmed">Attributs conservés : {resultat.colonnes.join(", ") || "aucun"}.</Text>
          <Group justify="flex-end"><Button onClick={onClose}>Fermer</Button></Group>
        </Stack>
      ) : (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            Shapefile dans une archive .zip (avec ses fichiers .shp, .shx, .dbf et .prj), GeoPackage (.gpkg), GeoJSON ou KML.
            La projection est lue dans le fichier et convertie automatiquement.
          </Text>
          <FileInput
            label="Fichier"
            placeholder="Choisir un fichier…"
            accept=".zip,.gpkg,.geojson,.json,.kml"
            value={fichier}
            onChange={(f) => {
              setFichier(f);
              if (f && !nom) setNom(f.name.replace(/\.[^.]+$/, ""));
            }}
            leftSection={<Upload size={14} />}
            required
          />
          <SimpleGrid cols={{ base: 1, xs: 2 }}>
            <TextInput label="Nom de la couche" placeholder="Ex : Points d'eau réalisés" value={nom} onChange={(e) => setNom(e.currentTarget.value)} />
            <ColorInput label="Couleur" value={couleur} onChange={setCouleur} swatches={COULEURS} format="hex" />
          </SimpleGrid>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={onClose}>Annuler</Button>
            <Button onClick={valider} loading={importer.isPending} leftSection={<Upload size={15} />}>Importer</Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}

function LigneCouche({ couche }: { couche: CoucheImportee }) {
  const modifier = useModifierCouche();
  const supprimer = useSupprimerCouche();
  const [nom, setNom] = useState(couche.nom);
  const enregistrer = (champs: Partial<CoucheImportee>) =>
    modifier.mutate({ id: couche.id, ...champs }, { onError: (e) => notifications.show({ message: messageErreurApi(e, "Erreur"), color: "red" }) });

  return (
    <Paper withBorder p="xs" radius="md">
      <Group gap="xs" wrap="nowrap" align="flex-end">
        <TextInput label="Nom" size="xs" value={nom} onChange={(e) => setNom(e.currentTarget.value)} onBlur={() => nom.trim() && nom !== couche.nom && enregistrer({ nom: nom.trim() })} style={{ flex: 1 }} />
        <ColorInput label="Couleur" size="xs" w={120} value={couche.couleur} onChangeEnd={(c) => enregistrer({ couleur: c })} swatches={COULEURS} format="hex" />
        <Select
          label="Noms affichés"
          size="xs"
          w={150}
          data={couche.colonnes}
          value={couche.champ_etiquette || null}
          onChange={(v) => enregistrer({ champ_etiquette: v ?? "" })}
          clearable
          placeholder="Aucun"
        />
        <ActionIcon variant="subtle" color="red" mb={2} aria-label="Supprimer la couche"
          onClick={() => confirmerSuppression({ message: `Supprimer la couche « ${couche.nom} » ?`, onConfirm: () => supprimer.mutate(couche.id) })}>
          <Trash2 size={15} />
        </ActionIcon>
      </Group>
      <Text size="xs" c="dimmed" mt={4}>
        <Badge size="xs" variant="light" mr={6}>{GEOMETRIES[couche.geometrie]}</Badge>
        {couche.nombre_objets} objet(s) · {couche.fichier_source} · importée le {new Date(couche.created_at).toLocaleDateString("fr-FR")} par {couche.cree_par_nom}
      </Text>
    </Paper>
  );
}

export function GererCouchesModal({ couches, onClose }: { couches: CoucheImportee[]; onClose: () => void }) {
  return (
    <Modal opened onClose={onClose} title="Couches importées" size="xl">
      <Stack gap="xs">
        {couches.length === 0 && <Text c="dimmed" size="sm">Aucune couche importée.</Text>}
        {couches.map((c) => <LigneCouche key={c.id} couche={c} />)}
      </Stack>
    </Modal>
  );
}

const COUCHES_FOND = [
  { value: "regions", label: "Régions" },
  { value: "provinces", label: "Provinces" },
  { value: "communes", label: "Communes" },
  { value: "routes", label: "Routes" },
  { value: "villages", label: "Villes et villages" },
  { value: "noms", label: "Noms" },
];

/** Carte imprimable : formats A0 à A4, PDF ou PNG, couches et filtres de la carte à l'écran. */
export function TelechargerCarteModal({ options, couchesImportees, onClose }: {
  options: Pick<OptionsCarteImprimable, "projet" | "zone" | "couches" | "importees">;
  couchesImportees: CoucheImportee[];
  onClose: () => void;
}) {
  const [papier, setPapier] = useState<OptionsCarteImprimable["papier"]>("A3");
  const [orientation, setOrientation] = useState<OptionsCarteImprimable["orientation"]>("auto");
  const [sortie, setSortie] = useState<OptionsCarteImprimable["sortie"]>("pdf");
  const [couches, setCouches] = useState(options.couches.filter((c) => COUCHES_FOND.some((f) => f.value === c)));
  const [importees, setImportees] = useState(options.importees.map(String));
  const [enCours, setEnCours] = useState(false);

  async function telecharger() {
    setEnCours(true);
    try {
      await telechargerCarteImprimable({ ...options, papier, orientation, sortie, couches, importees: importees.map(Number) });
    } catch {
      notifications.show({ message: "La carte n'a pas pu être générée (réessayez dans un instant).", color: "red" });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Modal opened onClose={onClose} title="Télécharger la carte" size="lg">
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          Carte à l'échelle avec grille de coordonnées, légende, situation, chiffres clés, tableau des localités et cartouche ;
          mêmes filtres (projet, zone) que la carte à l'écran.
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <div>
            <Text size="sm" fw={500} mb={4}>Format papier</Text>
            <SegmentedControl fullWidth value={papier} onChange={(v) => setPapier(v as OptionsCarteImprimable["papier"])} data={["A4", "A3", "A1", "A0"]} />
          </div>
          <div>
            <Text size="sm" fw={500} mb={4}>Orientation</Text>
            <SegmentedControl fullWidth value={orientation} onChange={(v) => setOrientation(v as OptionsCarteImprimable["orientation"])}
              data={[{ value: "auto", label: "Auto" }, { value: "portrait", label: "Portrait" }, { value: "paysage", label: "Paysage" }]} />
          </div>
          <div>
            <Text size="sm" fw={500} mb={4}>Fichier</Text>
            <SegmentedControl fullWidth value={sortie} onChange={(v) => setSortie(v as OptionsCarteImprimable["sortie"])}
              data={[{ value: "pdf", label: "PDF" }, { value: "png", label: "Image PNG" }]} />
          </div>
        </SimpleGrid>
        <div>
          <Text size="sm" fw={500} mb={4}>Couches</Text>
          <Checkbox.Group value={couches} onChange={setCouches}>
            <Group gap="md">{COUCHES_FOND.map((c) => <Checkbox key={c.value} value={c.value} label={c.label} />)}</Group>
          </Checkbox.Group>
          {couchesImportees.length > 0 && (
            <Checkbox.Group value={importees} onChange={setImportees} mt="xs">
              <Group gap="md">
                {couchesImportees.map((c) => (
                  <Checkbox key={c.id} value={String(c.id)} label={<Group gap={4}><span style={{ width: 10, height: 10, borderRadius: 2, background: c.couleur, display: "inline-block" }} />{c.nom}</Group>} />
                ))}
              </Group>
            </Checkbox.Group>
          )}
        </div>
        {papier === "A0" && <Text size="xs" c="dimmed">Le format A0 peut prendre une à deux minutes.</Text>}
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>Fermer</Button>
          <Button leftSection={<FileDown size={16} />} loading={enCours} onClick={telecharger}>Télécharger</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
