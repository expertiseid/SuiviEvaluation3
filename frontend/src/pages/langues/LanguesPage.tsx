import { useEffect, useMemo, useState } from "react";
import { Check, Download, History, RotateCcw, Search, Upload } from "lucide-react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  FileButton,
  Group,
  Loader,
  Modal,
  Pagination,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useConfigurationMenu } from "../../api/dashboard";
import {
  useCorrigerTraduction,
  useDefinirLangueParDefaut,
  useImporterTraductions,
  useJournalTraductions,
  useRetirerCorrection,
  useTraductionsCorrigees,
  type TraductionCorrigee,
} from "../../api/langues";
import { TitreRubrique } from "../../components/common/TitreRubrique";
import sources from "../../i18n/sources.json";
import { langue, langueParDefaut, LANGUES, locale, type Langue } from "../../utils/i18n";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";

const PAR_PAGE = 50;
const LANGUES_TRADUITES = LANGUES.filter((l) => l.code !== "fr");

/**
 * Les emplacements {0}, {1}… du texte français reçoivent une valeur (un nom, un nombre) à
 * l'affichage : la traduction doit garder exactement les mêmes. Renvoie le problème, ou null.
 */
function reperesIncoherents(source: string, traduction: string): string | null {
  const reperes = (texte: string) => new Set(texte.match(/\{\d+\}/g) ?? []);
  const attendus = reperes(source);
  const presents = reperes(traduction);
  const manquants = [...attendus].filter((r) => !presents.has(r));
  const enTrop = [...presents].filter((r) => !attendus.has(r));
  const problemes = [];
  if (manquants.length) problemes.push(voc`Il manque ${manquants.join(", ")} : gardez-le tel quel, il sera remplacé par une valeur à l'affichage.`);
  if (enTrop.length) problemes.push(voc`${enTrop.join(", ")} n'existe pas dans le texte français.`);
  return problemes.length ? problemes.join(" ") : null;
}

// Écran (module) où s'affiche un texte, déduit du fichier qui le contient (voir scripts/extraire-textes.cjs).
const ALIAS_MODULES: Record<string, string> = {
  indicators: "indicateurs",
  charts: "graphiques",
  common: "commun",
  audit: "commun",
  api: "commun",
  utils: "commun",
  types: "commun",
  auth: "connexion",
  layouts: "menu",
};

function moduleDe(lieu: string) {
  if (lieu === "serveur") return "serveur";
  const parties = lieu.split("/");
  const fichier = parties.pop() ?? "";
  if (parties[0] === "pages" || parties[0] === "components") parties.shift();
  const dossier = parties[0] ?? (fichier.startsWith("Dashboard") ? "dashboard" : "commun");
  return ALIAS_MODULES[dossier] ?? dossier;
}

const libellesModules = (): Record<string, string> => ({
  approbations: voc("Approbations"),
  beneficiaires: voc("Bénéficiaires"),
  carte: voc("Carte"),
  commun: voc("Éléments communs"),
  connexion: voc("Connexion"),
  dashboard: voc("Tableau de bord"),
  documents: voc("Documents"),
  geo: voc("Zones administratives"),
  graphiques: voc("Graphiques"),
  indicateurs: voc("Indicateurs"),
  langues: voc("Langues"),
  menu: voc("Menu"),
  notifications: voc("Notifications"),
  organisation: voc("Organisation"),
  parametres: voc("Paramètres"),
  partage: voc("Partage"),
  planification: voc("Planification"),
  projets: voc("Projets"),
  serveur: voc("Messages du serveur"),
  strategie: voc("Cadre stratégique"),
  suivi: voc("Suivi"),
  utilisateurs: voc("Utilisateurs"),
});

const nomFichier = (lieu: string) => lieu.split("/").pop()?.replace(/\.tsx?$/, "") ?? lieu;

/** Lit un fichier CSV (séparateur ; , ou tabulation, détecté sur la première ligne). */
function lireCsv(texte: string): string[][] {
  texte = texte.replace(/^\uFEFF/, "");
  const premiere = texte.split(/\r?\n/, 1)[0];
  const separateur = [";", "\t", ","].reduce((a, b) => (premiere.split(b).length > premiere.split(a).length ? b : a));
  const lignes: string[][] = [];
  let ligne: string[] = [];
  let champ = "";
  let entreGuillemets = false;
  for (let i = 0; i < texte.length; i++) {
    const c = texte[i];
    if (entreGuillemets) {
      if (c === '"' && texte[i + 1] === '"') {
        champ += '"';
        i++;
      } else if (c === '"') entreGuillemets = false;
      else champ += c;
    } else if (c === '"') entreGuillemets = true;
    else if (c === separateur) {
      ligne.push(champ);
      champ = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && texte[i + 1] === "\n") i++;
      ligne.push(champ);
      lignes.push(ligne);
      ligne = [];
      champ = "";
    } else champ += c;
  }
  if (champ || ligne.length) lignes.push([...ligne, champ]);
  return lignes;
}

