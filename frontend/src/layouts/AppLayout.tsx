import { useState } from "react";
import { NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  Gauge,
  Activity,
  Users,
  Copy,
  UserCog,
  Target,
  MapPin,
  FileSpreadsheet,
  FileText,
  Sliders,
  PenLine,
  RotateCcw,
  type LucideIcon,
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
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useDisclosure } from "@mantine/hooks";
import { useAuth } from "../auth/useAuth";
import { useConfigurationMenu, useEcheances, useUpdateConfigurationMenu } from "../api/dashboard";
import { NotificationBell } from "../components/notifications/NotificationBell";
import { ICONES_MENU } from "../utils/iconesMenu";
import { TERMES, definirVocabulaire, voc, type Vocabulaire } from "../utils/vocabulaire";
import { EcheancesBanner } from "../components/notifications/EcheancesBanner";

type NavItem = { to: string; label: string; icon: LucideIcon };

const ITEM_ACCUEIL: NavItem = { to: "/", label: "Tableau de bord", icon: LayoutDashboard };

const ITEMS_PRINCIPAUX: NavItem[] = [
  { to: "/planification", label: "Planification complète", icon: FileSpreadsheet },
  { to: "/strategie", label: "Cadre stratégique", icon: Target },
  { to: "/projets", label: "Projets", icon: FolderKanban },
  { to: "/indicateurs", label: "Indicateurs", icon: Gauge },
  { to: "/suivi", label: "Suivi", icon: Activity },
  { to: "/beneficiaires", label: "Bénéficiaires", icon: Users },
  { to: "/doublons", label: "Doublons d'enregistrement", icon: Copy },
  { to: "/zones-administratives", label: "Zones administratives", icon: MapPin },
  { to: "/documents", label: "Documents", icon: FileText },
];

const ITEMS_ADMIN: NavItem[] = [
  { to: "/utilisateurs", label: "Utilisateurs", icon: UserCog },
  { to: "/parametres-alerte", label: "Paramètres d'alerte", icon: Sliders },
];

const TOUS_LES_ITEMS = [ITEM_ACCUEIL, ...ITEMS_PRINCIPAUX, ...ITEMS_ADMIN];

/** Choix d'une icône parmi celles proposées (ICONES_MENU). */
function ChoixIcone({ icone: Icone, onChoisir }: { icone: LucideIcon; onChoisir: (nom: string) => void }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <Popover opened={ouvert} onChange={setOuvert} position="bottom-start" withArrow shadow="md">
      <Popover.Target>
        <Tooltip label="Changer l'icône">
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
        <Tabs.Tab value="menu">Menu</Tabs.Tab>
        <Tabs.Tab value="vocabulaire">Vocabulaire</Tabs.Tab>
      </Tabs.List>
      <Tabs.Panel value="vocabulaire">
        <Stack gap="xs">
          <Text size="sm" c="dimmed">
            Remplace les termes de la plateforme par ceux de ton organisation : ils changent partout (écrans,
            formulaires, rattachements, messages, exports). Indique le singulier, le pluriel et le genre (pour
            accorder « un/une », « le/la », « nouveau/nouvelle »…). Laisse vide pour garder le terme par défaut.
          </Text>
          <Table withRowBorders={false} verticalSpacing={4}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Terme par défaut</Table.Th>
                <Table.Th>Singulier</Table.Th>
                <Table.Th>Pluriel</Table.Th>
                <Table.Th>Féminin</Table.Th>
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
          <Text size="xs" c="dimmed">Clique sur « Enregistrer » (onglet Menu ou ci-dessous) pour appliquer.</Text>
          <Group justify="flex-end">
            <Button
              loading={enregistrer.isPending}
              onClick={async () => {
                try {
                  await enregistrer.mutateAsync({ libelles: valeurs, icones: iconesChoisies, vocabulaire: termes });
                  notifications.show({ message: "Vocabulaire mis à jour", color: "green" });
                  onClose();
                  window.location.reload();
                } catch {
                  notifications.show({ message: "Erreur lors de l'enregistrement du vocabulaire", color: "red" });
                }
              }}
            >
              Enregistrer
            </Button>
          </Group>
        </Stack>
      </Tabs.Panel>
      <Tabs.Panel value="menu">
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            Donne à chaque rubrique le nom et l'icône utilisés dans ton organisation (clique sur l'icône pour la
            changer). Les changements s'appliquent à tous les utilisateurs ; ↺ revient au nom et à l'icône par défaut.
          </Text>
          {TOUS_LES_ITEMS.map((item) => (
            <Group key={item.to} gap="xs" wrap="nowrap" align="flex-end">
              <ChoixIcone
                icone={ICONES_MENU[iconesChoisies[item.to]] ?? item.icon}
                onChoisir={(nom) => setIconesChoisies((v) => ({ ...v, [item.to]: nom }))}
              />
              <TextInput
                style={{ flex: 1 }}
                label={`Par défaut : ${item.label}`}
                placeholder={item.label}
                value={valeurs[item.to] ?? ""}
                maxLength={60}
                onChange={(e) => {
                  const valeur = e.currentTarget.value;
                  setValeurs((v) => ({ ...v, [item.to]: valeur }));
                }}
              />
              <Tooltip label="Revenir au nom et à l'icône par défaut">
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
                  notifications.show({ message: "Menu mis à jour", color: "green" });
                  onClose();
                  // Le vocabulaire s'applique à tous les textes : on recharge pour l'appliquer partout.
                  if (JSON.stringify(termes) !== JSON.stringify(vocabulaire)) window.location.reload();
                } catch {
                  notifications.show({ message: "Erreur lors de l'enregistrement du menu", color: "red" });
                }
              }}
            >
              Enregistrer
            </Button>
          </Group>
        </Stack>
      </Tabs.Panel>
    </Tabs>
  );
}

