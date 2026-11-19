import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Download, FileSpreadsheet, FileText, FolderKanban, Paintbrush, Presentation, Wallet, Users, Gauge, MapPin, SlidersHorizontal } from "lucide-react";
import { ActionIcon, Badge, Button, Grid, Group, Menu, Paper, SimpleGrid, Stack, Table, Text, Title, Tooltip } from "@mantine/core";
import {
  useConfigurationTableauDeBord,
  useDashboardConsolide,
  useEnregistrerConfigurationTableauDeBord,
  telechargerTableauDeBord,
  type FormatExportTableauDeBord,
} from "../api/dashboard";
import { notifications } from "@mantine/notifications";
import { messageErreurApi } from "../utils/erreurs";
import { usePartage } from "../utils/partage";
import { BoutonPartage } from "../components/partage/BoutonPartage";
import { FiltresTableauDeBord } from "../components/dashboard/FiltresTableauDeBord";
import { FILTRES_PAR_DEFAUT, versParametres, type EtatFiltres } from "../utils/filtresTableauDeBord";
import { PersonnalisationModal, type DefinitionBloc } from "../components/dashboard/PersonnalisationModal";
import { StatCard } from "../components/common/StatCard";
import { CamembertChart } from "../components/charts/CamembertChart";
import { ChoixTypeGraphique, GraphiqueAdaptable, type SerieGraphique } from "../components/charts/GraphiqueAdaptable";
import { ExportBloc, HORS_EXPORT, type DonneesExport } from "../components/charts/ExportBloc";
import { exporterCommeEcran } from "../utils/exportEcran";
import { ApparenceBlocDrawer } from "../components/dashboard/ApparenceBlocDrawer";
import { ApparenceContext, useApparence, type ApparenceBloc } from "../utils/apparence";
import { typesPossibles, type TypeGraphique } from "../utils/typesGraphiques";
import { PROJET_STATUT_LABEL } from "../utils/statusTones";
import type {
  AvancementActivites, DashboardConsolide, FinancesTableauDeBord, FiltresDashboard, LigneRepartitionProjets, PilotageTableauDeBord, QualiteTableauDeBord,
  PerformanceIndicateurs, PlaintesTableauDeBord, StatutProjet, TerritoiresTableauDeBord,
} from "../types";
import { TitreRubrique } from "../components/common/TitreRubrique";
import { voc } from "../utils/vocabulaire";

import { langue, locale, nombreCourt, traduireDonnee } from "../utils/i18n";
// Couleurs fixes par statut ; une couleur par projet (cycle) pour les répartitions par projet.
const COULEURS_PROJET_STATUT: Record<StatutProjet, string> = {
  EN_PREPARATION: "#868e96",
  EN_COURS: "#12b886",
  CLOTURE: "#1c7ed6",
};
const COULEURS_SERIE = ["#12b886", "#1c7ed6", "#f59f00", "#ae3ec9", "#e8590c", "#0ca678", "#4263eb", "#d6336c"];
const COULEUR_FEMMES = "#d6336c";
const COULEUR_HOMMES = "#1c7ed6";

const CLE_STOCKAGE_FILTRES = "tableau-de-bord.filtres";

function CarteGraphique({ titre, sousTitre, actions, donnees, filtres, children }: {
  titre: string; sousTitre?: string; actions?: ReactNode; donnees?: () => DonneesExport | null; filtres?: FiltresDashboard;
  children: ReactNode;
}) {
  // Zone reproduite par les images : titre et contenu, sans les boutons.
  const zone = useRef<HTMLDivElement>(null);
  return (
    <Paper withBorder p="md" radius="md" h="100%" ref={zone}>
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb="sm">
        <div>
          <Title order={4} c="dark.8" style={{ borderLeft: "4px solid var(--mantine-color-teal-6)", paddingLeft: 10 }}>
            {titre}
          </Title>
          {sousTitre && <Text size="sm" c="dimmed" mt={2} pl={14}>{sousTitre}</Text>}
        </div>
        <Group gap={6} wrap="nowrap" className={HORS_EXPORT}>
          {actions}
          <ExportBloc titre={titre} zone={zone} donnees={donnees} filtres={filtres} />
        </Group>
      </Group>
      {children}
    </Paper>
  );
}

interface ChiffreCle { libelle: string; valeur: number; texte: string; icone: ReactNode; couleur: string }

