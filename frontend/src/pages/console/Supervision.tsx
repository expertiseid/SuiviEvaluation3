import type { ReactNode } from "react";
import {
  Alert, Badge, Box, Button, Card, Group, Loader, Progress, SimpleGrid, Stack, Table, Text, ThemeIcon, Title,
} from "@mantine/core";
import { Building2, CircleAlert, CreditCard, Database, HardDrive, Server, ShieldCheck, UserPlus } from "lucide-react";
import { type VueEnsemble, useVueEnsemble } from "../../api/console";
import { JaugeStockage } from "../../components/common/EspaceStockage";
import { StatCard } from "../../components/common/StatCard";
import { locale } from "../../utils/i18n";
import { GO, volumeLisible } from "../../utils/stockage";
import { voc } from "../../utils/vocabulaire";

type Disque = NonNullable<VueEnsemble["disque"]>;

const somme = (n: number, devise: string) => `${n.toLocaleString("fr-FR")} ${devise === "XOF" ? "FCFA" : devise === "USD" ? "$" : devise}`;
const pourcent = (partie: number, total: number) => (total ? Math.round((partie / total) * 100) : 0);
const couleur = (part: number) => (part >= 90 ? "red" : part >= 75 ? "orange" : "teal");
const duree = (secondes: number) => {
  const jours = Math.floor(secondes / 86400);
  const heures = Math.floor((secondes % 86400) / 3600);
  return jours ? voc`${jours} j ${heures} h` : voc`${heures} h`;
};

/** Titre d'une rubrique de la console, avec une phrase qui dit à quoi elle sert. */
export function EnTeteRubrique({ titre, description, action }: { titre: string; description: string; action?: ReactNode }) {
  return (
    <Group justify="space-between" align="flex-end" mb="md">
      <Box>
        <Title order={2}>{titre}</Title>
        <Text c="dimmed" size="sm" mt={4}>{description}</Text>
      </Box>
      {action}
    </Group>
  );
}

/** Une ligne « libellé … valeur ». */
function Ligne({ libelle, valeur }: { libelle: string; valeur: ReactNode }) {
  return (
    <Group justify="space-between" gap="xs" wrap="nowrap">
      <Text size="sm" c="dimmed">{libelle}</Text>
      <Text size="sm" fw={600} ta="right">{valeur}</Text>
    </Group>
  );
}

function Jauge({ utilise, total, taille = "md" }: { utilise: number; total: number; taille?: "md" | "xl" }) {
  const part = pourcent(utilise, total);
  return <Progress value={Math.max(part, 1)} color={couleur(part)} size={taille} radius="xl" />;
}

function Carte({ icone, couleurIcone = "teal", titre, sousTitre, etat, children }: {
  icone: ReactNode; couleurIcone?: string; titre: string; sousTitre?: string; etat?: ReactNode; children: ReactNode;
}) {
  return (
    <Card withBorder radius="md" padding="lg" h="100%">
      <Group gap="sm" align="flex-start" mb="md" wrap="nowrap">
        <ThemeIcon variant="light" color={couleurIcone} size={38} radius="md">{icone}</ThemeIcon>
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Text fw={700}>{titre}</Text>
          {sousTitre && <Text size="xs" c="dimmed">{sousTitre}</Text>}
          {etat && <Box mt={6}>{etat}</Box>}
        </Box>
      </Group>
      <Stack gap="xs">{children}</Stack>
    </Card>
  );
}

const Etat = ({ ok, texte }: { ok: boolean; texte?: string }) => (
  <Badge variant="light" color={ok ? "teal" : "red"} leftSection={<Box w={7} h={7} bg={ok ? "teal.6" : "red.6"} style={{ borderRadius: "50%" }} />}>
    {texte ?? (ok ? voc("En marche") : voc("Injoignable"))}
  </Badge>
);

