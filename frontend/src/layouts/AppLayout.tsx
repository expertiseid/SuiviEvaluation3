import { useState } from "react";
import { NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Building2,
  ClipboardCheck,
  Copy,
  FileSpreadsheet,
  FileText,
  FolderKanban,
  Gauge,
  Layers,
  LayoutDashboard,
  LogOut,
  Map as MapIcon,
  MapPin,
  MessagesSquare,
  PenLine,
  RotateCcw,
  Languages,
  Sliders,
  Target,
  UserCog,
  Users,
  type LucideIcon,
  ScrollText,
} from "lucide-react";
import {
  ActionIcon,
  AppShell,
  Checkbox,
  Loader,
  Table,
  Tabs,
  Popover,
  SimpleGrid,
  Avatar,
  Burger,
  Divider,
  Group,
  Modal,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Tooltip,
  Button,
  Alert,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useDisclosure } from "@mantine/hooks";
import { useAuth } from "../auth/useAuth";
import { useConfigurationMenu, useEcheances, useUpdateConfigurationMenu } from "../api/dashboard";
import { NotificationBell } from "../components/notifications/NotificationBell";
import { ChoixLangue } from "../components/common/ChoixLangue";
import { ICONES_MENU } from "../utils/iconesMenu";
import { TERMES, definirVocabulaire, voc, type Vocabulaire } from "../utils/vocabulaire";
import { langue } from "../utils/i18n";
import { EcheancesBanner } from "../components/notifications/EcheancesBanner";
import { useAccesModules } from "../utils/modules";
import { libelleRole } from "../utils/roles";
import { useTypesDocuments } from "../api/strategy";
import { routeMaillon } from "../utils/chaineDocuments";

type NavItem = { to: string; label: string; icon: LucideIcon };

const ITEM_ACCUEIL: NavItem = { to: "/", label: voc("Tableau de bord"), icon: LayoutDashboard };

const ITEMS_PRINCIPAUX: NavItem[] = [
  { to: "/planification", label: voc("Planification complète"), icon: FileSpreadsheet },
  { to: "/strategie", label: voc("Cadre stratégique"), icon: Target },
  { to: "/projets", label: voc("Projets"), icon: FolderKanban },
  { to: "/indicateurs", label: voc("Indicateurs"), icon: Gauge },
  { to: "/suivi", label: voc("Suivi"), icon: Activity },
  { to: "/approbations", label: voc("Approbations"), icon: ClipboardCheck },
  { to: "/beneficiaires", label: voc("Bénéficiaires"), icon: Users },
  { to: "/carte", label: voc("Carte"), icon: MapIcon },
  { to: "/doublons", label: voc("Doublons d'enregistrement"), icon: Copy },
  { to: "/zones-administratives", label: voc("Zones administratives"), icon: MapPin },
  { to: "/documents", label: voc("Documents"), icon: FileText },
  { to: "/plaintes", label: voc("Plaintes et retours"), icon: MessagesSquare },
];

const ITEMS_ADMIN: NavItem[] = [
  { to: "/utilisateurs", label: voc("Utilisateurs"), icon: UserCog },
  { to: "/organisation", label: voc("Organisation"), icon: Building2 },
  { to: "/parametres-alerte", label: voc("Paramètres d'alerte"), icon: Sliders },
  { to: "/langues", label: voc("Langues"), icon: Languages },
  { to: "/journal-audit", label: voc("Journal d'audit"), icon: ScrollText },
];

const TOUS_LES_ITEMS = [ITEM_ACCUEIL, ...ITEMS_PRINCIPAUX, ...ITEMS_ADMIN];

/** Choix d'une icône parmi celles proposées (ICONES_MENU). */
function ChoixIcone({ icone: Icone, onChoisir }: { icone: LucideIcon; onChoisir: (nom: string) => void }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <Popover opened={ouvert} onChange={setOuvert} position="bottom-start" withArrow shadow="md">
      <Popover.Target>
        <Tooltip label={voc("Changer l'icône")}>
          <ActionIcon variant="default" size="lg" mb={1} onClick={() => setOuvert((o) => !o)}>
            <Icone size={17} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>
      <Popover.Dropdown>
        <SimpleGrid cols={8} spacing={4}>
          {Object.entries(ICONES_MENU).map(([nom, Icon]) => (
            <ActionIcon
              key={nom}
              variant={Icon === Icone ? "filled" : "subtle"}
              color="teal"
              aria-label={nom}
              onClick={() => {
                onChoisir(nom);
                setOuvert(false);
              }}
            >
              <Icon size={17} />
            </ActionIcon>
          ))}
        </SimpleGrid>
      </Popover.Dropdown>
    </Popover>
  );
}

