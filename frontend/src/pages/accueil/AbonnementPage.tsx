import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Alert, Badge, Button, Card, Container, Group, List, SimpleGrid, Stack, Text, Textarea, ThemeIcon, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { CircleCheck, Crown, Lock, Rocket, Sprout } from "lucide-react";
import { type DemandeAbonnement, choisirOffre } from "../../api/identite";
import { messageErreurApi } from "../../utils/erreurs";
import { voc } from "../../utils/vocabulaire";
import { CadreVitrine } from "./CadreVitrine";
import { CLE_ABONNEMENT } from "./InscriptionPage";

const OFFRES = [
  { code: "ESSENTIEL", icone: Sprout, nom: () => voc("Essentiel"), pour: () => voc("Petites organisations"), points: () => [
    voc("Jusqu'à 5 projets"), voc("Planification, cadre logique et indicateurs"), voc("Suivi périodique et documents"), voc("Jusqu'à 10 utilisateurs"),
  ] },
  { code: "STANDARD", icone: Rocket, nom: () => voc("Standard"), pour: () => voc("Organisations avec plusieurs projets"), points: () => [
    voc("Jusqu'à 25 projets"), voc("Toute l'offre Essentiel"), voc("Bénéficiaires, carte, plaintes et retours"), voc("Rapports multilingues"), voc("Jusqu'à 50 utilisateurs"),
  ] },
  { code: "INSTITUTION", icone: Crown, nom: () => voc("Institution"), pour: () => voc("Grands programmes et institutions"), points: () => [
    voc("Projets et utilisateurs sans limite"), voc("Tous les modules"), voc("Installation dédiée, formation et accompagnement"), voc("Assistance prioritaire"),
  ] },
];

/** « Vous devez vous abonner avant de continuer » : après la création du profil, ou à la connexion d'un profil non abonné. */
export function AbonnementPage() {
  const { state } = useLocation();
  const [demande, setDemande] = useState<DemandeAbonnement | null>(() => {
    if (state && (state as DemandeAbonnement).reference) return state as DemandeAbonnement;
    try { return JSON.parse(sessionStorage.getItem(CLE_ABONNEMENT) ?? "null"); } catch { return null; }
  });
  const [choix, setChoix] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const valider = async () => {
    if (!demande || !choix) return;
    setEnvoi(true);
    try {
      const suite = await choisirOffre(demande.reference, choix, message);
      setDemande(suite);
      try { sessionStorage.setItem(CLE_ABONNEMENT, JSON.stringify(suite)); } catch { /* navigation privée */ }
    } catch (error) {
      notifications.show({ color: "red", message: messageErreurApi(error, voc("L'envoi n'a pas abouti. Réessayez.")) });
    } finally {
      setEnvoi(false);
    }
  };

  if (!demande) {
    return (
      <CadreVitrine>
        <Container size="sm" py="xl">
          <Alert color="gray" title={voc("Aucun profil en cours")}>
            {voc("Créez le profil de votre organisation, ou connectez-vous avec l'identifiant choisi.")}
            <Group mt="sm"><Button component={Link} to="/inscription">{voc("Créer le profil")}</Button><Button component={Link} to="/login" variant="default">{voc("Se connecter")}</Button></Group>
          </Alert>
        </Container>
      </CadreVitrine>
    );
  }

  const offreChoisie = demande.offre ? OFFRES.find((o) => o.code === demande.offre) : null;
  return (
    <CadreVitrine>
      <Container size="lg" py="xl">
        <Stack gap="lg">
          <Card withBorder radius="md" padding="lg" bg="orange.0" style={{ borderColor: "var(--mantine-color-orange-3)" }}>
            <Group gap="md" wrap="nowrap" align="flex-start">
              <ThemeIcon size={44} radius="xl" color="orange"><Lock size={22} /></ThemeIcon>
              <Stack gap={4}>
                <Title order={2}>{voc("Vous devez vous abonner avant de continuer")}</Title>
                <Text>{voc`Le profil de ${demande.organisation} est créé. Pour accéder à la plateforme, choisissez une offre : l'équipe d'Expertise-ID vous contacte pour activer votre espace.`}</Text>
              </Stack>
            </Group>
          </Card>

          {demande.espace ? (
            <Alert color="teal" icon={<CircleCheck size={20} />} title={voc("Votre espace est prêt")}>
              <Text size="sm">{voc("Connectez-vous avec l'adresse courriel et le mot de passe choisis à l'inscription.")}</Text>
              <Button mt="sm" component={Link} to="/login">{voc("Se connecter")}</Button>
            </Alert>
          ) : offreChoisie ? (
            <Alert color="teal" icon={<CircleCheck size={20} />} title={voc`Offre ${offreChoisie.nom()} choisie`}>
              {voc("Merci ! Expertise-ID a reçu votre demande et vous contactera rapidement pour finaliser l'abonnement et activer votre espace. Vous pourrez alors vous connecter avec votre adresse courriel.")}
              {demande.contact && <Text size="sm" mt={6}>{voc("Contact :")} <a href={`mailto:${demande.contact}`}>{demande.contact}</a></Text>}
            </Alert>
          ) : (
            <>
              <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
                {OFFRES.map(({ code, icone: Icone, nom, pour, points }) => {
                  const actif = choix === code;
                  return (
                    <Card key={code} withBorder radius="md" padding="lg" onClick={() => setChoix(code)} style={{
                      cursor: "pointer", borderWidth: actif ? 2 : 1, borderColor: actif ? "var(--mantine-color-teal-6)" : undefined,
                      boxShadow: actif ? "var(--mantine-shadow-md)" : undefined,
                    }}>
                      <Stack gap="sm" h="100%">
                        <Group justify="space-between">
                          <ThemeIcon size={40} radius="md" variant="light" color="teal"><Icone size={20} /></ThemeIcon>
                          {code === "STANDARD" && <Badge color="teal">{voc("Le plus choisi")}</Badge>}
                        </Group>
                        <div>
                          <Text fw={800} size="xl">{nom()}</Text>
                          <Text size="sm" c="dimmed">{pour()}</Text>
                        </div>
                        <List size="sm" spacing={4} icon={<CircleCheck size={15} color="var(--mantine-color-teal-6)" />} style={{ flex: 1 }}>
                          {points().map((p) => <List.Item key={p}>{p}</List.Item>)}
                        </List>
                        <Text size="sm" fw={600} c="teal.8">{voc("Tarif sur devis")}</Text>
                        <Button variant={actif ? "filled" : "light"} fullWidth>{actif ? voc("Offre sélectionnée") : voc("Choisir cette offre")}</Button>
                      </Stack>
                    </Card>
                  );
                })}
              </SimpleGrid>
              <Card withBorder radius="md" padding="lg">
                <Stack gap="sm">
                  <Textarea label={voc("Précisions pour Expertise-ID (facultatif)")} autosize minRows={2} value={message} onChange={(e) => setMessage(e.currentTarget.value)} />
                  <Group justify="flex-end">
                    <Button size="md" onClick={valider} loading={envoi} disabled={!choix}>{voc("Envoyer ma demande d'abonnement")}</Button>
                  </Group>
                </Stack>
              </Card>
            </>
          )}
          <Text size="xs" c="dimmed" ta="center">{voc("Les offres et tarifs sont donnés à titre indicatif et confirmés avec Expertise-ID.")}</Text>
        </Stack>
      </Container>
    </CadreVitrine>
  );
}