/** Disque commun des fichiers des clients (Volume Hetzner) : agrandi tout seul jusqu'au plafond. */
function CarteDisque({ disque }: { disque: Disque | null }) {
  if (!disque) return <Alert color="gray">{voc("Disque des données : mesure impossible.")}</Alert>;
  const part = pourcent(disque.utilise, disque.total);
  const totalGo = Math.round(disque.total / GO);
  return (
    <Carte icone={<HardDrive size={20} />} titre={voc("Disque des données")} sousTitre={voc("Fichiers des clients (Volume Hetzner)")}
      etat={<Badge variant="light" color={couleur(part)}>{voc`${part} % utilisé`}</Badge>}>
      <Jauge utilise={disque.utilise} total={disque.total} taille="xl" />
      <Ligne libelle={voc("Taille")} valeur={volumeLisible(disque.total)} />
      <Ligne libelle={voc("Utilisé")} valeur={volumeLisible(disque.utilise)} />
      <Ligne libelle={voc("Libre")} valeur={volumeLisible(disque.libre)} />
      {disque.plafond_go && (
        <>
          <Ligne libelle={voc("Plafond de l'agrandissement automatique")} valeur={voc`${disque.plafond_go} Go`} />
          <Text size="xs" c="dimmed" mt={4}>
            {voc`Agrandi tout seul dès ${disque.seuil} % d'utilisation, sans coupure, jusqu'à ${disque.plafond_go} Go. Vous êtes prévenu par courriel s'il approche du plafond.`}
          </Text>
          {totalGo >= 0.9 * disque.plafond_go && (
            <Alert color="orange" variant="light" icon={<CircleAlert size={16} />}>{voc("Le disque approche du plafond : pensez à le relever.")}</Alert>
          )}
        </>
      )}
    </Carte>
  );
}

function CartePlateforme({ serveur }: { serveur: VueEnsemble["serveurs"]["plateforme"] }) {
  const { memoire, disque } = serveur;
  return (
    <Carte icone={<Server size={20} />} titre={voc("Serveur de la plateforme")} sousTitre={voc("Fait tourner l'application et le site")} etat={<Etat ok />}>
      {memoire.total != null && memoire.libre != null && (
        <>
          <Ligne libelle={voc("Mémoire utilisée")} valeur={voc`${volumeLisible(memoire.total - memoire.libre)} sur ${volumeLisible(memoire.total)}`} />
          <Jauge utilise={memoire.total - memoire.libre} total={memoire.total} />
        </>
      )}
      {disque && (
        <>
          <Ligne libelle={voc("Disque du serveur")} valeur={voc`${volumeLisible(disque.utilise)} sur ${volumeLisible(disque.total)}`} />
          <Jauge utilise={disque.utilise} total={disque.total} />
        </>
      )}
      {serveur.processeurs != null && serveur.charge != null && (
        <Ligne libelle={voc("Charge des processeurs")} valeur={voc`${pourcent(serveur.charge, serveur.processeurs)} % (${serveur.processeurs} cœurs)`} />
      )}
      {serveur.allume_depuis != null && <Ligne libelle={voc("Allumé depuis")} valeur={duree(serveur.allume_depuis)} />}
    </Carte>
  );
}

function CarteDonnees({ serveur }: { serveur: VueEnsemble["serveurs"]["donnees"] }) {
  return (
    <Carte icone={<Database size={20} />} couleurIcone="blue" titre={voc("Serveur des données")} sousTitre={voc("Bases de données et fichiers des clients")}
      etat={<Etat ok={serveur.joignable} />}>
      {serveur.joignable ? (
        <>
          <Ligne libelle={voc("Lien privé chiffré")} valeur={voc`répond en ${String(serveur.reponse_ms).replace(".", ",")} ms`} />
          <Ligne libelle={voc("Bases de données")} valeur={voc`${serveur.bases ?? 0} bases, ${volumeLisible(serveur.taille_bases ?? 0)}`} />
          <Text size="xs" c="dimmed" mt={4}>{voc("Sauvegarde de toutes les bases et de tous les fichiers chaque nuit à 2 h, 7 jours gardés.")}</Text>
        </>
      ) : (
        <Alert color="red" variant="light">{voc("La plateforme n'arrive pas à joindre la base de données : les clients ne peuvent plus travailler.")}</Alert>
      )}
    </Carte>
  );
}

