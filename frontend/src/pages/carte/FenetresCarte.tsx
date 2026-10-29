import { type ReactNode, useState } from "react";
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

import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
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
    if (!fichier || !nom.trim()) {
      notifications.show({ message: voc("Choisissez un fichier et le nom de la couche."), color: "orange" });
      return;
    }
    try {
      setResultat(await importer.mutateAsync({ fichier, nom: nom.trim(), couleur }));
    } catch (e) {
      notifications.show({ message: messageErreurApi(e, "Import impossible"), color: "red", autoClose: 10000 });
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc("Importer une couche sur la carte")} size="lg">
      {resultat ? (
        <Stack gap="sm">
          <Alert color="teal" title={voc`« ${resultat.nom} » importée`}>
            {resultat.nombre_objets} {voc("objet(s) (")}{GEOMETRIES[resultat.geometrie].toLowerCase()}{voc(") · projection d'origine :")} {resultat.projection_source || "—"}{voc(", convertie en WGS 84.")}
            {resultat.champ_etiquette ? voc` Noms affichés : attribut « ${resultat.champ_etiquette} ».` : voc(" Aucun attribut de nom reconnu (modifiable dans « Gérer les couches »).")}
          </Alert>
          <Text size="xs" c="dimmed">{voc("Attributs conservés :")} {resultat.colonnes.join(", ") || voc("aucun")}.</Text>
          <Group justify="flex-end"><Button onClick={onClose}>{voc("Fermer")}</Button></Group>
        </Stack>
      ) : (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {voc("Shapefile dans une archive .zip (avec ses fichiers .shp, .shx, .dbf et .prj), GeoPackage (.gpkg), GeoJSON ou KML. La projection est lue dans le fichier et convertie automatiquement.")}
          </Text>
          <FileInput
            label={voc("Fichier")}
            placeholder={voc("Choisir un fichier…")}
            accept=".zip,.gpkg,.geojson,.json,.kml"
            value={fichier}
            onChange={setFichier}
            leftSection={<Upload size={14} />}
            required
          />
          <SimpleGrid cols={{ base: 1, xs: 2 }}>
            <TextInput
              label={voc("Nom affiché dans les couches")}
              description={voc("C'est ce nom qui apparaît pour cocher la couche sur la carte.")}
              placeholder={voc("Ex : Forages réalisés")}
              required
              value={nom}
              onChange={(e) => setNom(e.currentTarget.value)}
            />
            <ColorInput label={voc("Couleur")} value={couleur} onChange={setCouleur} swatches={COULEURS} format="hex" />
          </SimpleGrid>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={onClose}>{voc("Annuler")}</Button>
            <Button onClick={valider} loading={importer.isPending} leftSection={<Upload size={15} />}>{voc("Importer")}</Button>
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
        <TextInput label={voc("Nom")} size="xs" value={nom} onChange={(e) => setNom(e.currentTarget.value)} onBlur={() => nom.trim() && nom !== couche.nom && enregistrer({ nom: nom.trim() })} style={{ flex: 1 }} />
        <ColorInput label={voc("Couleur")} size="xs" w={120} value={couche.couleur} onChangeEnd={(c) => enregistrer({ couleur: c })} swatches={COULEURS} format="hex" />
        <Select
          label={voc("Noms affichés")}
          size="xs"
          w={150}
          data={couche.colonnes}
          value={couche.champ_etiquette || null}
          onChange={(v) => enregistrer({ champ_etiquette: v ?? "" })}
          clearable
          placeholder={voc("Aucun")}
        />
        <ActionIcon variant="subtle" color="red" mb={2} aria-label={voc("Supprimer la couche")}
          onClick={() => confirmerSuppression({ message: voc`Supprimer la couche « ${couche.nom} » ?`, onConfirm: () => supprimer.mutate(couche.id) })}>
          <Trash2 size={15} />
        </ActionIcon>
      </Group>
      <Text size="xs" c="dimmed" mt={4}>
        <Badge size="xs" variant="light" mr={6}>{GEOMETRIES[couche.geometrie]}</Badge>
        {couche.nombre_objets} {voc("objet(s) ·")} {couche.fichier_source} {voc("· importée le")} {new Date(couche.created_at).toLocaleDateString(locale())} {voc("par")} {couche.cree_par_nom}
      </Text>
    </Paper>
  );
}