function renderNavLink(item: NavItem, pathname: string) {
  const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
  return (
    <NavLink
      key={item.to}
      component={RouterNavLink}
      to={item.to}
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
  const { data: echeances } = useEcheances();
  const { data: configurationMenu, isLoading: chargementMenu } = useConfigurationMenu();
  // Le vocabulaire doit être connu avant d'afficher les pages (leurs textes l'utilisent).
  definirVocabulaire(configurationMenu?.vocabulaire);
  const [personnalisationOuverte, setPersonnalisationOuverte] = useState(false);
  const libelles = configurationMenu?.libelles ?? {};
  const icones = configurationMenu?.icones ?? {};
  const avecLibelle = (item: NavItem): NavItem => ({
    ...item,
    label: libelles[item.to] || voc(item.label),
    icon: ICONES_MENU[icones[item.to]] ?? item.icon,
  });

  const surTableauDeBord = pathname === "/";
  const afficherBandeau = surTableauDeBord && !!echeances && echeances.length > 0;

  return (
    <AppShell
      header={{ height: afficherBandeau ? 88 : 56 }}
      navbar={{ width: 230, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="lg"
    >
      <AppShell.Header withBorder={false} bg="teal.9" c="white">
        <Group h={56} px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" color="white" />
            <Text fw={700} size="sm">Plateforme de Suivi-Évaluation</Text>
          </Group>
          <Group gap="sm">
            <NotificationBell />
            {user && (
              <Group gap={8}>
                <Avatar size={26} radius="xl" color="teal.2" variant="filled">
                  {initiales(user.first_name || user.username)}
                </Avatar>
                <Text size="xs" c="teal.1">
                  {user.first_name || user.username} · {user.role_libelle || user.role}
                </Text>
              </Group>
            )}
            <Button
              variant="subtle"
              color="gray.0"
              size="xs"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Déconnexion
            </Button>
          </Group>
        </Group>
        {afficherBandeau && <EcheancesBanner />}
      </AppShell.Header>

      <AppShell.Navbar p="xs" bg="gray.0">
        <ScrollArea>
          {renderNavLink(avecLibelle(ITEM_ACCUEIL), pathname)}
          <Divider my={4} />
          {ITEMS_PRINCIPAUX.map((item) => renderNavLink(avecLibelle(item), pathname))}
          {user?.role === "ADMIN" && (
            <>
              {ITEMS_ADMIN.map((item) => renderNavLink(avecLibelle(item), pathname))}
              <Divider my={4} />
              <NavLink
                label="Personnaliser le menu"
                leftSection={<PenLine size={17} strokeWidth={2} />}
                onClick={() => setPersonnalisationOuverte(true)}
                c="dimmed"
              />
            </>
          )}
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0">
        {chargementMenu ? <Loader size="sm" /> : <Outlet />}
      </AppShell.Main>

      <Modal
        opened={personnalisationOuverte}
        onClose={() => setPersonnalisationOuverte(false)}
        title="Personnaliser le menu"
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
