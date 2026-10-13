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
  type LucideIcon,
} from "lucide-react";
import { AppShell, Avatar, Burger, Divider, Group, NavLink, ScrollArea, Text, Button } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useAuth } from "../auth/useAuth";
import { useEcheances } from "../api/dashboard";
import { NotificationBell } from "../components/notifications/NotificationBell";
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
  { to: "/doublons", label: "Doublons signalés", icon: Copy },
  { to: "/zones-administratives", label: "Zones administratives", icon: MapPin },
  { to: "/documents", label: "Documents", icon: FileText },
];

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
          {renderNavLink(ITEM_ACCUEIL, pathname)}
          <Divider my={4} />
          {ITEMS_PRINCIPAUX.map((item) => renderNavLink(item, pathname))}
          {user?.role === "ADMIN" && (
            <>
              {renderNavLink({ to: "/utilisateurs", label: "Utilisateurs", icon: UserCog }, pathname)}
              {renderNavLink({ to: "/parametres-alerte", label: "Paramètres d'alerte", icon: Sliders }, pathname)}
            </>
          )}
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0">
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