export function GererCouchesModal({ couches, onClose }: { couches: CoucheImportee[]; onClose: () => void }) {
  return (
    <Modal opened onClose={onClose} title={voc("Couches importées")} size="xl">
      <Stack gap="xs">
        {couches.length === 0 && <Text c="dimmed" size="sm">{voc("Aucune couche importée.")}</Text>}
        {couches.map((c) => <LigneCouche key={c.id} couche={c} />)}
      </Stack>
    </Modal>
  );
}

const COUCHES_FOND = [
  { value: "points", label: voc("Bénéficiaires") },
  { value: "regions", label: voc("Régions") },
  { value: "provinces", label: voc("Provinces") },
  { value: "communes", label: voc("Communes") },
  { value: "routes", label: voc("Routes") },
  { value: "villages", label: voc("Villes et villages") },
  { value: "noms", label: voc("Noms") },
  { value: "beneficiaires", label: voc("Noms des bénéficiaires (GPS)") },
];
const FONDS_CARTE = [
  { value: "neutre", label: voc("Neutre") },
  { value: "osm", label: voc("OpenStreetMap") },
  { value: "satellite", label: voc("Satellite") },
  { value: "aucun", label: voc("Aucun") },
];

/** Bloc titré de la fenêtre de téléchargement (mise en page, contenu, couches). */
function Bloc({ titre, children }: { titre: string; children: ReactNode }) {
  return (
    <Paper withBorder radius="md" p="md">
      <Text size="xs" fw={700} tt="uppercase" c="dimmed" mb="sm">{titre}</Text>
      {children}
    </Paper>
  );
}

/** Réglage à choix (contrôle segmenté) avec son libellé, aligné sur les champs de saisie. */
function Reglage({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="sm" fw={500} mb={4}>{label}</Text>
      {children}
    </div>
  );
}

