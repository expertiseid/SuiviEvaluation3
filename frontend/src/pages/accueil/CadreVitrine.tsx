import { Anchor, Box, Button, Container, Group, Stack } from "@mantine/core";
import { Link } from "react-router-dom";
import { ChoixLangue } from "../../components/common/ChoixLangue";
import { LogoPlateforme, PiedDePage } from "../../components/common/Logos";
import { voc } from "../../utils/vocabulaire";

/** Cadre des pages publiques de présentation : accueil, inscription, abonnement, à propos. */
export function CadreVitrine({ children }: { children: React.ReactNode }) {
  return (
    <Box bg="gray.0" mih="100vh" style={{ display: "flex", flexDirection: "column" }}>
      <Box bg="white" style={{ borderBottom: "1px solid var(--mantine-color-gray-2)", position: "sticky", top: 0, zIndex: 10 }}>
        <Container size="lg" py="sm">
          <Group justify="space-between" wrap="nowrap">
            <Anchor component={Link} to="/accueil" underline="never" c="dark"><LogoPlateforme taille={34} /></Anchor>
            <Group gap="sm" wrap="nowrap">
              <Anchor component={Link} to="/a-propos" size="sm" c="dark" visibleFrom="sm">{voc("À propos")}</Anchor>
              <ChoixLangue connecte={false} couleur="gray" />
              <Button component={Link} to="/login" variant="default" size="sm">{voc("Se connecter")}</Button>
            </Group>
          </Group>
        </Container>
      </Box>
      <Box style={{ flex: 1 }}>{children}</Box>
      <Box bg="white" style={{ borderTop: "1px solid var(--mantine-color-gray-2)" }}>
        <Container size="lg">
          <Stack gap={0}><PiedDePage /></Stack>
        </Container>
      </Box>
    </Box>
  );
}
