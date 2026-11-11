import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Badge, Box, Button, Card, Container, Group, List, SimpleGrid, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  BarChart3,
  Building2,
  FileText,
  Gauge,
  Info,
  MessagesSquare,
  MonitorPlay,
  Network,
  ShieldCheck,
  Target,
  UserPlus,
  Users,
} from "lucide-react";
import { connexionDemo, useIdentiteOrganisation } from "../../api/identite";
import { useAuth } from "../../auth/useAuth";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { LogoComplet } from "../../components/common/Logos";
import { CadreVitrine } from "./CadreVitrine";

const FONCTIONNALITES = [
  { icone: Target, titre: () => voc("Cadres stratégiques et cadre logique"), texte: () => voc("Objectifs, résultats et activités reliés, avec indicateurs, sources de vérification et hypothèses.") },
  { icone: Network, titre: () => voc("Planification libre"), texte: () => voc("Chaque projet nomme et empile ses propres niveaux, importe son plan de travail depuis Excel.") },
  { icone: Gauge, titre: () => voc("Indicateurs et suivi"), texte: () => voc("Valeurs de référence, cibles, réalisations, taux d'avancement et alertes sur les échéances.") },
  { icone: Users, titre: () => voc("Bénéficiaires et carte"), texte: () => voc("Registre des bénéficiaires, détection des doublons, carte des zones d'intervention.") },
  { icone: MessagesSquare, titre: () => voc("Plaintes et retours"), texte: () => voc("Mécanisme complet : formulaire public, circuit confidentiel, délais, messages au plaignant.") },
  { icone: FileText, titre: () => voc("Documents"), texte: () => voc("Dossiers et sous-dossiers, versions, aperçu des photos, liens sécurisés.") },
  { icone: BarChart3, titre: () => voc("Tableaux de bord et rapports"), texte: () => voc("Exports Excel, PDF et Word, en français, anglais, arabe, espagnol, allemand et italien.") },
  { icone: ShieldCheck, titre: () => voc("Sécurité"), texte: () => voc("Code de connexion par courriel, données protégées chiffrées, journal d'audit non modifiable.") },
];