/** Carte imprimable : formats A0 à A4, PDF ou PNG, couches et filtres de la carte à l'écran. */
export function TelechargerCarteModal({ options, couchesImportees, onClose }: {
  options: Pick<OptionsCarteImprimable, "projet" | "zone" | "couches" | "importees" | "fond" | "parZone" | "niveauZone">;
  couchesImportees: CoucheImportee[];
  onClose: () => void;
}) {
  const [papier, setPapier] = useState<OptionsCarteImprimable["papier"]>("A3");
  const [orientation, setOrientation] = useState<OptionsCarteImprimable["orientation"]>("auto");
  const [sortie, setSortie] = useState<OptionsCarteImprimable["sortie"]>("pdf");
  const [couches, setCouches] = useState(options.couches.filter((c) => COUCHES_FOND.some((f) => f.value === c)));
  const [fond, setFond] = useState(options.fond);
  const [parZone, setParZone] = useState(options.parZone);
  const [niveauZone, setNiveauZone] = useState(String(options.niveauZone));
  const [etendue, setEtendue] = useState<OptionsCarteImprimable["etendue"]>("pays");
  const [titre, setTitre] = useState("");
  const [sousTitre, setSousTitre] = useState("");
  const [tente, setTente] = useState(false);
  const complet = titre.trim() !== "" && sousTitre.trim() !== "";
  const [importees, setImportees] = useState(options.importees.map(String));
  const [enCours, setEnCours] = useState(false);

  async function telecharger() {
    setTente(true);
    if (!complet) return;
    setEnCours(true);
    try {
      await telechargerCarteImprimable({ ...options, papier, orientation, sortie, fond, parZone, etendue, titre: titre.trim(), sousTitre: sousTitre.trim(), niveauZone: Number(niveauZone), couches, importees: importees.map(Number) });
    } catch {
      notifications.show({ message: voc("La carte n'a pas pu être générée (réessayez dans un instant)."), color: "red" });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Modal opened onClose={onClose} title={voc("Télécharger la carte")} size="xl">
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {voc("Carte à l'échelle avec grille de coordonnées, légende, situation, chiffres clés, tableau des localités et cartouche ; mêmes filtres (projet, zone) que la carte à l'écran.")}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={voc("Titre de la carte")}
            placeholder={voc("Ex. : Budget des projets par province")}
            required
            value={titre}
            onChange={(e) => setTitre(e.currentTarget.value)}
            error={tente && !titre.trim() ? voc("Indiquez le titre de la carte.") : undefined}
            maxLength={120}
            data-autofocus
          />
          <TextInput
            label={voc("Sous-titre")}
            placeholder={voc("Ex. : Situation au 31 octobre 2026")}
            required
            value={sousTitre}
            onChange={(e) => setSousTitre(e.currentTarget.value)}
            error={tente && !sousTitre.trim() ? voc("Indiquez le sous-titre.") : undefined}
            maxLength={200}
          />
        </SimpleGrid>

        <Bloc titre={voc("Mise en page")}>
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
            <Reglage label={voc("Format papier")}>
              <SegmentedControl fullWidth value={papier} onChange={(v) => setPapier(v as OptionsCarteImprimable["papier"])} data={["A4", "A3", "A1", "A0"]} />
            </Reglage>
            <Reglage label={voc("Orientation")}>
              <SegmentedControl fullWidth value={orientation} onChange={(v) => setOrientation(v as OptionsCarteImprimable["orientation"])}
                data={[{ value: "auto", label: voc("Auto") }, { value: "portrait", label: voc("Portrait") }, { value: "paysage", label: voc("Paysage") }]} />
            </Reglage>
            <Reglage label={voc("Fichier")}>
              <SegmentedControl fullWidth value={sortie} onChange={(v) => setSortie(v as OptionsCarteImprimable["sortie"])}
                data={[{ value: "pdf", label: voc("PDF") }, { value: "png", label: voc("Image PNG") }]} />
            </Reglage>
          </SimpleGrid>
        </Bloc>

        <Bloc titre={voc("Contenu")}>
          <Stack gap="sm">
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
              <Select
                label={voc("Colorier les zones selon")}
                value={parZone}
                onChange={(v) => setParZone(v ?? "aucun")}
                allowDeselect={false}
                data={[
                  { value: "aucun", label: voc("Rien (carte des bénéficiaires)") },
                  { value: "projets", label: voc("Nombre de projets") },
                  { value: "beneficiaires", label: voc("Bénéficiaires") },
                  { value: "budget", label: voc("Budget") },
                  { value: "taux_physique", label: voc("Exécution physique") },
                  { value: "taux_financier", label: voc("Exécution financière") },
                ]}
              />
              {parZone !== "aucun" ? (
                <Reglage label={voc("Par")}>
                  <SegmentedControl fullWidth value={niveauZone} onChange={setNiveauZone}
                    data={[{ value: "1", label: voc("Région") }, { value: "2", label: voc("Province") }, { value: "3", label: voc("Commune") }]} />
                </Reglage>
              ) : options.zone ? (
                <Reglage label={voc("Étendue")}>
                  <Text size="sm" c="dimmed" mt={6}>{voc("Étendue : la zone choisie dans le filtre.")}</Text>
                </Reglage>
              ) : (
                <Reglage label={voc("Étendue")}>
                  <SegmentedControl fullWidth value={etendue} onChange={(v) => setEtendue(v as OptionsCarteImprimable["etendue"])}
                    data={[{ value: "pays", label: voc("Tout le pays") }, { value: "beneficiaires", label: voc("Autour des bénéficiaires") }]} />
                </Reglage>
              )}
            </SimpleGrid>
            <Reglage label={voc("Fond de carte")}>
              <SegmentedControl fullWidth value={fond} onChange={setFond} data={FONDS_CARTE} />
            </Reglage>
          </Stack>
        </Bloc>

        <Bloc titre={voc("Couches")}>
          <Checkbox.Group value={couches} onChange={setCouches}>
            <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm" verticalSpacing="xs">
              {COUCHES_FOND.map((c) => <Checkbox key={c.value} value={c.value} label={c.label} />)}
            </SimpleGrid>
          </Checkbox.Group>
          {couchesImportees.length > 0 && (
            <>
              <Text size="xs" c="dimmed" fw={600} mt="sm" mb={6}>{voc("Couches importées")}</Text>
              <Checkbox.Group value={importees} onChange={setImportees}>
                <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm" verticalSpacing="xs">
                  {couchesImportees.map((c) => (
                    <Checkbox key={c.id} value={String(c.id)} label={<Group gap={4} wrap="nowrap"><span style={{ width: 10, height: 10, borderRadius: 2, background: c.couleur, display: "inline-block", flexShrink: 0 }} />{c.nom}</Group>} />
                  ))}
                </SimpleGrid>
              </Checkbox.Group>
            </>
          )}
        </Bloc>

        {(papier === "A0" || papier === "A1") && <Text size="xs" c="dimmed">{voc("Les grands formats peuvent prendre une à deux minutes, surtout avec un fond de carte.")}</Text>}
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>{voc("Fermer")}</Button>
          <Button leftSection={<FileDown size={16} />} loading={enCours} onClick={telecharger} disabled={!complet}>{voc("Télécharger")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
