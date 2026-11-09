import { type ReactNode, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ActionIcon, Alert, Anchor, AppShell, Badge, Box, Burger, Button, Card, Checkbox, Container, Group, Loader, Modal, NavLink, NumberInput, Popover,
  ScrollArea, Stack, Table, Text, TextInput, Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  Building2, CirclePause, CirclePlay, CreditCard, Handshake, HardDrive, LayoutDashboard, LogOut, Newspaper, Pencil, Rocket, UserPlus,
} from "lucide-react";
import {
  type OrganisationPlateforme, useActiverDemande, useDemandesConsole, useOrganisationsConsole, useStatutOrganisation, useStockageOrganisation, useVueEnsemble,
} from "../../api/console";
import { type DemandeInscription, useIdentiteOrganisation } from "../../api/identite";
import { useAuth } from "../../auth/useAuth";
import { JaugeStockage } from "../../components/common/EspaceStockage";
import { LogoPlateforme, PiedDePage } from "../../components/common/Logos";
import { messageErreurApi } from "../../utils/erreurs";
import { locale } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";
import { erreursParChamp } from "../plaintes/saisieRetour";
import { ActualitesSite, PartenairesSite } from "./SiteVitrine";
import { EnTeteRubrique, PaiementsConsole, StockageServeurs, VueEnsembleConsole } from "./Supervision";

const COULEUR_DEMANDE: Record<string, string> = {
  ABONNEMENT_REQUIS: "orange", OFFRE_CHOISIE: "blue", EN_ACTIVATION: "grape", ACTIVEE: "teal", REFUSEE: "gray",
};
const date = (d: string | null) => (d ? new Date(d).toLocaleDateString(locale()) : "—");

