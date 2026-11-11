import { Link } from "react-router-dom";
import { Anchor, Box, Button, Card, Container, Group, Image, List, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { ArrowLeft, CircleCheck } from "lucide-react";
import { useIdentiteOrganisation } from "../../api/identite";
import { useAuth } from "../../auth/useAuth";
import { LogoComplet } from "../../components/common/Logos";
import { voc } from "../../utils/vocabulaire";
import { CadreVitrine } from "./CadreVitrine";

function Contenu() {
  const { data: plateforme } = useIdentiteOrganisation();
  return (
    <Stack gap="xl">
      <Card withBorder radius="lg" padding="xl">
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="xl" style={{ alignItems: "center" }}>
          <Group justify="center">
            <Image src="/logo-expertise-id.png" w={200} h={200} alt="Expertise-ID" />
          </Group>
          <Stack gap="sm" style={{ gridColumn: "span 2" }}>
            <Title order={2}>{voc("À propos")}</Title>
            <Text>
              {voc("La plateforme Expertise-ID Monitora est conçue et développée par Expertise-ID. Elle aide les organisations de développement à planifier leurs projets, suivre leurs indicateurs, gérer leurs bénéficiaires, leurs documents et les retours des communautés, et à rendre compte de leurs résultats.")}
            </Text>
            <Text c="dimmed">
              {voc("Expertise-ID accompagne les ONG, les institutions publiques et les partenaires techniques et financiers dans le suivi-évaluation, la gestion axée sur les résultats et les solutions numériques.")}
            </Text>
            <Anchor href="https://www.expertise-id.com" target="_blank" rel="noopener" fw={600}>{voc("Visiter le site d'Expertise-ID")} ↗</Anchor>
            {plateforme?.contact && (
              <Text size="sm">{voc("Contact :")} <Anchor href={`mailto:${plateforme.contact}`}>{plateforme.contact}</Anchor></Text>
            )}
          </Stack>
        </SimpleGrid>
      </Card>
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <Card withBorder radius="md" padding="lg">
          <LogoComplet largeur={340} />
          <List mt="md" size="sm" spacing={6} icon={<CircleCheck size={16} color="var(--mantine-color-teal-6)" />}>
            <List.Item>{voc("Cadres stratégiques, cadre logique et planification à niveaux libres")}</List.Item>
            <List.Item>{voc("Indicateurs, suivi périodique, alertes et tableaux de bord")}</List.Item>
            <List.Item>{voc("Bénéficiaires, zones d'intervention et carte")}</List.Item>
            <List.Item>{voc("Mécanisme de gestion des plaintes et retours, avec circuit confidentiel")}</List.Item>
            <List.Item>{voc("Documents, rapports et exports en six langues")}</List.Item>
          </List>
        </Card>
        <Card withBorder radius="md" padding="lg">
          <Text fw={700}>{voc("Sécurité et protection des données")}</Text>
          <List mt="md" size="sm" spacing={6} icon={<CircleCheck size={16} color="var(--mantine-color-teal-6)" />}>
            <List.Item>{voc("Code de connexion envoyé par courriel à chaque connexion")}</List.Item>
            <List.Item>{voc("Données protégées chiffrées, liens de téléchargement temporaires")}</List.Item>
            <List.Item>{voc("Habilitations confidentielles à double validation")}</List.Item>
            <List.Item>{voc("Journal d'audit non modifiable et registre des traitements")}</List.Item>
          </List>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}

/** « À propos » : Expertise-ID et la plateforme ; dans la plateforme une fois connecté, sinon en vitrine. */
export function AProposPage() {
  const { user } = useAuth();
  if (user) {
    return (
      <Box bg="gray.0" mih="100vh" py="lg">
        <Container size="lg">
          <Stack gap="md">
            <Button component={Link} to="/" variant="subtle" leftSection={<ArrowLeft size={16} />} w="fit-content">{voc("Retour à la plateforme")}</Button>
            <Contenu />
          </Stack>
        </Container>
      </Box>
    );
  }
  return (
    <CadreVitrine>
      <Container size="lg" py="xl"><Contenu /></Container>
    </CadreVitrine>
  );
}