const celluleCsv = (valeur: string) => `"${valeur.replace(/"/g, '""')}"`;

interface ImportPrepare {
  lignes: { source: string; traduction: string | null }[];
  erreurs: { source: string; erreur: string }[];
  ignorees: number;
}

export function LanguesPage() {
  return (
    <Stack gap="md">
      <div>
        <TitreRubrique route="/langues" defaut={voc("Langues")} />
        <Text c="dimmed" size="sm">
          {voc("Chaque utilisateur choisit sa langue (en haut de l'écran). Ici : la langue proposée par défaut, et la correction des traductions livrées avec la plateforme.")}
        </Text>
      </div>
      <LangueParDefautCard />
      <TraductionsCard />
    </Stack>
  );
}

function LangueParDefautCard() {
  const { data: configuration } = useConfigurationMenu();
  const definir = useDefinirLangueParDefaut();
  const [choix, setChoix] = useState<Langue>(langueParDefaut());
  const enregistree = configuration?.langue_defaut ?? langueParDefaut();
  useEffect(() => setChoix(enregistree), [enregistree]);

  return (
    <Card withBorder padding="lg" radius="md">
      <Title order={4} mb={4}>{voc("Langue par défaut de l'organisation")}</Title>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Utilisée sur la page de connexion et pour les utilisateurs qui n'ont pas choisi de langue.")}
      </Text>
      <Group align="flex-end">
        <Select
          data={LANGUES.map((l) => ({ value: l.code, label: l.nom }))}
          value={choix}
          onChange={(v) => v && setChoix(v as Langue)}
          allowDeselect={false}
          w={240}
        />
        <Button
          disabled={choix === enregistree}
          loading={definir.isPending}
          onClick={async () => {
            try {
              await definir.mutateAsync(choix);
              notifications.show({ color: "green", message: voc("Langue par défaut enregistrée") });
            } catch (err) {
              notifications.show({ color: "red", message: messageErreurApi(err, voc("Erreur lors de l'enregistrement")) });
            }
          }}
        >
          {voc("Enregistrer")}
        </Button>
      </Group>
    </Card>
  );
}