/** Chiffres clés : cartes, ou tableau (et « les deux » : cartes puis tableau). */
function ChiffresCles({ chiffres, type }: { chiffres: ChiffreCle[]; type: TypeGraphique }) {
  const apparence = useApparence();
  const cartes = (
    <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="md">
      {chiffres.map((c) => <StatCard key={c.libelle} label={c.libelle} value={c.texte} icon={c.icone} color={c.couleur} />)}
    </SimpleGrid>
  );
  const tableau = (
    <Table withTableBorder striped verticalSpacing={6} fz="sm">
      <Table.Tbody>
        {chiffres.map((c) => (
          <Table.Tr key={c.libelle}><Table.Td>{c.libelle}</Table.Td><Table.Td ta="right" fw={600} style={{ whiteSpace: "nowrap" }}>{c.texte}</Table.Td></Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
  if (type === "tableau" || apparence.mode === "tableau") return tableau;
  return apparence.mode === "les_deux" ? <Stack gap="sm">{cartes}{tableau}</Stack> : cartes;
}

/** Nombre de zones couvertes par niveau : cartes de chiffres, graphique ou tableau (et « les deux »). */
function CouvertureZones({ zones, type }: { zones: DashboardConsolide["zones_couvertes"]; type: TypeGraphique }) {
  const apparence = useApparence();
  if (zones.length === 0) return <Vide message={voc("Aucun pays renseigné sur les projets.")} />;
  const graphique = (t: TypeGraphique) => (
    <GraphiqueAdaptable type={t} categories={zones.map((z) => traduireDonnee(z.niveau))} libelleCategories={voc("Niveau")}
      series={[{ cle: "n", nom: voc("Zones"), couleur: "#15aabf", valeurs: zones.map((z) => z.count) }]}
      couleursCategories={zones.map((_, i) => COULEURS_SERIE[i % COULEURS_SERIE.length])} unite={voc("zones")} hauteur={240} />
  );
  if (type !== "cartes") return graphique(type);
  const cartes = (
    <SimpleGrid cols={{ base: 2, xs: 4 }} spacing="md">
      {zones.map((z) => <StatCard key={z.niveau} label={traduireDonnee(z.niveau)} value={z.count} icon={<MapPin size={20} />} color="cyan" />)}
    </SimpleGrid>
  );
  if (apparence.mode === "tableau") return graphique("tableau");
  return apparence.mode === "les_deux" ? <Stack gap="sm">{cartes}{graphique("tableau")}</Stack> : cartes;
}

/** « 2026-10 » → « oct. 2026 » */
function formatMois(mois: string): string {
  const [a, m] = mois.split("-").map(Number);
  return new Date(a, m - 1, 1).toLocaleDateString(locale(), { month: "short", year: "numeric" });
}

function formatFcfaCourt(v: number): string {
  return nombreCourt(v);
}

function fcfa(v: number): string {
  return `${Number(v).toLocaleString(locale())} FCFA`;
}

const pourcentage = (v: number) => `${v} %`;

/** État mémorisé dans le navigateur (préférence d'affichage, sans enjeu si perdu). */
function useEtatMemorise<T>(cle: string, defaut: T): [T, (v: T) => void] {
  const [valeur, setValeur] = useState<T>(() => {
    try {
      const brut = localStorage.getItem(cle);
      return brut ? { ...defaut, ...JSON.parse(brut) } : defaut;
    } catch {
      return defaut;
    }
  });
  function enregistrer(v: T) {
    setValeur(v);
    try {
      localStorage.setItem(cle, JSON.stringify(v));
    } catch {
      // stockage indisponible (navigation privée…) : préférence non mémorisée
    }
  }
  return [valeur, enregistrer];
}

function Vide({ message }: { message: string }) {
  return <Text size="sm" c="dimmed" py="xl" ta="center">{message}</Text>;
}

const LIMITE_LIGNES = 8;

/**
 * Graphique (type au choix) des montants + tableau « libellé / nombre de
 * projets / montant / projets ». Les 8 premiers (par montant) sont affichés,
 * les autres à la demande ; le total porte toujours sur l'ensemble.
 */
function RepartitionProjets({
  type,
  lignes: toutes,
  colonne,
  noteMontant,
  vide,
  couleur,
}: {
  type: TypeGraphique;
  lignes: LigneRepartitionProjets[];
  colonne: string;
  noteMontant?: string;
  vide: string;
  couleur: string;
}) {
  const [toutVoir, setToutVoir] = useState(false);
  const apparence = useApparence();
  if (toutes.length === 0) return <Vide message={vide} />;
  if (apparence.tri && apparence.tri !== "aucun") {
    // Même ordre que le graphique (tri de l'apparence du bloc), sur le montant.
    toutes = [...toutes].sort((x, y) => (Number(x.montant) - Number(y.montant)) * (apparence.tri === "croissant" ? 1 : -1));
  }
  const totalMontant = toutes.reduce((s, l) => s + Number(l.montant), 0);
  const nbMasques = toutVoir ? 0 : Math.max(0, toutes.length - LIMITE_LIGNES);
  const lignes = toutVoir ? toutes : toutes.slice(0, LIMITE_LIGNES);
  // Le tableau ne s'ajoute au graphique qu'à la demande (mode « Tableau » ou « Les deux ») : pas de tableau-légende.
  const avecTableau = type === "tableau" || apparence.mode === "tableau" || apparence.mode === "les_deux";
  return (
    <Stack gap="sm">
      {type !== "tableau" && apparence.mode !== "tableau" && (
        <ApparenceContext.Provider value={{ ...apparence, mode: "graphique" }}>
        <GraphiqueAdaptable
          type={type}
          categories={lignes.map((l) => l.libelle)}
          series={[{ cle: "montant", nom: voc("Montant"), couleur, valeurs: lignes.map((l) => Number(l.montant)) }]}
          couleursCategories={type === "camembert" ? lignes.map((_, i) => COULEURS_SERIE[i % COULEURS_SERIE.length]) : undefined}
          formatValeur={fcfa}
          formatAxe={formatFcfaCourt}
          unite="FCFA"
          hauteur={Math.max(160, lignes.length * 44)}
        />
        </ApparenceContext.Provider>
      )}
      {avecTableau && <Table striped withTableBorder verticalSpacing={6} fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{colonne}</Table.Th>
            <Table.Th ta="right">{voc("Projets")}</Table.Th>
            <Table.Th ta="right">{voc("Montant (FCFA)")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lignes.map((l) => (
            <Table.Tr key={l.libelle}>
              <Table.Td>{l.libelle}</Table.Td>
              {/* Codes des projets au survol du nombre, plutôt qu'une liste qui encombre le tableau. */}
              <Table.Td ta="right">
                <Tooltip label={l.projets.join(", ")} multiline maw={360} withArrow disabled={l.projets.length === 0}>
                  <Text span size="sm" style={{ cursor: "help", borderBottom: "1px dotted var(--mantine-color-gray-5)" }}>{l.nombre}</Text>
                </Tooltip>
              </Table.Td>
              <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{Number(l.montant).toLocaleString(locale())}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot bg="gray.1">
          <Table.Tr>
            <Table.Th>{voc("Total")}</Table.Th>
            <Table.Th />
            <Table.Th ta="right" style={{ whiteSpace: "nowrap" }}>{totalMontant.toLocaleString(locale())}</Table.Th>
          </Table.Tr>
        </Table.Tfoot>
      </Table>}
      {toutes.length > LIMITE_LIGNES && (
        <Button variant="subtle" size="xs" onClick={() => setToutVoir((v) => !v)}>
          {toutVoir ? voc`Afficher seulement les ${LIMITE_LIGNES} premiers` : voc`Afficher les ${nbMasques} autres`}
        </Button>
      )}
      {noteMontant && <Text size="xs" c="dimmed">{noteMontant}</Text>}
    </Stack>
  );
}

/**
 * Un bloc du tableau de bord. `graphique` : le bloc contient un graphique
 * dont l'utilisateur peut changer le type (types proposés + type par défaut).
 */
type Bloc = DefinitionBloc & {
  largeur: 4 | 6 | 12;
  avecCarte?: boolean;
  graphique?: { types: TypeGraphique[]; defaut: TypeGraphique };
  rendu: (type: TypeGraphique) => ReactNode;
  /** Données du bloc pour son téléchargement (CSV, Excel avec graphique natif). */
  donnees?: (type: TypeGraphique) => DonneesExport | null;
};

export function DashboardConsolidePage() {
  const [filtres, setFiltres] = useEtatMemorise<EtatFiltres>(CLE_STOCKAGE_FILTRES, FILTRES_PAR_DEFAUT);
  // Blocs et types de graphiques : configuration commune à tous, modifiable
  // seulement par l'Administrateur ou un rôle ayant ce droit.
  const { data: configuration } = useConfigurationTableauDeBord();
  const enregistrer = useEnregistrerConfigurationTableauDeBord();
  const peutPersonnaliser = configuration?.peut_modifier ?? false;
  const masques = configuration?.blocs_masques ?? [];
  const types = (configuration?.types_graphiques ?? {}) as Record<string, TypeGraphique>;
  const [personnalisation, setPersonnalisation] = useState(false);

  const apparences = configuration?.apparences ?? {};
  const [aPersonnaliser, setAPersonnaliser] = useState<Bloc | null>(null);
  function sauvegarder(payload: { blocs_masques?: string[]; types_graphiques?: Record<string, TypeGraphique>;
    apparences?: Record<string, ApparenceBloc> }, apres?: () => void) {
    enregistrer.mutate(payload, {
      onSuccess: () => apres?.(),
      onError: (error) =>
        notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" }),
    });
  }
  /** Séries (plusieurs) ou catégories (une seule série) du bloc, pour choisir leurs couleurs. */
  function nomsColorables(b: Bloc): string[] {
    const d = b.donnees?.(typeDe(b));
    if (!d) return [];
    const unique = d.series === 1 || d.entetes.length === 2;
    return unique ? d.lignes.map((l) => String(l[0])) : d.entetes.slice(1);
  }
  // Lien de partage : filtres enregistrés avec le lien, ni personnalisation ni liens vers les projets.
  const partage = usePartage();
  const parametres = partage ? (partage.filtres as FiltresDashboard) : versParametres(filtres);
  const { data, isLoading, isFetching } = useDashboardConsolide(parametres);
  const [exportEnCours, setExportEnCours] = useState(false);
  const grille = useRef<HTMLDivElement>(null);
  async function exporter(fichier: FormatExportTableauDeBord) {
    setExportEnCours(true);
    try {
      if (fichier === "pptx") {
        await telechargerTableauDeBord(parametres, fichier);
        return;
      }
      // PDF, Word et Excel : chaque bloc affiché, tel qu'il est à l'écran (et sa place dans la grille).
      const blocsEcran = Array.from(grille.current?.querySelectorAll<HTMLElement>("[data-export-bloc]") ?? [])
        .map((colonne) => ({
          // Le contenu visible du bloc (pas une feuille de style ajoutée avant lui).
          element: Array.from(colonne.children).find((c): c is HTMLElement => c instanceof HTMLElement
            && c.tagName !== "STYLE" && c.getBoundingClientRect().height > 0) ?? colonne,
          titre: colonne.dataset.titre ?? "",
          largeur: Number(colonne.dataset.largeur) || 12,
        }));
      if (blocsEcran.length === 0) {
        notifications.show({ message: voc("Aucun bloc affiché à exporter."), color: "orange" });
        return;
      }
      const attente = notifications.show({
        message: voc("Préparation de l'export : chaque bloc est copié tel qu'il s'affiche. Cela peut prendre une demi-minute."),
        loading: true, autoClose: false,
      });
      try {
        await exporterCommeEcran(fichier, blocsEcran, parametres);
      } finally {
        notifications.hide(attente);
      }
    } catch (error) {
      notifications.show({ message: messageErreurApi(error, voc("L'export a échoué.")), color: "red" });
    } finally {
      setExportEnCours(false);
    }
  }

  const blocs = data ? definirBlocs(data, !partage) : [];
  const visibles = blocs.filter((b) => !masques.includes(b.cle));

  function typeDe(b: Bloc): TypeGraphique {
    const choisi = types[b.cle];
    return b.graphique && choisi && b.graphique.types.includes(choisi) ? choisi : (b.graphique?.defaut ?? "colonnes");
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <TitreRubrique route="/" defaut={voc("Tableau de bord")} majuscules />
        {!partage && (
          <Group gap="xs">
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <Button variant="light" color="green" leftSection={<Download size={16} />} rightSection={<ChevronDown size={14} />}
                  loading={exportEnCours}>
                  {voc("Exporter")}
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<FileSpreadsheet size={15} color="var(--mantine-color-green-7)" />} onClick={() => exporter("xlsx")}>Excel</Menu.Item>
                <Menu.Item leftSection={<FileText size={15} color="var(--mantine-color-red-7)" />} onClick={() => exporter("pdf")}>PDF</Menu.Item>
                <Menu.Item leftSection={<FileText size={15} color="var(--mantine-color-blue-7)" />} onClick={() => exporter("docx")}>Word</Menu.Item>
                <Menu.Item leftSection={<Presentation size={15} color="var(--mantine-color-orange-7)" />} onClick={() => exporter("pptx")}>PowerPoint</Menu.Item>
              </Menu.Dropdown>
            </Menu>
            <BoutonPartage type="TABLEAU_DE_BORD" filtres={parametres as Record<string, unknown>} />
            {peutPersonnaliser && (
              <Button variant="light" leftSection={<SlidersHorizontal size={16} />} onClick={() => setPersonnalisation(true)}>
                {voc("Personnaliser")}{blocs.length > 0 && voc` (${visibles.length}/${blocs.length} blocs)`}
              </Button>
            )}
          </Group>
        )}
      </Group>

      {!partage && <FiltresTableauDeBord valeur={filtres} onChange={setFiltres} nombreProjets={data?.nombre_projets} />}

      {isLoading || !data ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : (
        <Grid gap="md" ref={grille} style={{ opacity: isFetching ? 0.6 : 1, transition: "opacity 150ms" }}>
          {visibles.length === 0 && (
            <Grid.Col span={12}>
              <Vide
                message={
                  peutPersonnaliser
                    ? voc("Tous les blocs sont masqués — clique sur « Personnaliser » pour en afficher.")
                    : voc("Aucun bloc affiché : l'administrateur a masqué tous les blocs du tableau de bord.")
                }
              />
            </Grid.Col>
          )}
          {visibles.map((b) => (
            <Grid.Col key={b.cle} span={{ base: 12, md: b.largeur === 12 ? 12 : 6, xl: b.largeur }}
              data-export-bloc={b.cle} data-titre={apparences[b.cle]?.titre || b.titre} data-largeur={b.largeur}>
              <ApparenceContext.Provider value={apparences[b.cle] ?? {}}>
              {b.avecCarte === false ? (
                b.rendu(typeDe(b))
              ) : (
                <CarteGraphique
                  titre={apparences[b.cle]?.titre || b.titre}
                  sousTitre={apparences[b.cle]?.sous_titre}
                  donnees={b.donnees ? () => b.donnees!(typeDe(b)) : undefined}
                  filtres={parametres}
                  actions={
                    peutPersonnaliser && !partage && (
                      <Group gap={6} wrap="nowrap">
                        {b.graphique && (
                          <ChoixTypeGraphique
                            valeur={typeDe(b)}
                            types={b.graphique.types}
                            onChange={(t) => sauvegarder({ types_graphiques: { ...types, [b.cle]: t } })}
                          />
                        )}
                        <Tooltip label={voc("Personnaliser ce bloc")} withArrow>
                          <ActionIcon variant="default" size="md" onClick={() => setAPersonnaliser(b)} aria-label={voc("Personnaliser ce bloc")}>
                            <Paintbrush size={15} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    )
                  }
                >
                  {b.rendu(typeDe(b))}
                </CarteGraphique>
              )}
              </ApparenceContext.Provider>
            </Grid.Col>
          ))}
        </Grid>
      )}

      {aPersonnaliser && (
        <ApparenceBlocDrawer
          opened
          onClose={() => setAPersonnaliser(null)}
          titreDefaut={aPersonnaliser.titre}
          initiale={apparences[aPersonnaliser.cle] ?? {}}
          noms={nomsColorables(aPersonnaliser)}
          avecGraphique={!!aPersonnaliser.graphique?.types.some((t) => t !== "cartes" && t !== "tableau")}
          apercu={() => aPersonnaliser.rendu(typeDe(aPersonnaliser))}
          enregistrement={enregistrer.isPending}
          onEnregistrer={(a) => {
            const suivantes = { ...apparences };
            if (Object.keys(a).length) suivantes[aPersonnaliser.cle] = a;
            else delete suivantes[aPersonnaliser.cle];
            sauvegarder({ apparences: suivantes }, () => {
              setAPersonnaliser(null);
              notifications.show({ message: voc("Apparence enregistrée : tout le monde voit ce bloc ainsi."), color: "green" });
            });
          }}
        />
      )}

      <PersonnalisationModal
        opened={personnalisation}
        onClose={() => setPersonnalisation(false)}
        blocs={blocs}
        masques={masques}
        onChange={(liste) => sauvegarder({ blocs_masques: liste })}
        onReinitialiserTypes={() => sauvegarder({ types_graphiques: {} })}
      />
    </Stack>
  );
}

/** Tous les blocs du tableau de bord, dans l'ordre d'affichage. */
function definirBlocs(data: DashboardConsolide, liensProjets = true): Bloc[] {
  // Un projet garde la même couleur dans tous les graphiques (ordre alphabétique des codes).
  const codesProjets = data.projets.map((p) => p.code).sort();
  const couleurProjet = (code: string) => COULEURS_SERIE[codesProjets.indexOf(code) % COULEURS_SERIE.length];
  const couleursProjets = codesProjets.map(couleurProjet);
  const totalIndicateurs = data.indicateurs_par_statut.reduce((somme, p) => somme + p.count, 0);
  const budget = data.budget_detail;
  const cibles = data.cibles;
  const statuts = Object.keys(COULEURS_PROJET_STATUT) as StatutProjet[];
  const graphique = (nbSeries: number, defaut: TypeGraphique) => ({ types: typesPossibles(nbSeries), defaut });
  const serieParProjet = (lignes: Record<string, number | string>[]): SerieGraphique[] =>
    codesProjets.map((code) => ({
      cle: code,
      nom: code,
      couleur: couleurProjet(code),
      valeurs: lignes.map((l) => (l[code] === undefined ? 0 : Number(l[code]))),
    }));

  // Données des blocs à télécharger : première colonne = catégories, suivantes = séries.
  const depuisSeries = (libelle: string, categories: string[], series: { nom: string; couleur: string; valeurs: (number | null)[] }[],
    type: TypeGraphique, couleursCategories?: string[]): DonneesExport => ({
    entetes: [libelle, ...series.map((x) => x.nom)],
    lignes: categories.map((c, i) => [c, ...series.map((x) => x.valeurs[i] ?? null)]),
    type,
    legende: series.length > 1 ? series.map(({ nom, couleur }) => ({ nom, couleur }))
      : type === "camembert" && couleursCategories
        ? categories.map((nom, i) => ({ nom: `${nom} (${(series[0]?.valeurs[i] ?? 0).toLocaleString(locale())})`, couleur: couleursCategories[i] }))
        : undefined,
  });
  const depuisRepartition = (colonne: string, lignes: LigneRepartitionProjets[], type: TypeGraphique): DonneesExport => ({
    entetes: [colonne, voc("Montant (FCFA)"), voc("Projets")], series: 1, type,
    lignes: lignes.map((l) => [l.libelle, Number(l.montant), l.nombre]),
  });
  const statutsLibelles = statuts.map((s) => PROJET_STATUT_LABEL[s]);
  const budgetsProjets = codesProjets.map((code) => Number(data.projets.find((p) => p.code === code)?.budget_total ?? 0));
  const avancementProjets = data.avancement.par_projet;

  const chiffresCles: ChiffreCle[] = [
    { libelle: voc("Projets"), valeur: data.nombre_projets, texte: String(data.nombre_projets), icone: <FolderKanban size={20} />, couleur: "teal" },
    { libelle: voc("Budget total"), valeur: Number(data.budget_total), texte: fcfa(data.budget_total), icone: <Wallet size={20} />, couleur: "indigo" },
    { libelle: voc("Bénéficiaires"), valeur: data.nombre_beneficiaires, texte: String(data.nombre_beneficiaires), icone: <Users size={20} />, couleur: "grape" },
    { libelle: voc("Indicateurs suivis"), valeur: totalIndicateurs, texte: String(totalIndicateurs), icone: <Gauge size={20} />, couleur: "orange" },
  ];
  return [
    {
      cle: "chiffres-cles", titre: voc("Chiffres clés"), groupe: "Vue d'ensemble", largeur: 12,
      donnees: () => ({ entetes: [voc("Chiffre"), voc("Valeur")], type: "tableau",
        lignes: chiffresCles.map((c) => [c.libelle, c.valeur]) }),
      // Unités différentes (projets, FCFA, personnes) : cartes ou tableau, pas de graphique commun.
      graphique: { types: ["cartes", "tableau"], defaut: "cartes" },
      rendu: (type) => <ChiffresCles chiffres={chiffresCles} type={type} />,
    },
    {
      cle: "couverture", titre: voc("Couverture géographique (nombre de zones)"), groupe: voc("Géographie"), largeur: 12,
      donnees: () => ({ entetes: [voc("Niveau"), voc("Zones")], type: "colonnes",
        lignes: data.zones_couvertes.map((z) => [traduireDonnee(z.niveau), z.count]) }),
      // Cartes de chiffres par défaut ; on peut choisir à la place un graphique ou un tableau (ou les deux).
      graphique: { types: ["cartes", ...typesPossibles(1)], defaut: "cartes" },
      rendu: (type) => <CouvertureZones zones={data.zones_couvertes} type={type} />,
    },
    // Un bloc par niveau géographique (pays, puis région, province, commune…), chacun masquable et réglable.
    {
      cle: "pays", titre: voc("Projets par pays"), groupe: voc("Géographie"), largeur: 6,
      donnees: (type) => depuisRepartition(voc("Pays"), data.projets_par_pays, type),
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_pays} colonne={voc("Pays")} vide={voc("Aucun pays renseigné.")}
          couleur="#0c8599" noteMontant={voc("Montant = budget total des projets du pays.")} />
      ),
    },
    ...(data.projets_par_zone.length === 0
      ? [{
          cle: "zones", titre: voc("Projets par zone d'intervention"), groupe: voc("Géographie"), largeur: 6,
          rendu: () => <Vide message={voc("Aucune zone d'intervention renseignée sur les fiches projet (champ « Zones »).")} />,
        } as Bloc]
      : data.projets_par_zone.map((n, rang): Bloc => ({
          cle: `zones-niveau-${rang + 1}`,
          donnees: (type) => depuisRepartition(traduireDonnee(n.niveau), n.zones, type),
          titre: voc`Projets par ${langue() === "de" ? traduireDonnee(n.niveau) : traduireDonnee(n.niveau).toLowerCase()}`,
          groupe: voc("Géographie"), largeur: 6,
          graphique: graphique(1, "barres"),
          rendu: (type) => (
            <RepartitionProjets type={type} lignes={n.zones} colonne={traduireDonnee(n.niveau)} vide="—" couleur="#1098ad" />
          ),
        }))),
    {
      cle: "budget-detail", titre: voc("Budget total et détail"), groupe: voc("Budget et financements"), largeur: 12,
      donnees: (type) => depuisSeries(voc("Projet"), budget.par_projet.map((p) => p.code), [
        { nom: voc("Fonds propres"), couleur: "#12b886", valeurs: budget.par_projet.map((p) => Number(p.fonds_propres)) },
        { nom: voc("Financements bailleurs"), couleur: "#1c7ed6", valeurs: budget.par_projet.map((p) => Number(p.financements_bailleurs)) },
      ], type),
      graphique: graphique(2, "barres"),
      rendu: (type) => (
        <Stack gap="md">
          <SimpleGrid cols={{ base: 1, xs: 2, lg: 5 }} spacing="sm">
            <StatCard label={voc("Budget total")} value={fcfa(budget.total)} icon={<Wallet size={20} />} color="indigo" />
            <StatCard label={voc("Fonds propres")} value={fcfa(budget.fonds_propres)} icon={<Wallet size={20} />} color="teal" />
            <StatCard label={voc("Financements bailleurs")} value={fcfa(budget.financements_bailleurs)} icon={<Wallet size={20} />} color="blue" />
            <StatCard label={voc("Alloué aux activités")} value={fcfa(budget.alloue_activites)} icon={<Wallet size={20} />} color="grape" />
            <StatCard label={voc("Dépensé (suivi)")} value={fcfa(budget.depense_activites)} icon={<Wallet size={20} />} color="orange" />
          </SimpleGrid>
          <GraphiqueAdaptable
            type={type}
            categories={budget.par_projet.map((p) => p.code)}
            libelleCategories={voc("Projet")}
            total
            series={[
              { cle: "fp", nom: voc("Fonds propres"), couleur: "#12b886", valeurs: budget.par_projet.map((p) => Number(p.fonds_propres)) },
              { cle: "fb", nom: voc("Financements bailleurs"), couleur: "#1c7ed6", valeurs: budget.par_projet.map((p) => Number(p.financements_bailleurs)) },
            ]}
            formatValeur={fcfa}
            formatAxe={formatFcfaCourt}
            etiquettes={false}
          />
        </Stack>
      ),
    },
    {
      cle: "bailleurs", titre: voc("Projets par bailleur"), groupe: voc("Budget et financements"), largeur: 4,
      donnees: (type) => depuisRepartition(voc("Bailleur"), data.projets_par_bailleur, type),
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_bailleur} colonne={voc("Bailleur")} vide={voc("Aucun bailleur renseigné.")}
          couleur="#1c7ed6"
          noteMontant={voc("Montant = financements saisis ; à défaut, budget du projet hors fonds propres, attribué au bailleur principal.")} />
      ),
    },
    {
      cle: "consortium", titre: voc("Projets par partenaire de consortium"), groupe: voc("Budget et financements"), largeur: 4,
      donnees: (type) => depuisRepartition(voc("Partenaire"), data.projets_par_consortium, type),
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_consortium} colonne={voc("Partenaire")} vide={voc("Aucun projet en consortium.")}
          couleur="#ae3ec9" noteMontant={voc("Montant = budget total des projets auxquels le partenaire participe.")} />
      ),
    },
    {
      cle: "mise-en-oeuvre", titre: voc("Projets par partenaire de mise en œuvre"), groupe: voc("Budget et financements"), largeur: 4,
      donnees: (type) => depuisRepartition(voc("Partenaire"), data.projets_par_mise_en_oeuvre, type),
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_mise_en_oeuvre} colonne={voc("Partenaire")}
          vide={voc("Aucun partenaire de mise en œuvre renseigné.")} couleur="#f59f00"
          noteMontant={voc("Montant = budget total des projets mis en œuvre par le partenaire.")} />
      ),
    },
    {
      cle: "cibles", titre: voc("Cibles des projets (par sexe et par statut)"), groupe: voc("Bénéficiaires"), largeur: 12,
      donnees: (type) => depuisSeries(voc("Projet"), cibles.par_projet.map((p) => p.code), [
        { nom: voc("Femmes"), couleur: COULEUR_FEMMES, valeurs: cibles.par_projet.map((p) => p.femmes) },
        { nom: voc("Hommes"), couleur: COULEUR_HOMMES, valeurs: cibles.par_projet.map((p) => p.hommes) },
        { nom: voc("Jeunes"), couleur: "#f59f00", valeurs: cibles.par_projet.map((p) => p.jeunes) },
        { nom: voc("PDI"), couleur: "#ae3ec9", valeurs: cibles.par_projet.map((p) => p.pdi) },
      ], type),
      graphique: graphique(4, "colonnes"),
      rendu: (type) => (
        <Grid gap="lg">
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Text fw={600} mb="xs">{voc("Cible totale :")} {cibles.totale.toLocaleString(locale())} {voc("personnes")}</Text>
            <CamembertChart
              unite={voc("personnes")}
              parts={[
                { libelle: voc("Femmes"), valeur: cibles.femmes, couleur: COULEUR_FEMMES },
                { libelle: voc("Hommes"), valeur: cibles.hommes, couleur: COULEUR_HOMMES },
              ]}
            />
            <Group gap="xs" mt="md">
              <Badge size="lg" variant="light" color="orange">{voc("Jeunes :")} {cibles.jeunes.toLocaleString(locale())}</Badge>
              <Badge size="lg" variant="light" color="grape">{voc("PDI :")} {cibles.pdi.toLocaleString(locale())}</Badge>
            </Group>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <GraphiqueAdaptable
              type={type}
              categories={cibles.par_projet.map((p) => p.code)}
              libelleCategories={voc("Projet")}
              total
              series={[
                { cle: "femmes", nom: voc("Femmes"), couleur: COULEUR_FEMMES, valeurs: cibles.par_projet.map((p) => p.femmes) },
                { cle: "hommes", nom: voc("Hommes"), couleur: COULEUR_HOMMES, valeurs: cibles.par_projet.map((p) => p.hommes) },
                { cle: "jeunes", nom: voc("Jeunes"), couleur: "#f59f00", valeurs: cibles.par_projet.map((p) => p.jeunes) },
                { cle: "pdi", nom: voc("PDI"), couleur: "#ae3ec9", valeurs: cibles.par_projet.map((p) => p.pdi) },
              ]}
              hauteur={300}
              etiquettes={false}
            />
            <Text size="xs" c="dimmed">{voc("Cibles saisies sur la fiche de chaque projet (les jeunes et les PDI font partie de la cible totale).")}</Text>
          </Grid.Col>
        </Grid>
      ),
    },
    {
      cle: "finances", titre: voc("Budget et efficience"), groupe: voc("Budget et financements"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Projet"), voc("Dépensé (FCFA)"), voc("Budget révisé (FCFA)"), voc("Engagé (FCFA)"), voc("Exécution financière (%)"),
          voc("Exécution physique (%)"), voc("Financements acquis (FCFA)"), voc("Reçus des bailleurs (FCFA)")],
        series: 2, type: "barres",
        lignes: data.finances.par_projet.map((p) => [p.code, Number(p.depense), Number(p.budget_revise), Number(p.engage), p.taux_execution,
          data.execution_par_projet.find((e) => e.code === p.code)?.physique ?? null, Number(p.financements_acquis), Number(p.financements_recus)]),
      }),
      rendu: () => <FinancesBloc f={data.finances} physique={Object.fromEntries(data.execution_par_projet.map((e) => [e.code, e.physique]))} />,
    },
    {
      cle: "avancement", titre: voc("Avancement et retards des activités"), groupe: voc("Projets"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Projet"), voc("En retard"), voc("Activités"), voc("Terminées"), voc("Retard moyen (jours)"), voc("Exécution à date (%)")],
        series: 1, type: "barres",
        lignes: avancementProjets.map((p) => [p.code, p.en_retard, p.prevues, p.terminees, p.retard_moyen_jours, p.taux_execution_a_date]),
      }),
      rendu: () => <AvancementActivitesBloc a={data.avancement} />,
    },
    {
      cle: "territoires", titre: voc("Bénéficiaires et territoires"), groupe: voc("Bénéficiaires"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Territoire"), voc("Bénéficiaires"), voc("Femmes (%)"), voc("Population"), voc("Pour 1 000 habitants"), voc("Abandon (%)")],
        series: 1, type: "barres",
        lignes: data.territoires.territoires.map((t) => [t.zone, t.beneficiaires, t.part_femmes, t.population, t.pour_1000_habitants, t.taux_abandon]),
      }),
      rendu: () => <TerritoiresBloc t={data.territoires} />,
    },
    {
      cle: "qualite", titre: voc("Qualité des données"), groupe: voc("Pilotage"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Composante"), voc("Valeur (%)"), voc("Poids")], series: 1, type: "barres",
        lignes: ([["completude", voc("Complétude")], ["ponctualite", voc("Saisies dans les délais")], ["plausibilite", voc("Valeurs plausibles")],
          ["doublons", voc("Doublons traités")]] as const).map(([c, nom]) => [nom, data.qualite.composantes[c], data.qualite.poids[c]]),
      }),
      rendu: () => <QualiteBloc q={data.qualite} />,
    },
    {
      cle: "pilotage", titre: voc("Rapports, risques et apprentissage"), groupe: voc("Pilotage"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Niveau de risque"), voc("Risques ouverts")], series: 1, type: "colonnes",
        lignes: ([["CRITIQUE", voc("Critique")], ["ELEVE", voc("Élevé")], ["MOYEN", voc("Moyen")], ["FAIBLE", voc("Faible")]] as const)
          .map(([n, nom]) => [nom, data.pilotage.risques.par_niveau[n]]),
      }),
      rendu: () => <PilotageBloc p={data.pilotage} />,
    },
    {
      cle: "performance", titre: voc("Performance des indicateurs"), groupe: voc("Projets"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Indicateur"), voc("Projet"), voc("Référence"), voc("Valeur actuelle"), voc("Cible"), voc("Écart à la cible"),
          voc("Taux d'atteinte (%)"), voc("Tendance")],
        series: 1, type: "barres",
        lignes: data.performance.liste.map((x) => [x.libelle, x.projet, nombreOuNul(x.reference), nombreOuNul(x.actuelle), Number(x.cible),
          nombreOuNul(x.ecart), x.taux, x.tendance ? LIBELLES_TENDANCE()[x.tendance] : ""]),
      }),
      rendu: () => <PerformanceBloc p={data.performance} liens={liensProjets} />,
    },
    {
      cle: "plaintes", titre: voc("Plaintes et retours"), groupe: voc("Pilotage"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Type de retour"), voc("Dossiers")], series: 1, type: "barres",
        lignes: data.plaintes.par_type.map((x) => [traduireDonnee(x.libelle), x.nombre]),
      }),
      rendu: () => <PlaintesBloc p={data.plaintes} />,
    },
    {
      cle: "performance-territoires", titre: voc("Performance par région"), groupe: voc("Géographie"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Pays"), voc("Région"), voc("Projets"), voc("Activités"), voc("Activités réalisées (%)"), voc("Dépenses (FCFA)"),
          voc("Réalisation des indicateurs (%)")],
        series: 1, type: "barres",
        lignes: data.performance_territoires.flatMap((p) => p.zones.map((z) => [p.pays, z.zone, z.projets, z.activites, z.part_realisees,
          z.depenses, z.taux_indicateurs])),
      }),
      rendu: () => <PerformanceTerritoiresBloc t={data.performance_territoires} />,
    },
    {
      cle: "projets-statut", titre: voc("Projets par statut"), groupe: voc("Projets"), largeur: 4,
      donnees: (type) => depuisSeries(voc("Statut"), statutsLibelles,
        [{ nom: voc("Projets"), couleur: "#12b886", valeurs: statuts.map((x) => data.projets_par_statut[x] ?? 0) }], type,
        statuts.map((x) => COULEURS_PROJET_STATUT[x])),
      graphique: graphique(1, "camembert"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={statuts.map((s) => PROJET_STATUT_LABEL[s])}
          libelleCategories={voc("Statut")}
          total
          series={[{ cle: "n", nom: voc("Projets"), couleur: "#12b886", valeurs: statuts.map((s) => data.projets_par_statut[s] ?? 0) }]}
          couleursCategories={statuts.map((s) => COULEURS_PROJET_STATUT[s])}
          unite={data.nombre_projets > 1 ? voc("projets") : voc("projet")}
        />
      ),
    },
    {
      cle: "budget-projet", titre: voc("Budget par projet (FCFA)"), groupe: voc("Budget et financements"), largeur: 4,
      donnees: (type) => depuisSeries(voc("Projet"), codesProjets,
        [{ nom: voc("Budget (FCFA)"), couleur: "#4263eb", valeurs: budgetsProjets }], type, couleursProjets),
      graphique: graphique(1, "camembert"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={codesProjets}
          series={[{
            cle: "budget", nom: voc("Budget"), couleur: "#4263eb",
            valeurs: codesProjets.map((code) => Number(data.projets.find((p) => p.code === code)?.budget_total ?? 0)),
          }]}
          couleursCategories={couleursProjets}
          formatValeur={fcfa}
          formatAxe={formatFcfaCourt}
          unite="FCFA"
          hauteur={Math.max(280, codesProjets.length * 22)}
          libelleCategories={voc("Projet")}
          total
        />
      ),
    },
    {
      cle: "beneficiaires-sexe", titre: voc("Bénéficiaires inscrits par sexe"), groupe: voc("Bénéficiaires"), largeur: 4,
      donnees: (type) => depuisSeries(voc("Sexe"), [voc("Femmes"), voc("Hommes")],
        [{ nom: voc("Bénéficiaires"), couleur: COULEUR_FEMMES, valeurs: [data.beneficiaires_par_sexe.F ?? 0, data.beneficiaires_par_sexe.M ?? 0] }],
        type, [COULEUR_FEMMES, COULEUR_HOMMES]),
      graphique: graphique(1, "camembert"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={[voc("Femmes"), voc("Hommes")]}
          libelleCategories={voc("Sexe")}
          total
          series={[{ cle: "n", nom: voc("Bénéficiaires"), couleur: COULEUR_FEMMES, valeurs: [data.beneficiaires_par_sexe.F ?? 0, data.beneficiaires_par_sexe.M ?? 0] }]}
          couleursCategories={[COULEUR_FEMMES, COULEUR_HOMMES]}
          unite={voc("bénéficiaires")}
        />
      ),
    },
    {
      cle: "activites-projet", titre: voc("Activités par statut, par projet"), groupe: voc("Projets"), largeur: 6,
      donnees: (type) => depuisSeries(voc("Projet"), data.activites_par_projet.map((p) => p.code), [
        { nom: voc("Non réalisées"), couleur: "#adb5bd", valeurs: data.activites_par_projet.map((p) => p.NON_REALISEE ?? 0) },
        { nom: voc("En cours"), couleur: "#fab219", valeurs: data.activites_par_projet.map((p) => p.EN_COURS ?? 0) },
        { nom: voc("Réalisées"), couleur: "#0ca30c", valeurs: data.activites_par_projet.map((p) => p.REALISEE ?? 0) },
        { nom: voc("Suspendues"), couleur: "#e8590c", valeurs: data.activites_par_projet.map((p) => p.SUSPENDUE ?? 0) },
        { nom: voc("Annulées"), couleur: "#495057", valeurs: data.activites_par_projet.map((p) => p.ANNULEE ?? 0) },
      ], type),
      graphique: graphique(5, "colonnes-empilees"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.activites_par_projet.map((p) => p.code)}
          libelleCategories={voc("Projet")}
          total
          series={[
            { cle: "nr", nom: voc("Non réalisées"), couleur: "#adb5bd", valeurs: data.activites_par_projet.map((p) => p.NON_REALISEE ?? 0) },
            { cle: "ec", nom: voc("En cours"), couleur: "#fab219", valeurs: data.activites_par_projet.map((p) => p.EN_COURS ?? 0) },
            { cle: "re", nom: voc("Réalisées"), couleur: "#0ca30c", valeurs: data.activites_par_projet.map((p) => p.REALISEE ?? 0) },
            // Suspendues et annulées : affichées seulement s'il y en a.
            ...([["su", voc("Suspendues"), "#e8590c", "SUSPENDUE"], ["an", voc("Annulées"), "#495057", "ANNULEE"]] as const)
              .filter(([, , , statut]) => data.activites_par_projet.some((p) => p[statut]))
              .map(([cle, nom, couleur, statut]) => ({ cle, nom, couleur, valeurs: data.activites_par_projet.map((p) => p[statut] ?? 0) })),
          ]}
        />
      ),
    },
    {
      cle: "beneficiaires-projet", titre: voc("Bénéficiaires par projet (femmes / hommes)"), groupe: voc("Bénéficiaires"), largeur: 6,
      donnees: (type) => depuisSeries(voc("Projet"), data.beneficiaires_par_projet_sexe.map((p) => p.code), [
        { nom: voc("Femmes"), couleur: COULEUR_FEMMES, valeurs: data.beneficiaires_par_projet_sexe.map((p) => p.F ?? 0) },
        { nom: voc("Hommes"), couleur: COULEUR_HOMMES, valeurs: data.beneficiaires_par_projet_sexe.map((p) => p.M ?? 0) },
      ], type),
      graphique: graphique(2, "colonnes"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.beneficiaires_par_projet_sexe.map((p) => p.code)}
          libelleCategories={voc("Projet")}
          series={[
            { cle: "F", nom: voc("Femmes"), couleur: COULEUR_FEMMES, valeurs: data.beneficiaires_par_projet_sexe.map((p) => p.F ?? 0) },
            { cle: "M", nom: voc("Hommes"), couleur: COULEUR_HOMMES, valeurs: data.beneficiaires_par_projet_sexe.map((p) => p.M ?? 0) },
          ]}
        />
      ),
    },
    {
      cle: "indicateurs-statut", titre: voc("Indicateurs par statut"), groupe: voc("Projets"), largeur: 6,
      donnees: (type) => depuisSeries(voc("Niveau d'alerte"), data.indicateurs_par_statut.map((p) => p.libelle),
        [{ nom: voc("Indicateurs"), couleur: "#868e96", valeurs: data.indicateurs_par_statut.map((p) => p.count) }], type,
        data.indicateurs_par_statut.map((p) => p.couleur)),
      graphique: graphique(1, "colonnes"),
      rendu: (type) => (
        <Stack gap="xs">
          <GraphiqueAdaptable
            type={type}
            categories={data.indicateurs_par_statut.map((p) => p.libelle)}
            libelleCategories={voc("Niveau d'alerte")}
            total
            series={[{ cle: "n", nom: voc("Indicateurs"), couleur: "#868e96", valeurs: data.indicateurs_par_statut.map((p) => p.count) }]}
            couleursCategories={data.indicateurs_par_statut.map((p) => p.couleur)}
            unite={voc("indicateurs")}
          />
          {/* Indicateurs en retard de saisie (fréquence de collecte) : leur niveau d'alerte peut être dépassé. */}
          <Text size="sm" c={data.indicateurs_non_actualises ? "orange.8" : "dimmed"}>
            {data.indicateurs_non_actualises
              ? voc`${data.indicateurs_non_actualises} indicateur(s) non actualisé(s) : une nouvelle valeur est attendue selon leur fréquence de collecte.`
              : voc("Tous les indicateurs sont à jour de leur fréquence de collecte.")}
          </Text>
        </Stack>
      ),
    },
    {
      cle: "execution-projet", titre: voc("Exécution par projet (%)"), groupe: voc("Projets"), largeur: 6,
      donnees: (type) => depuisSeries(voc("Projet"), data.execution_par_projet.map((p) => p.code), [
        { nom: voc("Exécution physique (%)"), couleur: "#1c7ed6", valeurs: data.execution_par_projet.map((p) => p.physique) },
        { nom: voc("Exécution financière (%)"), couleur: "#12b886", valeurs: data.execution_par_projet.map((p) => p.financier) },
      ], type),
      graphique: graphique(2, "colonnes"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.execution_par_projet.map((p) => p.code)}
          libelleCategories={voc("Projet")}
          series={[
            { cle: "physique", nom: voc("Exécution physique"), couleur: "#1c7ed6", valeurs: data.execution_par_projet.map((p) => p.physique) },
            { cle: "financier", nom: voc("Exécution financière"), couleur: "#12b886", valeurs: data.execution_par_projet.map((p) => p.financier) },
          ]}
          formatValeur={pourcentage}
          hauteur={Math.max(280, data.execution_par_projet.length * (type === "barres" ? 60 : 0))}
        />
      ),
    },
    {
      cle: "depenses-mois", titre: voc("Dépenses cumulées par projet (FCFA)"), groupe: voc("Évolution dans le temps"), largeur: 6,
      donnees: (type) => depuisSeries(voc("Mois"), data.depenses_par_mois.map((l) => String(l.mois)),
        serieParProjet(data.depenses_par_mois).filter((x) => x.valeurs.some((v) => v)), type),
      graphique: graphique(2, "courbes"),
      rendu: (type) =>
        data.depenses_par_mois.length === 0 ? (
          <Vide message={voc("Aucune dépense saisie dans le suivi.")} />
        ) : (
          <GraphiqueAdaptable
            type={type}
            categories={data.depenses_par_mois.map((l) => String(l.mois))}
            libelleCategories={voc("Mois")}
            series={serieParProjet(data.depenses_par_mois).filter((s) => s.valeurs.some((v) => v))}
            formatCategorie={formatMois}
            formatValeur={fcfa}
            formatAxe={formatFcfaCourt}
            etiquettes={false}
          />
        ),
    },
    {
      cle: "inscriptions-mois", titre: voc("Nouveaux bénéficiaires inscrits par mois"), groupe: voc("Évolution dans le temps"), largeur: 6,
      donnees: (type) => depuisSeries(voc("Mois"), data.inscriptions_par_mois.map((l) => String(l.mois)),
        serieParProjet(data.inscriptions_par_mois).filter((x) => x.valeurs.some((v) => v)), type),
      graphique: graphique(2, "colonnes"),
      rendu: (type) =>
        data.inscriptions_par_mois.length === 0 ? (
          <Vide message={voc("Aucune inscription.")} />
        ) : (
          <>
            <GraphiqueAdaptable
              type={type}
              categories={data.inscriptions_par_mois.map((l) => String(l.mois))}
              libelleCategories={voc("Mois")}
              total
              series={serieParProjet(data.inscriptions_par_mois).filter((s) => s.valeurs.some((v) => v))}
              formatCategorie={formatMois}
            />
            <Text size="xs" c="dimmed" mt={4}>{voc("Nombre de bénéficiaires ajoutés à chaque projet pendant le mois.")}</Text>
          </>
        ),
    },
    {
      cle: "liste-projets", titre: voc("Liste des projets"), groupe: voc("Projets"), largeur: 12,
      donnees: () => ({
        entetes: [voc("Code"), voc("Budget (FCFA)"), voc("Nom"), voc("Statut")], series: 1, type: "barres",
        lignes: data.projets.map((p) => [p.code, Number(p.budget_total), p.nom, PROJET_STATUT_LABEL[p.statut] ?? p.statut]),
      }),
      rendu: () =>
        data.projets.length === 0 ? (
          <Vide message={voc("Aucun projet pour le moment.")} />
        ) : (
          <Table.ScrollContainer minWidth={520}>
            <Table striped highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Code")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Nom")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed">{voc("Statut")}</Table.Th>
                  <Table.Th tt="uppercase" fz="xs" c="dimmed" ta="right">{voc("Budget")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.projets.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Text size="sm" fw={500} c="dimmed">{p.code}</Text>
                    </Table.Td>
                    <Table.Td>
                      {liensProjets ? (
                        <Text component={Link} to={`/projets/${p.id}`} size="sm" fw={500} c="teal.8">
                          {p.nom}
                        </Text>
                      ) : (
                        <Text size="sm" fw={500}>{p.nom}</Text>
                      )}
                    </Table.Td>
                    <Table.Td>{PROJET_STATUT_LABEL[p.statut] ?? p.statut}</Table.Td>
                    <Table.Td ta="right">{fcfa(Number(p.budget_total))}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        ),
    },
  ];
}