/** Espace vendu aux clients (somme de leurs espaces) comparé au disque réel. */
function CarteEspaceVendu({ vue }: { vue: VueEnsemble }) {
  const { vendu_go, utilise } = vue.stockage;
  const disqueGo = vue.disque ? vue.disque.total / GO : 0;
  return (
    <Carte icone={<ShieldCheck size={20} />} couleurIcone="grape" titre={voc("Espace vendu aux clients")} sousTitre={voc("Somme des espaces des organisations clientes")}>
      <Ligne libelle={voc("Espace vendu")} valeur={voc`${vendu_go} Go`} />
      <Ligne libelle={voc("Réellement occupé")} valeur={volumeLisible(utilise)} />
      {vendu_go > 0 && <Jauge utilise={utilise} total={vendu_go * GO} />}
      <Text size="xs" c="dimmed" mt={4}>
        {vendu_go > disqueGo
          ? voc("Plus d'espace vendu que la taille du disque : c'est normal, les clients ne remplissent pas tout ; le disque grandit avec ce qu'ils occupent vraiment.")
          : voc("Le disque est plus grand que tout l'espace vendu.")}
      </Text>
    </Carte>
  );
}

function TableauEspaces({ espaces }: { espaces: VueEnsemble["stockage"]["espaces"] }) {
  return (
    <Card withBorder radius="md" padding="lg">
      <Title order={4} mb="sm">{voc("Espace de chaque organisation")}</Title>
      <Table.ScrollContainer minWidth={560}>
        <Table verticalSpacing="sm" highlightOnHover>
          <Table.Thead>
            <Table.Tr><Table.Th>{voc("Organisation")}</Table.Th><Table.Th w={320}>{voc("Stockage")}</Table.Th></Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {espaces.map((e) => (
              <Table.Tr key={e.id}>
                <Table.Td>
                  <Group gap={6}>
                    <Text size="sm" fw={600}>{e.nom}</Text>
                    {e.mode_demo && <Badge size="xs" variant="light" color="orange">{voc("Démonstration")}</Badge>}
                    {e.statut === "SUSPENDUE" && <Badge size="xs" variant="light" color="red">{voc("Suspendue")}</Badge>}
                  </Group>
                </Table.Td>
                <Table.Td><JaugeStockage espace={e} /></Table.Td>
              </Table.Tr>
            ))}
            {espaces.length === 0 && (
              <Table.Tr><Table.Td colSpan={2}><Text size="sm" c="dimmed">{voc("Aucune organisation pour l'instant.")}</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Card>
  );
}

function TableauPaiements({ paiements, limite }: { paiements: VueEnsemble["paiements"]; limite?: number }) {
  const lignes = limite ? paiements.slice(0, limite) : paiements;
  return (
    <Table.ScrollContainer minWidth={720}>
      <Table verticalSpacing="sm" highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Date")}</Table.Th><Table.Th>{voc("Organisation")}</Table.Th><Table.Th>{voc("Achat")}</Table.Th>
            <Table.Th>{voc("Montant")}</Table.Th><Table.Th>{voc("État")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lignes.map((p, i) => (
            <Table.Tr key={i}>
              <Table.Td><Text size="sm">{new Date(p.date).toLocaleDateString(locale())}</Text></Table.Td>
              <Table.Td><Text size="sm" fw={600}>{p.organisation || "—"}</Text></Table.Td>
              <Table.Td>
                <Text size="sm">{p.nature === "STOCKAGE" ? voc`Stockage + ${p.tranches * 10} Go` : voc("Abonnement")}</Text>
                <Text size="xs" c="dimmed">{p.mois % 12 === 0 ? voc`${p.mois / 12} an(s)` : voc`${p.mois} mois`}</Text>
              </Table.Td>
              <Table.Td><Text size="sm" fw={600}>{somme(p.montant, p.devise)}</Text></Table.Td>
              <Table.Td>
                <Badge variant="light" tt="none" color={p.statut === "PAYE" ? "teal" : p.statut === "ECHOUE" ? "gray" : "orange"}>{p.statut_libelle}</Badge>
              </Table.Td>
            </Table.Tr>
          ))}
          {lignes.length === 0 && (
            <Table.Tr><Table.Td colSpan={5}><Text size="sm" c="dimmed">{voc("Aucun paiement pour l'instant.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

function useVue() {
  const { data: vue, isLoading, isError } = useVueEnsemble();
  const attente = isLoading ? <Loader /> : isError || !vue ? <Alert color="red">{voc("Les informations n'ont pas pu être chargées.")}</Alert> : null;
  return { vue, attente };
}

/** Accueil de la console : chiffres clés, disque, serveurs, derniers paiements. */
export function VueEnsembleConsole({ aller }: { aller: (rubrique: string) => void }) {
  const { vue, attente } = useVue();
  if (!vue) return attente;
  const recus = vue.paiements_30_jours.map((p) => somme(p.total, p.devise)).join(" + ") || "0";
  const partDisque = vue.disque ? pourcent(vue.disque.utilise, vue.disque.total) : null;
  const toutVaBien = vue.serveurs.donnees.joignable && (partDisque ?? 0) < 90;
  return (
    <Stack gap="lg">
      <EnTeteRubrique titre={voc("Vue d'ensemble")} description={voc("L'essentiel de la plateforme en un coup d'œil : clients, paiements, stockage et serveurs.")} />
      <Alert variant="light" color={toutVaBien ? "teal" : "red"} icon={toutVaBien ? <ShieldCheck size={18} /> : <CircleAlert size={18} />}>
        {toutVaBien ? voc("Tout fonctionne normalement.") : voc("Un point demande votre attention : voir « Stockage et serveurs ».")}
      </Alert>
      <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
        <StatCard label={voc("Organisations clientes")} value={String(vue.organisations.actives)} icon={<Building2 size={18} />} />
        <StatCard label={voc("Demandes à traiter")} value={String(vue.demandes_a_traiter)} icon={<UserPlus size={18} />} color={vue.demandes_a_traiter ? "orange" : "gray"} />
        <StatCard label={voc("Reçu ces 30 derniers jours")} value={recus} icon={<CreditCard size={18} />} color="blue" />
        <StatCard label={voc("Disque des données")} value={partDisque == null ? "—" : voc`${partDisque} % utilisé`} icon={<HardDrive size={18} />} color={couleur(partDisque ?? 0)} />
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, md: 3 }}>
        <CarteDisque disque={vue.disque} />
        <CartePlateforme serveur={vue.serveurs.plateforme} />
        <CarteDonnees serveur={vue.serveurs.donnees} />
      </SimpleGrid>
      <Card withBorder radius="md" padding="lg">
        <Group justify="space-between" mb="sm">
          <Title order={4}>{voc("Derniers paiements")}</Title>
          <Button variant="subtle" size="xs" onClick={() => aller("paiements")}>{voc("Tout voir")}</Button>
        </Group>
        <TableauPaiements paiements={vue.paiements} limite={5} />
      </Card>
    </Stack>
  );
}

/** Stockage et serveurs : disque commun, espace vendu, serveurs, espace de chaque organisation. */
export function StockageServeurs() {
  const { vue, attente } = useVue();
  if (!vue) return attente;
  return (
    <Stack gap="lg">
      <EnTeteRubrique titre={voc("Stockage et serveurs")}
        description={voc("Le disque des fichiers des clients, l'espace vendu, l'état des deux serveurs et l'espace de chaque organisation. Mis à jour toutes les minutes.")} />
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <CarteDisque disque={vue.disque} />
        <CarteEspaceVendu vue={vue} />
        <CartePlateforme serveur={vue.serveurs.plateforme} />
        <CarteDonnees serveur={vue.serveurs.donnees} />
      </SimpleGrid>
      <TableauEspaces espaces={vue.stockage.espaces} />
    </Stack>
  );
}

export function PaiementsConsole() {
  const { vue, attente } = useVue();
  if (!vue) return attente;
  return (
    <Stack gap="lg">
      <EnTeteRubrique titre={voc("Paiements")} description={voc("Abonnements et stockage payés en ligne (CinetPay) : les 30 derniers.")} />
      <Card withBorder radius="md" padding="lg"><TableauPaiements paiements={vue.paiements} /></Card>
    </Stack>
  );
}