/**
 * Noms et icônes des rubriques du menu, choisis par l'Administrateur —
 * communs à tous les utilisateurs. ↺ rend à la rubrique son nom et son icône
 * par défaut.
 */
function PersonnalisationMenuModal({
  libelles,
  icones,
  vocabulaire,
  onClose,
}: {
  libelles: Record<string, string>;
  icones: Record<string, string>;
  vocabulaire: Vocabulaire;
  onClose: () => void;
}) {
  const [valeurs, setValeurs] = useState<Record<string, string>>(libelles);
  const [iconesChoisies, setIconesChoisies] = useState<Record<string, string>>(icones);
  const [termes, setTermes] = useState<Vocabulaire>(vocabulaire);
  const enregistrer = useUpdateConfigurationMenu();
  const modifierTerme = (cle: string, champ: "singulier" | "pluriel" | "feminin", valeur: string | boolean, femininDefaut: boolean) =>
    setTermes((t) => ({
      ...t,
      [cle]: { ...(t[cle] ?? { singulier: "", pluriel: "", feminin: femininDefaut }), [champ]: valeur },
    }));
  return (
    <Tabs defaultValue="menu">
      <Tabs.List mb="sm">
        <Tabs.Tab value="menu">{voc("Menu")}</Tabs.Tab>
        <Tabs.Tab value="vocabulaire">{voc("Vocabulaire")}</Tabs.Tab>
      </Tabs.List>
      <Tabs.Panel value="vocabulaire">
        <Stack gap="xs">
          <Text size="sm" c="dimmed">
            {voc("Remplace les termes de la plateforme par ceux de ton organisation : ils changent partout (écrans, formulaires, rattachements, messages, exports). Indique le singulier, le pluriel et le genre (pour accorder « un/une », « le/la », « nouveau/nouvelle »…). Laisse vide pour garder le terme par défaut.")}
          </Text>
          <Table withRowBorders={false} verticalSpacing={4}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{voc("Terme par défaut")}</Table.Th>
                <Table.Th>{voc("Singulier")}</Table.Th>
                <Table.Th>{voc("Pluriel")}</Table.Th>
                <Table.Th>{voc("Féminin")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {TERMES.map(([cle, singulier, pluriel, femininDefaut]) => (
                <Table.Tr key={cle}>
                  <Table.Td>
                    <Text size="sm">{singulier[0].toUpperCase() + singulier.slice(1)}</Text>
                  </Table.Td>
                  <Table.Td>
                    <TextInput
                      size="xs"
                      placeholder={singulier}
                      maxLength={60}
                      value={termes[cle]?.singulier ?? ""}
                      onChange={(e) => modifierTerme(cle, "singulier", e.currentTarget.value, femininDefaut)}
                    />
                  </Table.Td>
                  <Table.Td>
                    <TextInput
                      size="xs"
                      placeholder={pluriel}
                      maxLength={60}
                      value={termes[cle]?.pluriel ?? ""}
                      onChange={(e) => modifierTerme(cle, "pluriel", e.currentTarget.value, femininDefaut)}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Checkbox
                      checked={termes[cle]?.feminin ?? femininDefaut}
                      onChange={(e) => modifierTerme(cle, "feminin", e.currentTarget.checked, femininDefaut)}
                    />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Text size="xs" c="dimmed">{voc("Clique sur « Enregistrer » (onglet Menu ou ci-dessous) pour appliquer.")}</Text>
          <Group justify="flex-end">
            <Button
              loading={enregistrer.isPending}
              onClick={async () => {
                try {
                  await enregistrer.mutateAsync({ libelles: valeurs, icones: iconesChoisies, vocabulaire: termes });
                  notifications.show({ message: voc("Vocabulaire mis à jour"), color: "green" });
                  onClose();
                  window.location.reload();
                } catch {
                  notifications.show({ message: voc("Erreur lors de l'enregistrement du vocabulaire"), color: "red" });
                }
              }}
            >
              {voc("Enregistrer")}
            </Button>
          </Group>
        </Stack>
      </Tabs.Panel>
      <Tabs.Panel value="menu">
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {voc("Donne à chaque rubrique le nom et l'icône utilisés dans ton organisation (clique sur l'icône pour la changer). Les changements s'appliquent à tous les utilisateurs ; ↺ revient au nom et à l'icône par défaut.")}
          </Text>
          {TOUS_LES_ITEMS.map((item) => (
            <Group key={item.to} gap="xs" wrap="nowrap" align="flex-end">
              <ChoixIcone
                icone={ICONES_MENU[iconesChoisies[item.to]] ?? item.icon}
                onChoisir={(nom) => setIconesChoisies((v) => ({ ...v, [item.to]: nom }))}
              />
              <TextInput
                style={{ flex: 1 }}
                label={voc`Par défaut : ${item.label}`}
                placeholder={item.label}
                value={valeurs[item.to] ?? ""}
                maxLength={60}
                onChange={(e) => {
                  const valeur = e.currentTarget.value;
                  setValeurs((v) => ({ ...v, [item.to]: valeur }));
                }}
              />
              <Tooltip label={voc("Revenir au nom et à l'icône par défaut")}>
                <ActionIcon
                  variant="subtle"
                  mb={4}
                  disabled={!valeurs[item.to] && !iconesChoisies[item.to]}
                  onClick={() => {
                    setValeurs((v) => ({ ...v, [item.to]: "" }));
                    setIconesChoisies((v) => ({ ...v, [item.to]: "" }));
                  }}
                >
                  <RotateCcw size={15} />
                </ActionIcon>
              </Tooltip>
            </Group>
          ))}
          <Group justify="flex-end">
            <Button
              loading={enregistrer.isPending}
              onClick={async () => {
                try {
                  await enregistrer.mutateAsync({ libelles: valeurs, icones: iconesChoisies, vocabulaire: termes });
                  notifications.show({ message: voc("Menu mis à jour"), color: "green" });
                  onClose();
                  // Le vocabulaire s'applique à tous les textes : on recharge pour l'appliquer partout.
                  if (JSON.stringify(termes) !== JSON.stringify(vocabulaire)) window.location.reload();
                } catch {
                  notifications.show({ message: voc("Erreur lors de l'enregistrement du menu"), color: "red" });
                }
              }}
            >
              {voc("Enregistrer")}
            </Button>
          </Group>
        </Stack>
      </Tabs.Panel>
    </Tabs>
  );
}

function renderNavLink(item: NavItem, pathname: string) {
  const active =
    item.to === "/"
      ? pathname === "/"
      : item.to === "/strategie"
        ? // Les maillons suivants de la chaîne ont leur propre rubrique (/strategie/type/…).
          pathname.startsWith(item.to) && !pathname.startsWith("/strategie/type/")
        : pathname.startsWith(item.to);
  return (
    <NavLink
      key={item.to}
      component={RouterNavLink}
      to={item.to}
      // Le lien de React Router ne se marque pas actif tout seul : seul `active` (ci-dessus) compte.
      end
      label={item.label}
      leftSection={<item.icon size={17} strokeWidth={2} />}
      active={active}
      variant="filled"
      color="teal"
      mb={2}
    />
  );
}

function initiales(nom: string) {
  return nom
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // Modules cachés à cet utilisateur (rôle ou compte, voir utils/modules.ts).
  const { estMasque } = useAccesModules();
  const moduleMasque = ITEMS_PRINCIPAUX.some((item) => estMasque(item.to) && pathname.startsWith(item.to));
  const { data: echeances } = useEcheances();
  const { data: configurationMenu, isLoading: chargementMenu } = useConfigurationMenu();
  // Le vocabulaire doit être connu avant d'afficher les pages (leurs textes l'utilisent).
  definirVocabulaire(configurationMenu?.vocabulaire);
  const [personnalisationOuverte, setPersonnalisationOuverte] = useState(false);
  const libelles = configurationMenu?.libelles ?? {};
  const icones = configurationMenu?.icones ?? {};
  const avecLibelle = (item: NavItem): NavItem => ({
    ...item,
    // Les noms personnalisés par l'organisation sont en français : dans une autre langue, on garde la traduction.
    label: (langue() === "fr" && libelles[item.to]) || voc(item.label),
    icon: ICONES_MENU[icones[item.to]] ?? item.icon,
  });

  // Chaîne des documents stratégiques : chaque maillon après le premier est une rubrique à part,
  // placée juste sous « Cadre stratégique » (mêmes droits que celle-ci).
  const { data: maillons } = useTypesDocuments();
  const itemsMaillons: NavItem[] = (maillons ?? []).slice(1).map((m) => ({
    to: routeMaillon(m.id),
    label: m.nom_pluriel,
    icon: ICONES_MENU[m.icone] ?? Layers,
  }));
  const itemsPrincipaux = ITEMS_PRINCIPAUX.flatMap((item) => (item.to === "/strategie" ? [item, ...itemsMaillons] : [item]));

  const surTableauDeBord = pathname === "/";
  const afficherBandeau = surTableauDeBord && !!echeances && echeances.length > 0;

  return (
    <AppShell
      header={{ height: afficherBandeau ? 88 : 56 }}
      navbar={{ width: 230, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding={{ base: "sm", sm: "lg" }}
    >
      <AppShell.Header withBorder={false} bg="teal.9" c="white">
        <Group h={56} px={{ base: "xs", sm: "md" }} justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" color="white" />
            <Text fw={700} size="sm" truncate>
              <Text span inherit visibleFrom="xs">{voc("Plateforme de")} </Text>{voc("Suivi-Évaluation")}
            </Text>
          </Group>
          {/* Sur téléphone : cloche, initiales et icône de déconnexion seulement. */}
          <Group gap="sm" wrap="nowrap">
            <ChoixLangue connecte />
            <NotificationBell />
            {user && (
              <Group gap={8} wrap="nowrap">
                <Avatar size={26} radius="xl" color="teal.2" variant="filled">
                  {initiales(user.first_name || user.username)}
                </Avatar>
                <Text size="xs" c="teal.1" visibleFrom="md">
                  {user.first_name || user.username} · {user.role_libelle ? libelleRole(user.role_libelle) : user.role}
                </Text>
              </Group>
            )}
            <Button
              variant="subtle"
              color="gray.0"
              size="xs"
              visibleFrom="sm"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              {voc("Déconnexion")}
            </Button>
            <ActionIcon
              variant="subtle"
              color="gray.0"
              hiddenFrom="sm"
              aria-label={voc("Déconnexion")}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut size={18} />
            </ActionIcon>
          </Group>
        </Group>
        {afficherBandeau && <EcheancesBanner />}
      </AppShell.Header>

      <AppShell.Navbar p="xs" bg="gray.0">
        <ScrollArea>
          {renderNavLink(avecLibelle(ITEM_ACCUEIL), pathname)}
          <Divider my={4} />
          {itemsPrincipaux
            .filter((item) => !estMasque(item.to.startsWith("/strategie") ? "/strategie" : item.to))
            .map((item) => renderNavLink(item.to.startsWith("/strategie/type/") ? item : avecLibelle(item), pathname))}
          {user?.role === "ADMIN" && (
            <>
              {ITEMS_ADMIN.map((item) => renderNavLink(avecLibelle(item), pathname))}
              <Divider my={4} />
              <NavLink
                label={voc("Personnaliser le menu")}
                leftSection={<PenLine size={17} strokeWidth={2} />}
                onClick={() => setPersonnalisationOuverte(true)}
                c="dimmed"
              />
            </>
          )}
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0">
        {chargementMenu ? (
          <Loader size="sm" />
        ) : moduleMasque ? (
          <Alert color="gray" title={voc("Module non accessible")}>
            {voc("Ce module n'est pas accessible avec votre compte. Adressez-vous à l'administrateur si vous en avez besoin.")}
          </Alert>
        ) : (
          <Outlet />
        )}
      </AppShell.Main>

      <Modal
        opened={personnalisationOuverte}
        onClose={() => setPersonnalisationOuverte(false)}
        title={voc("Personnaliser le menu")}
        size="lg"
      >
        {personnalisationOuverte && (
          <PersonnalisationMenuModal
            libelles={libelles}
            icones={icones}
            vocabulaire={configurationMenu?.vocabulaire ?? {}}
            onClose={() => setPersonnalisationOuverte(false)}
          />
        )}
      </Modal>
    </AppShell>
  );
}
