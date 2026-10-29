import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { FolderKanban, Wallet, Users, Gauge, MapPin, SlidersHorizontal } from "lucide-react";
import { Badge, Button, Grid, Group, Paper, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import {
  useConfigurationTableauDeBord,
  useDashboardConsolide,
  useEnregistrerConfigurationTableauDeBord,
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
import { typesPossibles, type TypeGraphique } from "../utils/typesGraphiques";
import { PROJET_STATUT_LABEL } from "../utils/statusTones";
import type { DashboardConsolide, FiltresDashboard, LigneRepartitionProjets, StatutProjet } from "../types";
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

function CarteGraphique({ titre, actions, children }: { titre: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <Paper withBorder p="md" radius="md" h="100%">
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb="sm">
        <Title order={4} c="dark.8" style={{ borderLeft: "4px solid var(--mantine-color-teal-6)", paddingLeft: 10 }}>
          {titre}
        </Title>
        {actions}
      </Group>
      {children}
    </Paper>
  );
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
  if (toutes.length === 0) return <Vide message={vide} />;
  const totalMontant = toutes.reduce((s, l) => s + Number(l.montant), 0);
  const nbMasques = toutVoir ? 0 : Math.max(0, toutes.length - LIMITE_LIGNES);
  const lignes = toutVoir ? toutes : toutes.slice(0, LIMITE_LIGNES);
  return (
    <Stack gap="sm">
      {type !== "tableau" && (
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
      )}
      <Table striped withTableBorder verticalSpacing={6} fz="sm">
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
              <Table.Td>
                {l.libelle}
                <Group gap={4} mt={2}>
                  {l.projets.map((code) => <Badge key={code} size="xs" variant="light">{code}</Badge>)}
                </Group>
              </Table.Td>
              <Table.Td ta="right">{l.nombre}</Table.Td>
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
      </Table>
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

  function sauvegarder(payload: { blocs_masques?: string[]; types_graphiques?: Record<string, TypeGraphique> }) {
    enregistrer.mutate(payload, {
      onError: (error) =>
        notifications.show({ message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")), color: "red" }),
    });
  }
  // Lien de partage : filtres enregistrés avec le lien, ni personnalisation ni liens vers les projets.
  const partage = usePartage();
  const parametres = partage ? (partage.filtres as FiltresDashboard) : versParametres(filtres);
  const { data, isLoading, isFetching } = useDashboardConsolide(parametres);

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
        {!partage && <BoutonPartage type="TABLEAU_DE_BORD" filtres={parametres as Record<string, unknown>} />}
        {peutPersonnaliser && !partage && (
          <Button variant="light" leftSection={<SlidersHorizontal size={16} />} onClick={() => setPersonnalisation(true)}>
            {voc("Personnaliser")}{blocs.length > 0 && voc` (${visibles.length}/${blocs.length} blocs)`}
          </Button>
        )}
      </Group>

      {!partage && <FiltresTableauDeBord valeur={filtres} onChange={setFiltres} nombreProjets={data?.nombre_projets} />}

      {isLoading || !data ? (
        <Text c="dimmed">{voc("Chargement…")}</Text>
      ) : (
        <Grid gutter="md" style={{ opacity: isFetching ? 0.6 : 1, transition: "opacity 150ms" }}>
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
            <Grid.Col key={b.cle} span={{ base: 12, md: b.largeur === 12 ? 12 : 6, xl: b.largeur }}>
              {b.avecCarte === false ? (
                b.rendu(typeDe(b))
              ) : (
                <CarteGraphique
                  titre={b.titre}
                  actions={
                    b.graphique && peutPersonnaliser && (
                      <ChoixTypeGraphique
                        valeur={typeDe(b)}
                        types={b.graphique.types}
                        onChange={(t) => sauvegarder({ types_graphiques: { ...types, [b.cle]: t } })}
                      />
                    )
                  }
                >
                  {b.rendu(typeDe(b))}
                </CarteGraphique>
              )}
            </Grid.Col>
          ))}
        </Grid>
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

  return [
    {
      cle: "chiffres-cles", titre: voc("Chiffres clés"), groupe: "Vue d'ensemble", largeur: 12, avecCarte: false,
      rendu: () => (
        <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="md">
          <StatCard label={voc("Projets")} value={data.nombre_projets} icon={<FolderKanban size={20} />} color="teal" />
          <StatCard label={voc("Budget total")} value={fcfa(data.budget_total)} icon={<Wallet size={20} />} color="indigo" />
          <StatCard label={voc("Bénéficiaires")} value={data.nombre_beneficiaires} icon={<Users size={20} />} color="grape" />
          <StatCard label={voc("Indicateurs suivis")} value={totalIndicateurs} icon={<Gauge size={20} />} color="orange" />
        </SimpleGrid>
      ),
    },
    {
      cle: "couverture", titre: voc("Couverture géographique (nombre de zones)"), groupe: voc("Géographie"), largeur: 12,
      rendu: () =>
        data.zones_couvertes.length === 0 ? (
          <Vide message={voc("Aucun pays renseigné sur les projets.")} />
        ) : (
          <SimpleGrid cols={{ base: 2, xs: 4 }} spacing="md">
            {data.zones_couvertes.map((z) => (
              <StatCard key={z.niveau} label={traduireDonnee(z.niveau)} value={z.count} icon={<MapPin size={20} />} color="cyan" />
            ))}
          </SimpleGrid>
        ),
    },
    {
      cle: "pays-zones", titre: voc("Projets par pays et zone d'intervention"), groupe: voc("Géographie"), largeur: 12,
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <SimpleGrid cols={{ base: 1, md: 2, xl: 1 + Math.max(1, data.projets_par_zone.length) }} spacing="lg">
          <div>
            <Text fw={600} mb="xs">{voc("Par pays")}</Text>
            <RepartitionProjets type={type} lignes={data.projets_par_pays} colonne={voc("Pays")} vide={voc("Aucun pays renseigné.")}
              couleur="#0c8599" noteMontant={voc("Montant = budget total des projets du pays.")} />
          </div>
          {data.projets_par_zone.length === 0 ? (
            <div>
              <Text fw={600} mb="xs">{voc("Par zone administrative")}</Text>
              <Vide message={voc("Aucune zone d'intervention renseignée sur les fiches projet (champ « Zones »).")} />
            </div>
          ) : (
            data.projets_par_zone.map((n) => (
              <div key={n.niveau}>
                <Text fw={600} mb="xs">{voc("Par")} {langue() === "de" ? traduireDonnee(n.niveau) : traduireDonnee(n.niveau).toLowerCase()}</Text>
                <RepartitionProjets type={type} lignes={n.zones} colonne={traduireDonnee(n.niveau)} vide="—" couleur="#1098ad" />
              </div>
            ))
          )}
        </SimpleGrid>
      ),
    },
    {
      cle: "budget-detail", titre: voc("Budget total et détail"), groupe: voc("Budget et financements"), largeur: 12,
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
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_bailleur} colonne={voc("Bailleur")} vide={voc("Aucun bailleur renseigné.")}
          couleur="#1c7ed6"
          noteMontant={voc("Montant = financements saisis ; à défaut, budget du projet hors fonds propres, attribué au bailleur principal.")} />
      ),
    },
    {
      cle: "consortium", titre: voc("Projets par partenaire de consortium"), groupe: voc("Budget et financements"), largeur: 4,
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_consortium} colonne={voc("Partenaire")} vide={voc("Aucun projet en consortium.")}
          couleur="#ae3ec9" noteMontant={voc("Montant = budget total des projets auxquels le partenaire participe.")} />
      ),
    },
    {
      cle: "mise-en-oeuvre", titre: voc("Projets par partenaire de mise en œuvre"), groupe: voc("Budget et financements"), largeur: 4,
      graphique: graphique(1, "barres"),
      rendu: (type) => (
        <RepartitionProjets type={type} lignes={data.projets_par_mise_en_oeuvre} colonne={voc("Partenaire")}
          vide={voc("Aucun partenaire de mise en œuvre renseigné.")} couleur="#f59f00"
          noteMontant={voc("Montant = budget total des projets mis en œuvre par le partenaire.")} />
      ),
    },
    {
      cle: "cibles", titre: voc("Cibles des projets (par sexe et par statut)"), groupe: voc("Bénéficiaires"), largeur: 12,
      graphique: graphique(4, "colonnes"),
      rendu: (type) => (
        <Grid gutter="lg">
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
      cle: "projets-statut", titre: voc("Projets par statut"), groupe: voc("Projets"), largeur: 4,
      graphique: graphique(1, "camembert"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={statuts.map((s) => PROJET_STATUT_LABEL[s])}
          series={[{ cle: "n", nom: voc("Projets"), couleur: "#12b886", valeurs: statuts.map((s) => data.projets_par_statut[s] ?? 0) }]}
          couleursCategories={statuts.map((s) => COULEURS_PROJET_STATUT[s])}
          unite={data.nombre_projets > 1 ? voc("projets") : voc("projet")}
        />
      ),
    },
    {
      cle: "budget-projet", titre: voc("Budget par projet (FCFA)"), groupe: voc("Budget et financements"), largeur: 4,
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
        />
      ),
    },
    {
      cle: "beneficiaires-sexe", titre: voc("Bénéficiaires inscrits par sexe"), groupe: voc("Bénéficiaires"), largeur: 4,
      graphique: graphique(1, "camembert"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={[voc("Femmes"), voc("Hommes")]}
          series={[{ cle: "n", nom: voc("Bénéficiaires"), couleur: COULEUR_FEMMES, valeurs: [data.beneficiaires_par_sexe.F ?? 0, data.beneficiaires_par_sexe.M ?? 0] }]}
          couleursCategories={[COULEUR_FEMMES, COULEUR_HOMMES]}
          unite={voc("bénéficiaires")}
        />
      ),
    },
    {
      cle: "activites-projet", titre: voc("Activités par statut, par projet"), groupe: voc("Projets"), largeur: 6,
      graphique: graphique(3, "colonnes-empilees"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.activites_par_projet.map((p) => p.code)}
          series={[
            { cle: "nr", nom: voc("Non réalisées"), couleur: "#adb5bd", valeurs: data.activites_par_projet.map((p) => p.NON_REALISEE ?? 0) },
            { cle: "ec", nom: voc("En cours"), couleur: "#fab219", valeurs: data.activites_par_projet.map((p) => p.EN_COURS ?? 0) },
            { cle: "re", nom: voc("Réalisées"), couleur: "#0ca30c", valeurs: data.activites_par_projet.map((p) => p.REALISEE ?? 0) },
          ]}
        />
      ),
    },
    {
      cle: "beneficiaires-projet", titre: voc("Bénéficiaires par projet (femmes / hommes)"), groupe: voc("Bénéficiaires"), largeur: 6,
      graphique: graphique(2, "colonnes"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.beneficiaires_par_projet_sexe.map((p) => p.code)}
          series={[
            { cle: "F", nom: voc("Femmes"), couleur: COULEUR_FEMMES, valeurs: data.beneficiaires_par_projet_sexe.map((p) => p.F ?? 0) },
            { cle: "M", nom: voc("Hommes"), couleur: COULEUR_HOMMES, valeurs: data.beneficiaires_par_projet_sexe.map((p) => p.M ?? 0) },
          ]}
        />
      ),
    },
    {
      cle: "indicateurs-statut", titre: voc("Indicateurs par statut"), groupe: voc("Projets"), largeur: 6,
      graphique: graphique(1, "colonnes"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.indicateurs_par_statut.map((p) => p.libelle)}
          series={[{ cle: "n", nom: voc("Indicateurs"), couleur: "#868e96", valeurs: data.indicateurs_par_statut.map((p) => p.count) }]}
          couleursCategories={data.indicateurs_par_statut.map((p) => p.couleur)}
          unite={voc("indicateurs")}
        />
      ),
    },
    {
      cle: "execution-projet", titre: voc("Exécution par projet (%)"), groupe: voc("Projets"), largeur: 6,
      graphique: graphique(2, "colonnes"),
      rendu: (type) => (
        <GraphiqueAdaptable
          type={type}
          categories={data.execution_par_projet.map((p) => p.code)}
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
      graphique: graphique(2, "courbes"),
      rendu: (type) =>
        data.depenses_par_mois.length === 0 ? (
          <Vide message={voc("Aucune dépense saisie dans le suivi.")} />
        ) : (
          <GraphiqueAdaptable
            type={type}
            categories={data.depenses_par_mois.map((l) => String(l.mois))}
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
      graphique: graphique(2, "colonnes"),
      rendu: (type) =>
        data.inscriptions_par_mois.length === 0 ? (
          <Vide message={voc("Aucune inscription.")} />
        ) : (
          <>
            <GraphiqueAdaptable
              type={type}
              categories={data.inscriptions_par_mois.map((l) => String(l.mois))}
              series={serieParProjet(data.inscriptions_par_mois).filter((s) => s.valeurs.some((v) => v))}
              formatCategorie={formatMois}
            />
            <Text size="xs" c="dimmed" mt={4}>{voc("Nombre de bénéficiaires ajoutés à chaque projet pendant le mois.")}</Text>
          </>
        ),
    },
    {
      cle: "liste-projets", titre: voc("Liste des projets"), groupe: voc("Projets"), largeur: 12,
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