const pct = (x: number | null) => (x === null ? "—" : `${x.toLocaleString(locale())} %`);
const jours = (x: number | null) => (x === null ? "—" : voc`${Math.round(x).toLocaleString(locale())} j`);

/**
 * Avancement des activités de terrain : démarrage, achèvement, exécution à date, retards et délais,
 * jalons, activités incomplètes ; retards par projet et activités les plus en retard.
 */
function AvancementActivitesBloc({ a }: { a: AvancementActivites }) {
  if (a.prevues === 0) return <Vide message={voc("Aucune activité planifiée sur ces projets.")} />;
  const incompletes = [
    a.sans_responsable && voc`${a.sans_responsable} sans responsable`,
    a.sans_calendrier && voc`${a.sans_calendrier} sans dates`,
    a.sans_budget && voc`${a.sans_budget} sans budget`,
    a.demarrage_en_retard && voc`${a.demarrage_en_retard} qui auraient dû démarrer`,
  ].filter(Boolean);
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatCard label={voc("Démarrées")} value={`${pct(a.taux_demarrage)}`} icon={<Gauge size={20} />} color="blue" />
        <StatCard label={voc("Terminées")} value={`${pct(a.taux_achevement)}`} icon={<Gauge size={20} />} color="teal" />
        <StatCard label={voc("Exécution à date")} value={pct(a.taux_execution_a_date)} icon={<Gauge size={20} />} color="indigo" />
        <StatCard label={voc("En retard")} value={`${a.en_retard} (${pct(a.part_en_retard)})`} icon={<Gauge size={20} />}
          color={a.en_retard ? "red" : "teal"} />
        <StatCard label={voc("Retard moyen")} value={jours(a.retard_moyen_jours)} icon={<Gauge size={20} />} color="orange" />
        <StatCard label={voc("Terminées dans les délais")} value={pct(a.terminees_dans_les_delais)} icon={<Gauge size={20} />} color="teal" />
        <StatCard label={voc("Jalons atteints")} value={a.jalons.total ? `${a.jalons.atteints} / ${a.jalons.total} · ${pct(a.jalons.part_atteints)}` : "—"}
          icon={<Gauge size={20} />} color="grape" />
        <StatCard label={voc("Avec justificatifs")} value={pct(a.avec_justificatifs)} icon={<Gauge size={20} />} color="gray" />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {voc`${a.prevues} activités de terrain : ${a.demarrees} démarrées, ${a.terminees} terminées ; ${a.attendues_a_date} devaient être terminées aujourd'hui.`}
        {(a.suspendues > 0 || a.annulees > 0) && " " + voc`${a.suspendues} suspendue(s) ; ${a.annulees} annulée(s), retirée(s) des activités prévues et des taux.`}
        {a.duree_moyenne_realisation_jours !== null && " " + voc`Durée moyenne de réalisation : ${jours(a.duree_moyenne_realisation_jours)}.`}
        {a.retard_moyen_a_l_achevement_jours !== null && " " + voc`Retard moyen des activités terminées après leur échéance : ${jours(a.retard_moyen_a_l_achevement_jours)}.`}
        {a.jalons.en_retard > 0 && " " + voc`${a.jalons.en_retard} jalon(s) en retard.`}
      </Text>
      {incompletes.length > 0 && (
        <Text size="sm" c="orange.8">{voc("À compléter :")} {incompletes.join(" · ")}.</Text>
      )}
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <div>
          <Text fw={600} mb="xs">{voc("Retards par projet")}</Text>
          <Table.ScrollContainer minWidth={420} mah={360}>
            <Table striped withTableBorder stickyHeader verticalSpacing={6} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Projet")}</Table.Th>
                  <Table.Th ta="right">{voc("Activités")}</Table.Th>
                  <Table.Th ta="right">{voc("En retard")}</Table.Th>
                  <Table.Th ta="right">{voc("Retard moyen")}</Table.Th>
                  <Table.Th ta="right">{voc("Exécution à date")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {a.par_projet.map((p) => (
                  <Table.Tr key={p.code}>
                    <Table.Td fw={600}>{p.code}</Table.Td>
                    <Table.Td ta="right">{p.prevues}</Table.Td>
                    <Table.Td ta="right" c={p.en_retard ? "red.7" : undefined}>{p.en_retard}</Table.Td>
                    <Table.Td ta="right">{jours(p.retard_moyen_jours)}</Table.Td>
                    <Table.Td ta="right">{pct(p.taux_execution_a_date)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
        <div>
          <Text fw={600} mb="xs">{voc("Activités les plus en retard")}</Text>
          {a.activites_en_retard.length === 0 ? (
            <Text size="sm" c="dimmed">{voc("Aucune activité en retard.")}</Text>
          ) : (
            <Table.ScrollContainer minWidth={420} mah={360}>
              <Table striped withTableBorder stickyHeader verticalSpacing={6} fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{voc("Activité")}</Table.Th>
                    <Table.Th>{voc("Échéance")}</Table.Th>
                    <Table.Th ta="right">{voc("Retard")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {a.activites_en_retard.map((r) => (
                    <Table.Tr key={`${r.projet}-${r.code}-${r.libelle}`}>
                      <Table.Td>
                        <Text size="sm">{r.libelle}</Text>
                        <Text size="xs" c="dimmed">{r.projet}{r.code ? ` · ${r.code}` : ""}</Text>
                      </Table.Td>
                      <Table.Td style={{ whiteSpace: "nowrap" }}>{new Date(r.date_fin).toLocaleDateString(locale())}</Table.Td>
                      <Table.Td ta="right" c="red.7" style={{ whiteSpace: "nowrap" }}>{jours(r.jours)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </div>
      </SimpleGrid>
    </Stack>
  );
}

/** Écart (points) entre exécution financière et physique au-delà duquel un projet est signalé. */
const ECART_FINANCIER_PHYSIQUE = 20;

/**
 * Budget et efficience : budget initial et révisé, engagé, dépensé, attendu à date, solde ; financements
 * acquis, reçus et restant à trouver ; coûts unitaires ; rapprochement exécution financière / physique.
 */
function FinancesBloc({ f, physique }: { f: FinancesTableauDeBord; physique: Record<string, number | null> }) {
  const montant = (x: string | number | null) => (x === null ? "—" : fcfa(Number(x)));
  const court = (x: string | number | null) => (x === null ? "—" : `${formatFcfaCourt(Number(x))} FCFA`);
  const ecart = Number(f.ecart_a_date);
  const signales = f.par_projet.filter((p) => p.taux_execution !== null && physique[p.code] !== null && physique[p.code] !== undefined
    && p.taux_execution - (physique[p.code] as number) >= ECART_FINANCIER_PHYSIQUE);
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatCard label={voc("Budget révisé")} value={court(f.budget_revise)} icon={<Wallet size={20} />} color="indigo" />
        <StatCard label={voc("Engagé")} value={`${court(f.engage)} · ${pct(f.taux_engagement)}`} icon={<Wallet size={20} />} color="grape" />
        <StatCard label={voc("Dépensé")} value={`${court(f.depense)} · ${pct(f.taux_execution)}`} icon={<Wallet size={20} />} color="orange" />
        <StatCard label={voc("Reste à dépenser")} value={court(f.reste_a_depenser)} icon={<Wallet size={20} />} color="teal" />
        <StatCard label={voc("Financements acquis")} value={court(f.financements_acquis)} icon={<Wallet size={20} />} color="blue" />
        <StatCard label={voc("Reçus des bailleurs")} value={`${court(f.financements_recus)} · ${pct(f.taux_decaissement)}`} icon={<Wallet size={20} />} color="cyan" />
        <StatCard label={voc("Coût par bénéficiaire")} value={court(f.cout_par_beneficiaire)} icon={<Users size={20} />} color="pink" />
        <StatCard label={voc("Lignes en dépassement")} value={`${f.lignes_en_depassement} / ${f.lignes_budgetees} · ${pct(f.part_lignes_en_depassement)}`} icon={<Gauge size={20} />}
          color={f.lignes_en_depassement ? "red" : "teal"} />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {voc`Budget initial ${montant(f.budget_initial)} ; dépense attendue à ce jour ${montant(f.depense_attendue_a_date)}, soit un écart de ${ecart > 0 ? "+" : ""}${montant(ecart)}.`}
        {f.taux_engagement !== null && " " + voc`Solde non engagé : ${montant(f.solde_non_engage)}.`}
        {Number(f.besoin_de_financement) > 0 && " " + voc`Financement restant à trouver : ${montant(f.besoin_de_financement)}.`}
        {f.cout_par_activite_realisee !== null && " " + voc`Coût moyen d'une activité réalisée : ${montant(f.cout_par_activite_realisee)}.`}
      </Text>
      {signales.length > 0 && (
        <Text size="sm" c="orange.8">
          {voc`Dépensent plus vite qu'ils n'avancent (écart d'au moins ${ECART_FINANCIER_PHYSIQUE} points) :`} {signales.map((p) => p.code).join(", ")}.
        </Text>
      )}
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <div>
          <Text fw={600} mb="xs">{voc("Exécution par projet")}</Text>
          <Table.ScrollContainer minWidth={520} mah={380}>
            <Table striped withTableBorder stickyHeader verticalSpacing={6} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Projet")}</Table.Th>
                  <Table.Th ta="right">{voc("Budget révisé")}</Table.Th>
                  <Table.Th ta="right">{voc("Dépensé")}</Table.Th>
                  <Table.Th ta="right">{voc("Financier")}</Table.Th>
                  <Table.Th ta="right">{voc("Physique")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {f.par_projet.map((p) => {
                  const ecartProjet = p.taux_execution !== null && physique[p.code] != null ? p.taux_execution - (physique[p.code] as number) : null;
                  return (
                    <Table.Tr key={p.code}>
                      <Table.Td fw={600}>{p.code}</Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{court(p.budget_revise)}</Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{court(p.depense)}</Table.Td>
                      <Table.Td ta="right" c={ecartProjet !== null && ecartProjet >= ECART_FINANCIER_PHYSIQUE ? "orange.8" : undefined}>{pct(p.taux_execution)}</Table.Td>
                      <Table.Td ta="right">{pct(physique[p.code] ?? null)}</Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
        <div>
          <Text fw={600} mb="xs">{voc("Coûts unitaires : prévu et réel")}</Text>
          {f.couts_unitaires.length === 0 ? (
            <Text size="sm" c="dimmed">{voc("Il faut une quantité prévue et réalisée, un budget et une dépense sur une même activité.")}</Text>
          ) : (
            <Table.ScrollContainer minWidth={480} mah={380}>
              <Table striped withTableBorder stickyHeader verticalSpacing={6} fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{voc("Activité")}</Table.Th>
                    <Table.Th ta="right">{voc("Prévu / unité")}</Table.Th>
                    <Table.Th ta="right">{voc("Réel / unité")}</Table.Th>
                    <Table.Th ta="right">{voc("Écart")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {f.couts_unitaires.map((u) => (
                    <Table.Tr key={`${u.projet}-${u.code}-${u.libelle}`}>
                      <Table.Td>
                        <Text size="sm">{u.libelle}</Text>
                        <Text size="xs" c="dimmed">{u.projet}{u.code ? ` · ${u.code}` : ""}{u.unite ? ` · ${voc`par ${u.unite}`}` : ""}</Text>
                      </Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{montant(u.prevu)}</Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{montant(u.reel)}</Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }} c={(u.ecart_pourcent ?? 0) > 0 ? "red.7" : "teal.7"}>
                        {u.ecart_pourcent === null ? "—" : `${u.ecart_pourcent > 0 ? "+" : ""}${u.ecart_pourcent.toLocaleString(locale())} %`}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </div>
      </SimpleGrid>
    </Stack>
  );
}

/**
 * Bénéficiaires directs, indirects et ménages, couverture de la cible, maintien, abandon et paquet complet,
 * satisfaction, comparaison des territoires, zones ciblées sans bénéficiaire, bénéficiaires hors zone,
 * coordonnées non valides, surfaces et longueurs des couches, plaintes pour 1 000 bénéficiaires.
 */
function TerritoiresBloc({ t }: { t: TerritoiresTableauDeBord }) {
  const n = (x: number | null) => (x === null ? "—" : x.toLocaleString(locale()));
  const ecart = (e: TerritoiresTableauDeBord["ecart_couverture"], unite: string) => e && voc`de ${n(e.valeur_basse)}${unite} (${e.plus_bas}) à ${n(e.valeur_haute)}${unite} (${e.plus_haut})`;
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatCard label={voc("Bénéficiaires directs")} value={n(t.directs)} icon={<Users size={20} />} color="teal" />
        <StatCard label={voc("Bénéficiaires indirects")} value={n(t.indirects)} icon={<Users size={20} />} color="cyan" />
        <StatCard label={voc("Couverture de la cible")} value={t.cible === null ? "—" : `${pct(t.couverture_cible)} · ${n(t.cible)}`}
          icon={<Gauge size={20} />} color="indigo" />
        <StatCard label={voc("Maintien")} value={t.taux_maintien === null ? "—" : `${pct(t.taux_maintien)} · ${voc`${n(t.abandons)} abandon(s)`}`}
          icon={<Gauge size={20} />} color={(t.taux_abandon ?? 0) >= 20 ? "orange" : "teal"} />
        <StatCard label={voc("Paquet complet reçu")} value={pct(t.taux_paquet_complet)} icon={<Gauge size={20} />} color="grape" />
        <StatCard label={voc("Satisfaction")} value={t.satisfaction_moyenne === null ? "—" : `${n(t.satisfaction_moyenne)} / 5 · ${pct(t.part_satisfaits)}`}
          icon={<Users size={20} />} color="pink" />
        <StatCard label={voc("Zones ciblées sans bénéficiaire")} value={`${n(t.zones_sans_beneficiaire)} / ${n(t.zones_ciblees)}`} icon={<MapPin size={20} />}
          color={t.zones_sans_beneficiaire ? "orange" : "teal"} />
        <StatCard label={voc("Plaintes pour 1 000 bénéficiaires")} value={n(t.plaintes_pour_1000)} icon={<FileText size={20} />} color="red" />
        <StatCard label={voc("Participations aux activités")}
          value={`${n(t.participations)}${t.participations_par_beneficiaire !== null ? ` · ${voc`${n(t.participations_par_beneficiaire)} par personne`}` : ""}`}
          icon={<Users size={20} />} color="blue" />
        <StatCard label={voc("Plusieurs types d'appui")} value={`${n(t.plusieurs_appuis)} · ${pct(t.part_plusieurs_appuis)}`} icon={<Users size={20} />} color="violet" />
        <StatCard label={voc("Personnes vulnérables")} value={`${n(t.vulnerables)} · ${pct(t.part_vulnerables)}`} icon={<Users size={20} />} color="orange" />
        <StatCard label={voc("Ménages bénéficiaires")} value={t.menages ? `${n(t.menages)} · ${voc`${n(t.personnes_des_menages)} pers.`}` : "—"}
          icon={<Users size={20} />} color="lime" />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {t.source_indirects === "projets" && voc("Bénéficiaires indirects : estimations saisies dans les projets.")}
        {t.source_indirects === "menages" && voc`Bénéficiaires indirects estimés d'après ${n(t.menages)} ménage(s) renseigné(s) (${n(t.personnes_des_menages)} personnes).`}
        {t.source_indirects === null && voc("Bénéficiaires indirects : à saisir dans le projet, ou la taille du ménage dans la fiche du bénéficiaire.")}
        {" "}{t.statuts_saisis
          ? voc`${n(t.parcours)} parcours (un bénéficiaire dans un projet).`
          : voc("Maintien, abandon et paquet complet : à renseigner dans la liste des bénéficiaires de chaque activité (colonne « Statut »).")}
        {t.satisfaction_reponses > 0 && " " + voc`Satisfaction : ${n(t.satisfaction_reponses)} réponse(s), part de 4 et 5 sur 5.`}
        {t.coordonnees_renseignees > 0 && " " + voc`Positions GPS valides : ${pct(Math.round((1 - t.coordonnees_invalides / t.coordonnees_renseignees) * 1000) / 10)} (${n(t.coordonnees_renseignees - t.coordonnees_invalides)} sur ${n(t.coordonnees_renseignees)}).`}
        {" "}{voc`Plaintes récurrentes : ${pct(t.taux_plaintes_recurrentes)} des ${n(t.plaintes)} dossiers.`}
      </Text>
      {(t.ecart_couverture || t.ecart_femmes) && (
        <Text size="sm">
          <strong>{voc("Écarts entre territoires :")}</strong>
          {t.ecart_couverture && " " + voc`bénéficiaires pour 1 000 habitants ${ecart(t.ecart_couverture, "")}${t.ecart_couverture.rapport ? voc`, soit ${n(t.ecart_couverture.rapport)} fois plus` : ""} ;`}
          {t.ecart_femmes && " " + voc`part de femmes ${ecart(t.ecart_femmes, " %")}.`}
        </Text>
      )}
      {(t.hors_zone > 0 || t.coordonnees_invalides > 0 || t.zones_coordonnees_invalides > 0) && (
        <Text size="sm" c="orange.8">
          {t.hors_zone > 0 && voc`${n(t.hors_zone)} bénéficiaire(s) inscrit(s) hors des zones de leur projet (${t.hors_zone_exemples.slice(0, 5).map((h) => `${h.projet} : ${h.zone}`).join(", ")}).`}
          {t.coordonnees_invalides > 0 && " " + voc`${n(t.coordonnees_invalides)} position(s) GPS non valide(s) sur ${n(t.coordonnees_renseignees)}.`}
          {t.zones_coordonnees_invalides > 0 && " " + voc`${n(t.zones_coordonnees_invalides)} zone(s) avec un centre hors du pays.`}
        </Text>
      )}
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <div>
          <Text fw={600} mb="xs">{voc("Par territoire")}</Text>
          <Table.ScrollContainer minWidth={520} mah={380}>
            <Table striped withTableBorder stickyHeader verticalSpacing={6} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Territoire")}</Table.Th>
                  <Table.Th ta="right">{voc("Bénéficiaires")}</Table.Th>
                  <Table.Th ta="right">{voc("Femmes")}</Table.Th>
                  <Table.Th ta="right">
                    <Tooltip label={voc("Population saisie dans « Zones administratives », ou somme de celle des zones qu'il contient.")} multiline w={260}>
                      <span>{voc("Pour 1 000 hab.")}</span>
                    </Tooltip>
                  </Table.Th>
                  <Table.Th ta="right">{voc("Abandon")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {t.territoires.map((x) => (
                  <Table.Tr key={`${x.pays}-${x.zone}`}>
                    <Table.Td fw={600}>{x.zone}</Table.Td>
                    <Table.Td ta="right">{n(x.beneficiaires)}</Table.Td>
                    <Table.Td ta="right">{pct(x.part_femmes)}</Table.Td>
                    <Table.Td ta="right">{n(x.pour_1000_habitants)}</Table.Td>
                    <Table.Td ta="right">{pct(x.taux_abandon)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
        <Stack gap="md">
          <div>
            <Text fw={600} mb="xs">{voc("Zones ciblées sans bénéficiaire")}</Text>
            {t.zones_sans_beneficiaire_exemples.length === 0 ? (
              <Text size="sm" c="dimmed">{voc("Toutes les zones ciblées par les projets ont au moins un bénéficiaire inscrit.")}</Text>
            ) : (
              <Table.ScrollContainer minWidth={360} mah={220}>
                <Table striped withTableBorder stickyHeader verticalSpacing={4} fz="sm">
                  <Table.Thead>
                    <Table.Tr><Table.Th>{voc("Projet")}</Table.Th><Table.Th>{voc("Zone")}</Table.Th><Table.Th>{voc("Niveau")}</Table.Th></Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {t.zones_sans_beneficiaire_exemples.map((z) => (
                      <Table.Tr key={`${z.projet}-${z.zone}`}><Table.Td fw={600}>{z.projet}</Table.Td><Table.Td>{z.zone}</Table.Td><Table.Td>{z.niveau}</Table.Td></Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
            {t.zones_sans_beneficiaire > t.zones_sans_beneficiaire_exemples.length && (
              <Text size="xs" c="dimmed" mt={4}>{voc`… et ${n(t.zones_sans_beneficiaire - t.zones_sans_beneficiaire_exemples.length)} autre(s).`}</Text>
            )}
          </div>
          <GroupesBeneficiaires t={t} />
          {t.couches.some((c) => c.surface_ha !== null || c.longueur_km !== null) && (
            <div>
              <Text fw={600} mb="xs">{voc("Couches importées : surfaces et longueurs")}</Text>
              <Table withTableBorder verticalSpacing={4} fz="sm">
                <Table.Tbody>
                  {t.couches.filter((c) => c.surface_ha !== null || c.longueur_km !== null).map((c) => (
                    <Table.Tr key={c.nom}>
                      <Table.Td>{c.nom}</Table.Td>
                      <Table.Td ta="right">{voc`${n(c.objets)} objet(s)`}</Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>
                        {c.surface_ha !== null ? `${Math.round(c.surface_ha).toLocaleString(locale())} ha` : `${(c.longueur_km ?? 0).toLocaleString(locale(), { maximumFractionDigits: 1 })} km`}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </div>
          )}
        </Stack>
      </SimpleGrid>
    </Stack>
  );
}

/** Âge, groupes vulnérables (statuts particuliers) et couverture des groupes prioritaires ciblés. */
function GroupesBeneficiaires({ t }: { t: TerritoiresTableauDeBord }) {
  const n = (x: number) => x.toLocaleString(locale());
  if (t.directs === 0) return null;
  return (
    <div>
      <Text fw={600} mb="xs">{voc("Âge et groupes vulnérables")}</Text>
      <Table withTableBorder striped verticalSpacing={4} fz="sm">
        <Table.Tbody>
          {t.par_age.map((a) => (
            <Table.Tr key={`age-${a.tranche}`}>
              <Table.Td>{a.tranche ? traduireDonnee(a.tranche) : voc("Âge non renseigné")}</Table.Td>
              <Table.Td ta="right">{n(a.nombre)}</Table.Td>
              <Table.Td ta="right" c="dimmed">{pct(Math.round(a.nombre / t.directs * 1000) / 10)}</Table.Td>
            </Table.Tr>
          ))}
          {t.par_statut.map((x) => (
            <Table.Tr key={`statut-${x.statut}`}>
              <Table.Td>{traduireDonnee(x.statut)}</Table.Td>
              <Table.Td ta="right">{n(x.nombre)}</Table.Td>
              <Table.Td ta="right" c="dimmed">{pct(x.part)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {t.groupes_prioritaires.length > 0 && (
        <Text size="xs" c="dimmed" mt={4}>
          {voc("Couverture des groupes prioritaires ciblés :")}{" "}
          {t.groupes_prioritaires.map((g) => voc`${traduireDonnee(g.groupe)} ${n(g.atteints)} sur ${n(g.cible)} (${pct(g.couverture)})`).join(" ; ")}.
        </Text>
      )}
    </div>
  );
}

const COMPOSANTES_QUALITE = () => [
  { cle: "completude", nom: voc("Complétude"), aide: voc("Part des informations essentielles renseignées (activités, indicateurs, bénéficiaires).") },
  { cle: "ponctualite", nom: voc("Saisies dans les délais"), aide: voc("Saisies faites au plus tard 30 jours après la fin de leur période.") },
  { cle: "plausibilite", nom: voc("Valeurs plausibles"), aide: voc("Valeurs qui ne s'écartent pas fortement des autres valeurs du même indicateur ; quantités réalisées pas plus de 2 fois au-dessus du prévu.") },
  { cle: "doublons", nom: voc("Doublons traités"), aide: voc("Doublons de bénéficiaires signalés et déjà examinés (fusionnés ou écartés).") },
] as const;

/** Score de qualité des données, ses composantes et le détail de leur calcul. */
function QualiteBloc({ q }: { q: QualiteTableauDeBord }) {
  const n = (x: number) => x.toLocaleString(locale());
  const couleur = (x: number | null) => (x === null ? "gray" : x >= 80 ? "teal" : x >= 60 ? "yellow" : "red");
  const c = q.completude;
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="sm">
        <StatCard label={voc("Score de qualité")} value={q.score === null ? "—" : `${n(q.score)} / 100`} icon={<Gauge size={20} />} color={couleur(q.score)} />
        {COMPOSANTES_QUALITE().map((x) => (
          <Tooltip key={x.cle} label={x.aide} multiline w={280}>
            <div>
              <StatCard label={`${x.nom} (${q.poids[x.cle]} %)`} value={pct(q.composantes[x.cle])} icon={<Gauge size={20} />} color={couleur(q.composantes[x.cle])} />
            </div>
          </Tooltip>
        ))}
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {voc("Calcul du score : moyenne des composantes pondérée par leur poids (entre parenthèses) ; une composante sans donnée n'est pas comptée.")}
        {" "}{voc`${n(q.saisies_a_temps)} saisie(s) sur ${n(q.saisies)} faite(s) dans les ${q.delai_jours} jours ; ${n(q.atypiques)} valeur(s) atypique(s) sur ${n(q.valeurs_verifiees)} vérifiée(s) ; ${n(q.doublons_non_traites)} doublon(s) à examiner sur ${n(q.doublons_signales)}.`}
        {q.approbations_en_attente > 0 && " " + voc`${n(q.approbations_en_attente)} saisie(s) en attente d'approbation.`}
      </Text>
      <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="sm">
        <StatCard label={voc("Saisies validées")} value={pct(q.taux_validation)} icon={<Gauge size={20} />} color={couleur(q.taux_validation)} />
        <StatCard label={voc("Saisies rejetées")} value={`${n(q.saisies_rejetees)} · ${pct(q.taux_rejet)}`} icon={<Gauge size={20} />}
          color={q.saisies_rejetees ? "orange" : "teal"} />
        <StatCard label={voc("Délai fin de période → saisie")} value={jours(q.delai_saisie_jours)} icon={<Gauge size={20} />} color="blue" />
        <StatCard label={voc("Délai saisie → approbation")} value={jours(q.delai_validation_jours)} icon={<Gauge size={20} />} color="indigo" />
        <StatCard label={voc("Valeurs avec justificatif")} value={pct(q.valeurs_justifiees)} icon={<FileText size={20} />} color={couleur(q.valeurs_justifiees)} />
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <div>
          <Text fw={600} mb="xs">{voc("Complétude")}</Text>
          <Table withTableBorder striped verticalSpacing={5} fz="sm">
            <Table.Tbody>
              {([
                [voc("Activités"), c.activites, { responsable: voc("responsable"), dates: voc("dates"), budget: voc("budget"), quantite_prevue: voc("quantité prévue") }],
                [voc("Indicateurs"), c.indicateurs, { reference: voc("valeur de référence"), valeurs: voc("au moins une valeur saisie") }],
                [voc("Bénéficiaires"), c.beneficiaires, { date_naissance: voc("date de naissance"), localite: voc("localité"), contact: voc("téléphone ou pièce"), consentement: voc("consentement") }],
              ] as const).map(([nom, f, libelles]) => (
                <Table.Tr key={nom}>
                  <Table.Td fw={600} style={{ whiteSpace: "nowrap" }}>{nom} <Text span size="xs" c="dimmed">({n(f.total)})</Text></Table.Td>
                  <Table.Td ta="right" fw={600} c={`${couleur(f.completude)}.7`}>{pct(f.completude)}</Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {Object.entries(libelles).map(([cle, libelle]) => `${libelle} ${pct(f.champs[cle] ?? null)}`).join(" · ")}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>
        <div>
          <Text fw={600} mb="xs">{voc("Valeurs atypiques à vérifier")}</Text>
          {q.atypiques_exemples.length === 0 ? (
            <Text size="sm" c="dimmed">{voc("Aucune valeur atypique détectée.")}</Text>
          ) : (
            <Table.ScrollContainer minWidth={420} mah={300}>
              <Table striped withTableBorder stickyHeader verticalSpacing={5} fz="sm">
                <Table.Tbody>
                  {q.atypiques_exemples.map((x, i) => (
                    <Table.Tr key={i}>
                      <Table.Td>
                        <Text size="sm">{x.libelle}</Text>
                        <Text size="xs" c="dimmed">
                          {x.projet}{x.motif === "quantite" ? ` · ${voc`prévu : ${n(x.prevu ?? 0)}`}` : x.periode_fin ? ` · ${voc`période finie le ${new Date(x.periode_fin).toLocaleDateString(locale())}`}` : ""}
                        </Text>
                      </Table.Td>
                      <Table.Td ta="right" style={{ whiteSpace: "nowrap" }} fw={600}>{n(x.valeur)} {x.unite}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </div>
      </SimpleGrid>
    </Stack>
  );
}

/** Rapports attendus, reçus et validés ; risques et leur suivi ; recommandations ; leçons et décisions. */
function PilotageBloc({ p }: { p: PilotageTableauDeBord }) {
  const n = (x: number) => x.toLocaleString(locale());
  const { rapports: ra, risques: ri, recommandations: re, apprentissage: ap } = p;
  const dateFr = (d: string | null) => (d ? new Date(d).toLocaleDateString(locale()) : "—");
  const niveaux = { CRITIQUE: [voc("Critique"), "red"], ELEVE: [voc("Élevé"), "orange"], MOYEN: [voc("Moyen"), "yellow"], FAIBLE: [voc("Faible"), "green"] } as const;
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatCard label={voc("Rapports reçus / attendus")} value={`${n(ra.recus)} / ${n(ra.attendus_a_date)}`} icon={<FileText size={20} />}
          color={ra.en_retard ? "orange" : "teal"} />
        <StatCard label={voc("Rapports validés")} value={n(ra.valides)} icon={<FileText size={20} />} color="teal" />
        <StatCard label={voc("Risques critiques et élevés")} value={n(ri.par_niveau.CRITIQUE + ri.par_niveau.ELEVE)} icon={<Gauge size={20} />}
          color={ri.par_niveau.CRITIQUE ? "red" : "orange"} />
        <StatCard label={voc("Risques réévalués (3 mois)")} value={pct(ri.suivis)} icon={<Gauge size={20} />} color={(ri.suivis ?? 0) >= 80 ? "teal" : "orange"} />
        <StatCard label={voc("Recommandations mises en œuvre")} value={re.retenues ? `${pct(re.taux_mise_en_oeuvre)} · ${n(re.realisees)} / ${n(re.retenues)}` : "—"}
          icon={<Gauge size={20} />} color="indigo" />
        <StatCard label={voc("Recommandations en retard")} value={n(re.en_retard)} icon={<Gauge size={20} />} color={re.en_retard ? "red" : "teal"} />
        <StatCard label={voc("Leçons et bonnes pratiques")} value={n(ap.lecons + ap.bonnes_pratiques)} icon={<FileText size={20} />} color="grape" />
        <StatCard label={voc("Décisions documentées")} value={n(ap.decisions)} icon={<FileText size={20} />} color="cyan" />
        <StatCard label={voc("Rapports produits (échus)")} value={pct(ra.taux_remis)} icon={<FileText size={20} />} color="blue" />
        <StatCard label={voc("Acceptés dès la 1re remise")} value={pct(ra.acceptes_premiere_soumission)} icon={<FileText size={20} />} color="teal" />
        <StatCard label={voc("Risques graves avec mesures")} value={ri.graves ? `${pct(ri.graves_avec_mesures)} · ${n(ri.graves)}` : "—"}
          icon={<Gauge size={20} />} color={(ri.graves_avec_mesures ?? 100) >= 100 ? "teal" : "orange"} />
        <StatCard label={voc("Mesures d'atténuation réalisées")}
          value={ri.mesures ? `${pct(ri.taux_execution_mesures)} · ${n(ri.mesures_realisees)} / ${n(ri.mesures)}` : "—"}
          icon={<Gauge size={20} />} color={ri.mesures_en_retard ? "orange" : "teal"} />
        <StatCard label={voc("Documents obligatoires disponibles")}
          value={p.documents_obligatoires.total ? `${pct(p.documents_obligatoires.taux_disponibilite)} · ${n(p.documents_obligatoires.disponibles)} / ${n(p.documents_obligatoires.total)}` : "—"}
          icon={<FileText size={20} />} color={p.documents_obligatoires.manquants_echus ? "red" : "teal"} />
        <StatCard label={voc("Leçons ayant entraîné un changement")}
          value={ap.lecons + ap.bonnes_pratiques ? `${n(ap.lecons_adaptees)} · ${pct(ap.part_lecons_adaptees)}` : "—"}
          icon={<FileText size={20} />} color="grape" />
        <StatCard label={voc("Analyses partagées")} value={`${n(p.partages.liens)} · ${voc`${n(p.partages.consultations)} consultation(s)`}`}
          icon={<FileText size={20} />} color="gray" />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {ra.total === 0
          ? voc("Aucun rapport attendu n'est encore enregistré : ajoutez-les dans l'onglet « Pilotage » de chaque projet.")
          : voc`Rapports remis à temps : ${pct(ra.taux_a_temps)} ; ${n(ra.en_retard)} en retard ; ${n(ra.a_revoir)} à revoir.`}
        {ra.retard_moyen_jours !== null && " " + voc`Retard moyen de remise : ${jours(ra.retard_moyen_jours)}.`}
        {ra.delai_validation_jours !== null && " " + voc`Délai moyen de validation : ${jours(ra.delai_validation_jours)}.`}
        {" "}{voc`${n(ri.total)} risque(s) recensé(s) : ${n(ri.ouverts)} ouvert(s) dont ${n(ri.survenus)} survenu(s), ${n(ri.clos)} maîtrisé(s) ou clos ; mesures d'atténuation prévues pour ${pct(ri.avec_mesures)} ; ${n(ri.revue_en_retard)} revue(s) en retard.`}
        {ri.delai_resolution_jours !== null && " " + voc`Problèmes survenus puis résolus : ${n(ri.problemes_resolus)}, en ${jours(ri.delai_resolution_jours)} en moyenne.`}
        {re.total > 0 && " " + voc`${n(re.total)} recommandation(s) formulée(s), ${n(re.en_cours)} en cours.`}
        {re.par_origine.length > 0 && " " + voc`Mise en œuvre selon l'origine : ${re.par_origine.map((o) => `${o.libelle} ${pct(o.taux_mise_en_oeuvre)} (${n(o.realisees)}/${n(o.retenues)})`).join(", ")}.`}
        {ri.mesures_en_retard > 0 && " " + voc`${n(ri.mesures_en_retard)} mesure(s) d'atténuation en retard.`}
        {p.documents_obligatoires.manquants_echus > 0 && " " + voc`Documents obligatoires manquants après leur échéance : ${p.documents_obligatoires.manquants_exemples.slice(0, 5).map((d) => `${d.projet} : ${d.libelle}`).join(", ")}${p.documents_obligatoires.manquants_echus > 5 ? "…" : ""}.`}
      </Text>
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <div>
          <Text fw={600} mb="xs">{voc("Risques critiques et élevés")}</Text>
          {ri.graves_exemples.length === 0 ? (
            <Text size="sm" c="dimmed">{voc("Aucun risque critique ou élevé ouvert.")}</Text>
          ) : (
            <Table.ScrollContainer minWidth={540} mah={320}>
              <Table striped withTableBorder stickyHeader verticalSpacing={5} fz="sm">
                <Table.Thead>
                  <Table.Tr><Table.Th>{voc("Risque")}</Table.Th><Table.Th>{voc("Niveau")}</Table.Th><Table.Th>{voc("Dernière réévaluation")}</Table.Th></Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {ri.graves_exemples.map((r) => (
                    <Table.Tr key={`${r.projet}-${r.code}`}>
                      <Table.Td><Text size="sm">{r.libelle}</Text><Text size="xs" c="dimmed">{r.projet} · {r.code}</Text></Table.Td>
                      <Table.Td style={{ whiteSpace: "nowrap" }}>
                        <Badge variant="light" color={niveaux[r.niveau][1]} styles={{ root: { overflow: "visible" }, label: { overflow: "visible" } }}>
                          {niveaux[r.niveau][0]} · {r.criticite}
                        </Badge>
                      </Table.Td>
                      <Table.Td c={r.derniere_revue ? undefined : "red.7"}>{r.derniere_revue ? dateFr(r.derniere_revue) : voc("Jamais")}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </div>
        <Stack gap="md">
          {ra.en_retard_exemples.length > 0 && (
            <div>
              <Text fw={600} mb="xs">{voc("Rapports en retard")}</Text>
              <Table withTableBorder striped verticalSpacing={4} fz="sm">
                <Table.Tbody>
                  {ra.en_retard_exemples.map((r, i) => (
                    <Table.Tr key={i}>
                      <Table.Td><Text size="sm">{r.libelle}</Text><Text size="xs" c="dimmed">{r.projet} · {dateFr(r.echeance)}</Text></Table.Td>
                      <Table.Td ta="right" c="red.7" style={{ whiteSpace: "nowrap" }}>{voc`${n(r.jours)} j`}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </div>
          )}
          {re.en_retard_exemples.length > 0 && (
            <div>
              <Text fw={600} mb="xs">{voc("Recommandations en retard")}</Text>
              <Table withTableBorder striped verticalSpacing={4} fz="sm">
                <Table.Tbody>
                  {re.en_retard_exemples.map((r) => (
                    <Table.Tr key={`${r.projet}-${r.code}`}>
                      <Table.Td><Text size="sm">{r.libelle}</Text><Text size="xs" c="dimmed">{r.projet} · {r.code} · {dateFr(r.echeance)}</Text></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </div>
          )}
          {ra.en_retard_exemples.length === 0 && re.en_retard_exemples.length === 0 && (
            <Text size="sm" c="dimmed">{voc("Aucun rapport ni aucune recommandation en retard.")}</Text>
          )}
        </Stack>
      </SimpleGrid>
    </Stack>
  );
}

const nombreOuNul = (x: string | null) => (x === null ? null : Number(x));

const LIBELLES_TENDANCE = () => ({ progres: voc("En progrès"), recul: voc("En recul"), stable: voc("Stable") });

/**
 * Performance des indicateurs : renseignés, cible atteinte, en progrès ou en recul ; éléments de la
 * planification (produits, effets…) dont tous les indicateurs ont atteint leur cible ; documents de la chaîne
 * stratégique ; tableau référence / actuelle / cible / écart / taux / tendance, les moins avancés d'abord.
 */
function PerformanceBloc({ p, liens }: { p: PerformanceIndicateurs; liens: boolean }) {
  const n = (x: number) => x.toLocaleString(locale());
  const valeur = (x: string | null) => (x === null ? "—" : Number(x).toLocaleString(locale(), { maximumFractionDigits: 2 }));
  if (p.total === 0) return <Vide message={voc("Aucun indicateur sur ces projets.")} />;
  const tendances = LIBELLES_TENDANCE();
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="sm">
        <Tooltip label={voc("Moyenne des taux d'atteinte (plafonnés à 100 %), pondérée par le poids de chaque indicateur (vide : 1). Le poids se règle dans la fiche de l'indicateur.")}
          multiline w={300}>
          <div>
            <StatCard label={voc("Score de performance")} value={p.score === null ? "—" : `${n(p.score)} / 100`} icon={<Gauge size={20} />}
              color={p.score === null ? "gray" : p.score >= 80 ? "teal" : p.score >= 50 ? "yellow" : "red"} />
          </div>
        </Tooltip>
        <StatCard label={voc("Indicateurs renseignés")} value={`${n(p.renseignes)} / ${n(p.total)} · ${pct(p.part_renseignes)}`} icon={<Gauge size={20} />}
          color="blue" />
        <StatCard label={voc("Cible atteinte")} value={`${n(p.atteints)} / ${n(p.avec_taux)} · ${pct(p.part_atteints)}`} icon={<Gauge size={20} />} color="teal" />
        <StatCard label={voc("En progrès")} value={p.part_en_progres === null ? "—" : `${n(p.en_progres)} · ${pct(p.part_en_progres)}`} icon={<Gauge size={20} />}
          color="green" />
        <StatCard label={voc("En recul")} value={p.part_en_recul === null ? "—" : `${n(p.en_recul)} · ${pct(p.part_en_recul)}`} icon={<Gauge size={20} />}
          color={p.en_recul ? "red" : "teal"} />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {voc("Écart à la cible : ce qu'il reste à faire pour l'atteindre (négatif : cible dépassée). Tendance : entre les deux dernières valeurs saisies, pour les indicateurs mesurés à chaque saisie (taux, niveaux) ; un indicateur cumulable progresse à chaque saisie.")}
        {" "}{p.indicateurs_ponderes > 0
          ? voc`Score : ${n(p.indicateurs_ponderes)} indicateur(s) ont un poids réglé.`
          : voc("Score : tous les indicateurs ont le même poids (réglable dans la fiche de chaque indicateur).")}
        {p.documents.length > 0 && " " + voc`Documents stratégiques dont relèvent les projets : ${p.documents.map((d) => `${traduireDonnee(d.type)} ${n(d.nombre)}`).join(", ")}.`}
      </Text>
      <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="lg">
        <div>
          <Text fw={600} mb="xs">{voc("Résultats atteints par niveau")}</Text>
          {p.par_niveau.length === 0 ? (
            <Text size="sm" c="dimmed">{voc("Aucun indicateur n'est rattaché à un élément de la planification.")}</Text>
          ) : (
            <Table withTableBorder striped verticalSpacing={4} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Niveau")}</Table.Th>
                  <Table.Th ta="right">
                    <Tooltip label={voc("Éléments dont au moins un indicateur a une valeur.")} multiline w={240}><span>{voc("Mesurés")}</span></Tooltip>
                  </Table.Th>
                  <Table.Th ta="right">
                    <Tooltip label={voc("Éléments dont tous les indicateurs ont atteint leur cible.")} multiline w={240}><span>{voc("Atteints")}</span></Tooltip>
                  </Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {p.par_niveau.map((x) => (
                  <Table.Tr key={x.niveau}>
                    <Table.Td fw={600}>{traduireDonnee(x.niveau)} <Text span size="xs" c="dimmed">({n(x.elements)})</Text></Table.Td>
                    <Table.Td ta="right">{n(x.mesures)}</Table.Td>
                    <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{n(x.atteints)} · {pct(x.part)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
          {p.scores_projets.length > 1 && (
            <>
              <Text fw={600} mt="md" mb="xs">{voc("Score de performance par projet")}</Text>
              <Table.ScrollContainer minWidth={240} mah={260}>
                <Table withTableBorder striped stickyHeader verticalSpacing={4} fz="sm">
                  <Table.Tbody>
                    {p.scores_projets.map((x) => (
                      <Table.Tr key={x.projet}>
                        <Table.Td fw={600}>{x.projet} <Text span size="xs" c="dimmed">({n(x.indicateurs)})</Text></Table.Td>
                        <Table.Td ta="right" fw={600} c={x.score === null ? "dimmed" : x.score >= 80 ? "teal.7" : x.score < 50 ? "red.7" : undefined}>
                          {x.score === null ? "—" : `${n(x.score)} / 100`}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </>
          )}
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <Text fw={600} mb="xs">
            {voc("Indicateurs, les moins avancés d'abord")}
            {p.total > p.liste.length && <Text span size="xs" c="dimmed" fw={400}> {voc`(${n(p.liste.length)} sur ${n(p.total)})`}</Text>}
          </Text>
          <Table.ScrollContainer minWidth={720} mah={420}>
            <Table striped withTableBorder stickyHeader verticalSpacing={5} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{voc("Indicateur")}</Table.Th>
                  <Table.Th ta="right">{voc("Référence")}</Table.Th>
                  <Table.Th ta="right">{voc("Actuelle")}</Table.Th>
                  <Table.Th ta="right">{voc("Cible")}</Table.Th>
                  <Table.Th ta="right">{voc("Écart")}</Table.Th>
                  <Table.Th ta="right">{voc("Taux")}</Table.Th>
                  <Table.Th>{voc("Tendance")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {p.liste.map((x) => (
                  <Table.Tr key={x.id}>
                    <Table.Td>
                      {liens ? <Text component={Link} to={`/indicateurs/${x.id}`} size="sm" c="blue.7">{x.libelle}</Text> : <Text size="sm">{x.libelle}</Text>}
                      <Text size="xs" c="dimmed">{x.projet}{x.unite ? ` · ${x.unite}` : ""}{x.calcule ? ` · ${voc("calculé")}` : ""}</Text>
                    </Table.Td>
                    <Table.Td ta="right">{valeur(x.reference)}</Table.Td>
                    <Table.Td ta="right">{valeur(x.actuelle)}</Table.Td>
                    <Table.Td ta="right">{valeur(x.cible)}</Table.Td>
                    <Table.Td ta="right" c={x.ecart !== null && Number(x.ecart) <= 0 ? "teal.7" : undefined}>{valeur(x.ecart)}</Table.Td>
                    <Table.Td ta="right" fw={600} style={{ whiteSpace: "nowrap" }}
                      c={x.taux === null ? "dimmed" : x.taux >= 100 ? "teal.7" : x.taux < 50 ? "red.7" : undefined}>{pct(x.taux)}</Table.Td>
                    <Table.Td>
                      {x.tendance && (
                        <Badge variant="light" size="sm" color={x.tendance === "progres" ? "green" : x.tendance === "recul" ? "red" : "gray"}
                          styles={{ root: { overflow: "visible" }, label: { overflow: "visible" } }}>{tendances[x.tendance]}</Badge>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
      </SimpleGrid>
    </Stack>
  );
}

/** Plaintes et retours des projets : volumes, traitement, délais, satisfaction et mesures correctives (totaux seulement). */
function PlaintesBloc({ p }: { p: PlaintesTableauDeBord }) {
  const n = (x: number) => x.toLocaleString(locale());
  if (p.total === 0) return <Vide message={voc("Aucune plainte ni aucun retour enregistré sur ces projets.")} />;
  const repartition = (titre: string, lignes: { libelle: string; nombre: number }[]) => (
    <div>
      <Text fw={600} mb="xs">{titre}</Text>
      <Table withTableBorder striped verticalSpacing={4} fz="sm">
        <Table.Tbody>
          {lignes.map((l) => (
            <Table.Tr key={l.libelle}><Table.Td>{traduireDonnee(l.libelle)}</Table.Td><Table.Td ta="right" fw={600}>{n(l.nombre)}</Table.Td></Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </div>
  );
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatCard label={voc("Retours reçus")} value={`${n(p.total)} · ${voc`${n(p.ouverts)} ouvert(s)`}`} icon={<FileText size={20} />} color="blue" />
        <StatCard label={voc("En retard")} value={n(p.en_retard)} icon={<Gauge size={20} />} color={p.en_retard ? "red" : "teal"} />
        <StatCard label={voc("Traités dans les délais")} value={pct(p.dans_delais)} icon={<Gauge size={20} />} color="teal" />
        <StatCard label={voc("Délai de traitement")} value={p.delai_moyen === null ? "—" : voc`${jours(p.delai_moyen)} (médiane ${jours(p.delai_median)})`}
          icon={<Gauge size={20} />} color="indigo" />
        <StatCard label={voc("Accusés de réception")} value={p.taux_accuse === null ? "—"
          : `${pct(p.taux_accuse)}${p.delai_accuse_moyen !== null ? ` · ${voc`${jours(p.delai_accuse_moyen)} en moyenne`}` : ""}`}
          icon={<FileText size={20} />} color="cyan" />
        <StatCard label={voc("Réponse apportée")} value={`${pct(p.taux_resolution)} · ${voc`${n(p.clotures)} clôturé(s)`}`} icon={<Gauge size={20} />} color="teal" />
        <StatCard label={voc("Réouvertures et recours")} value={pct(p.taux_reouverture)} icon={<Gauge size={20} />} color="orange" />
        <StatCard label={voc("Satisfaction après traitement")} value={p.satisfaction === null ? "—" : pct(p.satisfaction)} icon={<Users size={20} />} color="pink" />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        {voc`Mesures correctives : ${pct(p.avec_mesure_corrective)} des dossiers clôturés en ont entraîné une ; ${n(p.actions_correctives)} action(s), dont ${pct(p.mise_en_oeuvre_mesures)} réalisées.`}
        {" "}{p.satisfaction === null && p.satisfaction_reponses > 0 && voc`Satisfaction : affichée à partir de 10 réponses (${n(p.satisfaction_reponses)} pour l'instant).`}
        {" "}{voc("Les répartitions ne comptent pas les dossiers confidentiels. Une baisse des plaintes n'est pas forcément une amélioration : elle peut aussi traduire un accès difficile au mécanisme.")}
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="lg">
        {repartition(voc("Par type de retour"), p.par_type)}
        {repartition(voc("Par canal"), p.par_canal)}
        {repartition(voc("Par catégorie"), p.par_categorie)}
        {repartition(voc("Par région"), p.par_territoire)}
      </SimpleGrid>
    </Stack>
  );
}

/** Par région : projets présents, activités réalisées, dépenses et réalisation des indicateurs ; écart entre régions. */
function PerformanceTerritoiresBloc({ t }: { t: DashboardConsolide["performance_territoires"] }) {
  const n = (x: number) => x.toLocaleString(locale());
  if (t.length === 0) return <Vide message={voc("Aucune zone d'intervention renseignée sur les fiches projet.")} />;
  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        {voc("Un projet présent dans plusieurs régions compte dans chacune (comme sur la carte) : les chiffres d'une région sont ceux des projets qui y interviennent.")}
        {t.filter((p) => p.ecart).map((p) => " " + voc`Écart de réalisation des indicateurs (${p.pays}) : de ${pct(p.ecart!.valeur_basse)} (${p.ecart!.plus_bas}) à ${pct(p.ecart!.valeur_haute)} (${p.ecart!.plus_haut}), soit ${n(p.ecart!.difference)} points.`).join("")}
      </Text>
      {t.map((p) => (
        <Table.ScrollContainer key={p.pays} minWidth={640} mah={420}>
          <Table striped withTableBorder stickyHeader verticalSpacing={5} fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{traduireDonnee(p.niveau)}{t.length > 1 ? ` (${p.pays})` : ""}</Table.Th>
                <Table.Th ta="right">{voc("Projets")}</Table.Th>
                <Table.Th ta="right">{voc("Activités")}</Table.Th>
                <Table.Th ta="right">{voc("Réalisées")}</Table.Th>
                <Table.Th ta="right">{voc("Dépenses (FCFA)")}</Table.Th>
                <Table.Th ta="right">{voc("Réalisation des indicateurs")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {p.zones.map((z) => (
                <Table.Tr key={z.zone}>
                  <Table.Td fw={600}>{z.zone}</Table.Td>
                  <Table.Td ta="right">{n(z.projets)}</Table.Td>
                  <Table.Td ta="right">{n(z.activites)}</Table.Td>
                  <Table.Td ta="right">{pct(z.part_realisees)}</Table.Td>
                  <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>{n(z.depenses)}</Table.Td>
                  <Table.Td ta="right" fw={600}>{pct(z.taux_indicateurs)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      ))}
    </Stack>
  );
}