/** Page d'accueil publique : présentation, connexion, création du profil d'une organisation, démonstration. */
export function AccueilPage() {
  const { data: plateforme } = useIdentiteOrganisation();
  const { ouvrirSession } = useAuth();
  const navigate = useNavigate();
  const [demarrage, setDemarrage] = useState(false);
  const demoDisponible = !!plateforme && (plateforme.mode_demo || plateforme.demo_disponible);
  const [parametres] = useSearchParams();
  const demarre = useRef(false);

  const essayerDemo = async () => {
    if (!plateforme) return;
    // Installation séparée : la démonstration est une autre installation.
    if (!plateforme.multi_organisations && !plateforme.mode_demo && plateforme.url_demo) {
      window.location.href = `${plateforme.url_demo.replace(/\/$/, "")}/accueil?demo=1`;
      return;
    }
    setDemarrage(true);
    try {
      await ouvrirSession(await connexionDemo(), "/");
      navigate("/");
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("La démonstration n'est pas disponible pour le moment.")) });
    } finally {
      setDemarrage(false);
    }
  };

  // Arrivée par « Essayer la démo » (page de connexion, site vitrine) : la démonstration s'ouvre d'elle-même.
  useEffect(() => {
    if (demoDisponible && parametres.get("demo") === "1" && !demarre.current) {
      demarre.current = true;
      essayerDemo();
    }
  });

  const boutonDemo = (
    <Button size="lg" variant="white" color="teal" leftSection={<MonitorPlay size={20} />} onClick={essayerDemo} loading={demarrage}
      >
      {voc("Essayer la démo")}
    </Button>
  );

  return (
    <CadreVitrine>
      <Box style={{ background: "linear-gradient(135deg, var(--mantine-color-teal-9), var(--mantine-color-teal-6))" }} c="white">
        <Container size="lg" py={{ base: 40, sm: 72 }}>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing={40} style={{ alignItems: "center" }}>
            <Stack gap="lg">
              <Badge variant="white" color="teal" size="lg" tt="none" w="fit-content">{voc("Suivi-évaluation de projets de développement")}</Badge>
              <Title order={1} fz={{ base: 32, sm: 44 }} lh={1.1}>{voc("Pilotez vos projets, mesurez vos résultats, rendez compte aux communautés.")}</Title>
              <Text size="lg" c="teal.0">
                {voc("Une plateforme unique pour planifier, suivre les indicateurs, gérer les bénéficiaires, les documents et les plaintes, et produire vos rapports.")}
              </Text>
              <Group gap="sm">
                {plateforme?.inscriptions !== false && (
                  <Button size="lg" color="dark" leftSection={<UserPlus size={20} />} component={Link} to="/inscription">
                    {voc("Créer le profil de mon organisation")}
                  </Button>
                )}
                {demoDisponible && boutonDemo}
              </Group>
              <Text size="sm" c="teal.1">
                {voc("Déjà abonné ?")}{" "}
                <Text component={Link} to="/login" span fw={700} c="white" td="underline">{voc("Se connecter")}</Text>
              </Text>
            </Stack>
            <Card radius="lg" shadow="xl" padding="xl" visibleFrom="md">
              <Stack align="center" gap="md">
                <LogoComplet largeur={380} />
                <SimpleGrid cols={3} w="100%">
                  {[[voc("Projets"), "51"], [voc("Indicateurs"), "340"], [voc("Bénéficiaires"), "12 400"]].map(([l, n]) => (
                    <Stack key={l} gap={0} align="center">
                      <Text fw={800} size="xl" c="teal.8">{n}</Text>
                      <Text size="xs" c="dimmed">{l}</Text>
                    </Stack>
                  ))}
                </SimpleGrid>
                <Text size="xs" c="dimmed" ta="center">{voc("Exemple de tableau de bord consolidé")}</Text>
              </Stack>
            </Card>
          </SimpleGrid>
        </Container>
      </Box>

      <Container size="lg" py={56}>
        <Stack gap="xl">
          <Stack gap={4} align="center">
            <Title order={2} ta="center">{voc("Tout le cycle du projet, au même endroit")}</Title>
            <Text c="dimmed" ta="center" maw={640}>{voc("Chaque organisation règle la plateforme à sa façon : noms des niveaux, rubriques, langues, logo.")}</Text>
          </Stack>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="md">
            {FONCTIONNALITES.map(({ icone: Icone, titre, texte }) => (
              <Card key={titre()} withBorder radius="md" padding="lg">
                <ThemeIcon size={42} radius="md" variant="light" color="teal"><Icone size={22} /></ThemeIcon>
                <Text fw={700} mt="sm">{titre()}</Text>
                <Text size="sm" c="dimmed" mt={4}>{texte()}</Text>
              </Card>
            ))}
          </SimpleGrid>
        </Stack>
      </Container>

      <Box bg="white">
        <Container size="lg" py={48}>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing={32} style={{ alignItems: "center" }}>
            {demoDisponible && <Stack gap="sm">
              <Group gap="xs"><MonitorPlay size={22} color="var(--mantine-color-teal-7)" /><Title order={3}>{voc("Mode démonstration")}</Title></Group>
              <Text c="dimmed">{voc("Découvrez la plateforme sans compte, sur des données d'exemple :")}</Text>
              <List size="sm" spacing={4}>
                <List.Item>{voc("5 projets complets, avec tous les onglets remplis ;")}</List.Item>
                <List.Item>{voc("toutes les rubriques et toutes les fonctionnalités ;")}</List.Item>
                <List.Item>{voc("vous pouvez ouvrir et remplir chaque formulaire : l'enregistrement est simulé, rien n'est conservé.")}</List.Item>
              </List>
              <Group>
                <Button leftSection={<MonitorPlay size={18} />} onClick={essayerDemo} loading={demarrage}>{voc("Essayer la démo")}</Button>
              </Group>
            </Stack>}
            <Card withBorder radius="md" padding="lg" bg="teal.0">
              <Group gap="sm" wrap="nowrap" align="flex-start">
                <ThemeIcon size={42} radius="md" color="teal"><Building2 size={22} /></ThemeIcon>
                <Stack gap={4}>
                  <Text fw={700}>{voc("Votre organisation veut l'utiliser ?")}</Text>
                  <Text size="sm" c="dimmed">{voc("Créez le profil de votre organisation, choisissez une offre : l'équipe d'Expertise-ID active votre espace et vous accompagne.")}</Text>
                  <Group mt="xs" gap="xs">
                    <Button component={Link} to="/inscription" variant="light" leftSection={<UserPlus size={16} />}>{voc("Créer le profil")}</Button>
                    <Button component={Link} to="/a-propos" variant="subtle" leftSection={<Info size={16} />}>{voc("En savoir plus")}</Button>
                  </Group>
                </Stack>
              </Group>
            </Card>
          </SimpleGrid>
        </Container>
      </Box>
    </CadreVitrine>
  );
}