function TraductionsCard() {
  const [cible, setCible] = useState<Langue>(langue() === "fr" ? "en" : langue());
  const [catalogue, setCatalogue] = useState<Record<string, string> | null>(null);
  const [contextes, setContextes] = useState<Record<string, string[]>>({});
  const [recherche, setRecherche] = useState("");
  const [filtre, setFiltre] = useState("tous");
  const [module, setModule] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [journalOuvert, setJournalOuvert] = useState(false);
  const [importPrepare, setImportPrepare] = useState<ImportPrepare | null>(null);
  const { data: corrections, isLoading } = useTraductionsCorrigees(cible);
  const importer = useImporterTraductions();
  const libelles = useMemo(() => libellesModules(), []);

  // Traductions livrées avec l'application, pour comparer et revenir en arrière.
  useEffect(() => {
    let actif = true;
    setCatalogue(null);
    import(`../../i18n/${cible}.json`).then((m) => actif && setCatalogue(m.default as Record<string, string>));
    return () => {
      actif = false;
    };
  }, [cible]);

  useEffect(() => {
    import("../../i18n/contextes.json").then((m) => setContextes(m.default as Record<string, string[]>));
  }, []);

  const modulesParSource = useMemo(
    () => new Map(Object.entries(contextes).map(([source, lieux]) => [source, [...new Set(lieux.map(moduleDe))]])),
    [contextes],
  );
  const optionsModules = useMemo(
    () =>
      [...new Set([...modulesParSource.values()].flat())]
        .map((cle) => ({ value: cle, label: libelles[cle] ?? cle }))
        .sort((a, b) => a.label.localeCompare(b.label, locale())),
    [modulesParSource, libelles],
  );

  const parSource = useMemo(() => new Map((corrections ?? []).map((c) => [c.source, c])), [corrections]);
  const lignes = useMemo(() => {
    const terme = recherche.trim().toLowerCase();
    return (sources as string[]).filter((source) => {
      if (filtre === "corriges" && !parSource.has(source)) return false;
      if (filtre === "manquants" && catalogue && source in catalogue) return false;
      if (module && !modulesParSource.get(source)?.includes(module)) return false;
      if (!terme) return true;
      const traduction = parSource.get(source)?.traduction ?? catalogue?.[source] ?? "";
      return source.toLowerCase().includes(terme) || traduction.toLowerCase().includes(terme);
    });
  }, [recherche, filtre, module, modulesParSource, parSource, catalogue]);
  useEffect(() => setPage(1), [recherche, filtre, module, cible]);

  const pages = Math.max(1, Math.ceil(lignes.length / PAR_PAGE));
  const visibles = lignes.slice((page - 1) * PAR_PAGE, page * PAR_PAGE);
  const nomLangue = LANGUES.find((l) => l.code === cible)?.nom ?? cible;

  function exporter() {
    if (!catalogue) return;
    const entete = [voc("Texte français"), nomLangue, voc("Écran")];
    const rangees = (sources as string[]).map((source) => [
      source,
      parSource.get(source)?.traduction ?? catalogue[source] ?? "",
      (modulesParSource.get(source) ?? []).map((m) => libelles[m] ?? m).join(", "),
    ]);
    // Point-virgule et BOM : Excel (réglages français) ouvre le fichier directement, accents compris.
    const contenu = "﻿" + [entete, ...rangees].map((r) => r.map(celluleCsv).join(";")).join("\r\n") + "\r\n";
    const lien = document.createElement("a");
    lien.href = URL.createObjectURL(new Blob([contenu], { type: "text/csv;charset=utf-8" }));
    lien.download = `traductions-${cible}.csv`;
    lien.click();
    URL.revokeObjectURL(lien.href);
  }

  async function preparerImport(fichier: File | null) {
    if (!fichier || !catalogue) return;
    const octets = await fichier.arrayBuffer();
    let texte = new TextDecoder("utf-8").decode(octets);
    // Fichier réenregistré par Excel en « CSV » simple : encodage Windows au lieu d'UTF-8.
    if (texte.includes("�")) texte = new TextDecoder("windows-1252").decode(octets);
    const connues = new Set(sources as string[]);
    const resultat: ImportPrepare = { lignes: [], erreurs: [], ignorees: 0 };
    for (const [source = "", traduction = ""] of lireCsv(texte).slice(1)) {
      if (!connues.has(source) || !traduction.trim()) {
        if (source || traduction) resultat.ignorees++;
        continue;
      }
      const correction = parSource.get(source);
      const livree = catalogue[source] ?? "";
      if (traduction === (correction?.traduction ?? livree)) continue;
      const erreur = reperesIncoherents(source, traduction);
      if (erreur) resultat.erreurs.push({ source, erreur });
      else if (correction && traduction === livree) resultat.lignes.push({ source, traduction: null });
      else resultat.lignes.push({ source, traduction });
    }
    setImportPrepare(resultat);
  }

  async function appliquerImport() {
    if (!importPrepare) return;
    try {
      const r = await importer.mutateAsync({ langue: cible, lignes: importPrepare.lignes });
      notifications.show({
        color: "green",
        message: voc`Import terminé : ${r.corrigees} traduction(s) corrigée(s), ${r.retirees} remise(s) à l'origine.`,
      });
      setImportPrepare(null);
    } catch (err) {
      notifications.show({ color: "red", message: messageErreurApi(err, voc("Erreur lors de l'import")) });
    }
  }

  return (
    <Card withBorder padding="lg" radius="md">
      <Group justify="space-between" align="flex-start" mb={4}>
        <Title order={4}>{voc("Traductions de l'interface")}</Title>
        <Group gap="xs">
          <Button size="xs" variant="default" leftSection={<Download size={14} />} disabled={!catalogue} onClick={exporter}>
            {voc("Exporter")}
          </Button>
          <FileButton accept=".csv,text/csv" onChange={preparerImport}>
            {(props) => (
              <Button {...props} size="xs" variant="default" leftSection={<Upload size={14} />} disabled={!catalogue}>
                {voc("Importer")}
              </Button>
            )}
          </FileButton>
          <Button size="xs" variant="default" leftSection={<History size={14} />} onClick={() => setJournalOuvert(true)}>
            {voc("Historique")}
          </Button>
        </Group>
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {voc("Le texte français sert de référence. Modifiez une traduction puis validez : elle remplace celle livrée avec la plateforme, pour tous les utilisateurs, au prochain chargement de la page. ↺ revient à la traduction d'origine.")}{" "}
        {voc("Pour faire traduire une langue entière, exportez-la, faites compléter la colonne de traduction dans Excel puis importez le fichier.")}
      </Text>
      <Group mb="sm" wrap="wrap">
        <SegmentedControl
          value={cible}
          onChange={(v) => setCible(v as Langue)}
          data={LANGUES_TRADUITES.map((l) => ({ value: l.code, label: l.nom }))}
        />
        <TextInput
          placeholder={voc("Rechercher un texte…")}
          leftSection={<Search size={14} />}
          value={recherche}
          onChange={(e) => setRecherche(e.currentTarget.value)}
          style={{ flex: 1, minWidth: 200 }}
        />
        <Select
          placeholder={voc("Tous les écrans")}
          data={optionsModules}
          value={module}
          onChange={setModule}
          clearable
          searchable
          w={200}
        />
        <SegmentedControl
          value={filtre}
          onChange={setFiltre}
          data={[
            { value: "tous", label: voc("Tous") },
            { value: "corriges", label: voc("Corrigés") },
            { value: "manquants", label: voc("Non traduits") },
          ]}
        />
      </Group>
      {isLoading || !catalogue ? (
        <Loader size="sm" />
      ) : (
        <>
          <Text size="xs" c="dimmed" mb={6}>
            {voc`${lignes.length} texte(s) · ${parSource.size} correction(s) pour cette langue`}
          </Text>
          <Table.ScrollContainer minWidth={700}>
            <Table verticalSpacing={6} striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w="45%">{voc("Texte français")}</Table.Th>
                  <Table.Th>{voc("Traduction")}</Table.Th>
                  <Table.Th w={80} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {visibles.map((source) => (
                  <LigneTraduction
                    key={`${cible}-${source}`}
                    langue={cible}
                    source={source}
                    livree={catalogue[source] ?? ""}
                    correction={parSource.get(source)}
                    lieux={contextes[source] ?? []}
                    ecrans={(modulesParSource.get(source) ?? []).map((m) => libelles[m] ?? m)}
                  />
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          {pages > 1 && <Pagination mt="sm" total={pages} value={page} onChange={setPage} size="sm" />}
        </>
      )}
      <JournalModal langue={cible} nomLangue={nomLangue} opened={journalOuvert} onClose={() => setJournalOuvert(false)} />
      <Modal opened={!!importPrepare} onClose={() => setImportPrepare(null)} title={voc`Importer des traductions (${nomLangue})`} size="lg">
        {importPrepare && (
          <Stack gap="sm">
            {importPrepare.erreurs.length > 0 ? (
              <>
                <Alert color="red">
                  {voc`${importPrepare.erreurs.length} ligne(s) à corriger dans le fichier : rien n'a été importé. Corrigez-les puis importez à nouveau.`}
                </Alert>
                <Table.ScrollContainer minWidth={500} mah={360}>
                  <Table verticalSpacing={4} fz="xs">
                    <Table.Tbody>
                      {importPrepare.erreurs.map((e) => (
                        <Table.Tr key={e.source}>
                          <Table.Td w="50%">{e.source}</Table.Td>
                          <Table.Td c="red">{e.erreur}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              </>
            ) : (
              <Text size="sm">
                {importPrepare.lignes.length === 0
                  ? voc("Aucune traduction modifiée dans ce fichier.")
                  : voc`${importPrepare.lignes.filter((l) => l.traduction !== null).length} traduction(s) seront corrigées et ${importPrepare.lignes.filter((l) => l.traduction === null).length} remise(s) à l'origine, pour tous les utilisateurs.`}
              </Text>
            )}
            {importPrepare.ignorees > 0 && (
              <Text size="xs" c="dimmed">
                {voc`${importPrepare.ignorees} ligne(s) ignorée(s) : traduction vide, ou texte français qui n'existe plus dans la plateforme.`}
              </Text>
            )}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setImportPrepare(null)}>{voc("Annuler")}</Button>
              {importPrepare.erreurs.length === 0 && importPrepare.lignes.length > 0 && (
                <Button loading={importer.isPending} onClick={appliquerImport}>{voc("Appliquer")}</Button>
              )}
            </Group>
          </Stack>
        )}
      </Modal>
    </Card>
  );
}

function JournalModal({ langue: cible, nomLangue, opened, onClose }: { langue: Langue; nomLangue: string; opened: boolean; onClose: () => void }) {
  const { data, isLoading } = useJournalTraductions(cible, opened);
  return (
    <Modal opened={opened} onClose={onClose} title={voc`Historique des traductions (${nomLangue})`} size="xl">
      {isLoading ? (
        <Loader size="sm" />
      ) : !data?.length ? (
        <Text size="sm" c="dimmed">{voc("Aucune modification enregistrée.")}</Text>
      ) : (
        <Table.ScrollContainer minWidth={700}>
          <Table verticalSpacing={4} fz="xs" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={130}>{voc("Date")}</Table.Th>
                <Table.Th w={120}>{voc("Par")}</Table.Th>
                <Table.Th>{voc("Texte français")}</Table.Th>
                <Table.Th>{voc("Traduction")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((e, i) => (
                <Table.Tr key={i}>
                  <Table.Td>{new Date(e.date).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" })}</Table.Td>
                  <Table.Td>{e.utilisateur ?? "—"}</Table.Td>
                  <Table.Td>{e.source}</Table.Td>
                  <Table.Td dir={cible === "ar" ? "rtl" : "ltr"}>
                    {e.type === "retrait" ? (
                      <Badge size="xs" color="gray" variant="light">{voc("Remise à l'origine")}</Badge>
                    ) : (
                      e.traduction
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Modal>
  );
}

function LigneTraduction({
  langue: cible,
  source,
  livree,
  correction,
  lieux,
  ecrans,
}: {
  langue: Langue;
  source: string;
  livree: string;
  correction?: TraductionCorrigee;
  lieux: string[];
  ecrans: string[];
}) {
  const actuelle = correction?.traduction ?? livree;
  const [valeur, setValeur] = useState(actuelle);
  useEffect(() => setValeur(actuelle), [actuelle]);
  const corriger = useCorrigerTraduction();
  const retirer = useRetirerCorrection();
  const modifiee = valeur !== actuelle;
  const erreur = modifiee ? reperesIncoherents(source, valeur) : null;
  const valide = modifiee && !!valeur.trim() && !erreur;

  async function valider() {
    try {
      // Revenir exactement à la traduction livrée revient à retirer la correction.
      if (correction && valeur === livree) await retirer.mutateAsync(correction);
      else await corriger.mutateAsync({ langue: cible, source, traduction: valeur });
      notifications.show({ color: "green", message: voc("Traduction enregistrée") });
    } catch (err) {
      notifications.show({ color: "red", message: messageErreurApi(err, voc("Erreur lors de l'enregistrement")) });
    }
  }

  const fichiers = lieux.filter((l) => l !== "serveur").map(nomFichier);
  const dateCorrection = correction && new Date(correction.updated_at).toLocaleDateString(locale());

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{source}</Text>
        <Group gap={6} mt={2}>
          {ecrans.length > 0 && (
            <Tooltip
              label={fichiers.length ? fichiers.join(", ") : voc("Message envoyé par le serveur")}
              multiline
              maw={400}
            >
              <Text size="xs" c="dimmed">{ecrans.join(" · ")}</Text>
            </Tooltip>
          )}
          {!livree && <Badge size="xs" color="orange" variant="light">{voc("Non traduit")}</Badge>}
          {correction && (
            <Tooltip
              label={
                correction.modifie_par_nom
                  ? voc`Corrigé par ${correction.modifie_par_nom} le ${dateCorrection}`
                  : voc`Corrigé le ${dateCorrection}`
              }
            >
              <Badge size="xs" color="violet" variant="light">{voc("Corrigé")}</Badge>
            </Tooltip>
          )}
        </Group>
      </Table.Td>
      <Table.Td>
        <TextInput
          size="xs"
          value={valeur}
          dir={cible === "ar" ? "rtl" : "ltr"}
          error={erreur}
          onChange={(e) => setValeur(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && valide && valider()}
        />
      </Table.Td>
      <Table.Td>
        <Group gap={4} wrap="nowrap">
          <Tooltip label={voc("Valider")}>
            <ActionIcon variant="light" color="green" disabled={!valide} loading={corriger.isPending} onClick={valider}>
              <Check size={14} />
            </ActionIcon>
          </Tooltip>
          {correction && (
            <Tooltip label={voc("Revenir à la traduction d'origine")}>
              <ActionIcon variant="subtle" color="gray" loading={retirer.isPending} onClick={() => retirer.mutate(correction)}>
                <RotateCcw size={14} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}