/** Création de l'espace d'une organisation inscrite : identifiant interne (nom de sa base), référentiel des zones. */
function ActiverModal({ demande, onClose }: { demande: DemandeInscription; onClose: () => void }) {
  const activer = useActiverDemande();
  const [sousDomaine, setSousDomaine] = useState(demande.sous_domaine);
  const [zones, setZones] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const valider = async () => {
    setErreur(null);
    try {
      await activer.mutateAsync({ id: demande.id, sous_domaine: sousDomaine, zones });
      notifications.show({ color: "teal", message: voc("Création de l'espace lancée : elle prend jusqu'à une minute.") });
      onClose();
    } catch (error) {
      setErreur(erreursParChamp(error).sous_domaine ?? messageErreurApi(error, voc("L'activation n'a pas abouti.")));
    }
  };
  return (
    <Modal opened onClose={onClose} title={voc`Activer l'espace de ${demande.organisation}`} size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          {voc("La plateforme crée la base de données de l'organisation, ses tables et son compte administrateur (adresse courriel et mot de passe choisis à l'inscription), puis envoie le courriel « Votre espace est prêt ».")}
        </Text>
        <TextInput label={voc("Identifiant interne")} value={sousDomaine} onChange={(e) => setSousDomaine(e.currentTarget.value.toLowerCase())}
          description={voc("Sert à nommer la base de l'organisation ; les utilisateurs ne le voient pas.")} error={erreur} dir="ltr" />
        <Checkbox checked={zones} onChange={(e) => setZones(e.currentTarget.checked)}
          label={voc("Installer le référentiel des zones du Burkina Faso (régions et provinces)")} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{voc("Annuler")}</Button>
          <Button leftSection={<Rocket size={16} />} onClick={valider} loading={activer.isPending}>{voc("Créer et ouvrir l'espace")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Demandes() {
  const { data: demandes = [], isLoading } = useDemandesConsole();
  const [aActiver, setAActiver] = useState<DemandeInscription | null>(null);
  if (isLoading) return <Loader size="sm" />;
  return (
    <>
      <Table.ScrollContainer minWidth={980}>
        <Table striped highlightOnHover verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{voc("Reçue le")}</Table.Th>
              <Table.Th>{voc("Organisation")}</Table.Th>
              <Table.Th>{voc("Contact")}</Table.Th>
              <Table.Th>{voc("Identifiant interne")}</Table.Th>
              <Table.Th>{voc("Offre")}</Table.Th>
              <Table.Th>{voc("État")}</Table.Th>
              <Table.Th w={150} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {demandes.map((d) => (
              <Table.Tr key={d.id} style={{ verticalAlign: "top" }}>
                <Table.Td><Text size="sm">{date(d.cree_le)}</Text></Table.Td>
                <Table.Td>
                  <Text size="sm" fw={600}>{d.organisation}</Text>
                  <Text size="xs" c="dimmed">{[d.type_organisation, d.pays, d.taille].filter(Boolean).join(" · ")}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{d.contact_nom}</Text>
                  <Text size="xs"><Anchor href={`mailto:${d.courriel}`} size="xs">{d.courriel}</Anchor> · {d.telephone}</Text>
                </Table.Td>
                <Table.Td><Text size="sm" ff="monospace">{d.sous_domaine || "—"}</Text></Table.Td>
                <Table.Td>{d.offre_libelle ? <Badge variant="light">{d.offre_libelle}</Badge> : <Text size="sm" c="dimmed">—</Text>}</Table.Td>
                <Table.Td>
                  <Badge variant="light" color={COULEUR_DEMANDE[d.statut]} tt="none" leftSection={d.statut === "EN_ACTIVATION" ? <Loader size={10} color="grape" /> : undefined}>
                    {d.statut_libelle}
                  </Badge>
                  {d.erreur_activation && (
                    <Tooltip label={d.erreur_activation} multiline w={320}><Text size="xs" c="red" mt={4}>{voc("Échec de la dernière activation")}</Text></Tooltip>
                  )}
                </Table.Td>
                <Table.Td>
                  {(d.statut === "ABONNEMENT_REQUIS" || d.statut === "OFFRE_CHOISIE") && (
                    <Button size="xs" leftSection={<Rocket size={14} />} onClick={() => setAActiver(d)}>{voc("Activer")}</Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
            {demandes.length === 0 && (
              <Table.Tr><Table.Td colSpan={7}><Text size="sm" c="dimmed">{voc("Aucune demande pour l'instant.")}</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {aActiver && <ActiverModal demande={aActiver} onClose={() => setAActiver(null)} />}
    </>
  );
}

/** Agrandir l'espace de stockage d'une organisation (demande du client) ou revenir à celui de son offre. */
function ModifierStockage({ organisation }: { organisation: OrganisationPlateforme }) {
  const [ouvert, setOuvert] = useState(false);
  const [go, setGo] = useState<number | string>("");
  const changer = useStockageOrganisation();
  const enregistrer = async (valeur: number | null) => {
    try {
      await changer.mutateAsync({ id: organisation.id, stockage_go: valeur });
      setOuvert(false);
      notifications.show({ color: "teal", message: voc("Espace de stockage enregistré") });
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  return (
    <Popover opened={ouvert} onChange={setOuvert} width={260} position="bottom-end" withArrow>
      <Popover.Target>
        <Tooltip label={voc("Modifier l'espace de stockage")}>
          <ActionIcon variant="subtle" size="sm" aria-label={voc("Modifier l'espace de stockage")}
            onClick={() => { setGo(organisation.stockage_go ?? organisation.stockage.limite_go ?? ""); setOuvert((o) => !o); }}>
            <Pencil size={14} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="xs">
          <NumberInput label={voc("Espace de stockage (Go)")} min={1} max={100000} allowDecimal={false} value={go} onChange={setGo} />
          <Button size="xs" loading={changer.isPending} disabled={!go} onClick={() => enregistrer(Number(go))}>{voc("Enregistrer")}</Button>
          {organisation.stockage_go != null && (
            <Button size="xs" variant="subtle" onClick={() => enregistrer(null)}>{voc("Revenir à l'espace de l'offre")}</Button>
          )}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

function Organisations() {
  const { data: organisations = [], isLoading } = useOrganisationsConsole();
  const changer = useStatutOrganisation();
  const basculer = async (id: number, statut: "ACTIVE" | "SUSPENDUE") => {
    try {
      await changer.mutateAsync({ id, statut });
      notifications.show({ color: statut === "ACTIVE" ? "teal" : "orange", message: statut === "ACTIVE" ? voc("Espace réactivé") : voc("Espace suspendu") });
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("Erreur lors de l'enregistrement")) });
    }
  };
  if (isLoading) return <Loader size="sm" />;
  return (
    <Table.ScrollContainer minWidth={1040}>
      <Table striped highlightOnHover verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{voc("Organisation")}</Table.Th>
            <Table.Th>{voc("Comptes")}</Table.Th>
            <Table.Th>{voc("Offre")}</Table.Th>
            <Table.Th w={190}>{voc("Stockage")}</Table.Th>
            <Table.Th>{voc("Ouvert le")}</Table.Th>
            <Table.Th miw={120}>{voc("État")}</Table.Th>
            <Table.Th w={150} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {organisations.map((o) => (
            <Table.Tr key={o.id}>
              <Table.Td>
                <Text size="sm" fw={600}>{o.nom}</Text>
                {o.mode_demo && <Badge size="xs" variant="light" color="orange">{voc("Démonstration")}</Badge>}
              </Table.Td>
              <Table.Td><Text size="sm">{o.comptes}</Text></Table.Td>
              <Table.Td><Text size="sm">{o.offre === "STOCKAGE_PLUS" ? voc("Standard + stockage") : o.offre === "PARTENARIAT" ? voc("Partenariat") : o.offre === "STANDARD" ? voc("Standard")
                : o.offre === "STANDARD_25" ? voc`Standard ${25} Go` : o.offre === "STANDARD_50" ? voc`Standard ${50} Go` : o.offre || "—"}</Text></Table.Td>
              <Table.Td>
                <Group gap={4} wrap="nowrap" align="flex-start">
                  <Box style={{ flex: 1 }}><JaugeStockage espace={o.stockage} /></Box>
                  <ModifierStockage organisation={o} />
                </Group>
              </Table.Td>
              <Table.Td><Text size="sm">{date(o.active_le)}</Text></Table.Td>
              <Table.Td><Badge variant="light" tt="none" color={o.statut === "ACTIVE" ? "teal" : o.statut === "SUSPENDUE" ? "red" : "gray"}>{o.statut_libelle}</Badge></Table.Td>
              <Table.Td>
                {o.statut === "ACTIVE" && (
                  <Button size="xs" variant="light" color="orange" leftSection={<CirclePause size={14} />} onClick={() => basculer(o.id, "SUSPENDUE")}>{voc("Suspendre")}</Button>
                )}
                {o.statut === "SUSPENDUE" && (
                  <Button size="xs" variant="light" leftSection={<CirclePlay size={14} />} onClick={() => basculer(o.id, "ACTIVE")}>{voc("Réactiver")}</Button>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
          {organisations.length === 0 && (
            <Table.Tr><Table.Td colSpan={7}><Text size="sm" c="dimmed">{voc("Aucune organisation pour l'instant.")}</Text></Table.Td></Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

const RUBRIQUES = [
  { groupe: "", items: [{ cle: "vue", label: "Vue d'ensemble", icone: LayoutDashboard }] },
  { groupe: "Clients", items: [
    { cle: "demandes", label: "Demandes d'inscription", icone: UserPlus },
    { cle: "organisations", label: "Organisations", icone: Building2 },
    { cle: "paiements", label: "Paiements", icone: CreditCard },
  ] },
  { groupe: "Infrastructure", items: [{ cle: "stockage", label: "Stockage et serveurs", icone: HardDrive }] },
  { groupe: "Site vitrine", items: [
    { cle: "actualites", label: "Actualités", icone: Newspaper },
    { cle: "partenaires", label: "Partenaires", icone: Handshake },
  ] },
];

/** Rubrique de la console : titre, description et contenu dans une carte. */
function Rubrique({ titre, description, children }: { titre: string; description: string; children: ReactNode }) {
  return (
    <>
      <EnTeteRubrique titre={titre} description={description} />
      <Card withBorder radius="md" padding="lg">{children}</Card>
    </>
  );
}

function Contenu({ rubrique, aller }: { rubrique: string; aller: (cle: string) => void }) {
  switch (rubrique) {
    case "demandes":
      return <Rubrique titre={voc("Demandes d'inscription")} description={voc("Organisations qui ont créé leur profil sur le site : activez leur espace une fois l'abonnement réglé.")}><Demandes /></Rubrique>;
    case "organisations":
      return <Rubrique titre={voc("Organisations")} description={voc("Espaces ouverts : offre, comptes, stockage ; suspendre ou réactiver un client.")}><Organisations /></Rubrique>;
    case "paiements":
      return <PaiementsConsole />;
    case "stockage":
      return <StockageServeurs />;
    case "actualites":
      return <Rubrique titre={voc("Actualités du site")} description={voc("Articles affichés sur le site vitrine.")}><ActualitesSite /></Rubrique>;
    case "partenaires":
      return <Rubrique titre={voc("Partenaires du site")} description={voc("Logos des partenaires affichés sur le site vitrine.")}><PartenairesSite /></Rubrique>;
    default:
      return <VueEnsembleConsole aller={aller} />;
  }
}

/** Console Expertise-ID (plateforme multi-organisations), ouverte depuis sa page de connexion /expertise-id. */
export function ConsolePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: plateforme } = useIdentiteOrganisation();
  const [parametres, setParametres] = useSearchParams();
  const [ouvert, { toggle, close }] = useDisclosure();
  const rubrique = parametres.get("rubrique") || "vue";
  const operateur = !!plateforme?.multi_organisations && !!user?.est_operateur;
  const { data: vue } = useVueEnsemble(operateur);
  const aller = (cle: string) => { setParametres(cle === "vue" ? {} : { rubrique: cle }); close(); window.scrollTo(0, 0); };

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 250, breakpoint: "sm", collapsed: { mobile: !ouvert } }} padding={0}>
      <AppShell.Header withBorder={false} bg="teal.9" c="white">
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={ouvert} onClick={toggle} hiddenFrom="sm" size="sm" color="white" />
            <Box visibleFrom="sm"><LogoPlateforme taille={30} clair /></Box>
            <Box hiddenFrom="sm"><LogoPlateforme taille={30} clair avecNom={false} /></Box>
            <Badge color="white" c="teal.9" variant="filled" visibleFrom="xs">{voc("Console Expertise-ID")}</Badge>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <Text size="sm" visibleFrom="sm">{user?.email || user?.username}</Text>
            <Button size="xs" variant="subtle" color="gray.0" leftSection={<LogOut size={14} />} onClick={() => { logout(); navigate("/expertise-id"); }}>{voc("Déconnexion")}</Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs" bg="gray.0">
        <AppShell.Section grow component={ScrollArea}>
          {operateur && RUBRIQUES.map(({ groupe, items }) => (
            <Box key={groupe} mb="xs">
              {groupe && <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="sm" pt="sm" pb={4}>{voc(groupe)}</Text>}
              {items.map(({ cle, label, icone: Icone }) => (
                <NavLink key={cle} label={voc(label)} leftSection={<Icone size={17} strokeWidth={2} />} active={rubrique === cle}
                  variant="filled" color="teal" mb={2} onClick={() => aller(cle)}
                  rightSection={cle === "demandes" && vue?.demandes_a_traiter ? <Badge size="sm" color="orange" circle>{vue.demandes_a_traiter}</Badge> : undefined} />
              ))}
            </Box>
          ))}
        </AppShell.Section>
        <AppShell.Section><PiedDePage /></AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0">
        <Container size="xl" py="lg">
          {!plateforme ? <Loader /> : !plateforme.multi_organisations ? (
            <Alert color="gray">{voc("La console Expertise-ID n'est disponible que sur la plateforme multi-organisations.")}</Alert>
          ) : !user?.est_operateur ? (
            <Alert color="orange">{voc("Réservé aux opérateurs Expertise-ID.")}</Alert>
          ) : (
            <Contenu rubrique={rubrique} aller={aller} />
          )}
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
